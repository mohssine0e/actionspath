"""CI/CD and GitHub Actions tooling module for ActionsPath.

Provides:
- WorkspaceManager: Ephemeral Git workspaces in ~/.actionspath/workspaces/.
- Validation: Syntax, schema, DAG dependencies, actionlint.
- Doctor: Environment diagnostics for git, gh, actionlint, act.
"""

from actionspath.cicd.doctor import (
    DoctorReport,
    OSInfo,
    ToolStatus,
    check_act,
    check_actionlint,
    check_gh,
    check_git,
    check_kubectl_installed,
    detect_k8s_environment,
    detect_os,
    render_doctor_report,
    run_doctor,
    show_kubectl_install,
    show_minikube_required_warning,
    show_setup_guide,
)
from actionspath.cicd.validator import (
    ValidationResult,
    check_actionlint_installed,
    execute_command,
    run_actionlint,
    validate_command_output,
    validate_from_spec,
    validate_job_dependencies,
    validate_output,
    validate_workflow,
    validate_workflow_structure,
    validate_yaml_syntax,
)
from actionspath.cicd.workspace import (
    DeployedResource,
    DeploymentResult,
    WorkspaceManager,
    delete_resources,
    deploy_manifest,
)

__all__ = [
    "WorkspaceManager",
    "DeployedResource",
    "DeploymentResult",
    "deploy_manifest",
    "delete_resources",
    "ValidationResult",
    "validate_yaml_syntax",
    "validate_workflow_structure",
    "validate_job_dependencies",
    "check_actionlint_installed",
    "run_actionlint",
    "validate_workflow",
    "validate_command_output",
    "validate_from_spec",
    "execute_command",
    "validate_output",
    "ToolStatus",
    "DoctorReport",
    "OSInfo",
    "detect_os",
    "check_kubectl_installed",
    "detect_k8s_environment",
    "show_setup_guide",
    "show_kubectl_install",
    "show_minikube_required_warning",
    "check_git",
    "check_gh",
    "check_actionlint",
    "check_act",
    "run_doctor",
    "render_doctor_report",
]
