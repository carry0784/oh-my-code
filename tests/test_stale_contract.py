"""
K-Dexter Stale Contract Tests

Sprint Contract: CARD-2026-0330-STALE-HELPER-CONSOLIDATION (Level B)

Tests the centralized stale contract module:
  AXIS 1: Constant Correctness (threshold defaults, band multipliers)
  AXIS 2: Band Classification (classify_stale_band boundary precision)
  AXIS 3: Terminal State Lookup (is_terminal_state per tier)
  AXIS 4: Drift Detection (contract values match cleanup_simulation_service)
  AXIS 5: Import Consolidation (cleanup_simulation imports from contract)
  AXIS 6: Safety Invariants (read-only, no mutations)

Run: pytest tests/test_stale_contract.py -v
"""
import sys
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance",
    "app.services.order_service", "app.services.position_service",
    "app.services.signal_service", "ccxt", "ccxt.async_support",
    "redis", "celery", "asyncpg",
    "kdexter", "kdexter.ledger", "kdexter.ledger.forbidden_ledger",
    "kdexter.audit", "kdexter.audit.evidence_store",
    "kdexter.state_machine", "kdexter.state_machine.security_state",
]
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# -- Imports ---------------------------------------------------------------- #

from app.core.stale_contract import (
    STALE_THRESHOLD_DEFAULTS,
    THRESHOLD_WATCH_UPPER,
    THRESHOLD_PROLONGED,
    TERMINAL_STATES_BY_TIER,
    classify_stale_band,
    is_terminal_state,
    get_stale_threshold,
)


# =========================================================================== #
# AXIS 1: Constant Correctness                                                #
# =========================================================================== #

class TestConstantCorrectness:

    def test_agent_threshold_default(self):
        assert STALE_THRESHOLD_DEFAULTS["agent"] == 600.0

    def test_execution_threshold_default(self):
        assert STALE_THRESHOLD_DEFAULTS["execution"] == 300.0

    def test_submit_threshold_default(self):
        assert STALE_THRESHOLD_DEFAULTS["submit"] == 180.0

    def test_threshold_defaults_has_three_tiers(self):
        assert set(STALE_THRESHOLD_DEFAULTS.keys()) == {"agent", "execution", "submit"}

    def test_watch_upper_value(self):
        assert THRESHOLD_WATCH_UPPER == 1.5

    def test_prolonged_value(self):
        assert THRESHOLD_PROLONGED == 3.0

    def test_watch_upper_less_than_prolonged(self):
        assert THRESHOLD_WATCH_UPPER < THRESHOLD_PROLONGED

    def test_all_thresholds_positive(self):
        assert THRESHOLD_WATCH_UPPER > 0
        assert THRESHOLD_PROLONGED > 0
        for val in STALE_THRESHOLD_DEFAULTS.values():
            assert val > 0


# =========================================================================== #
# AXIS 2: Band Classification                                                 #
# =========================================================================== #

class TestBandClassification:

    def test_below_watch_upper_is_early(self):
        assert classify_stale_band(1.0) == "early"
        assert classify_stale_band(1.49) == "early"

    def test_at_watch_upper_is_review(self):
        assert classify_stale_band(1.5) == "review"

    def test_between_watch_and_prolonged_is_review(self):
        assert classify_stale_band(2.0) == "review"
        assert classify_stale_band(2.99) == "review"

    def test_at_prolonged_is_prolonged(self):
        assert classify_stale_band(3.0) == "prolonged"

    def test_above_prolonged_is_prolonged(self):
        assert classify_stale_band(5.0) == "prolonged"
        assert classify_stale_band(10.0) == "prolonged"

    def test_just_crossed_threshold_is_early(self):
        """multiplier just above 1.0 (just crossed stale threshold) → early."""
        assert classify_stale_band(1.01) == "early"

    def test_zero_multiplier_is_early(self):
        """Edge case: 0 multiplier → early."""
        assert classify_stale_band(0.0) == "early"


# =========================================================================== #
# AXIS 3: Terminal State Lookup                                                #
# =========================================================================== #

class TestTerminalStateLookup:

    def test_agent_blocked_is_terminal(self):
        assert is_terminal_state("BLOCKED", "agent") is True

    def test_agent_receipted_is_terminal(self):
        assert is_terminal_state("RECEIPTED", "agent") is True

    def test_agent_failed_is_terminal(self):
        assert is_terminal_state("FAILED", "agent") is True

    def test_agent_guarded_is_not_terminal(self):
        assert is_terminal_state("GUARDED", "agent") is False

    def test_execution_terminal_states(self):
        assert is_terminal_state("EXEC_BLOCKED", "execution") is True
        assert is_terminal_state("EXEC_RECEIPTED", "execution") is True
        assert is_terminal_state("EXEC_FAILED", "execution") is True

    def test_execution_non_terminal(self):
        assert is_terminal_state("EXEC_GUARDED", "execution") is False

    def test_submit_terminal_states(self):
        assert is_terminal_state("SUBMIT_BLOCKED", "submit") is True
        assert is_terminal_state("SUBMIT_RECEIPTED", "submit") is True
        assert is_terminal_state("SUBMIT_FAILED", "submit") is True

    def test_submit_non_terminal(self):
        assert is_terminal_state("SUBMIT_GUARDED", "submit") is False

    def test_unknown_tier_returns_false(self):
        assert is_terminal_state("BLOCKED", "unknown_tier") is False

    def test_cross_tier_state_not_terminal(self):
        """Agent terminal state is NOT terminal in execution tier."""
        assert is_terminal_state("BLOCKED", "execution") is False
        assert is_terminal_state("EXEC_BLOCKED", "agent") is False

    def test_terminal_states_are_frozensets(self):
        for tier, states in TERMINAL_STATES_BY_TIER.items():
            assert isinstance(states, frozenset), f"{tier} should be frozenset"

    def test_each_tier_has_three_terminal_states(self):
        for tier, states in TERMINAL_STATES_BY_TIER.items():
            assert len(states) == 3, f"{tier} should have 3 terminal states"

    def test_get_stale_threshold_known_tiers(self):
        assert get_stale_threshold("agent") == 600.0
        assert get_stale_threshold("execution") == 300.0
        assert get_stale_threshold("submit") == 180.0

    def test_get_stale_threshold_unknown_tier(self):
        assert get_stale_threshold("unknown") == 600.0


# =========================================================================== #
# AXIS 4: Drift Detection                                                     #
# =========================================================================== #

class TestDriftDetection:
    """Verify stale_contract values match what cleanup_simulation_service uses."""

    def test_simulation_imports_watch_upper_from_contract(self):
        """cleanup_simulation_service.THRESHOLD_WATCH_UPPER == contract value."""
        from app.services.cleanup_simulation_service import (
            THRESHOLD_WATCH_UPPER as sim_watch,
        )
        assert sim_watch == THRESHOLD_WATCH_UPPER

    def test_simulation_imports_prolonged_from_contract(self):
        """cleanup_simulation_service.THRESHOLD_PROLONGED == contract value."""
        from app.services.cleanup_simulation_service import (
            THRESHOLD_PROLONGED as sim_prolonged,
        )
        assert sim_prolonged == THRESHOLD_PROLONGED

    def test_simulation_terminal_states_match_contract(self):
        """cleanup_simulation_service._TERMINAL_STATES_BY_TIER == contract."""
        from app.services.cleanup_simulation_service import (
            _TERMINAL_STATES_BY_TIER as sim_terminal,
        )
        assert sim_terminal == TERMINAL_STATES_BY_TIER

    def test_simulation_classify_band_matches_contract(self):
        """cleanup_simulation_service._classify_stale_band behaves identically."""
        from app.services.cleanup_simulation_service import (
            _classify_stale_band as sim_band,
        )
        test_values = [0.5, 1.0, 1.49, 1.5, 2.0, 2.99, 3.0, 5.0]
        for val in test_values:
            assert sim_band(val) == classify_stale_band(val), \
                f"Drift at multiplier={val}"

    def test_terminal_states_three_tiers_match(self):
        """Contract covers exactly the same 3 tiers."""
        assert set(TERMINAL_STATES_BY_TIER.keys()) == {"agent", "execution", "submit"}

    def test_agent_terminal_states_content(self):
        """Agent terminal states match sealed Ledger definition."""
        assert TERMINAL_STATES_BY_TIER["agent"] == frozenset(
            {"BLOCKED", "RECEIPTED", "FAILED"}
        )

    def test_execution_terminal_states_content(self):
        assert TERMINAL_STATES_BY_TIER["execution"] == frozenset(
            {"EXEC_BLOCKED", "EXEC_RECEIPTED", "EXEC_FAILED"}
        )

    def test_submit_terminal_states_content(self):
        assert TERMINAL_STATES_BY_TIER["submit"] == frozenset(
            {"SUBMIT_BLOCKED", "SUBMIT_RECEIPTED", "SUBMIT_FAILED"}
        )


# =========================================================================== #
# AXIS 5: Import Consolidation                                                 #
# =========================================================================== #

class TestImportConsolidation:
    """Verify cleanup_simulation_service imports from stale_contract (not local)."""

    def test_simulation_module_source_code_imports_contract(self):
        """The source of cleanup_simulation_service imports from stale_contract."""
        import app.services.cleanup_simulation_service as sim_mod
        source = inspect.getsource(sim_mod)
        assert "from app.core.stale_contract import" in source

    def test_no_local_classify_stale_band_definition(self):
        """cleanup_simulation_service has no locally-defined _classify_stale_band."""
        import app.services.cleanup_simulation_service as sim_mod
        source = inspect.getsource(sim_mod)
        # Should not have a 'def _classify_stale_band' — it's imported
        lines = source.split("\n")
        local_defs = [l for l in lines if l.strip().startswith("def _classify_stale_band")]
        assert len(local_defs) == 0, \
            "_classify_stale_band should be imported, not locally defined"

    def test_no_local_threshold_constants(self):
        """THRESHOLD_WATCH_UPPER and THRESHOLD_PROLONGED are not locally defined."""
        import app.services.cleanup_simulation_service as sim_mod
        source = inspect.getsource(sim_mod)
        lines = source.split("\n")
        # Should not have 'THRESHOLD_WATCH_UPPER = ' as a direct assignment
        local_assigns = [
            l for l in lines
            if l.strip().startswith("THRESHOLD_WATCH_UPPER =")
            or l.strip().startswith("THRESHOLD_PROLONGED =")
        ]
        assert len(local_assigns) == 0, \
            "Threshold constants should be imported from stale_contract"


# =========================================================================== #
# AXIS 6: Safety Invariants                                                    #
# =========================================================================== #

class TestSafetyInvariants:

    def test_terminal_states_immutable(self):
        """TERMINAL_STATES_BY_TIER values are frozensets (immutable)."""
        for tier, states in TERMINAL_STATES_BY_TIER.items():
            assert isinstance(states, frozenset)
            with pytest.raises(AttributeError):
                states.add("NEW_STATE")

    def test_contract_module_has_no_write_functions(self):
        """stale_contract has no functions that write or mutate state."""
        import app.core.stale_contract as mod
        source = inspect.getsource(mod)
        # No write/mutation keywords in function bodies
        dangerous = ["propose_and_guard", "record_receipt", "transition_to",
                      "delete", "remove", ".write(", ".update("]
        for keyword in dangerous:
            assert keyword not in source, \
                f"stale_contract should not contain '{keyword}'"

    def test_classify_stale_band_is_pure(self):
        """classify_stale_band returns consistent results (pure function)."""
        for val in [0.5, 1.5, 3.0, 5.0]:
            result1 = classify_stale_band(val)
            result2 = classify_stale_band(val)
            assert result1 == result2

    def test_is_terminal_state_is_pure(self):
        """is_terminal_state returns consistent results (pure function)."""
        assert is_terminal_state("BLOCKED", "agent") == is_terminal_state("BLOCKED", "agent")
        assert is_terminal_state("GUARDED", "agent") == is_terminal_state("GUARDED", "agent")
