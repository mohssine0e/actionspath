"""Acceptance Gate test suite: verifies high-fidelity grading across quizzes, scenarios, and labs."""

import pytest
from pathlib import Path
import yaml

from actionspath.quiz.engine import QuizEngine
from actionspath.cicd.labs import load_boss_lab, validate_boss_lab
from actionspath.cicd.validator import validate_scenario_assertions, _load_yaml


class TestAcceptanceGateQuizzes:
    """Every quiz across all 30 chapters must validate correct answers properly."""

    def test_all_chapter_quizzes_answerable(self):
        """Every multiple choice question in chapters 1-30 must be answerable via letter (A/B/C/D)."""
        chapters_dir = Path("actionspath/data/chapters")
        total_mc_tested = 0

        for cf in sorted(chapters_dir.glob("*.yaml")):
            with open(cf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            quiz_data = data.get("quiz", {})
            questions = quiz_data.get("questions", [])
            engine = QuizEngine(chapter=data["chapter"]["number"], quiz_data=quiz_data)

            for q_idx, q in enumerate(questions):
                if q.get("type") == "multiple_choice":
                    total_mc_tested += 1
                    options = q.get("options", [])
                    correct_val = q.get("correct")

                    # Find correct letter
                    correct_letter = None
                    for opt_idx, opt in enumerate(options):
                        if str(opt).strip().lower() == str(correct_val).strip().lower():
                            correct_letter = chr(ord("A") + opt_idx)
                            break
                        if isinstance(correct_val, int) and opt_idx == correct_val:
                            correct_letter = chr(ord("A") + opt_idx)
                            break

                    assert correct_letter is not None, (
                        f"{cf.name} question #{q_idx}: could not resolve correct letter for '{correct_val}' in {options}"
                    )

                    # Test answering with the letter
                    is_correct = engine._validate_multiple_choice(q, correct_letter)
                    assert is_correct, (
                        f"{cf.name} question #{q_idx}: answering '{correct_letter}' was rejected! (correct was {correct_val!r})"
                    )

                    # Also test that wrong letter is rejected
                    wrong_letter = "B" if correct_letter == "A" else "A"
                    is_wrong = engine._validate_multiple_choice(q, wrong_letter)
                    assert not is_wrong, (
                        f"{cf.name} question #{q_idx}: answering wrong letter '{wrong_letter}' was accepted!"
                    )

        assert total_mc_tested >= 60, f"Expected at least 60 multiple choice questions, tested {total_mc_tested}"


class TestAcceptanceGateScenarios:
    """Chapter scenario assertions must accurately match manifests."""

    def test_chapter_1_scenario_2_lint_runner_fix(self):
        """Chapter 1 scenario 'fix-missing-runner' must accept adding runs-on to the lint job."""
        with open("actionspath/data/chapters/01-workflow-anatomy.yaml", "r") as f:
            data = yaml.safe_load(f)

        scenario = next(s for s in data["scenarios"] if s["id"] == "fix-missing-runner")
        assertions = scenario["solution_validation"]["assertions"]

        # Solved manifest with runs-on added to the lint job
        solved_manifest = """name: Lint and Check
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Linting code..."
"""
        res = validate_scenario_assertions(solved_manifest, assertions)
        assert res.success, f"Scenario fix failed validation: {res.message}"

        # Broken starter must fail
        broken_manifest = scenario["manifest"]
        broken_res = validate_scenario_assertions(broken_manifest, assertions)
        assert not broken_res.success, "Broken starter unexpectedly passed!"


class TestAcceptanceGateBossLabs:
    """Boss Labs must reject starters, reject plausible wrong solutions, and accept correct solutions."""

    def test_boss_lab_4_security_audit(self, tmp_path):
        """Lab 4 must reject keeping static AWS secrets and accept the full zero-trust fix."""
        lab = load_boss_lab(4)
        assert lab is not None

        # 1. Unmodified starter must fail
        for rel_path, content in lab.initial_files.items():
            f = tmp_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")

        starter_res = validate_boss_lab(tmp_path, lab)
        assert not starter_res.success

        # 2. Plausible wrong solution: fixed pwnrequest and script injection, but kept AWS secret
        wrong_workflow = """name: Production Release
on:
  pull_request_target:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Log Issue Title
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: echo "$PR_TITLE"

      - name: Configure Cloud
        env:
          AWS_KEY: ${{ secrets.AWS_ACCESS_KEY_ID }}
        run: ./deploy-to-aws.sh --key "$AWS_KEY"
"""
        ci_file = tmp_path / ".github/workflows/ci.yml"
        ci_file.write_text(wrong_workflow, encoding="utf-8")

        wrong_res = validate_boss_lab(tmp_path, lab)
        assert not wrong_res.success, "Wrong solution keeping static AWS key unexpectedly passed!"

        # 3. Correct solution: static secret removed
        correct_workflow = """name: Production Release
on:
  pull_request_target:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Log Issue Title
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: echo "$PR_TITLE"

      - name: Configure Cloud
        run: ./deploy-to-aws.sh
"""
        ci_file.write_text(correct_workflow, encoding="utf-8")
        correct_res = validate_boss_lab(tmp_path, lab)
        assert correct_res.success, f"Correct solution failed: {[o.message for o in correct_res.objectives if not o.passed]}"

    def test_boss_lab_6_canary_rollback_guard(self, tmp_path):
        """Lab 6 must reject rollback step without 'if: failure()' and accept valid progressive rollout."""
        lab = load_boss_lab(6)
        assert lab is not None

        # 1. Unmodified starter must fail
        for rel_path, content in lab.initial_files.items():
            f = tmp_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")

        starter_res = validate_boss_lab(tmp_path, lab)
        assert not starter_res.success

        # 2. Plausible wrong solution: rollback step added without 'if: failure()'
        wrong_workflow = """name: Core Banking Deployment
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Shift 10% Canary Traffic
        run: ./router.sh --canary 10

      - name: Evaluate Canary Telemetry
        run: ./check-metrics.sh --max-error-rate 0.001

      - name: Rollback on Failure
        run: ./router.sh --rollback

      - name: Promote Full Rollout
        run: ./router.sh --canary 100
"""
        ci_file = tmp_path / ".github/workflows/ci.yml"
        ci_file.write_text(wrong_workflow, encoding="utf-8")

        wrong_res = validate_boss_lab(tmp_path, lab)
        assert not wrong_res.success, "Wrong solution without 'if: failure()' unexpectedly passed!"

        # 3. Correct solution: with all 6 objectives satisfied
        correct_workflow = """name: Core Banking Deployment
on:
  push:
    branches: [main]

concurrency:
  group: production-deployment
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Shift 10% Canary Traffic
        run: ./router.sh --canary 10

      - name: Evaluate Canary Telemetry
        run: ./check-metrics.sh --max-error-rate 0.001

      - name: Rollback on Failure
        if: failure()
        run: ./router.sh --rollback

      - name: Promote Full Rollout
        run: ./router.sh --canary 100

      - name: Audit Notification
        if: always()
        run: ./notify.sh
"""
        ci_file.write_text(correct_workflow, encoding="utf-8")
        correct_res = validate_boss_lab(tmp_path, lab)
        assert correct_res.success, f"Correct solution failed: {[o.message for o in correct_res.objectives if not o.passed]}"


class TestAcceptanceGatePractices:
    """Every practice command across all chapters must execute cleanly in its workspace."""

    def test_all_chapter_practice_commands_pass(self, tmp_path):
        """Verify all 31 practice commands execute in the practice workspace and pass validation."""
        from actionspath.cicd.workspace import WorkspaceManager
        from actionspath.cicd.validator import execute_command, validate_output

        wm = WorkspaceManager(base_dir=tmp_path / "workspaces")
        ws = wm.create_workspace("acceptance", "practice", init_git=True, force_clean=True)

        chapters_dir = Path("actionspath/data/chapters")
        for cf in sorted(chapters_dir.glob("*.yaml")):
            with open(cf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            practices = data.get("command_practice", [])
            for p in practices:
                cmd = p.get("command_hint")
                exp = p.get("validation", {}).get("expected_contains", "")
                result = execute_command(cmd, cwd=ws)
                assert result.success, f"{cf.name} practice {p.get('id')} failed with output: {result.output}"
                assert validate_output(result.output, exp), (
                    f"{cf.name} practice {p.get('id')} expected '{exp}' in output:\n{result.output}"
                )


class TestAcceptanceGateChapter0:
    """Acceptance tests for optional Chapter 0: Before Your First Workflow."""

    def test_chapter_0_starter_scenario_fails_for_intended_reason(self):
        """The starter manifest must fail evaluation because of illegal tab character / invalid YAML syntax."""
        from actionspath.content.loader import load_chapter
        ch0 = load_chapter(0)
        scenario = ch0["scenarios"][0]
        broken_manifest = scenario["manifest"]
        assertions = scenario["solution_validation"]["assertions"]

        # 1. Broken starter with hard tab (\t) must fail YAML syntax evaluation
        res = validate_scenario_assertions(broken_manifest, assertions)
        assert not res.success, "Broken starter scenario unexpectedly succeeded!"
        assert "invalid YAML syntax" in res.message, f"Expected YAML syntax error, got: {res.message}"

    def test_chapter_0_correct_repair_passes(self):
        """Valid YAML repair with 2-space indentation and aligned keys must pass all assertions."""
        from actionspath.content.loader import load_chapter
        ch0 = load_chapter(0)
        scenario = ch0["scenarios"][0]
        assertions = scenario["solution_validation"]["assertions"]

        solved_manifest = """name: System Configuration
version: 1.0
settings:
  enabled: true
  timeout: 30
notifications:
  - email
  - slack
"""
        res = validate_scenario_assertions(solved_manifest, assertions)
        assert res.success, f"Correct repair unexpectedly failed: {res.message}"

    def test_chapter_0_plausible_wrong_repair_fails(self):
        """Plausible wrong repair (fixing tabs but using wrong value or wrong key) must fail."""
        from actionspath.content.loader import load_chapter
        ch0 = load_chapter(0)
        scenario = ch0["scenarios"][0]
        assertions = scenario["solution_validation"]["assertions"]

        # Plausible wrong repair: valid YAML syntax, but timeout is 60 instead of 30
        wrong_manifest = """name: System Configuration
version: 1.0
settings:
  enabled: true
  timeout: 60
notifications:
  - email
  - slack
"""
        res = validate_scenario_assertions(wrong_manifest, assertions)
        assert not res.success, "Plausible wrong repair unexpectedly passed!"
        assert "timeout" in res.message or "30" in res.message

    def test_chapter_0_quiz_answers_accepted_correctly(self):
        """All 5 active recall questions in Chapter 0 must accept the correct answers and reject wrong ones."""
        from actionspath.content.loader import load_chapter
        ch0 = load_chapter(0)
        quiz_data = ch0["quiz"]
        engine = QuizEngine(chapter=0, quiz_data=quiz_data)

        questions = quiz_data["questions"]
        assert len(questions) == 5, f"Expected 5 questions, found {len(questions)}"

        # Q1: multiple_choice (exit code 0)
        q1 = questions[0]
        assert engine._validate_multiple_choice(q1, "A")
        assert not engine._validate_multiple_choice(q1, "B")

        # Q2: multiple_choice (PR definition)
        q2 = questions[1]
        assert engine._validate_multiple_choice(q2, "B")
        assert not engine._validate_multiple_choice(q2, "A")

        # Q3: true_false (git commit doesn't upload)
        q3 = questions[2]
        assert engine._validate_true_false(q3, "B")
        assert engine._validate_true_false(q3, "FALSE")
        assert not engine._validate_true_false(q3, "A")

        # Q4: multiple_choice (tab forbidden)
        q4 = questions[3]
        assert engine._validate_multiple_choice(q4, "A")
        assert not engine._validate_multiple_choice(q4, "B")

        # Q5: fill_yaml (- slack)
        q5 = questions[4]
        assert engine._validate_fill_yaml(q5, "- slack")
        assert engine._validate_fill_yaml(q5, "- SLACK")
        assert not engine._validate_fill_yaml(q5, "slack")

    def test_chapter_0_does_not_change_course_completion_percentage(self, monkeypatch, tmp_path):
        """Completing Chapter 0 must not change the course completion percentage or 30-chapter total."""
        import json
        from actionspath.utils.progress import get_course_progress

        progress_file = tmp_path / "progress.json"
        monkeypatch.setattr("actionspath.utils.progress.get_progress_file", lambda: progress_file)

        # Baseline: No progress -> 0% of 30 chapters
        progress_file.write_text(json.dumps({"chapters": {}}), encoding="utf-8")
        base_progress = get_course_progress(30)
        assert base_progress["total_chapters"] == 30
        assert base_progress["completed_chapters"] == 0
        assert base_progress["percentage"] == 0

        # State 1: Chapter 0 completed -> Must still be 0% of 30 chapters
        progress_file.write_text(
            json.dumps({"chapters": {"0": {"section": "completed"}}}),
            encoding="utf-8",
        )
        ch0_progress = get_course_progress(30)
        assert ch0_progress["completed_chapters"] == 0, "Chapter 0 must not increment completed_chapters!"
        assert ch0_progress["percentage"] == 0

        # State 2: Chapter 1 completed alone
        progress_file.write_text(
            json.dumps({"chapters": {"1": {"section": "completed"}}}),
            encoding="utf-8",
        )
        ch1_alone = get_course_progress(30)

        # State 3: Chapter 1 AND Chapter 0 completed -> Must have exact same completion percentage as Chapter 1 alone
        progress_file.write_text(
            json.dumps({"chapters": {"0": {"section": "completed"}, "1": {"section": "completed"}}}),
            encoding="utf-8",
        )
        ch1_with_ch0 = get_course_progress(30)
        assert ch1_with_ch0["completed_chapters"] == ch1_alone["completed_chapters"] == 1
        assert ch1_with_ch0["percentage"] == ch1_alone["percentage"] == 3
