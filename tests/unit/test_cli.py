"""Unit tests for kubepath CLI."""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from actionspath.cli import app, get_user_input, interactive_concepts, get_next_chapter, get_previous_chapter


runner = CliRunner()


class TestCLIApp:
    """Tests for the CLI application."""

    def test_app_exists(self):
        """Test that the CLI app is defined."""
        assert app is not None

    def test_app_has_name(self):
        """Test that the app has the correct name."""
        assert app.info.name == "actionspath"

    def test_help_command(self):
        """Test that --help works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Interactive CLI application for learning CI/CD and GitHub Actions" in result.stdout


class TestStartCommand:
    """Tests for the start command."""

    def test_start_command_exists(self):
        """Test that start command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "start" in result.stdout

    def test_start_with_nonexistent_chapter(self):
        """Test start command with nonexistent chapter shows error."""
        result = runner.invoke(app, ["start", "999"])
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower()

    def test_start_with_invalid_chapter_type(self):
        """Test start command with non-integer chapter."""
        result = runner.invoke(app, ["start", "abc"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "not a valid integer" in result.output

    def test_start_requires_chapter_argument(self):
        """Test that start command requires chapter argument."""
        result = runner.invoke(app, ["start"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_start_with_valid_chapter_quit_immediately(self):
        """Test start command with valid chapter, quit immediately."""
        # Simulate user pressing 'q' immediately
        result = runner.invoke(app, ["start", "1"], input="q\n")
        assert result.exit_code == 0
        # Should show chapter content before quitting
        assert "Chapter 1" in result.stdout or "Kubernetes" in result.stdout

    def test_start_with_reset_flag(self):
        """Test that --reset flag is accepted."""
        result = runner.invoke(app, ["start", "1", "--reset"], input="q\n")
        assert result.exit_code == 0


class TestListCommand:
    """Tests for the list command."""

    def test_list_command_exists(self):
        """Test that list command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "list" in result.stdout

    def test_list_runs_successfully(self):
        """Test that list command runs without error."""
        result = runner.invoke(app, ["list"], input="q\n")
        assert result.exit_code == 0
        assert "Browse Chapters" in result.stdout


class TestResetCommand:
    """Tests for the reset command."""

    def test_reset_command_exists(self):
        """Test that reset command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "reset" in result.stdout

    def test_reset_runs_successfully(self):
        """Test that reset command runs without error."""
        result = runner.invoke(app, ["reset", "1", "-y"])
        assert result.exit_code == 0
        assert "Progress reset" in result.stdout

    def test_reset_all_chapters(self):
        """Test that reset --all works."""
        result = runner.invoke(app, ["reset", "--all", "-y"])
        assert result.exit_code == 0
        assert "All course progress" in result.stdout

    def test_reset_with_confirmation_cancelled(self):
        """Test that reset can be cancelled."""
        result = runner.invoke(app, ["reset", "1"], input="n\n")
        assert result.exit_code == 0
        assert "Reset cancelled" in result.stdout


class TestGetUserInput:
    """Tests for get_user_input function."""

    def test_returns_first_character(self):
        """Test that first character is returned."""
        with patch("builtins.input", return_value="next"):
            result = get_user_input()
            assert result == "n"

    def test_returns_empty_for_empty_input(self):
        """Test that empty string returns empty."""
        with patch("builtins.input", return_value=""):
            result = get_user_input()
            assert result == ""

    def test_handles_keyboard_interrupt(self):
        """Test that KeyboardInterrupt returns 'q'."""
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = get_user_input()
            assert result == "q"

    def test_handles_eof(self):
        """Test that EOFError returns 'q'."""
        with patch("builtins.input", side_effect=EOFError):
            result = get_user_input()
            assert result == "q"

    def test_lowercases_input(self):
        """Test that input is lowercased."""
        with patch("builtins.input", return_value="N"):
            result = get_user_input()
            assert result == "n"


class TestInteractiveConcepts:
    """Tests for interactive_concepts function."""

    def test_quits_on_q(self):
        """Test that 'q' quits the loop."""
        concepts = [{"title": "Test", "content": "Content"}]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        with patch("actionspath.cli.get_user_input", return_value="q"):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                # Should not raise and should exit after one iteration
                interactive_concepts(1, concepts, chapter_meta)

    def test_navigates_forward_on_n(self):
        """Test that 'n' moves to next concept."""
        concepts = [
            {"title": "Concept 1", "content": "Content 1"},
            {"title": "Concept 2", "content": "Content 2"},
        ]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # First 'n' moves forward, then 'q' quits
        inputs = iter(["n", "q"])

        with patch("actionspath.cli.get_user_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.save_progress") as mock_save:
                    mock_console.return_value = MagicMock()
                    interactive_concepts(1, concepts, chapter_meta)
                    # Should have saved progress when moving to concept 2
                    mock_save.assert_called()

    def test_navigates_backward_on_p(self):
        """Test that 'p' moves to previous concept."""
        concepts = [
            {"title": "Concept 1", "content": "Content 1"},
            {"title": "Concept 2", "content": "Content 2"},
        ]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # 'n' moves forward, 'p' moves back, 'q' quits
        inputs = iter(["n", "p", "q"])

        with patch("actionspath.cli.get_user_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.save_progress") as mock_save:
                    mock_console.return_value = MagicMock()
                    interactive_concepts(1, concepts, chapter_meta)

    def test_returns_quit_on_quit(self):
        """Test that quitting returns 'quit'."""
        concepts = [{"title": "Test", "content": "Content"}]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        with patch("actionspath.cli.get_user_input", return_value="q"):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                result = interactive_concepts(1, concepts, chapter_meta)
                assert result == "quit"

    def test_returns_completed_on_completion(self):
        """Test that completing chapter returns 'completed'."""
        concepts = [{"title": "Test", "content": "Content"}]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # Press 'n' at the last (and only) concept
        with patch("actionspath.cli.get_user_input", return_value="n"):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.clear_progress"):
                    mock_console.return_value = MagicMock()
                    result = interactive_concepts(1, concepts, chapter_meta)
                    assert result == "completed"

    def test_returns_completed_when_no_next_chapter(self):
        """Test that completing last chapter returns 'completed'."""
        concepts = [{"title": "Test", "content": "Content"}]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        with patch("actionspath.cli.get_user_input", return_value="n"):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.clear_progress"):
                    mock_console.return_value = MagicMock()
                    result = interactive_concepts(1, concepts, chapter_meta)
                    assert result == "completed"

    def test_returns_previous_on_p_at_start(self):
        """Test that pressing 'p' at first concept returns 'previous'."""
        concepts = [{"title": "Test", "content": "Content"}]
        chapter_meta = {"number": 2, "title": "Test Chapter"}

        with patch("actionspath.cli.get_user_input", return_value="p"):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.get_previous_chapter", return_value=1):
                    mock_console.return_value = MagicMock()
                    result = interactive_concepts(2, concepts, chapter_meta)
                    assert result == "previous"  # Indicates go to previous chapter

    def test_start_from_last_parameter(self):
        """Test that start_from_last starts from the last concept."""
        concepts = [
            {"title": "Concept 1", "content": "Content 1"},
            {"title": "Concept 2", "content": "Content 2"},
        ]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # Should start at concept 2 (index 1), 'p' goes to concept 1, 'q' quits
        inputs = iter(["p", "q"])

        with patch("actionspath.cli.get_user_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                with patch("actionspath.cli.save_progress") as mock_save:
                    mock_console.return_value = MagicMock()
                    interactive_concepts(1, concepts, chapter_meta, start_from_last=True)
                    # Should save progress at index 0 when moving back
                    mock_save.assert_called()


class TestGetNextChapter:
    """Tests for get_next_chapter function."""

    def test_returns_next_chapter(self):
        """Test returns the next chapter number."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_next_chapter(1)
            assert result == 2

    def test_returns_none_at_last_chapter(self):
        """Test returns None when at last chapter."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_next_chapter(3)
            assert result is None

    def test_returns_none_for_unknown_chapter(self):
        """Test returns None for chapter not in list."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_next_chapter(99)
            assert result is None

    def test_handles_non_sequential_chapters(self):
        """Test works with non-sequential chapter numbers."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 5, 10]):
            result = get_next_chapter(5)
            assert result == 10


class TestGetPreviousChapter:
    """Tests for get_previous_chapter function."""

    def test_returns_previous_chapter(self):
        """Test returns the previous chapter number."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_previous_chapter(2)
            assert result == 1

    def test_returns_none_at_first_chapter(self):
        """Test returns None when at first chapter."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_previous_chapter(1)
            assert result is None

    def test_returns_none_for_unknown_chapter(self):
        """Test returns None for chapter not in list."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 2, 3]):
            result = get_previous_chapter(99)
            assert result is None

    def test_handles_non_sequential_chapters(self):
        """Test works with non-sequential chapter numbers."""
        with patch("actionspath.cli.get_available_chapters", return_value=[1, 5, 10]):
            result = get_previous_chapter(10)
            assert result == 5


class TestListChaptersCommand:
    """Tests for the enhanced list command."""

    def test_list_shows_available_chapters(self):
        """Test list shows available chapters."""
        result = runner.invoke(app, ["list"], input="q\n")
        assert result.exit_code == 0
        assert "Browse Chapters" in result.stdout

    def test_list_allows_quit(self):
        """Test list allows quitting with 'q'."""
        result = runner.invoke(app, ["list"], input="q\n")
        assert result.exit_code == 0

    def test_list_allows_empty_input_to_quit(self):
        """Test list allows empty input to quit."""
        result = runner.invoke(app, ["list"], input="\n")
        assert result.exit_code == 0


class TestDoctorCommand:
    """Tests for the doctor command."""

    def test_doctor_command_exists(self):
        """Test that doctor command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "doctor" in result.stdout

    def test_doctor_runs_and_shows_tools(self):
        """Test doctor runs and shows CI/CD diagnostic tools."""
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Git VCS" in result.stdout
        assert "GitHub CLI" in result.stdout
        assert "actionlint" in result.stdout

    def test_doctor_shows_ready_or_missing(self):
        """Test doctor shows readiness status."""
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "ActionsPath CI/CD Environment Doctor" in result.stdout


class TestPracticeCommand:
    """Tests for the practice command."""

    def test_practice_command_exists(self):
        """Test that practice command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "practice" in result.stdout

    def test_practice_requires_chapter_argument(self):
        """Test that practice command requires chapter argument."""
        result = runner.invoke(app, ["practice"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_practice_shows_theory_mode_skip(self):
        """Test practice shows theory mode skip message when hands-on mode is disabled."""
        with patch("actionspath.cli.get_hands_on_mode", return_value=False):
            result = runner.invoke(app, ["practice", "1"], input="\n\nq\n")
            assert "theory mode" in result.stdout.lower() or "skipping" in result.stdout.lower()

    def test_practice_fails_for_nonexistent_chapter(self):
        """Test practice fails for nonexistent chapter."""
        with patch("actionspath.cli.check_environment_interactive", return_value=True):
            result = runner.invoke(app, ["practice", "999"])
            assert result.exit_code != 0
            assert "not found" in result.stdout.lower()

    def test_practice_skips_to_complete_when_no_practices(self):
        """Test practice skips to chapter complete when no practices defined."""
        with patch("actionspath.cli.load_chapter") as mock_load:
            mock_load.return_value = {
                "chapter": {"number": 1, "title": "Test"},
                "concepts": [{"title": "Test", "content": "Test"}],
            }
            result = runner.invoke(app, ["practice", "1"], input="q\n")
            assert result.exit_code == 0
            assert "complete" in result.stdout.lower()

    def test_practice_with_valid_chapter_quit_immediately(self):
        """Test practice with valid chapter, quit immediately."""
        with patch("actionspath.cli.check_environment_interactive", return_value=True):
            with patch("actionspath.cli.load_chapter") as mock_load:
                mock_load.return_value = {
                    "chapter": {"number": 1, "title": "Test Chapter"},
                    "concepts": [{"title": "Test", "content": "Test"}],
                    "command_practice": [
                        {
                            "id": "cmd-01",
                            "title": "Test Practice",
                            "instructions": "Run a command",
                            "command_hint": "echo test",
                            "validation": {
                                "type": "command_output",
                                "command": "echo test",
                                "expected_contains": "test",
                            },
                            "points": 10,
                        }
                    ],
                }
                result = runner.invoke(app, ["practice", "1"], input="q\n")
                assert result.exit_code == 0


class TestInteractivePractice:
    """Tests for interactive_practice function."""

    def test_quits_on_q(self):
        """Test that 'q' quits the practice loop."""
        from actionspath.cli import interactive_practice

        practices = [{
            "title": "Test",
            "instructions": "Test",
            "command_hint": "echo test",
            "validation": {"type": "command_output", "command": "echo test"},
            "points": 10,
        }]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        with patch("actionspath.cli.get_command_input", return_value="q"):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                result = interactive_practice(1, practices, chapter_meta)
                assert result == "quit"

    def test_skip_advances_to_next(self):
        """Test that 's' advances to next practice."""
        from actionspath.cli import interactive_practice

        practices = [
            {"title": "Practice 1", "instructions": "Test", "command_hint": "echo 1", "points": 10},
            {"title": "Practice 2", "instructions": "Test", "command_hint": "echo 2", "points": 10},
        ]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # Skip first, then quit
        inputs = iter(["s", "q"])

        with patch("actionspath.cli.get_command_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                result = interactive_practice(1, practices, chapter_meta)
                assert result == "quit"

    def test_typing_command_executes_it(self):
        """Test that typing a command executes it and validates output."""
        from actionspath.cli import interactive_practice

        practices = [{
            "title": "Test",
            "instructions": "Test",
            "command_hint": "echo test",
            "validation": {"type": "command_output", "command": "echo test", "expected_contains": "hello"},
            "points": 10,
        }]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # Type a command, then quit
        inputs = iter(["echo hello", "q"])
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "hello world"
        mock_result.message = "OK"

        with patch("actionspath.cli.get_command_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.execute_command", return_value=mock_result):
                with patch("actionspath.cli.get_console") as mock_console:
                    mock_console.return_value = MagicMock()
                    with patch("builtins.input", return_value=""):
                        result = interactive_practice(1, practices, chapter_meta)
                        # Returns "completed" because output contains "hello"
                        assert result == "completed"

    def test_previous_goes_back(self):
        """Test that 'p' goes to previous practice."""
        from actionspath.cli import interactive_practice

        practices = [
            {"title": "Practice 1", "instructions": "Test", "command_hint": "echo 1", "points": 10},
            {"title": "Practice 2", "instructions": "Test", "command_hint": "echo 2", "points": 10},
        ]
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # Skip to second, go back, then quit
        inputs = iter(["s", "p", "q"])

        with patch("actionspath.cli.get_command_input", side_effect=lambda: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                result = interactive_practice(1, practices, chapter_meta)
                assert result == "quit"


class TestInteractiveQuiz:
    """Tests for interactive_quiz CLI flow."""

    def test_quiz_option_b_is_not_treated_as_quit(self):
        """Test that answer 'b' (Option B) is evaluated as answer, not quit."""
        from actionspath.cli import interactive_quiz

        quiz_data = {
            "questions": [
                {
                    "type": "true_false",
                    "question": "By default, multiple jobs run sequentially.",
                    "correct": False,
                    "points": 10,
                }
            ],
            "passing_score": 10,
        }
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        # User enters 'b' for False (correct), then Enter to advance, then Enter at summary
        inputs = iter(["b", "", ""])

        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                with patch("actionspath.cli.clear_screen"):
                    with patch("actionspath.cli.save_quiz_state"):
                        with patch("actionspath.cli.clear_quiz_state"):
                            result = interactive_quiz(1, quiz_data, chapter_meta)
                            assert result == "completed"

    def test_quiz_quits_on_q(self):
        """Test that answer 'q' saves state and returns quit."""
        from actionspath.cli import interactive_quiz

        quiz_data = {
            "questions": [
                {
                    "type": "true_false",
                    "question": "By default, multiple jobs run sequentially.",
                    "correct": False,
                    "points": 10,
                }
            ],
            "passing_score": 10,
        }
        chapter_meta = {"number": 1, "title": "Test Chapter"}

        with patch("builtins.input", return_value="q"):
            with patch("actionspath.cli.get_console") as mock_console:
                mock_console.return_value = MagicMock()
                with patch("actionspath.cli.clear_screen"):
                    with patch("actionspath.cli.save_quiz_state") as mock_save:
                        result = interactive_quiz(1, quiz_data, chapter_meta)
                        assert result == "quit"
                        assert mock_save.called
