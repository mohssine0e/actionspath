"""Integration tests for Boss Labs engine, validators, and CLI commands."""

import tempfile
from pathlib import Path
import pytest
from typer.testing import CliRunner

from actionspath.cicd.labs import (
    load_all_boss_labs,
    load_boss_lab,
    setup_lab_workspace,
    validate_boss_lab,
    get_lab_workspace_dir,
)
from actionspath.cli import app
from actionspath.utils.progress import (
    is_lab_completed,
    save_lab_completed,
    get_completed_labs,
)


@pytest.fixture
def runner():
    return CliRunner()


class TestBossLabs:
    """Tests for Boss Labs loading and validation."""

    def test_load_all_boss_labs(self):
        """All 6 Boss Labs must load and contain valid schema keys."""
        labs = load_all_boss_labs()
        assert len(labs) == 6, f"Expected 6 Boss Labs, found {len(labs)}"

        for idx, lab in enumerate(labs, 1):
            assert lab.module == idx
            assert lab.title, f"Lab {idx} missing title"
            assert lab.badge, f"Lab {idx} missing badge"
            assert lab.briefing, f"Lab {idx} missing briefing"
            assert len(lab.initial_files) > 0, f"Lab {idx} missing initial_files"
            assert len(lab.objectives) >= 3, f"Lab {idx} should have at least 3 objectives"
            for obj in lab.objectives:
                assert "id" in obj
                assert "title" in obj
                assert "assertions" in obj
                assert len(obj["assertions"]) > 0

    def test_lab_starter_fails_validation(self, tmp_path):
        """Unmodified starter files must fail validation with unedited status."""
        lab = load_boss_lab(1)
        assert lab is not None

        # Setup in tmp_path
        for rel_path, content in lab.initial_files.items():
            f = tmp_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")

        result = validate_boss_lab(tmp_path, lab)
        assert not result.success
        assert any("not been edited yet" in o.message for o in result.objectives)

    def test_lab_1_solution_passes(self, tmp_path):
        """Applying the correct solution for Lab 1 passes all objectives."""
        lab = load_boss_lab(1)
        assert lab is not None

        solved_workflow = """name: Production CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ format('Build {0}', github.sha) }}"

  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm test
"""
        target = tmp_path / ".github/workflows/ci.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(solved_workflow, encoding="utf-8")

        result = validate_boss_lab(tmp_path, lab)
        assert result.success, f"Lab 1 validation failed: {[o.message for o in result.objectives if not o.passed]}"
        for obj in result.objectives:
            assert obj.passed

    def test_boss_lab_progress_persistence(self, tmp_path, monkeypatch):
        """Testing lab completion tracking in progress."""
        test_file = tmp_path / "progress.json"
        monkeypatch.setattr("actionspath.utils.progress.get_progress_file", lambda: test_file)
        monkeypatch.setattr("actionspath.utils.progress.get_progress_dir", lambda: tmp_path)

        assert not is_lab_completed(1)
        save_lab_completed(1)
        assert is_lab_completed(1)
        assert 1 in get_completed_labs()

    def test_cli_lab_help(self, runner):
        """The 'actionspath lab --help' CLI command must return valid usage."""
        result = runner.invoke(app, ["lab", "--help"])
        assert result.exit_code == 0
        assert "Launch an end-of-module capstone Boss Lab" in result.output
