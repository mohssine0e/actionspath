"""Integration tests for kubepath CLI commands."""

import subprocess
import sys


class TestCLICommands:
    """Integration tests that run actual CLI commands."""

    def test_kubepath_help(self):
        """Test that actionspath --help runs successfully."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "actionspath" in result.stdout.lower()

    def test_kubepath_start_chapter_1_quit(self):
        """Test that actionspath start 1 runs and accepts quit command."""
        # Ensure clean state for chapter 1
        subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "reset", "1", "-y"],
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "start", "1"],
            capture_output=True,
            text=True,
            input="q\n",
        )
        assert result.returncode == 0
        assert "chapter" in result.stdout.lower() or "workflow" in result.stdout.lower()

    def test_kubepath_start_navigation(self):
        """Test navigating through concepts."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "start", "1", "--reset"],
            capture_output=True,
            text=True,
            input="n\nq\n",  # Next (from concept 1), then quit
        )
        assert result.returncode == 0

    def test_kubepath_start_nonexistent_chapter(self):
        """Test that starting nonexistent chapter shows error."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "start", "999"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stdout.lower()

    def test_kubepath_list(self):
        """Test that kubepath list runs without error."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "list"],
            capture_output=True,
            text=True,
            input="q\n",  # Quit the interactive selection
        )
        assert result.returncode == 0
        assert "Browse Chapters" in result.stdout

    def test_kubepath_invalid_chapter(self):
        """Test that invalid chapter type returns error."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "start", "invalid"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_kubepath_reset(self):
        """Test that reset command works."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "reset", "1", "-y"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Progress reset" in result.stdout

    def test_kubepath_reset_all(self):
        """Test that reset --all command works."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "reset", "--all", "-y"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "All course progress" in result.stdout

    def test_kubepath_start_with_reset_flag(self):
        """Test that start with --reset flag works."""
        result = subprocess.run(
            [sys.executable, "-m", "actionspath.cli", "start", "1", "--reset"],
            capture_output=True,
            text=True,
            input="q\n",
        )
        assert result.returncode == 0
