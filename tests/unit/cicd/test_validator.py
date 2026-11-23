"""Unit tests for workflow validator and DAG cycle detection."""

import pytest
from actionspath.cicd.validator import (
    validate_yaml_syntax,
    validate_workflow_structure,
    validate_job_dependencies,
    validate_workflow,
    execute_command,
    validate_output,
)


def test_valid_yaml_syntax():
    valid = "name: Test\non: push\njobs:\n  run:\n    runs-on: ubuntu-latest"
    res = validate_yaml_syntax(valid)
    assert res.success is True


def test_invalid_yaml_syntax():
    invalid = "name: Test\n  invalid_indent: [1, 2"
    res = validate_yaml_syntax(invalid)
    assert res.success is False
    assert len(res.errors) > 0


def test_workflow_structure_missing_trigger():
    no_on = "name: Test\njobs:\n  build:\n    runs-on: ubuntu-latest"
    res = validate_workflow_structure(no_on)
    assert res.success is False
    assert any("trigger" in e.lower() for e in res.errors)


def test_workflow_structure_missing_jobs():
    no_jobs = "name: Test\non: push"
    res = validate_workflow_structure(no_jobs)
    assert res.success is False
    assert any("jobs" in e.lower() for e in res.errors)


def test_workflow_structure_valid():
    valid = """
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
"""
    res = validate_workflow_structure(valid)
    assert res.success is True


def test_job_dependencies_linear():
    wf = """
name: Pipeline
on: push
jobs:
  lint:
    runs-on: ubuntu-latest
  build:
    needs: lint
    runs-on: ubuntu-latest
  deploy:
    needs: build
    runs-on: ubuntu-latest
"""
    res = validate_job_dependencies(wf)
    assert res.success is True
    assert "lint -> build -> deploy" in res.output


def test_job_dependencies_unknown_job():
    wf = """
name: BadDep
on: push
jobs:
  deploy:
    needs: nonexistent_job
    runs-on: ubuntu-latest
"""
    res = validate_job_dependencies(wf)
    assert res.success is False
    assert any("undefined job" in e for e in res.errors)


def test_job_dependencies_cycle():
    wf = """
name: Cycle
on: push
jobs:
  a:
    needs: c
    runs-on: ubuntu-latest
  b:
    needs: a
    runs-on: ubuntu-latest
  c:
    needs: b
    runs-on: ubuntu-latest
"""
    res = validate_job_dependencies(wf)
    assert res.success is False
    assert "circular dependency" in res.message.lower()


def test_execute_command_and_validate_output():
    res = execute_command("echo 'Hello ActionsPath'")
    assert res.success is True
    assert "Hello ActionsPath" in res.output
    assert validate_output(res.output, "Hello") is True
    assert validate_output(res.output, "NotInOutput") is False


def test_sanitize_command_blocks_interactive():
    from actionspath.cicd.validator import sanitize_command

    # Interactive TTY flags
    safe, _, err = sanitize_command("kubectl exec -it mypod -- bash")
    assert safe is False
    assert "-it" in err

    safe, _, err = sanitize_command("docker run -ti ubuntu bash")
    assert safe is False

    # Block direct editors
    safe, _, err = sanitize_command("nano .github/workflows/ci.yml")
    assert safe is False
    assert "Direct editor" in err

    # Block bare commands that wait for stdin
    safe, _, err = sanitize_command("cat")
    assert safe is False
    assert "requires arguments" in err

    # Block streaming commands
    safe, _, err = sanitize_command("tail -f /var/log/syslog")
    assert safe is False
    assert "tail -f" in err

    # Safe command passes
    safe, cmd, err = sanitize_command("git status")
    assert safe is True
    assert cmd == "git status"
    assert err is None


def test_execute_command_hang_guard():
    # Attempting to execute blocked command returns friendly error instantly
    res = execute_command("kubectl exec -it pod -- bash")
    assert res.success is False
    assert "Interactive mode (-it) is not supported" in res.message

    # Bare cat with stdin DEVNULL does not freeze
    res = execute_command("cat", timeout=2)
    assert res.success is False
    assert "requires arguments" in res.message


def test_semantic_scenario_assertions():
    from actionspath.cicd.validator import check_yaml_assertion, validate_scenario_assertions

    wf_yaml = """
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node: [18, 20]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
      - run: npm test
"""
    # Test path resolution and contains
    pass1, _ = check_yaml_assertion({"on": ["push", "pull_request"]}, {"path": "on", "contains": ["push", "pull_request"]})
    assert pass1 is True

    # Test full workflow assertions
    assertions = [
        {"path": "on", "contains": ["push", "pull_request"]},
        {"path": "jobs.build.strategy.matrix.node", "equals": [18, 20]},
        {"path": "jobs.build.steps", "has_step_using": "actions/setup-node"},
        {"path": "jobs.build.steps", "has_step_with_run": "npm test"},
    ]
    res = validate_scenario_assertions(wf_yaml, assertions)
    assert res.success is True

    # Test failing assertion
    fail_assertions = [
        {"path": "jobs.build.strategy.matrix.node", "equals": [16, 18], "message": "Must support Node 16 and 18"}
    ]
    fail_res = validate_scenario_assertions(wf_yaml, fail_assertions)
    assert fail_res.success is False
    assert "Must support Node 16 and 18" in fail_res.message


def test_validate_from_spec_with_assertions_and_starter():
    from actionspath.cicd.validator import validate_from_spec
    import tempfile
    from pathlib import Path

    starter = "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"

    with tempfile.TemporaryDirectory() as tmp:
        wf_file = Path(tmp) / "ci.yml"
        wf_file.write_text(starter)

        spec = {
            "type": "workflow",
            "file": "ci.yml",
            "assertions": [
                {"path": "on", "contains": "pull_request", "message": "Trigger must include pull_request"}
            ],
        }

        # 1. Unmodified starter fails with helpful message
        res_unmodified = validate_from_spec(spec, context={"workspace_path": tmp, "starter_manifest": starter})
        assert res_unmodified.success is False
        assert "Workflow has not been modified" in res_unmodified.message

        # 2. Modified but missing assertion fails
        wf_file.write_text("name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo modified\n")
        res_missing = validate_from_spec(spec, context={"workspace_path": tmp, "starter_manifest": starter})
        assert res_missing.success is False
        assert "Trigger must include pull_request" in res_missing.message

        # 3. Fixed workflow passes
        wf_file.write_text("name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n")
        res_pass = validate_from_spec(spec, context={"workspace_path": tmp, "starter_manifest": starter})
        assert res_pass.success is True

