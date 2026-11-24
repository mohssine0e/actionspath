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

        # 3. Correct solution: with 'if: failure()'
        correct_workflow = """name: Core Banking Deployment
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
        if: failure()
        run: ./router.sh --rollback

      - name: Promote Full Rollout
        run: ./router.sh --canary 100
"""
        ci_file.write_text(correct_workflow, encoding="utf-8")
        correct_res = validate_boss_lab(tmp_path, lab)
        assert correct_res.success, f"Correct solution failed: {[o.message for o in correct_res.objectives if not o.passed]}"
