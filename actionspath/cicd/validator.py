"""Workflow and YAML validation for GitHub Actions and CI/CD pipelines.

Validates:
1. YAML syntax using ruamel.yaml.
2. GitHub Actions workflow structure (triggers, jobs, steps).
3. Job dependency graphs and DAG cycles (topological sorting).
4. External actionlint execution if installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


@dataclass
class ValidationResult:
    """Result of a validation check."""

    success: bool
    message: str
    output: str = ""
    errors: List[str] = field(default_factory=list)


def _load_yaml(content_or_path: Union[str, Path]) -> Tuple[Optional[Any], Optional[str]]:
    """Parse YAML content using ruamel.yaml.

    Returns:
        Tuple of (parsed_data, error_message).
    """
    yaml = YAML(typ="safe")
    text = ""
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).is_file()
    ):
        file_path = Path(content_or_path)
        if not file_path.exists():
            return None, f"File not found: {file_path}"
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return None, f"Could not read file {file_path}: {e}"
    else:
        text = str(content_or_path)

    if not text.strip():
        return None, "Workflow content is empty"

    try:
        data = yaml.load(text)
        return data, None
    except YAMLError as e:
        error_msg = str(e)
        if hasattr(e, "problem_mark") and e.problem_mark:
            line = e.problem_mark.line + 1
            col = e.problem_mark.column + 1
            error_msg = f"Line {line}, Column {col}: {e.problem or 'Syntax error'}"
        return None, error_msg


def validate_yaml_syntax(content_or_path: Union[str, Path]) -> ValidationResult:
    """Validate YAML syntax for a workflow file or content string.

    Args:
        content_or_path: File path or raw YAML string.

    Returns:
        ValidationResult indicating syntax validity.
    """
    data, error = _load_yaml(content_or_path)
    if error:
        return ValidationResult(
            success=False,
            message=f"Invalid YAML syntax: {error}",
            output=error,
            errors=[error],
        )

    return ValidationResult(
        success=True,
        message="YAML syntax is valid",
        output="YAML parsed successfully",
    )


def validate_workflow_structure(content_or_path: Union[str, Path, Dict[str, Any]]) -> ValidationResult:
    """Validate GitHub Actions workflow schema and essential keys.

    Checks:
    - Root is a mapping/dict.
    - Workflow trigger 'on' is defined (or boolean True in YAML 1.1).
    - 'jobs' section is defined and is a non-empty mapping.
    - Each job has 'runs-on' or 'uses' (for reusable workflows).
    - If steps are defined, each step is a list of mapping items.
    """
    if isinstance(content_or_path, dict):
        data = content_or_path
    else:
        data, error = _load_yaml(content_or_path)
        if error:
            return ValidationResult(
                success=False,
                message=f"Workflow structure check failed: {error}",
                output=error,
                errors=[error],
            )

    if not isinstance(data, dict):
        msg = f"Root of workflow must be a mapping/dictionary, got {type(data).__name__}"
        return ValidationResult(success=False, message=msg, errors=[msg])

    errors: List[str] = []

    # 1. Trigger validation: 'on' key (in some YAML parsers 'on' without quotes becomes True)
    has_trigger = "on" in data or True in data or "true" in data
    if not has_trigger:
        errors.append("Missing required trigger 'on'. Workflows must declare an event trigger.")

    # 2. Jobs section
    if "jobs" not in data:
        errors.append("Missing required 'jobs' section.")
    elif not isinstance(data["jobs"], dict):
        errors.append(f"'jobs' must be a mapping of job_id -> job_definition, got {type(data['jobs']).__name__}.")
    elif len(data["jobs"]) == 0:
        errors.append("'jobs' section must contain at least one job.")
    else:
        # Validate individual jobs
        for job_id, job in data["jobs"].items():
            if not isinstance(job, dict):
                errors.append(f"Job '{job_id}' must be a dictionary, got {type(job).__name__}.")
                continue

            # Must have runs-on or uses (reusable workflow)
            has_runner = "runs-on" in job or "uses" in job
            if not has_runner:
                errors.append(f"Job '{job_id}' must specify 'runs-on' (e.g. ubuntu-latest) or 'uses' (reusable workflow).")

            # Validate steps if present
            if "steps" in job:
                steps = job["steps"]
                if not isinstance(steps, list):
                    errors.append(f"Job '{job_id}' steps must be a list, got {type(steps).__name__}.")
                else:
                    for idx, step in enumerate(steps):
                        if not isinstance(step, dict):
                            errors.append(f"Job '{job_id}' step #{idx+1} must be a dictionary.")
                        elif "uses" not in step and "run" not in step:
                            errors.append(f"Job '{job_id}' step #{idx+1} must define either 'uses' or 'run'.")

    if errors:
        return ValidationResult(
            success=False,
            message=f"Workflow structure validation failed with {len(errors)} error(s)",
            output="\n".join(errors),
            errors=errors,
        )

    return ValidationResult(
        success=True,
        message="Workflow structure is valid",
        output=f"Workflow contains {len(data.get('jobs', {}))} valid job(s)",
    )


def validate_job_dependencies(content_or_path: Union[str, Path, Dict[str, Any]]) -> ValidationResult:
    """Validate job dependency DAG and detect circular dependencies.

    Checks:
    - All job names listed in 'needs' exist in 'jobs'.
    - No circular dependencies exist in the job graph.
    """
    if isinstance(content_or_path, dict):
        data = content_or_path
    else:
        data, error = _load_yaml(content_or_path)
        if error:
            return ValidationResult(
                success=False,
                message=f"Dependency check failed: {error}",
                output=error,
                errors=[error],
            )

    if not isinstance(data, dict) or "jobs" not in data or not isinstance(data["jobs"], dict):
        return ValidationResult(
            success=False,
            message="No valid 'jobs' found to validate dependencies",
            errors=["No valid 'jobs' mapping in workflow"],
        )

    jobs = data["jobs"]
    all_job_ids = set(jobs.keys())
    adj_list: Dict[str, List[str]] = defaultdict(list)
    in_degree: Dict[str, int] = {j: 0 for j in all_job_ids}
    errors: List[str] = []

    for job_id, job_def in jobs.items():
        if not isinstance(job_def, dict):
            continue
        needs = job_def.get("needs", [])
        if isinstance(needs, str):
            dependencies = [needs]
        elif isinstance(needs, list):
            dependencies = [str(n) for n in needs]
        else:
            errors.append(f"Job '{job_id}' has invalid 'needs' specification of type {type(needs).__name__}")
            dependencies = []

        for dep in dependencies:
            if dep not in all_job_ids:
                errors.append(f"Job '{job_id}' depends on undefined job '{dep}' in 'needs'")
            else:
                adj_list[dep].append(job_id)
                in_degree[job_id] += 1

    if errors:
        return ValidationResult(
            success=False,
            message=f"Job dependency errors found: {len(errors)} error(s)",
            output="\n".join(errors),
            errors=errors,
        )

    # Topological sort (Kahn's algorithm) to detect cycles
    queue = deque([j for j, deg in in_degree.items() if deg == 0])
    visited_count = 0
    execution_order: List[str] = []

    while queue:
        node = queue.popleft()
        visited_count += 1
        execution_order.append(node)
        for neighbor in adj_list[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < len(all_job_ids):
        # Find remaining nodes with in_degree > 0
        cycle_nodes = [j for j, deg in in_degree.items() if deg > 0]
        msg = f"Circular dependency detected in jobs: {', '.join(cycle_nodes)}"
        return ValidationResult(
            success=False,
            message=msg,
            output=msg,
            errors=[msg],
        )

    order_str = " -> ".join(execution_order)
    return ValidationResult(
        success=True,
        message="Job dependencies are valid (no circular dependencies)",
        output=f"Resolved execution order: {order_str}",
    )


def check_actionlint_installed() -> bool:
    """Check if actionlint is installed and available in PATH."""
    return shutil.which("actionlint") is not None


def run_actionlint(
    content_or_path: Union[str, Path],
    cwd: Optional[Path] = None,
) -> ValidationResult:
    """Run actionlint against a workflow file or content string."""
    if not check_actionlint_installed():
        return ValidationResult(
            success=True,
            message="actionlint is not installed (skipping external linting)",
            output="actionlint not found in PATH",
        )

    temp_file: Optional[Path] = None
    target_path: Path

    if isinstance(content_or_path, Path) and content_or_path.is_file():
        target_path = content_or_path
    elif isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).is_file():
        target_path = Path(content_or_path)
    else:
        # Create temp file in a fake .github/workflows directory for actionlint rules
        tmp_dir = Path(tempfile.mkdtemp(prefix="actionspath_actionlint_"))
        wf_dir = tmp_dir / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        target_path = wf_dir / "workflow.yml"
        target_path.write_text(str(content_or_path), encoding="utf-8")
        temp_file = target_path

    try:
        run_cwd = cwd or target_path.parent
        res = subprocess.run(
            ["actionlint", "-oneline", str(target_path)],
            capture_output=True,
            text=True,
            cwd=run_cwd,
            timeout=15,
        )

        output = (res.stdout + res.stderr).strip()
        if res.returncode != 0:
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            return ValidationResult(
                success=False,
                message=f"actionlint detected {len(lines)} issue(s)",
                output=output,
                errors=lines,
            )

        return ValidationResult(
            success=True,
            message="actionlint passed with 0 issues",
            output=output or "actionlint OK",
        )
    except Exception as e:
        return ValidationResult(
            success=False,
            message=f"actionlint execution failed: {e}",
            output=str(e),
            errors=[str(e)],
        )
    finally:
        if temp_file and temp_file.exists():
            shutil.rmtree(temp_file.parent.parent.parent, ignore_errors=True)


def validate_workflow(
    content_or_path: Union[str, Path],
    workspace_path: Optional[Path] = None,
) -> ValidationResult:
    """Run full validation pipeline on a GitHub Actions workflow.

    Pipeline:
    1. YAML Syntax Check
    2. Workflow Schema / Structure Check
    3. Job Dependency / Cycle Check
    4. actionlint (if available)
    """
    # 1. YAML Syntax
    syntax_res = validate_yaml_syntax(content_or_path)
    if not syntax_res.success:
        return syntax_res

    # 2. Workflow Structure
    struct_res = validate_workflow_structure(content_or_path)
    if not struct_res.success:
        return struct_res

    # 3. Job Dependencies
    dep_res = validate_job_dependencies(content_or_path)
    if not dep_res.success:
        return dep_res

    # 4. actionlint
    if check_actionlint_installed():
        lint_res = run_actionlint(content_or_path, cwd=workspace_path)
        if not lint_res.success:
            return lint_res

    return ValidationResult(
        success=True,
        message="Workflow passed all CI/CD validations",
        output=f"{struct_res.output}\n{dep_res.output}",
    )


def execute_command(command: str, timeout: int = 30, cwd: Optional[Path | str] = None) -> ValidationResult:
    """Execute a user-provided command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout + result.stderr

        if result.returncode != 0:
            return ValidationResult(
                success=False,
                message=f"Command exited with code {result.returncode}",
                output=output,
                errors=[f"Exit code {result.returncode}"],
            )

        return ValidationResult(
            success=True,
            message="Command executed successfully",
            output=output,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            success=False,
            message=f"Command timed out after {timeout} seconds",
            errors=["Timeout expired"],
        )
    except Exception as e:
        return ValidationResult(
            success=False,
            message=f"Error executing command: {e}",
            errors=[str(e)],
        )


def validate_output(output: str, expected_contains: Optional[str] = None) -> bool:
    """Check if output contains expected text (case-insensitive)."""
    if expected_contains and expected_contains.lower() not in output.lower():
        return False
    return True


# ---------------------------------------------------------------------------
# Command and Generic Spec Validation Helpers (CLI & Scenario runner support)
# ---------------------------------------------------------------------------


def validate_command_output(
    command: str,
    expected_contains: Optional[str] = None,
    expected_not_contains: Optional[str] = None,
    timeout: int = 30,
    cwd: Optional[Path | str] = None,
) -> ValidationResult:
    """Run a shell command and validate its output.

    Args:
        command: Shell command string.
        expected_contains: Substring that must appear in stdout/stderr.
        expected_not_contains: Substring that must NOT appear in stdout/stderr.
        timeout: Timeout in seconds.
        cwd: Working directory.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout + result.stderr

        if result.returncode != 0 and not expected_contains:
            return ValidationResult(
                success=False,
                message=f"Command failed with exit code {result.returncode}",
                output=output,
                errors=[f"Exit code {result.returncode}"],
            )

        if expected_contains and expected_contains not in output:
            return ValidationResult(
                success=False,
                message=f"Expected '{expected_contains}' not found in output",
                output=output,
                errors=[f"Expected '{expected_contains}' missing"],
            )

        if expected_not_contains and expected_not_contains in output:
            return ValidationResult(
                success=False,
                message=f"Unexpected '{expected_not_contains}' found in output",
                output=output,
                errors=[f"Found unexpected text '{expected_not_contains}'"],
            )

        return ValidationResult(
            success=True,
            message="Command output verified successfully",
            output=output,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            success=False,
            message=f"Command timed out after {timeout} seconds",
            errors=["Timeout expired"],
        )
    except Exception as e:
        return ValidationResult(
            success=False,
            message=f"Command execution error: {e}",
            errors=[str(e)],
        )


def validate_from_spec(
    validation_spec: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """Validate learner solution according to a challenge validation specification.

    Supports:
    - type: "workflow" / "yaml": Validates workflow file or content.
    - type: "command": Runs command and tests output.
    - type: "file_exists": Verifies a required file was created.
    """
    v_type = validation_spec.get("type", "command")
    cwd = context.get("workspace_path") if context else None

    if v_type in ("workflow", "yaml"):
        file_path = validation_spec.get("file")
        if file_path and cwd:
            target = Path(cwd) / file_path
        elif file_path:
            target = Path(file_path)
        else:
            target = validation_spec.get("content", "")

        return validate_workflow(target, workspace_path=Path(cwd) if cwd else None)

    if v_type == "file_exists":
        file_path = validation_spec.get("file", "")
        target = Path(cwd) / file_path if cwd else Path(file_path)
        if target.exists():
            return ValidationResult(success=True, message=f"File {file_path} exists.")
        return ValidationResult(
            success=False,
            message=f"File {file_path} does not exist.",
            errors=[f"Missing file: {file_path}"],
        )

    # Default to command execution
    command = validation_spec.get("command", "")
    return validate_command_output(
        command=command,
        expected_contains=validation_spec.get("expected_contains"),
        expected_not_contains=validation_spec.get("expected_not_contains"),
        timeout=validation_spec.get("timeout", 30),
        cwd=cwd,
    )
