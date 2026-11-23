"""Unit tests for ActionsPath ScenarioEngine."""

import tempfile
from pathlib import Path

from actionspath.cicd.workspace import WorkspaceManager
from actionspath.scenarios.engine import ScenarioEngine, ScenarioState


def test_scenario_engine_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        wm = WorkspaceManager(base_dir=tmp)
        engine = ScenarioEngine(workspace_manager=wm)

        scenario = {
            "id": "fix-trigger",
            "title": "Fix Invalid Trigger",
            "description": "Fix invalid workflow syntax in ci.yml",
            "manifest": "name: CI\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
            "hints": ["Check if 'on' trigger is specified"],
            "solution_validation": {
                "type": "workflow",
                "file": ".github/workflows/ci.yml",
            },
            "points": 50,
            "hint_penalty": 10,
        }

        # 1. Start scenario
        res = engine.start_scenario(scenario)
        assert res.success is True
        assert engine.is_active is True
        assert engine.current_context.workspace_path.exists()
        assert (engine.current_context.workspace_path / ".github" / "workflows" / "ci.yml").is_file()

        # 2. Execute command in workspace
        cmd_res = engine.execute_learner_command("git status")
        assert cmd_res.success is True

        # 3. Validation before fix (missing 'on' trigger)
        val_res = engine.validate_solution()
        assert val_res.success is False

        # 4. Check diff before fix (should be empty)
        assert engine.get_diff() == ""

        # 5. Fix workflow
        fixed_content = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""
        wm.write_workflow(engine.current_context.workspace_path, "ci.yml", fixed_content)

        # 6. Check diff after edit
        diff = engine.get_diff()
        assert "on: [push]" in diff

        # 7. Test reset workflow
        assert engine.reset_workflow() is True
        wf_path = engine.current_context.workflow_path
        assert "on: [push]" not in wf_path.read_text(encoding="utf-8")
        assert engine.get_diff() == ""

        # 8. Re-apply fix for validation
        wm.write_workflow(engine.current_context.workspace_path, "ci.yml", fixed_content)
        val_res2 = engine.validate_solution()
        assert val_res2.success is True
        assert engine.is_completed is True

        # 9. Score calculation
        score = engine.calculate_score()
        assert score == 50

        # 10. Cleanup
        ws_path = engine.current_context.workspace_path
        engine.cleanup()
        assert not ws_path.exists()
