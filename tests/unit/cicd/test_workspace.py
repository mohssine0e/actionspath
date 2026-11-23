"""Unit tests for WorkspaceManager."""

from pathlib import Path
import tempfile

from actionspath.cicd.workspace import WorkspaceManager


def test_create_workspace_initializes_structure_and_git():
    with tempfile.TemporaryDirectory() as tmp:
        wm = WorkspaceManager(base_dir=tmp)
        ws = wm.create_workspace("01", "intro")

        assert ws.exists()
        assert (ws / ".github" / "workflows").is_dir()
        assert (ws / ".git").is_dir()
        assert (ws / "README.md").is_file()


def test_write_and_get_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        wm = WorkspaceManager(base_dir=tmp)
        ws = wm.create_workspace("02", "syntax")
        content = "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"

        wf_path = wm.write_workflow(ws, "ci.yml", content)
        assert wf_path.is_file()

        retrieved = wm.get_workflow(ws, "ci.yml")
        assert retrieved == content

        workflows = wm.list_workflows(ws)
        assert len(workflows) == 1
        assert workflows[0].name == "ci.yml"


def test_commit_changes():
    with tempfile.TemporaryDirectory() as tmp:
        wm = WorkspaceManager(base_dir=tmp)
        ws = wm.create_workspace("03", "commit_test")
        wm.write_workflow(ws, "deploy.yml", "name: Deploy\non: release\n")
        ok = wm.commit_changes(ws, "Add deploy workflow")
        assert ok is True


def test_clean_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        wm = WorkspaceManager(base_dir=tmp)
        ws = wm.create_workspace("04", "clean_test")
        assert ws.exists()
        cleaned = wm.clean_workspace(ws)
        assert cleaned is True
        assert not ws.exists()
