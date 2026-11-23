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
