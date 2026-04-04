"""
K-Dexter 4-State Regression Test

Verifies the evaluation system correctly grades all 4 states:
GREEN, YELLOW, RED/YELLOW, BLOCK.

Unit tests that directly call evaluate() and policy functions
without subprocess overhead.

Run: pytest tests/test_4state_regression.py -v
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


class TestGradeGreen:
    """State 1: GREEN - all pass, risk 0."""

    def test_green_grade(self):
        from scripts.evaluate_results import evaluate

        test_data = {
            "status": "PASS",
            "passed": 40,
            "failed": 0,
            "errors": 0,
            "total": 40,
            "failures": [],
        }
        val_data = {"overall": "PASS", "passed": 9, "failed": 0, "total": 9, "checks": []}
        report = evaluate(test_data, val_data)
        assert report["final_grade"] == "GREEN"
        assert report["risk_score"] == 0

    def test_green_risk_score(self):
        from scripts.evaluate_results import compute_risk_score, score_to_grade

        test_data = {
            "status": "PASS",
            "passed": 10,
            "failed": 0,
            "errors": 0,
            "total": 10,
            "failures": [],
        }
        score, breakdown = compute_risk_score(test_data, None)
        assert score == 0
        assert score_to_grade(score) == "GREEN"


class TestGradeYellow:
    """State 2: YELLOW - moderate failures, risk 3-7."""

    def test_yellow_from_test_and_error(self):
        from scripts.evaluate_results import evaluate

        test_data = {
            "status": "FAIL",
            "passed": 8,
            "failed": 1,
            "errors": 1,
            "total": 10,
            "failures": [
                {"test_id": "test_a", "detail": "fail"},
                {"test_id": "test_b", "detail": "error", "kind": "error"},
            ],
        }
        val_data = {"overall": "PASS", "passed": 9, "failed": 0, "total": 9, "checks": []}
        report = evaluate(test_data, val_data)
        assert report["final_grade"] == "YELLOW"
        assert 3 <= report["risk_score"] <= 7

    def test_yellow_risk_boundary(self):
        from scripts.evaluate_results import score_to_grade

        assert score_to_grade(3) == "YELLOW"
        assert score_to_grade(7) == "YELLOW"


class TestGradeRed:
    """State 3: RED - high risk, score 8+."""

    def test_red_from_high_failures(self):
        from scripts.evaluate_results import evaluate

        test_data = {
            "status": "FAIL",
            "passed": 0,
            "failed": 5,
            "errors": 3,
            "total": 8,
            "failures": [],
        }
        val_data = {
            "overall": "FAIL",
            "passed": 5,
            "failed": 4,
            "total": 9,
            "checks": [
                {"name": "import_check", "status": "FAIL", "detail": "import error"},
                {"name": "constitution", "status": "FAIL", "detail": "constitution mismatch"},
                {"name": "workers", "status": "FAIL", "detail": "missing"},
                {"name": "alembic", "status": "FAIL", "detail": "not found"},
            ],
        }
        report = evaluate(test_data, val_data)
        assert report["final_grade"] == "RED"
        assert report["risk_score"] >= 8

    def test_red_risk_boundary(self):
        from scripts.evaluate_results import score_to_grade

        assert score_to_grade(8) == "RED"
        assert score_to_grade(100) == "RED"


class TestGradeBlock:
    """State 4: BLOCK - governance violation forces RED."""

    def test_block_forces_red(self):
        from scripts.evaluate_results import evaluate

        test_data = {
            "status": "PASS",
            "passed": 40,
            "failed": 0,
            "errors": 0,
            "total": 40,
            "failures": [],
        }
        val_data = {"overall": "PASS", "passed": 9, "failed": 0, "total": 9, "checks": []}
        gov_data = {
            "judgment": "BLOCK",
            "total_risk_score": 3,
            "violations": [{"rule_code": "GC-01", "severity": "BLOCK"}],
            "warnings": [],
            "live_path_touches": [],
            "files_checked": ["test.py"],
        }
        report = evaluate(test_data, val_data, gov_data)
        assert report["final_grade"] == "RED"
        assert report.get("blocked") is True

    def test_block_overrides_green_tests(self):
        """Even with all tests passing, BLOCK forces RED."""
        from scripts.evaluate_results import evaluate

        test_data = {
            "status": "PASS",
            "passed": 100,
            "failed": 0,
            "errors": 0,
            "total": 100,
            "failures": [],
        }
        val_data = {"overall": "PASS", "passed": 9, "failed": 0, "total": 9, "checks": []}
        gov_data = {
            "judgment": "BLOCK",
            "total_risk_score": 5,
            "violations": [{"rule_code": "GC-03", "severity": "BLOCK"}],
            "warnings": [],
            "live_path_touches": [],
            "files_checked": ["x.py"],
        }
        report = evaluate(test_data, val_data, gov_data)
        assert report["final_grade"] == "RED"


class TestRecurrenceWeighting:
    """Recurrence multiplier verification."""

    def test_pattern_doubles_score(self):
        from scripts.evaluate_results import compute_risk_score

        test_data = {
            "failed": 1,
            "errors": 0,
            "total": 1,
            "failures": [{"test_id": "test_x"}],
        }
        patterns = [{"test_id": "test_x", "recurrence": "PATTERN"}]
        score, _ = compute_risk_score(test_data, None, failure_patterns=patterns)
        assert score == 2  # 1 * 2.0 = 2

    def test_first_keeps_base(self):
        from scripts.evaluate_results import compute_risk_score

        test_data = {
            "failed": 1,
            "errors": 0,
            "total": 1,
            "failures": [{"test_id": "test_y"}],
        }
        patterns = [{"test_id": "test_y", "recurrence": "FIRST"}]
        score, _ = compute_risk_score(test_data, None, failure_patterns=patterns)
        assert score == 1  # 1 * 1.0 = 1


class TestPolicyDecisions:
    """AutoFix policy engine decisions."""

    def test_governance_always_deny(self):
        from scripts.autofix_loop import _get_autofix_decision

        for rec in ["FIRST", "REPEAT", "PATTERN"]:
            decision, reason = _get_autofix_decision("F-GOVERNANCE", rec)
            assert decision == "DENY", f"F-GOVERNANCE {rec} should be DENY"

    def test_lint_always_allow(self):
        from scripts.autofix_loop import _get_autofix_decision

        for rec in ["FIRST", "REPEAT", "PATTERN"]:
            decision, reason = _get_autofix_decision("F-LINT", rec)
            assert decision == "ALLOW", f"F-LINT {rec} should be ALLOW"

    def test_import_pattern_is_manual(self):
        from scripts.autofix_loop import _get_autofix_decision

        decision, reason = _get_autofix_decision("F-IMPORT", "PATTERN")
        assert decision == "MANUAL"

    def test_reason_code_format(self):
        from scripts.autofix_loop import _get_autofix_decision

        decision, reason = _get_autofix_decision("F-TEST", "FIRST")
        assert "TEST" in reason
        assert "FIR" in reason
        assert "ALLOW" in reason
