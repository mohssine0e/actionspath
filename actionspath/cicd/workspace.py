"""CI/CD Workspace manager for hands-on GitHub Actions practice.

Manages ephemeral local Git repositories in ~/.actionspath/workspaces/
for writing, modifying, and testing GitHub Actions workflows.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeployedResource:
    """Tracks a practice resource or workflow file."""

    kind: str = "workflow"
    name: str = ""
    namespace: str = "default"


@dataclass
class DeploymentResult:
    """Result of deploying a workflow or practice fixture."""

    success: bool
    message: str
    resources: List[DeployedResource] = field(default_factory=list)
    output: str = ""


def deploy_manifest(manifest_yaml: str, workspace_path: Optional[Path] = None) -> DeploymentResult:
    """Deploy a workflow file to the practice workspace."""
    from actionspath.cicd.validator import ValidationResult

    wm = WorkspaceManager()
    ws = workspace_path or wm.get_workspace_path("practice")
    wm.ensure_base_dir()
    ws.mkdir(parents=True, exist_ok=True)
    wf_path = wm.write_workflow(ws, "workflow.yml", manifest_yaml)
    return DeploymentResult(
        success=True,
        message="Workflow written to workspace",
        resources=[DeployedResource(kind="Workflow", name=wf_path.name)],
        output=str(wf_path),
    )


def delete_resources(resources: List[DeployedResource], timeout: int = 30, force: bool = False):
    """Clean up practice resources."""
    from actionspath.cicd.validator import ValidationResult

    return ValidationResult(success=True, message="Practice resources cleaned up")


class WorkspaceManager:
    """Manages ephemeral git workspaces for GitHub Actions practice."""

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        """Initialize workspace manager.

        Args:
            base_dir: Optional custom base directory for workspaces.
                      Defaults to ~/.actionspath/workspaces/.
        """
        if base_dir is None:
            self.base_dir = Path.home() / ".actionspath" / "workspaces"
        else:
            self.base_dir = Path(base_dir).expanduser().resolve()

    def ensure_base_dir(self) -> Path:
        """Ensure the base workspaces directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir

    def get_workspace_path(self, chapter_id: str | int, name: str = "practice") -> Path:
        """Get the deterministic path for a chapter workspace."""
        clean_ch = str(chapter_id).strip().replace(" ", "_").lower()
        clean_name = str(name).strip().replace(" ", "_").lower()
        return self.base_dir / f"chapter_{clean_ch}_{clean_name}"

    def create_workspace(
        self,
        chapter_id: str | int,
        name: str = "practice",
        init_git: bool = True,
        force_clean: bool = False,
    ) -> Path:
        """Create an ephemeral workspace directory for practice.

        Args:
            chapter_id: Chapter identifier (e.g., '01', 1, 'workflow-anatomy').
            name: Sub-practice name or scenario name.
            init_git: If True, initialize a git repository and configure user.
            force_clean: If True, delete any existing workspace first.

        Returns:
            Path to the created workspace.
        """
        self.ensure_base_dir()
        workspace_path = self.get_workspace_path(chapter_id, name)

        if force_clean and workspace_path.exists():
            self.clean_workspace(workspace_path)

        workspace_path.mkdir(parents=True, exist_ok=True)

        # Create standard GitHub Actions directory structure
        workflows_dir = workspace_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Create basic README if not present
        readme_path = workspace_path / "README.md"
        if not readme_path.exists():
            readme_path.write_text(
                f"# ActionsPath Practice Workspace\n\n"
                f"Chapter: {chapter_id}\n"
                f"Practice: {name}\n\n"
                f"Workflows are located in `.github/workflows/`.\n",
                encoding="utf-8",
            )

        # Create basic pyproject.toml fixture if not present
        pyproject_path = workspace_path / "pyproject.toml"
        if not pyproject_path.exists():
            pyproject_path.write_text(
                '[project]\nname = "actionspath-demo"\nversion = "0.1.0"\ndescription = "Practice repository"\n',
                encoding="utf-8",
            )

        # Create basic Python package directory fixture if not present
        pkg_dir = workspace_path / "actionspath"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        init_file = pkg_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Practice package."""\n', encoding="utf-8")

        # Create basic sample workflow if not present
        sample_wf = workflows_dir / "ci.yml"
        if not sample_wf.exists():
            sample_wf.write_text(
                "name: CI\non: [push, pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
                encoding="utf-8",
            )

        # Initialize git if requested and not already initialized
        if init_git and not (workspace_path / ".git").exists():
            self._init_git_repo(workspace_path)

        return workspace_path

    def _init_git_repo(self, workspace_path: Path) -> bool:
        """Initialize and configure a git repository inside the workspace."""
        try:
            # Initialize git repository with main as default branch
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            # Configure local identity so commits never fail
            subprocess.run(
                ["git", "config", "user.name", "ActionsPath Learner"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "learner@actionspath.local"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            subprocess.run(
                ["git", "config", "commit.gpgsign", "false"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            # Stage initial files
            subprocess.run(
                ["git", "add", "."],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            return True
        except Exception as e:
            logger.warning("Failed to initialize git repository: %s", e)
            return False

    def write_workflow(
        self,
        workspace_path: Path,
        filename: str,
        content: str,
    ) -> Path:
        """Write a workflow YAML file into .github/workflows/.

        Args:
            workspace_path: The workspace root.
            filename: The file name (e.g., 'ci.yml' or 'build.yaml').
            content: The YAML content of the workflow.

        Returns:
            Path to the written workflow file.
        """
        if not (filename.endswith(".yml") or filename.endswith(".yaml")):
            filename = f"{filename}.yml"

        workflows_dir = workspace_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow_path = workflows_dir / filename
        workflow_path.write_text(content, encoding="utf-8")
        return workflow_path

    def get_workflow(
        self,
        workspace_path: Path,
        filename: str,
    ) -> Optional[str]:
        """Read a workflow YAML file from .github/workflows/.

        Returns:
            String content if found, None otherwise.
        """
        if not (filename.endswith(".yml") or filename.endswith(".yaml")):
            filename = f"{filename}.yml"

        workflow_path = workspace_path / ".github" / "workflows" / filename
        if workflow_path.is_file():
            return workflow_path.read_text(encoding="utf-8")
        return None

    def list_workflows(self, workspace_path: Path) -> List[Path]:
        """List all workflow files in .github/workflows/."""
        workflows_dir = workspace_path / ".github" / "workflows"
        if not workflows_dir.is_dir():
            return []

        files: List[Path] = []
        for ext in ("*.yml", "*.yaml"):
            files.extend(workflows_dir.glob(ext))
        return sorted(files)

    def write_file(
        self,
        workspace_path: Path,
        relative_path: str | Path,
        content: str,
    ) -> Path:
        """Write an arbitrary file in the workspace."""
        file_path = workspace_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def commit_changes(
        self,
        workspace_path: Path,
        message: str = "Update workflow",
    ) -> bool:
        """Stage and commit all changes in the workspace."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=workspace_path,
                capture_output=True,
                check=False,
                text=True,
            )
            # Returncode 0 = committed, 1 = working tree clean
            return res.returncode in (0, 1)
        except Exception as e:
            logger.warning("Failed to commit changes: %s", e)
            return False

    def clean_workspace(self, workspace_path: Path) -> bool:
        """Delete an ephemeral workspace directory."""
        if workspace_path.exists() and workspace_path.is_dir():
            shutil.rmtree(workspace_path, ignore_errors=True)
            return True
        return False

    def clean_all_workspaces(self) -> int:
        """Clean all workspaces in the base directory."""
        if not self.base_dir.exists():
            return 0

        count = 0
        for item in self.base_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                count += 1
        return count
