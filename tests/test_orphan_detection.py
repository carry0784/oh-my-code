"""
K-Dexter Orphan Detection Tests

Sprint Contract: CARD-2026-0330-ORPHAN (Level C)

Tests the cross-tier lineage verification for orphan proposal detection:
  AXIS 1: Orphan Detection Accuracy (valid lineage vs broken lineage)
  AXIS 2: Cross-Ledger Verification (Exec→Agent, Submit→Exec)
  AXIS 3: Empty/None Ledger Handling (fail-safe skip)
  AXIS 4: Read-Only Guarantee (no write methods in service source)
  AXIS 5: 4-Tier Board Integration (cross_tier_orphan_count in dashboard)
  AXIS 6: Edge Cases (sentinel IDs, duplicates, terminal orphans, empty proposals)

Run: pytest tests/test_orphan_detection.py -v
"""
import sys
import inspect
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Stub modules
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "app.core.database",
    "app.models",
    "app.models.order",
    "app.models.position",
    "app.models.signal",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges",
    "app.exchanges.factory",
    "app.exchanges.base",
    "app.exchanges.binance",
    "app.services.order_service",
    "app.services.position_service",
    "app.services.signal_service",
    "ccxt",
    "ccxt.async_support",
    "redis",
    "celery",
    "asyncpg",
    "kdexter",
    "kdexter.ledger",
    "kdexter.ledger.forbidden_ledger",
    "kdexter.audit",
    "kdexter.audit.evidence_store",
    "kdexter.state_machine",
    "kdexter.state_machine.security_state",
]

for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# -- Helpers ---------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _past_iso(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _make_action_proposals(*ids: str) -> list[dict]:
    """Create minimal ActionLedger-style proposal dicts."""
    return [{"proposal_id": pid, "status": "RECEIPTED", "created_at": _now_iso()} for pid in ids]


def _make_exec_proposals(pairs: list[tuple[str, str]]) -> list[dict]:
    """Create ExecutionLedger-style proposals: (proposal_id, agent_proposal_id)."""
    return [
        {"proposal_id": pid, "agent_proposal_id": apid, "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        for pid, apid in pairs
    ]


def _make_submit_proposals(pairs: list[tuple[str, str]]) -> list[dict]:
    """Create SubmitLedger-style proposals: (proposal_id, execution_proposal_id)."""
    return [
        {"proposal_id": pid, "execution_proposal_id": epid, "status": "SUBMIT_RECEIPTED", "created_at": _now_iso()}
        for pid, epid in pairs
    ]


class _FakeLedger:
    """Minimal ledger mock that returns proposals from get_proposals()."""
    def __init__(self, proposals: list[dict]):
        self._proposals_data = proposals

    def get_proposals(self) -> list[dict]:
        return self._proposals_data


# -- Import service --------------------------------------------------------- #

from app.services.orphan_detection_service import detect_orphans, OrphanReport, OrphanEntry, _SENTINEL_IDS


# =========================================================================== #
# AXIS 1: Orphan Detection Accuracy                                           #
# =========================================================================== #

class TestOrphanDetectionAccuracy:
    """Valid lineage = not orphan, broken lineage = orphan."""

    def test_valid_lineage_no_orphans(self):
        """All parent IDs exist → zero orphans."""
        action = _FakeLedger(_make_action_proposals("AP-1", "AP-2"))
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1"), ("EP-2", "AP-2")]))
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-1"), ("SP-2", "EP-2")]))

        report = detect_orphans(action, execution, submit)
        assert report.total_cross_tier_orphan_count == 0
        assert report.execution_orphan_count == 0
        assert report.submit_orphan_count == 0

    def test_broken_execution_lineage_detected(self):
        """Execution proposal references non-existent agent proposal."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1"), ("EP-2", "AP-MISSING")]))

        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1
        assert report.execution_orphans[0]["missing_parent_id"] == "AP-MISSING"

    def test_broken_submit_lineage_detected(self):
        """Submit proposal references non-existent execution proposal."""
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1")]))
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-1"), ("SP-2", "EP-GONE")]))

        report = detect_orphans(None, execution, submit)
        assert report.submit_orphan_count == 1
        assert report.submit_orphans[0]["missing_parent_id"] == "EP-GONE"

    def test_mixed_valid_and_orphan(self):
        """Mix of valid and orphan proposals across both tiers."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1"), ("EP-2", "AP-X")]))
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-1"), ("SP-2", "EP-Y")]))

        report = detect_orphans(action, execution, submit)
        assert report.execution_orphan_count == 1
        assert report.submit_orphan_count == 1
        assert report.total_cross_tier_orphan_count == 2


# =========================================================================== #
# AXIS 2: Cross-Ledger Verification                                           #
# =========================================================================== #

class TestCrossLedgerVerification:
    """Exec→Agent and Submit→Exec verification paths."""

    def test_exec_checks_against_action_ids(self):
        """Execution orphan detection uses ActionLedger proposal IDs."""
        action = _FakeLedger(_make_action_proposals("AP-100", "AP-200"))
        execution = _FakeLedger(_make_exec_proposals([
            ("EP-1", "AP-100"),
            ("EP-2", "AP-200"),
            ("EP-3", "AP-999"),
        ]))

        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1
        orphan_ids = [o["proposal_id"] for o in report.execution_orphans]
        assert "EP-3" in orphan_ids

    def test_submit_checks_against_execution_ids(self):
        """Submit orphan detection uses ExecutionLedger proposal IDs."""
        execution = _FakeLedger(_make_exec_proposals([("EP-A", "AP-1")]))
        submit = _FakeLedger(_make_submit_proposals([
            ("SP-1", "EP-A"),
            ("SP-2", "EP-B"),
            ("SP-3", "EP-C"),
        ]))

        report = detect_orphans(None, execution, submit)
        assert report.submit_orphan_count == 2
        orphan_ids = [o["proposal_id"] for o in report.submit_orphans]
        assert "SP-2" in orphan_ids
        assert "SP-3" in orphan_ids

    def test_tiers_checked_reflects_actual_checks(self):
        """tiers_checked list records which tiers were actually verified."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1")]))
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-1")]))

        report = detect_orphans(action, execution, submit)
        assert "execution" in report.tiers_checked
        assert "submit" in report.tiers_checked

    def test_orphan_entry_fields_complete(self):
        """OrphanEntry carries all required identification fields."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([("EP-orphan", "AP-GONE")]))

        report = detect_orphans(action, execution, None)
        assert len(report.execution_orphans) == 1
        entry = report.execution_orphans[0]
        assert entry["proposal_id"] == "EP-orphan"
        assert entry["tier"] == "execution"
        assert entry["missing_parent_type"] == "agent_proposal_id"
        assert entry["missing_parent_id"] == "AP-GONE"
        assert "current_status" in entry
        assert "created_at" in entry


# =========================================================================== #
# AXIS 3: Empty/None Ledger Handling                                          #
# =========================================================================== #

class TestEmptyNoneLedgerHandling:
    """Fail-safe: missing or None ledgers skip verification."""

    def test_all_none_returns_empty_report(self):
        """All ledgers None → empty report, no crash."""
        report = detect_orphans(None, None, None)
        assert report.total_cross_tier_orphan_count == 0
        assert report.tiers_checked == []

    def test_action_none_skips_execution_check(self):
        """No ActionLedger → cannot verify execution lineage → skip."""
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-MISSING")]))
        report = detect_orphans(None, execution, None)
        assert "execution" not in report.tiers_checked
        assert report.execution_orphan_count == 0

    def test_execution_none_skips_submit_check(self):
        """No ExecutionLedger → cannot verify submit lineage → skip."""
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-MISSING")]))
        report = detect_orphans(None, None, submit)
        assert "submit" not in report.tiers_checked
        assert report.submit_orphan_count == 0

    def test_empty_proposals_returns_zero_orphans(self):
        """Ledgers with zero proposals → zero orphans."""
        action = _FakeLedger([])
        execution = _FakeLedger([])
        submit = _FakeLedger([])

        report = detect_orphans(action, execution, submit)
        assert report.total_cross_tier_orphan_count == 0


# =========================================================================== #
# AXIS 4: Read-Only Guarantee                                                 #
# =========================================================================== #

class TestReadOnlyGuarantee:
    """Orphan detection service must be strictly read-only."""

    def test_source_has_no_propose_and_guard(self):
        """Service source must not call .propose_and_guard("""
        import app.services.orphan_detection_service as mod
        source = inspect.getsource(mod)
        assert ".propose_and_guard(" not in source

    def test_source_has_no_record_receipt(self):
        """Service source must not call .record_receipt("""
        import app.services.orphan_detection_service as mod
        source = inspect.getsource(mod)
        assert ".record_receipt(" not in source

    def test_source_has_no_transition_to(self):
        """Service source must not call .transition_to("""
        import app.services.orphan_detection_service as mod
        source = inspect.getsource(mod)
        assert ".transition_to(" not in source

    def test_source_has_no_underscore_proposals_access(self):
        """Service source must not directly access ._proposals"""
        import app.services.orphan_detection_service as mod
        source = inspect.getsource(mod)
        assert "._proposals" not in source


# =========================================================================== #
# AXIS 5: 4-Tier Board Integration                                            #
# =========================================================================== #

class TestFourTierBoardIntegration:
    """Orphan detection results appear in the dashboard board."""

    def test_board_response_has_cross_tier_orphan_fields(self):
        """FourTierBoardResponse schema includes cross-tier orphan fields."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "cross_tier_orphan_count" in fields

    def test_board_service_populates_orphan_count(self):
        """build_four_tier_board populates cross_tier_orphan_count from detect_orphans."""
        from app.services.four_tier_board_service import build_four_tier_board

        # Mock ledgers with get_board() and get_proposals()
        al = MagicMock()
        al.get_board.return_value = {
            "total": 1, "receipted_count": 1, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 0,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }
        al.get_proposals.return_value = [{"proposal_id": "AP-1", "status": "RECEIPTED"}]

        el = MagicMock()
        el.get_board.return_value = {
            "total": 1, "receipted_count": 1, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 0,
            "stale_threshold_seconds": 300.0, "guard_reason_top": [],
        }
        el.get_proposals.return_value = [
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-MISSING", "status": "EXEC_RECEIPTED"}
        ]

        sl = MagicMock()
        sl.get_board.return_value = {
            "total": 0, "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 0,
            "stale_threshold_seconds": 180.0, "guard_reason_top": [],
        }
        sl.get_proposals.return_value = []

        board = build_four_tier_board(al, el, sl)
        assert hasattr(board, "cross_tier_orphan_count")
        assert isinstance(board.cross_tier_orphan_count, int)
        # EP-1 references AP-MISSING which is not in action IDs → 1 orphan
        assert board.cross_tier_orphan_count >= 1

    def test_board_schema_orphan_detail_field(self):
        """FourTierBoardResponse has cross_tier_orphan_detail list."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "cross_tier_orphan_detail" in fields


# =========================================================================== #
# AXIS 6: Edge Cases                                                          #
# =========================================================================== #

class TestEdgeCases:
    """Sentinel IDs, duplicates, terminal orphans, boundary conditions."""

    def test_sentinel_none_treated_as_orphan(self):
        """agent_proposal_id=None → orphan."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": None, "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1

    def test_sentinel_empty_string_treated_as_orphan(self):
        """agent_proposal_id="" → orphan."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "", "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1

    def test_sentinel_NONE_string_treated_as_orphan(self):
        """agent_proposal_id="NONE" → orphan."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "NONE", "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1

    def test_sentinel_UNKNOWN_string_treated_as_orphan(self):
        """agent_proposal_id="UNKNOWN" → orphan."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "UNKNOWN", "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 1

    def test_duplicate_parent_ids_no_false_positive(self):
        """Multiple exec proposals referencing same valid parent → no orphans."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([
            ("EP-1", "AP-1"),
            ("EP-2", "AP-1"),
            ("EP-3", "AP-1"),
        ]))
        report = detect_orphans(action, execution, None)
        assert report.execution_orphan_count == 0

    def test_terminal_status_orphan_still_detected(self):
        """Orphan detection checks lineage regardless of status (even terminal)."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger([
            {"proposal_id": "EP-done", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        report = detect_orphans(action, execution, None)
        # Even terminal proposals with broken lineage should be detected
        assert report.execution_orphan_count == 1

    def test_orphan_report_to_dict(self):
        """OrphanReport.to_dict() returns serializable dictionary."""
        report = OrphanReport()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "execution_orphan_count" in d
        assert "submit_orphan_count" in d
        assert "total_cross_tier_orphan_count" in d

    def test_orphan_entry_to_dict(self):
        """OrphanEntry.to_dict() returns serializable dictionary."""
        entry = OrphanEntry(
            proposal_id="EP-1",
            tier="execution",
            missing_parent_type="agent_proposal_id",
            missing_parent_id="AP-GONE",
            current_status="EXEC_GUARDED",
        )
        d = entry.to_dict()
        assert d["proposal_id"] == "EP-1"
        assert d["tier"] == "execution"

    def test_sentinel_ids_frozenset_contents(self):
        """_SENTINEL_IDS contains expected values."""
        assert "" in _SENTINEL_IDS
        assert "NONE" in _SENTINEL_IDS
        assert "UNKNOWN" in _SENTINEL_IDS
        assert None in _SENTINEL_IDS

    def test_partial_observation_when_action_none(self):
        """partial_observation=True when action_ledger is None (skip)."""
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1")]))
        report = detect_orphans(None, execution, None)
        assert report.partial_observation is True
        assert "action" in report.skipped_tiers

    def test_partial_observation_false_when_all_checked(self):
        """partial_observation=False when all tiers available."""
        action = _FakeLedger(_make_action_proposals("AP-1"))
        execution = _FakeLedger(_make_exec_proposals([("EP-1", "AP-1")]))
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-1")]))
        report = detect_orphans(action, execution, submit)
        assert report.partial_observation is False

    def test_warnings_populated_on_skip(self):
        """warnings list populated when a tier is skipped."""
        submit = _FakeLedger(_make_submit_proposals([("SP-1", "EP-MISSING")]))
        report = detect_orphans(None, None, submit)
        assert len(report.warnings) > 0
        assert report.partial_observation is True

    def test_skipped_tiers_tracks_all_missing(self):
        """skipped_tiers records all tiers that couldn't be checked."""
        report = detect_orphans(None, None, None)
        assert "action" in report.skipped_tiers

    def test_report_to_dict_includes_new_fields(self):
        """to_dict includes partial_observation, skipped_tiers, warnings."""
        report = detect_orphans(None, None, None)
        d = report.to_dict()
        assert "partial_observation" in d
        assert "skipped_tiers" in d
        assert "warnings" in d
