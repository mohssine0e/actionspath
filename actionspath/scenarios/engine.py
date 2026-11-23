"""Core scenario engine for CI/CD and GitHub Actions debugging challenges."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from actionspath.ai.gemini import GeminiClient, GeminiHint, get_gemini_client
from actionspath.cicd.validator import (
    ValidationResult,
    execute_command,
    validate_from_spec,
    validate_workflow,
)
from actionspath.cicd.workspace import DeployedResource, WorkspaceManager
from actionspath.scenarios.cleanup import CleanupManager
from actionspath.scenarios.hints import HintManager
from actionspath.scenarios.history import CommandHistory


def has_yaml_content(manifest: str) -> bool:
    """Check if manifest has actual YAML content (not just comments).

    Args:
        manifest: YAML manifest string.

    Returns:
        True if the manifest contains actual YAML documents with content.
    """
    if not manifest or not manifest.strip():
        return False

    try:
        docs = list(yaml.safe_load_all(manifest))
        return any(doc is not None for doc in docs)
    except yaml.YAMLError:
        return False


class ScenarioState(Enum):
    """Current state of a scenario."""

    NOT_STARTED = "not_started"
    DEPLOYING = "deploying"
    ACTIVE = "active"  # Learner is investigating
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ScenarioResult:
    """Result of completing a scenario."""

    scenario_id: str
    success: bool
    points_earned: int
    max_points: int
    hints_used: int
    ai_hints_used: int
    hint_penalty: int
    commands_executed: int


@dataclass
class ScenarioContext:
    """Runtime context for an active scenario."""

    scenario_id: str
    title: str
    description: str
    manifest: str
    solution_validation: Dict[str, Any]
    base_points: int
    hint_penalty: int

    state: ScenarioState = ScenarioState.NOT_STARTED
    workspace_path: Optional[Path] = None
    workflow_path: Optional[Path] = None
    deployed_resources: List[DeployedResource] = field(default_factory=list)
    hint_manager: Optional[HintManager] = None
    command_history: Optional[CommandHistory] = None
    cleanup_manager: Optional[CleanupManager] = None
    workspace_manager: Optional[WorkspaceManager] = None


class ScenarioEngine:
    """Orchestrates scenario workspace setup, validation, and cleanup.

    The main orchestrator for GitHub Actions debugging scenarios. Handles:
    - Setting up ephemeral git workspaces with broken workflow files
    - Executing learner commands (git, actionlint, shell) in the workspace
    - Validating solutions via YAML AST checks and actionlint
    - Managing hints (static and AI)
    - Cleanup of practice workspaces
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        """Initialize the scenario engine."""
        self.gemini_client = gemini_client
        self.workspace_manager = workspace_manager or WorkspaceManager()
        self.current_context: Optional[ScenarioContext] = None

    def start_scenario(self, scenario: Dict[str, Any]) -> ValidationResult:
        """Start a new scenario in an ephemeral git workspace.

        Args:
            scenario: Scenario dict from chapter YAML.

        Returns:
            ValidationResult indicating if workspace initialization succeeded.
        """
        self.current_context = ScenarioContext(
            scenario_id=str(scenario["id"]),
            title=scenario.get("title", ""),
            description=scenario.get("description", ""),
            manifest=scenario.get("manifest", ""),
            solution_validation=scenario.get("solution_validation", {}),
            base_points=scenario.get("points", 25),
            hint_penalty=scenario.get("hint_penalty", 5),
            workspace_manager=self.workspace_manager,
        )

        hints = scenario.get("hints", [])
        self.current_context.hint_manager = HintManager(
            hints=hints,
            hint_penalty=scenario.get("hint_penalty", 5),
            ai_hint_penalty=scenario.get("ai_hint_penalty", 2),
        )
        self.current_context.command_history = CommandHistory()
        self.current_context.cleanup_manager = CleanupManager()

        # Create ephemeral Git workspace
        self.current_context.state = ScenarioState.DEPLOYING
        try:
            ws_path = self.workspace_manager.create_workspace(
                chapter_id=self.current_context.scenario_id,
                name="scenario",
                init_git=True,
                force_clean=True,
            )
            self.current_context.workspace_path = ws_path

            manifest = scenario.get("manifest", "")
            if has_yaml_content(manifest):
                wf_filename = scenario.get("workflow_file", "ci.yml")
                wf_path = self.workspace_manager.write_workflow(ws_path, wf_filename, manifest)
                self.current_context.workflow_path = wf_path
                self.current_context.deployed_resources = [
                    DeployedResource(kind="workflow", name=wf_filename)
                ]

            # Write any extra supporting files if defined
            for rel_path, file_content in scenario.get("files", {}).items():
                self.workspace_manager.write_file(ws_path, rel_path, file_content)

            # Stage and commit baseline scenario files
            self.workspace_manager.commit_changes(ws_path, f"Setup scenario {self.current_context.scenario_id}")

            self.current_context.state = ScenarioState.ACTIVE
            return ValidationResult(
                success=True,
                message=f"Practice workspace ready at {ws_path}",
                output=str(ws_path),
            )
        except Exception as e:
            self.current_context.state = ScenarioState.FAILED
            return ValidationResult(
                success=False,
                message=f"Failed to create practice workspace: {e}",
                output=str(e),
                errors=[str(e)],
            )

    def execute_learner_command(self, command: str) -> ValidationResult:
        """Execute a command typed by the learner inside the workspace directory."""
        if not self.current_context:
            return ValidationResult(
                success=False,
                message="No active scenario",
                output="",
            )

        if self.current_context.state != ScenarioState.ACTIVE:
            return ValidationResult(
                success=False,
                message=f"Scenario not active (state: {self.current_context.state.value})",
                output="",
            )

        start = time.time()
        cwd = self.current_context.workspace_path or Path.cwd()
        result = execute_command(command, cwd=cwd)
        duration_ms = int((time.time() - start) * 1000)

        # Record in history
        self.current_context.command_history.add(command, result, duration_ms)
        return result

    def validate_solution(self) -> ValidationResult:
        """Check if the learner has fixed the broken workflow in the workspace."""
        if not self.current_context:
            return ValidationResult(
                success=False,
                message="No active scenario",
                output="",
            )

        validation_spec = self.current_context.solution_validation
        if not validation_spec:
            # If no spec, check workflow syntax/linting on the main workflow file
            if self.current_context.workflow_path and self.current_context.workflow_path.is_file():
                return validate_workflow(
                    self.current_context.workflow_path,
                    workspace_path=self.current_context.workspace_path,
                )
            return ValidationResult(
                success=False,
                message="No validation spec defined for this scenario",
                output="",
            )

        self.current_context.state = ScenarioState.VALIDATING
        context = {"workspace_path": self.current_context.workspace_path}
        result = validate_from_spec(validation_spec, context=context)

        if result.success:
            self.current_context.state = ScenarioState.COMPLETED
        else:
            self.current_context.state = ScenarioState.ACTIVE

        return result

    def get_hint(self) -> Optional[Dict[str, Any]]:
        """Get the next static hint."""
        if not self.current_context or not self.current_context.hint_manager:
            return None

        hint_result = self.current_context.hint_manager.get_next_hint()
        if not hint_result:
            return None

        return {
            "text": hint_result.hint_text,
            "number": hint_result.hint_number,
            "total": hint_result.total_hints,
            "penalty": hint_result.penalty_applied,
            "has_more": hint_result.has_more_hints,
        }

    def get_ai_hint(self, current_error: str = "") -> Optional[GeminiHint]:
        """Get an AI-powered hint from Gemini."""
        if not self.current_context:
            return None

        client = self.gemini_client or get_gemini_client()
        if not client.is_available:
            return None

        history = self.current_context.command_history.format_for_ai_context()

        # Read latest workflow content if available
        current_manifest = self.current_context.manifest
        if self.current_context.workflow_path and self.current_context.workflow_path.is_file():
            try:
                current_manifest = self.current_context.workflow_path.read_text(encoding="utf-8")
            except Exception:
                pass

        hint = client.get_debugging_hint(
            scenario_description=self.current_context.description,
            manifest=current_manifest,
            command_history=history,
            current_error=current_error or self.current_context.command_history.get_last_error() or "",
        )

        if hint:
            self.current_context.hint_manager.record_ai_hint()

        return hint

    def calculate_score(self) -> int:
        """Calculate final score after hint penalties."""
        if not self.current_context or self.current_context.state != ScenarioState.COMPLETED:
            return 0

        return self.current_context.hint_manager.calculate_final_score(
            self.current_context.base_points
        )

    def get_result(self) -> Optional[ScenarioResult]:
        """Get final scenario result."""
        if not self.current_context:
            return None

        return ScenarioResult(
            scenario_id=self.current_context.scenario_id,
            success=self.current_context.state == ScenarioState.COMPLETED,
            points_earned=self.calculate_score(),
            max_points=self.current_context.base_points,
            hints_used=self.current_context.hint_manager.hints_used,
            ai_hints_used=self.current_context.hint_manager.ai_hints_used,
            hint_penalty=self.current_context.hint_manager.total_penalty,
            commands_executed=self.current_context.command_history.command_count,
        )

    def skip_scenario(self) -> None:
        """Skip current scenario."""
        if self.current_context:
            self.current_context.state = ScenarioState.SKIPPED
            self.cleanup()

    def cleanup(self) -> bool:
        """Clean up workspace resources."""
        if not self.current_context:
            return True

        if self.current_context.workspace_path and self.workspace_manager:
            return self.workspace_manager.clean_workspace(self.current_context.workspace_path)
        return True

    @property
    def is_active(self) -> bool:
        """Check if scenario is active."""
        return (
            self.current_context is not None
            and self.current_context.state == ScenarioState.ACTIVE
        )

    @property
    def is_completed(self) -> bool:
        """Check if scenario is completed."""
        return (
            self.current_context is not None
            and self.current_context.state == ScenarioState.COMPLETED
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current scenario status."""
        if not self.current_context:
            return {"active": False}

        return {
            "active": True,
            "scenario_id": self.current_context.scenario_id,
            "title": self.current_context.title,
            "state": self.current_context.state.value,
            "workspace_path": str(self.current_context.workspace_path or ""),
            "hints_used": self.current_context.hint_manager.hints_used if self.current_context.hint_manager else 0,
            "hints_remaining": self.current_context.hint_manager.hints_remaining if self.current_context.hint_manager else 0,
            "commands_executed": self.current_context.command_history.command_count if self.current_context.command_history else 0,
            "resources_deployed": len(self.current_context.deployed_resources),
        }

    def get_command_history_for_persistence(self) -> List[Dict[str, Any]]:
        """Get last 10 commands for persistence."""
        if not self.current_context or not self.current_context.command_history:
            return []

        recent = self.current_context.command_history.get_recent(10)
        return [
            {
                "command": r.command,
                "success": r.result.success,
                "output": r.result.output[:200] if r.result.output else "",
            }
            for r in recent
        ]

    def restore_hint_state(self, hints_used: int, ai_hints_used: int) -> None:
        """Restore hint state when resuming."""
        if self.current_context and self.current_context.hint_manager:
            self.current_context.hint_manager._hints_used = hints_used
            self.current_context.hint_manager._ai_hints_used = ai_hints_used

    def restore_command_history(self, history: List[Dict[str, Any]]) -> None:
        """Restore command history for AI context."""
        if not self.current_context or not self.current_context.command_history:
            return

        for entry in history:
            result = ValidationResult(
                success=entry.get("success", False),
                message="",
                output=entry.get("output", ""),
            )
            self.current_context.command_history.add(
                entry.get("command", ""), result, duration_ms=0
            )


def create_scenario_engine(
    enable_ai: bool = True,
    workspace_manager: Optional[WorkspaceManager] = None,
) -> ScenarioEngine:
    """Create a configured ScenarioEngine."""
    gemini = get_gemini_client() if enable_ai else None
    return ScenarioEngine(gemini_client=gemini, workspace_manager=workspace_manager)
