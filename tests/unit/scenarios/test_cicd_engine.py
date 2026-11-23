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

        # 4. Fix workflow
        fixed_content = """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""
        wm.write_workflow(engine.current_context.workspace_path, "ci.yml", fixed_content)

        # 5. Validation after fix
        val_res2 = engine.validate_solution()
        assert val_res2.success is True
        assert engine.is_completed is True

        # 6. Score calculation
        score = engine.calculate_score()
        assert score == 50

        # 7. Cleanup
        ws_path = engine.current_context.workspace_path
        engine.cleanup()
        assert not ws_path.exists()
