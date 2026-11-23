"""Unit tests for environment doctor."""

from actionspath.cicd.doctor import (
    check_git,
    check_gh,
    check_actionlint,
    check_act,
    run_doctor,
    detect_os,
)


def test_detect_os():
    os_info = detect_os()
    assert os_info.system in ("Linux", "Darwin", "Windows")
    assert os_info.name in ("linux", "macos", "windows", "unknown")


def test_check_git():
    status = check_git()
    assert status.name == "git"
    assert status.required is True
    # On linux workspace, git is installed
    assert status.installed is True
    assert status.status == "ok"


def test_run_doctor():
    report = run_doctor()
    assert "git" in report.tools
    assert "gh" in report.tools
    assert "actionlint" in report.tools
    assert "act" in report.tools
    assert report.is_ready is True
