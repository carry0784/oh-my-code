"""
G-MON Tests: Governance Monitor — 6-indicator automated surveillance

Tests the governance_monitor module in isolation (no app.state dependency).
"""

import sys
from unittest.mock import MagicMock

# Stub heavy modules before import
_STUB_MODULES = [
    "anthropic",
    "openai",
    "celery",
    "redis",
    "ccxt",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.orm.relationship",
    "alembic",
    "app.core.database",
    "app.models",
    "app.models.order",
    "app.models.signal",
    "app.models.position",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges.base",
    "app.exchanges.binance",
    "app.exchanges.upbit",
    "app.exchanges.bitget",
    "app.exchanges.kis",
    "app.exchanges.kiwoom",
    "app.exchanges.factory",
    "exchanges.base",
    "exchanges.binance",
    "exchanges.upbit",
    "exchanges.bitget",
    "exchanges.kis",
    "exchanges.kiwoom",
    "exchanges.factory",
]
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


from app.core.governance_monitor import (
    GovernanceMonitorReport,
    Indicator,
    IndicatorStatus,
    format_discord_report,
    format_report_text,
    _determine_overall,
)


class TestIndicatorStatus:
    def test_enum_values(self):
        assert IndicatorStatus.OK.value == "OK"
        assert IndicatorStatus.WARN.value == "WARN"
        assert IndicatorStatus.FAIL.value == "FAIL"

    def test_indicator_shape(self):
        ind = Indicator("BUDGET_CHECK", IndicatorStatus.OK, "0%", "<80%")
        assert ind.name == "BUDGET_CHECK"
        assert ind.status == IndicatorStatus.OK


class TestDetermineOverall:
    def test_all_ok(self):
        indicators = [
            Indicator("A", IndicatorStatus.OK, "", ""),
            Indicator("B", IndicatorStatus.OK, "", ""),
        ]
        assert _determine_overall(indicators) == IndicatorStatus.OK

    def test_one_warn(self):
        indicators = [
            Indicator("A", IndicatorStatus.OK, "", ""),
            Indicator("B", IndicatorStatus.WARN, "", ""),
        ]
        assert _determine_overall(indicators) == IndicatorStatus.WARN

    def test_one_fail(self):
        indicators = [
            Indicator("A", IndicatorStatus.OK, "", ""),
            Indicator("B", IndicatorStatus.FAIL, "", ""),
            Indicator("C", IndicatorStatus.WARN, "", ""),
        ]
        assert _determine_overall(indicators) == IndicatorStatus.FAIL


class TestReport:
    def test_report_to_dict(self):
        report = GovernanceMonitorReport(
            timestamp="2026-03-29T00:00:00+00:00",
            overall=IndicatorStatus.OK,
            indicators=[
                Indicator("BUDGET_CHECK", IndicatorStatus.OK, "0%", "<80%"),
            ],
            summary="G-MON: 1 OK",
        )
        d = report.to_dict()
        assert d["overall"] == "OK"
        assert len(d["indicators"]) == 1
        assert d["indicators"][0]["name"] == "BUDGET_CHECK"

    def test_format_report_text(self):
        report = GovernanceMonitorReport(
            timestamp="2026-03-29T00:00:00+00:00",
            overall=IndicatorStatus.WARN,
            indicators=[
                Indicator("BUDGET_CHECK", IndicatorStatus.OK, "10%", "<80%"),
                Indicator(
                    "PATTERN_CHECK", IndicatorStatus.WARN, "1 patterns", "<1", "Recurring failure"
                ),
            ],
            summary="G-MON: 1 OK, 1 WARN, 0 FAIL",
        )
        text = format_report_text(report)
        assert "K-Dexter Governance Monitor" in text
        assert "[OK]" in text
        assert "[!!]" in text
        assert "BUDGET_CHECK" in text
        assert "PATTERN_CHECK" in text

    def test_format_discord_report(self):
        report = GovernanceMonitorReport(
            timestamp="2026-03-29T00:00:00+00:00",
            overall=IndicatorStatus.FAIL,
            indicators=[
                Indicator("FORBIDDEN_CHECK", IndicatorStatus.FAIL, "2 blocks", "0"),
            ],
            summary="G-MON: 0 OK, 0 WARN, 1 FAIL",
        )
        payload = format_discord_report(report)
        assert "content" in payload
        assert "FAIL" in payload["content"]
        assert "FORBIDDEN_CHECK" in payload["content"]
        assert ":x:" in payload["content"]


class TestReportImmutability:
    """Monitor is read-only — report has no write methods."""

    def test_no_execute_method(self):
        assert not hasattr(GovernanceMonitorReport, "execute")
        assert not hasattr(GovernanceMonitorReport, "repair")
        assert not hasattr(GovernanceMonitorReport, "fix")

    def test_no_state_mutation(self):
        """Indicators are simple dataclasses, no side-effect methods."""
        ind = Indicator("X", IndicatorStatus.OK, "val", "thr")
        assert not hasattr(ind, "apply")
        assert not hasattr(ind, "reset")


class TestSixIndicators:
    """Verify all 6 expected indicator names are defined."""

    def test_indicator_names(self):
        expected = {
            "BUDGET_CHECK",
            "PATTERN_CHECK",
            "FORBIDDEN_CHECK",
            "TOKEN_USAGE",
            "AGENT_SUCCESS",
            "CONSTITUTION",
        }
        # Import the individual check functions
        from app.core.governance_monitor import (
            _check_budget,
            _check_pattern,
            _check_forbidden,
            _check_token_usage,
            _check_agent_success,
            _check_constitution,
        )

        # Each function should return an Indicator with the expected name
        # (they may fail in test context, but name should be correct)
        checks = [
            _check_budget,
            _check_pattern,
            _check_forbidden,
            _check_token_usage,
            _check_agent_success,
            _check_constitution,
        ]
        names = set()
        for fn in checks:
            try:
                ind = fn()
                names.add(ind.name)
            except Exception:
                pass
        assert names == expected
