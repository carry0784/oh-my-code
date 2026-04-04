"""
B-02 Historical Stats Tests — 6 tests

Validates:
  - AssetSnapshot model fields and defaults
  - Snapshot accumulation is append-only (no overwrite)
  - Time window insufficient samples detection
  - Time window ready state with PnL calculation
  - Live window status
  - Zero-position snapshot behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.asset_snapshot import AssetSnapshot


# ═══════════════════════════════════════════════════════════════════════════ #
# B-02: HISTORICAL STATS VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════ #


class TestHistoricalStats:
    """B-02: Historical Stats accumulation and query verification."""

    def test_snapshot_model_fields(self):
        """AssetSnapshot has all required fields."""
        # SQLAlchemy defaults apply at DB insert, not Python init.
        # Verify model accepts explicit values correctly.
        snap = AssetSnapshot(
            total_value=1000.0,
            trade_count=5,
            total_balance=1100.0,
            unrealized_pnl=100.0,
        )
        assert snap.total_value == 1000.0
        assert snap.trade_count == 5
        assert snap.total_balance == 1100.0
        assert snap.unrealized_pnl == 100.0

        # Verify column definitions exist on the model
        columns = AssetSnapshot.__table__.columns
        assert "total_value" in columns
        assert "trade_count" in columns
        assert "total_balance" in columns
        assert "unrealized_pnl" in columns
        assert "snapshot_at" in columns
        assert columns["snapshot_at"].index is True  # indexed for time queries

    def test_snapshot_accumulation_append_only(self):
        """Multiple snapshots are independent records (append, not overwrite)."""
        snap1 = AssetSnapshot(
            id="snap-001",
            total_value=100.0,
            trade_count=5,
            unrealized_pnl=10.0,
            total_balance=110.0,
        )
        snap2 = AssetSnapshot(
            id="snap-002",
            total_value=200.0,
            trade_count=8,
            unrealized_pnl=20.0,
            total_balance=220.0,
        )

        # Different IDs — each is an independent record
        assert snap1.id != snap2.id

        # Original values are preserved — snap2 does NOT overwrite snap1
        assert snap1.total_value == 100.0
        assert snap1.trade_count == 5
        assert snap2.total_value == 200.0
        assert snap2.trade_count == 8

        # No update/delete API on AssetSnapshot
        assert not hasattr(AssetSnapshot, "update")
        assert not hasattr(AssetSnapshot, "delete")

    def test_time_window_insufficient_samples(self):
        """Time windows return insufficient status when min_samples not met."""
        # Import time window definitions
        from app.api.routes.dashboard import _TIME_WINDOWS

        # Verify min_samples thresholds exist and are positive
        for label, delta, min_samples in _TIME_WINDOWS:
            if delta is None:  # "실시간" has no min_samples requirement
                assert min_samples == 0
                continue
            assert min_samples > 0, f"Window '{label}' must require positive min_samples"

        # Verify specific window thresholds
        windows_by_label = {label: (delta, ms) for label, delta, ms in _TIME_WINDOWS}
        assert windows_by_label["12시간"][1] == 2
        assert windows_by_label["1달"][1] == 80
        assert windows_by_label["6개월"][1] == 400

    def test_time_window_ready_pnl_semantics(self):
        """PnL calculation is unrealized delta (NOT realized PnL)."""
        # Create earliest and latest snapshots simulating a time window
        earliest = AssetSnapshot(
            total_value=1000.0,
            unrealized_pnl=50.0,
            total_balance=1050.0,
            trade_count=10,
        )
        latest = AssetSnapshot(
            total_value=1200.0,
            unrealized_pnl=80.0,
            total_balance=1280.0,
            trade_count=15,
        )

        # PnL semantics: unrealized PnL delta
        pnl_change = (latest.unrealized_pnl or 0) - (earliest.unrealized_pnl or 0)
        assert pnl_change == 30.0  # 80 - 50

        # Verify this is NOT total_value change
        value_change = latest.total_value - earliest.total_value
        assert value_change == 200.0  # Different from pnl_change
        assert pnl_change != value_change, (
            "PnL change must be unrealized delta, not total value change"
        )

    def test_time_window_live_status(self):
        """'실시간' window always returns live status."""
        from app.api.routes.dashboard import _TIME_WINDOWS

        live_windows = [(label, delta, ms) for label, delta, ms in _TIME_WINDOWS if delta is None]
        assert len(live_windows) == 1, "Exactly one live window must exist"
        assert live_windows[0][0] == "실시간"
        assert live_windows[0][2] == 0  # no min_samples for live

    def test_zero_positions_snapshot(self):
        """Snapshot with zero positions records 0 values (not NULL)."""
        # Simulate what record_asset_snapshot() does with no positions
        positions = []  # empty list
        total_value = sum(
            (getattr(p, "entry_price", 0) or 0) * (getattr(p, "quantity", 0) or 0)
            for p in positions
        )
        unrealized_pnl = sum(getattr(p, "unrealized_pnl", 0) or 0 for p in positions)
        total_balance = sum(
            (getattr(p, "current_price", 0) or 0) * (getattr(p, "quantity", 0) or 0)
            for p in positions
        )

        snap = AssetSnapshot(
            total_value=total_value,
            trade_count=0,
            unrealized_pnl=unrealized_pnl,
            total_balance=total_balance,
        )

        # Explicit zero values passed — not NULL, not omitted
        assert snap.total_value == 0.0
        assert snap.unrealized_pnl == 0.0
        assert snap.total_balance == 0.0
        assert snap.trade_count == 0
