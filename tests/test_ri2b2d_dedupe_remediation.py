"""CR-048 RI-2B-2d: Rollback dedupe_key remediation — pure unit tests.

These tests do NOT depend on SQLAlchemy mapper initialization and are
safe to run in CI without the full DB fixture stack.

Covers:
  - Finding #1: verdict as 8th dedupe_key input (collision prevention)
  - Finding #3: RollbackFailedError attributes + ExecutionVerdict.ROLLBACK_ORPHAN
"""

from __future__ import annotations

import pytest

from app.services.shadow_write_service import (
    ExecutionVerdict,
    RollbackFailedError,
    compute_dedupe_key,
)


# ── Finding #1: dedupe_key collision prevention ─────────────────


class TestDedupeKeyVerdictParam:
    """Verify 8th parameter (verdict) prevents EXECUTED vs ROLLED_BACK collision."""

    def test_executed_vs_rolled_back_differ(self):
        """Root regression for Finding #1: identical 7-tuple + different verdict."""
        k_exec = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        k_rb = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="rolled_back",
        )
        assert k_exec != k_rb

    def test_verdict_default_empty_backward_compat(self):
        """No-arg calls produce stable hash (RI-2B-1 backward compat)."""
        k1 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        k2 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            verdict="",
        )
        assert k1 == k2

    def test_same_verdict_deterministic(self):
        k1 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        k2 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        assert k1 == k2

    def test_sha256_hex_length(self):
        k = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            verdict="executed",
        )
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)

    def test_dry_run_true_vs_false_differ(self):
        """Existing behavior preserved: dry_run=True ≠ dry_run=False."""
        k_dry = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=True,
            verdict="would_write",
        )
        k_exec = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        assert k_dry != k_exec

    def test_different_verdicts_all_unique(self):
        """All ExecutionVerdict values produce distinct hashes."""
        keys = set()
        for v in ExecutionVerdict:
            k = compute_dedupe_key(
                "SOL/USDT",
                "symbols",
                "qualification_status",
                "unchecked",
                "pass",
                "fp1",
                dry_run=False,
                verdict=v.value,
            )
            keys.add(k)
        assert len(keys) == len(ExecutionVerdict)


# ── Finding #3: Explicit error signaling ────────────────────────


class TestRollbackFailedErrorContract:
    """RollbackFailedError carries diagnostic fields for callers."""

    def test_attributes(self):
        err = RollbackFailedError(
            symbol="SOL/USDT",
            execution_receipt_id="exec-001",
            phase="business_revert",
            cause=RuntimeError("test"),
        )
        assert err.symbol == "SOL/USDT"
        assert err.execution_receipt_id == "exec-001"
        assert err.phase == "business_revert"
        assert isinstance(err.cause, RuntimeError)

    def test_str_contains_context(self):
        err = RollbackFailedError(
            symbol="BTC/USDT",
            execution_receipt_id="exec-002",
            phase="receipt_insert",
            cause=ValueError("collision"),
        )
        msg = str(err)
        assert "BTC/USDT" in msg
        assert "exec-002" in msg
        assert "receipt_insert" in msg

    def test_is_exception_subclass(self):
        assert issubclass(RollbackFailedError, Exception)

    def test_raises_and_catches(self):
        with pytest.raises(RollbackFailedError) as exc_info:
            raise RollbackFailedError(
                symbol="ETH/USDT",
                execution_receipt_id="exec-003",
                phase="unknown",
                cause=RuntimeError("boom"),
            )
        assert exc_info.value.phase == "unknown"


class TestExecutionVerdictRollbackOrphan:
    """ROLLBACK_ORPHAN is a valid ExecutionVerdict member."""

    def test_exists(self):
        assert hasattr(ExecutionVerdict, "ROLLBACK_ORPHAN")

    def test_value(self):
        assert ExecutionVerdict.ROLLBACK_ORPHAN.value == "rollback_orphan"

    def test_total_count(self):
        """6 verdict values: EXECUTED, EXECUTION_FAILED, ROLLED_BACK, ROLLBACK_ORPHAN, BLOCKED."""
        assert len(ExecutionVerdict) == 5
