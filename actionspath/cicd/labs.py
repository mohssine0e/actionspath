"""Boss Lab capstone engine and multi-objective validation for ActionsPath."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from actionspath.cicd.validator import _load_yaml, check_yaml_assertion, validate_workflow_structure


@dataclass
class ObjectiveResult:
    """Evaluation result for an individual Boss Lab objective."""

    id: str
    title: str
    passed: bool
    message: str
    hint: Optional[str] = None


@dataclass
class BossLabValidationResult:
    """Overall evaluation result across all objectives of a Boss Lab."""

    success: bool
    objectives: List[ObjectiveResult] = field(default_factory=list)
    summary: str = ""
    syntax_error: Optional[str] = None


@dataclass
class BossLab:
    """Representation of an end-of-module capstone Boss Lab."""

    module: int
    id: str
    title: str
    badge: str
    scenario_type: str
    briefing: str
    objectives: List[Dict[str, Any]]
    simulated_log: Optional[str] = None
    initial_files: Dict[str, str] = field(default_factory=dict)
    solution_files: Optional[Dict[str, str]] = None


def get_labs_data_dir() -> Path:
    """Return path to data/labs directory."""
    return Path(__file__).resolve().parent.parent / "data" / "labs"


def load_boss_lab(module_num: int) -> Optional[BossLab]:
    """Load a Boss Lab specification for the given module number (1-6)."""
    labs_dir = get_labs_data_dir()
    lab_file = labs_dir / f"lab-{module_num:02d}.yaml"
    if not lab_file.exists():
        # Fallback to single digit or pattern
        matches = list(labs_dir.glob(f"*{module_num}*.yaml"))
        if matches:
            lab_file = matches[0]
        else:
            return None

    try:
        with open(lab_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return None

    lab_data = data.get("lab", {})
    if not lab_data:
        return None

    return BossLab(
        module=lab_data.get("module", module_num),
        id=lab_data.get("id", f"boss-lab-{module_num:02d}"),
        title=lab_data.get("title", f"Module {module_num} Capstone Lab"),
        badge=lab_data.get("badge", "Mastery Badge"),
        scenario_type=lab_data.get("scenario_type", "incident_triage"),
        briefing=lab_data.get("briefing", "").strip(),
        simulated_log=lab_data.get("simulated_log", "").strip() or None,
        initial_files=lab_data.get("initial_files", {}),
        objectives=lab_data.get("objectives", []),
        solution_files=lab_data.get("solution_files"),
    )


def load_all_boss_labs() -> List[BossLab]:
    """Load all available Boss Labs (modules 1 through 6)."""
    labs = []
    for m in range(1, 7):
        lab = load_boss_lab(m)
        if lab:
            labs.append(lab)
    return labs


def get_lab_workspace_dir(module_num: int) -> Path:
    """Return the isolated workspace directory for a specific Boss Lab."""
    base = Path.home() / ".actionspath" / "labs" / f"lab-{module_num:02d}"
    return base


def setup_lab_workspace(lab: BossLab, reset: bool = False) -> Path:
    """Set up the files in the lab workspace directory.

    If files already exist and reset is False, existing edits are preserved.
    """
    workspace = get_lab_workspace_dir(lab.module)
    if reset and workspace.exists():
        shutil.rmtree(workspace)

    workspace.mkdir(parents=True, exist_ok=True)

    for rel_path, content in lab.initial_files.items():
        file_path = workspace / rel_path
        if not file_path.exists() or reset:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    return workspace


def validate_boss_lab(workspace: Path, lab: BossLab) -> BossLabValidationResult:
    """Validate all objectives of a Boss Lab in the learner's workspace.

    Returns:
        BossLabValidationResult containing individual objective status.
    """
    objective_results: List[ObjectiveResult] = []
    all_passed = True

    # Cache parsed YAMLs per file path to avoid redundant parses
    parsed_cache: Dict[str, Tuple[Optional[Any], Optional[str]]] = {}

    for obj in lab.objectives:
        obj_id = obj.get("id", "objective")
        obj_title = obj.get("title", "Objective")
        obj_hint = obj.get("hint")
        target_file_rel = obj.get("file", ".github/workflows/ci.yml")
        target_file = workspace / target_file_rel

        if not target_file.exists():
            all_passed = False
            objective_results.append(
                ObjectiveResult(
                    id=obj_id,
                    title=obj_title,
                    passed=False,
                    message=f"Required file '{target_file_rel}' does not exist",
                    hint=obj_hint,
                )
            )
            continue

        # Load file YAML
        if target_file_rel not in parsed_cache:
            parsed_data, err = _load_yaml(target_file)
            parsed_cache[target_file_rel] = (parsed_data, err)
        else:
            parsed_data, err = parsed_cache[target_file_rel]

        if err or parsed_data is None:
            all_passed = False
            objective_results.append(
                ObjectiveResult(
                    id=obj_id,
                    title=obj_title,
                    passed=False,
                    message=f"YAML syntax error in '{target_file_rel}': {err}",
                    hint=obj_hint,
                )
            )
            continue

        # Check workflow structural schema if file is a GitHub Actions workflow
        if ".github/workflows" in target_file_rel:
            struct_res = validate_workflow_structure(target_file)
            if not struct_res.success:
                all_passed = False
                objective_results.append(
                    ObjectiveResult(
                        id=obj_id,
                        title=obj_title,
                        passed=False,
                        message=f"Workflow structure invalid: {struct_res.message}",
                        hint=obj_hint or "Check workflow schema: ensure 'on' and 'jobs' with valid runners are declared.",
                    )
                )
                continue

        # Check starter diff if defined
        starter_content = lab.initial_files.get(target_file_rel)
        if starter_content and target_file.read_text(encoding="utf-8").strip() == starter_content.strip():
            # Check if this objective expects modifications
            if obj.get("assertions"):
                all_passed = False
                objective_results.append(
                    ObjectiveResult(
                        id=obj_id,
                        title=obj_title,
                        passed=False,
                        message=f"File '{target_file_rel}' has not been edited yet",
                        hint=obj_hint or "Press [e] to edit the file and solve the objective.",
                    )
                )
                continue

        # Evaluate assertions for this objective
        obj_passed = True
        obj_fail_msg = "Passed"
        assertions = obj.get("assertions", [])

        for assertion in assertions:
            passed, fail_msg = check_yaml_assertion(parsed_data, assertion)
            if not passed:
                obj_passed = False
                custom_msg = assertion.get("message")
                obj_fail_msg = f"{custom_msg} ({fail_msg})" if custom_msg else fail_msg
                break

        if obj_passed:
            objective_results.append(
                ObjectiveResult(
                    id=obj_id,
                    title=obj_title,
                    passed=True,
                    message="All requirements satisfied",
                    hint=None,
                )
            )
        else:
            all_passed = False
            objective_results.append(
                ObjectiveResult(
                    id=obj_id,
                    title=obj_title,
                    passed=False,
                    message=obj_fail_msg,
                    hint=obj_hint,
                )
            )

    passed_count = sum(1 for r in objective_results if r.passed)
    total_count = len(objective_results)

    if all_passed:
        summary = f"🎉 ALL {total_count} OBJECTIVES COMPLETED! You earned the '{lab.badge}' title!"
    else:
        summary = f"Progress: {passed_count}/{total_count} objectives completed."

    return BossLabValidationResult(
        success=all_passed,
        objectives=objective_results,
        summary=summary,
    )


def run_boss_lab(module_num: int) -> bool:
    """Run interactive terminal session for a Boss Lab.

    Returns:
        True if the lab was successfully completed.
    """
    import difflib
    import subprocess
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from actionspath.console import clear_screen, get_console
    from actionspath.utils.progress import is_lab_completed, save_lab_completed

    console = get_console()
    lab = load_boss_lab(module_num)
    if not lab:
        console.print(f"[bold red]Boss Lab for Module {module_num} not found.[/bold red]")
        return False

    workspace = setup_lab_workspace(lab)

    def get_editor_cmd() -> str:
        ed = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not ed:
            for candidate in ("nano", "vim", "vi", "code"):
                if shutil.which(candidate):
                    ed = candidate
                    break
        return ed or "nano"

    while True:
        clear_screen()

        # Header banner
        header = Text()
        header.append(f"👑 MODULE {lab.module} BOSS LAB: ", style="bold yellow")
        header.append(lab.title, style="bold cyan")
        header.append(f"  |  Reward: ", style="dim")
        header.append(lab.badge, style="bold magenta")
        console.print(Panel(header, border_style="gold1"))

        # Briefing
        console.print(
            Panel(
                lab.briefing,
                title="[bold cyan]📋 Incident Briefing[/bold cyan]",
                border_style="bright_blue",
                padding=(0, 1),
            )
        )

        # Simulated log if present
        if lab.simulated_log:
            log_lines = []
            for line in lab.simulated_log.splitlines():
                if "##[error]" in line:
                    log_lines.append(f"[bold red]{line}[/bold red]")
                elif "##[warning]" in line:
                    log_lines.append(f"[bold yellow]{line}[/bold yellow]")
                elif "##[group]" in line:
                    log_lines.append(f"[bold cyan]{line}[/bold cyan]")
                else:
                    log_lines.append(f"[dim]{line}[/dim]")
            console.print(
                Panel(
                    "\n".join(log_lines),
                    title="[bold red]🔴 Simulated Runner Error Log[/bold red]",
                    border_style="red",
                    padding=(0, 1),
                )
            )

        # Evaluate current objectives status
        val_result = validate_boss_lab(workspace, lab)

        table = Table(title="[bold yellow]🎯 Mission Objectives[/bold yellow]", border_style="dim", expand=True)
        table.add_column("Status", width=8, justify="center")
        table.add_column("Objective", style="bold white")
        table.add_column("Verification Details", style="dim")

        for idx, obj_res in enumerate(val_result.objectives, 1):
            if obj_res.passed:
                status_icon = "[bold green][PASS][/bold green]"
                detail = "[green]✓ Objective criteria satisfied[/green]"
            else:
                status_icon = "[bold red][FAIL][/bold red]"
                detail = f"[red]{obj_res.message}[/red]"
            table.add_row(status_icon, f"{idx}. {obj_res.title}", detail)

        console.print(table)
        console.print(f"[dim]Workspace directory: {workspace}[/dim]\n")

        if val_result.success:
            save_lab_completed(lab.module)
            success_panel = Panel(
                f"[bold green]🏆 CONGRATULATIONS! ALL OBJECTIVES CLEARED![/bold green]\n\n"
                f"You have proven mastery of Module {lab.module}.\n"
                f"Title Unlocked: [bold yellow]{lab.badge}[/bold yellow]",
                title="[bold green]MISSION COMPLETE[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
            console.print(success_panel)
            input("\nPress Enter to return to menu...")
            return True

        # Interactive action prompt
        console.print("[bold yellow]Actions:[/bold yellow] [e] Edit files  [d] Diff changes  [v] Verify  [r] Reset  [q] Quit")
        choice = input("> ").strip().lower()

        if choice == "q":
            return False
        elif choice == "e":
            target_files = list(lab.initial_files.keys())
            if len(target_files) == 1:
                target_path = workspace / target_files[0]
            else:
                console.print("\nSelect file to edit:")
                for i, tf in enumerate(target_files, 1):
                    console.print(f"  [{i}] {tf}")
                f_idx = input("File number (or Enter for 1): ").strip()
                try:
                    chosen = target_files[int(f_idx) - 1]
                except (ValueError, IndexError):
                    chosen = target_files[0]
                target_path = workspace / chosen

            ed = get_editor_cmd()
            subprocess.run([ed, str(target_path)], check=False)
        elif choice == "d":
            clear_screen()
            console.print("[bold cyan]Current Workspace Diffs:[/bold cyan]\n")
            has_diff = False
            for rel_path, starter_content in lab.initial_files.items():
                curr_file = workspace / rel_path
                if curr_file.exists():
                    curr_content = curr_file.read_text(encoding="utf-8")
                    diff = difflib.unified_diff(
                        starter_content.splitlines(keepends=True),
                        curr_content.splitlines(keepends=True),
                        fromfile=f"starter/{rel_path}",
                        tofile=f"workspace/{rel_path}",
                    )
                    diff_text = "".join(diff)
                    if diff_text:
                        has_diff = True
                        console.print(Panel(diff_text, title=rel_path, border_style="yellow"))
            if not has_diff:
                console.print("[yellow]No modifications made yet. Press [e] to edit.[/yellow]")
            input("\nPress Enter to return...")
        elif choice == "r":
            confirm = input("Reset all files in this lab back to starter state? (y/N): ").strip().lower()
            if confirm == "y":
                setup_lab_workspace(lab, reset=True)
                console.print("[success]Lab workspace reset.[/success]")
        elif choice == "v":
            # Loop re-renders and evaluates
            pass

