"""Environment doctor for CI/CD and GitHub Actions tooling.

Checks local environment for:
1. git: Version control (Required)
2. gh: GitHub CLI & authentication status (Recommended)
3. actionlint: Workflow static analysis linter (Recommended)
4. act: Local GitHub Actions runner & Docker status (Optional)
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class OSInfo:
    """Operating system information."""

    system: str  # 'Darwin', 'Linux', 'Windows'
    name: str  # 'macos', 'linux', 'windows', 'unknown'
    is_wsl: bool = False


def detect_os() -> OSInfo:
    """Detect the current operating system."""
    sys_name = platform.system()
    is_wsl = False
    if sys_name == "Linux" and Path("/proc/version").exists():
        try:
            version_text = Path("/proc/version").read_text().lower()
            if "microsoft" in version_text or "wsl" in version_text:
                is_wsl = True
        except Exception:
            pass

    name_map = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}
    return OSInfo(system=sys_name, name=name_map.get(sys_name, "unknown"), is_wsl=is_wsl)


def check_kubectl_installed() -> bool:
    """Deprecated K8s check; checks git presence as minimal prerequisite."""
    return shutil.which("git") is not None


def detect_k8s_environment() -> Optional[Any]:
    """Deprecated K8s check; returns None in ActionsPath."""
    return None


def show_setup_guide(os_info: Optional[OSInfo] = None) -> None:
    """Display environment setup guide using doctor report."""
    report = run_doctor()
    render_doctor_report(report)


def show_kubectl_install(os_info: Optional[OSInfo] = None) -> None:
    """Display installation recommendations for missing tools."""
    report = run_doctor()
    render_doctor_report(report)


def show_minikube_required_warning(provider: Optional[str] = None) -> None:
    """No-op in ActionsPath."""
    pass


@dataclass
class ToolStatus:
    """Status report for a single CLI tool."""

    name: str
    display_name: str
    installed: bool
    version: Optional[str] = None
    required: bool = True
    status: str = "ok"  # "ok", "warning", "missing"
    message: str = ""
    install_command: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorReport:
    """Aggregated doctor inspection report."""

    is_ready: bool
    tools: Dict[str, ToolStatus]
    summary_message: str
    recommendations: List[str] = field(default_factory=list)


def _get_platform_os() -> str:
    """Return normalized OS name: 'linux', 'darwin', or 'windows'."""
    system = platform.system().lower()
    if "darwin" in system:
        return "darwin"
    if "windows" in system:
        return "windows"
    return "linux"


def check_git() -> ToolStatus:
    """Check Git installation and version."""
    path = shutil.which("git")
    if not path:
        os_type = _get_platform_os()
        if os_type == "darwin":
            cmd = "brew install git"
        elif os_type == "windows":
            cmd = "winget install --id Git.Git -e --source winget"
        else:
            cmd = "sudo apt-get install git (Ubuntu/Debian) or sudo dnf install git (Fedora)"

        return ToolStatus(
            name="git",
            display_name="Git VCS",
            installed=False,
            required=True,
            status="missing",
            message="Git is required to create practice workspaces and commit workflows",
            install_command=cmd,
        )

    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
        match = re.search(r"(\d+\.\d+(\.\d+)?)", res.stdout)
        version = match.group(1) if match else res.stdout.strip()
        return ToolStatus(
            name="git",
            display_name="Git VCS",
            installed=True,
            version=version,
            required=True,
            status="ok",
            message="Git is installed and ready",
        )
    except Exception as e:
        return ToolStatus(
            name="git",
            display_name="Git VCS",
            installed=True,
            required=True,
            status="warning",
            message=f"Git check error: {e}",
        )


def check_gh() -> ToolStatus:
    """Check GitHub CLI (gh) installation and authentication."""
    path = shutil.which("gh")
    os_type = _get_platform_os()

    if not path:
        if os_type == "darwin":
            cmd = "brew install gh"
        elif os_type == "windows":
            cmd = "winget install --id GitHub.cli -e --source winget"
        else:
            cmd = "sudo apt install gh (Debian) or sudo dnf install gh (Fedora)"

        return ToolStatus(
            name="gh",
            display_name="GitHub CLI (gh)",
            installed=False,
            required=False,
            status="missing",
            message="Recommended for repo management, issue tracking, and checking remote runs",
            install_command=cmd,
        )

    version: Optional[str] = None
    try:
        res = subprocess.run(["gh", "--version"], capture_output=True, text=True, check=False)
        match = re.search(r"(\d+\.\d+(\.\d+)?)", res.stdout)
        version = match.group(1) if match else res.stdout.strip()
    except Exception:
        pass

    # Check authentication status
    auth_ok = False
    try:
        auth_res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
        if auth_res.returncode == 0 or "Logged in to" in (auth_res.stdout + auth_res.stderr):
            auth_ok = True
    except Exception:
        pass

    if auth_ok:
        return ToolStatus(
            name="gh",
            display_name="GitHub CLI (gh)",
            installed=True,
            version=version,
            required=False,
            status="ok",
            message="Installed and authenticated",
            details={"authenticated": True},
        )

    return ToolStatus(
        name="gh",
        display_name="GitHub CLI (gh)",
        installed=True,
        version=version,
        required=False,
        status="warning",
        message="Installed, but not authenticated with GitHub",
        install_command="gh auth login",
        details={"authenticated": False},
    )


def check_actionlint() -> ToolStatus:
    """Check actionlint workflow linter."""
    path = shutil.which("actionlint")
    os_type = _get_platform_os()

    if not path:
        if os_type == "darwin":
            cmd = "brew install actionlint"
        elif os_type == "windows":
            cmd = "choco install actionlint or winget install rhysd.actionlint"
        else:
            cmd = "bash <(curl -s https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)"

        return ToolStatus(
            name="actionlint",
            display_name="actionlint",
            installed=False,
            required=False,
            status="missing",
            message="Recommended for static analysis of GitHub Actions workflow files",
            install_command=cmd,
        )

    try:
        res = subprocess.run(["actionlint", "-version"], capture_output=True, text=True, check=False)
        match = re.search(r"(\d+\.\d+(\.\d+)?)", res.stdout)
        version = match.group(1) if match else res.stdout.strip()
        return ToolStatus(
            name="actionlint",
            display_name="actionlint",
            installed=True,
            version=version,
            required=False,
            status="ok",
            message="Static workflow linter ready",
        )
    except Exception as e:
        return ToolStatus(
            name="actionlint",
            display_name="actionlint",
            installed=True,
            required=False,
            status="warning",
            message=f"actionlint check error: {e}",
        )


def check_act() -> ToolStatus:
    """Check act (run GitHub Actions locally) and Docker status."""
    path = shutil.which("act")
    os_type = _get_platform_os()

    if not path:
        if os_type == "darwin":
            cmd = "brew install act"
        elif os_type == "windows":
            cmd = "choco install act-cli or winget install nektos.act"
        else:
            cmd = "curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash"

        return ToolStatus(
            name="act",
            display_name="act (Local Runner)",
            installed=False,
            required=False,
            status="missing",
            message="Optional tool to run GitHub Actions locally inside Docker containers",
            install_command=cmd,
        )

    version: Optional[str] = None
    try:
        res = subprocess.run(["act", "--version"], capture_output=True, text=True, check=False)
        match = re.search(r"(\d+\.\d+(\.\d+)?)", res.stdout)
        version = match.group(1) if match else res.stdout.strip()
    except Exception:
        pass

    # act requires Docker running
    docker_running = False
    if shutil.which("docker"):
        try:
            d_res = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
            docker_running = (d_res.returncode == 0)
        except Exception:
            pass

    if docker_running:
        return ToolStatus(
            name="act",
            display_name="act (Local Runner)",
            installed=True,
            version=version,
            required=False,
            status="ok",
            message="Installed and Docker daemon is running",
            details={"docker_ready": True},
        )

    return ToolStatus(
        name="act",
        display_name="act (Local Runner)",
        installed=True,
        version=version,
        required=False,
        status="warning",
        message="Installed, but Docker daemon is not active (required to run act)",
        install_command="sudo systemctl start docker (or start Docker Desktop)",
        details={"docker_ready": False},
    )


def run_doctor() -> DoctorReport:
    """Run all CI/CD environment diagnostics."""
    tools = {
        "git": check_git(),
        "gh": check_gh(),
        "actionlint": check_actionlint(),
        "act": check_act(),
    }

    # Git is strictly required
    is_ready = tools["git"].installed

    recommendations: List[str] = []
    for tool in tools.values():
        if tool.status in ("missing", "warning") and tool.install_command:
            recommendations.append(f"{tool.display_name}: {tool.install_command}")

    if is_ready:
        summary = "Your environment is ready for ActionsPath hands-on practice!"
    else:
        summary = "Missing required dependencies (Git). Please install Git to continue."

    return DoctorReport(
        is_ready=is_ready,
        tools=tools,
        summary_message=summary,
        recommendations=recommendations,
    )


def render_doctor_report(report: DoctorReport, console: Optional[Console] = None) -> None:
    """Render doctor diagnosis using Rich formatting."""
    from actionspath.console import get_console

    con = console or get_console()

    table = Table(title="ActionsPath CI/CD Environment Doctor", header_style="bold cyan")
    table.add_column("Tool", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Version", justify="center")
    table.add_column("Notes")

    for tool in report.tools.values():
        if tool.status == "ok":
            status_text = "[bold green]✓ Ready[/bold green]"
        elif tool.status == "warning":
            status_text = "[bold yellow]⚠ Warning[/bold yellow]"
        else:
            status_text = "[bold red]✗ Missing[/bold red]" if tool.required else "[dim]○ Missing[/dim]"

        ver_text = tool.version or "-"
        table.add_row(tool.display_name, status_text, ver_text, tool.message)

    con.print(table)

    if report.recommendations:
        rec_text = "\n".join(f"• [bold]{rec}[/bold]" for rec in report.recommendations)
        con.print(
            Panel(
                rec_text,
                title="[bold yellow]Recommended Next Steps[/bold yellow]",
                border_style="yellow",
            )
        )

    if report.is_ready:
        con.print(f"\n[bold green]✓ {report.summary_message}[/bold green]\n")
    else:
        con.print(f"\n[bold red]✗ {report.summary_message}[/bold red]\n")
