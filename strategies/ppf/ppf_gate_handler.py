"""PPF Gate Handler -- Wrapper-level Step 5.75 injection.

Authority: PPF-IMPLEMENTATION-002 (C Chain)
scope_lock_hash: 44ab0e40b4b9d26d8762ae155318b205629099387e8b1fdb89cb343db1867a61

Purpose:
    Sits between SubmitLedger.submit_ready=True and OrderExecutor.execute_order()
    at Step 5.75 in the orchestrator pipeline. Engine core logic unchanged.

Constitution lock (C7):
    - core safety modules unchanged
    - wrapper injection only
    - no direct mutation to execution safety modules

Deny reason code version: v1 (9 codes, LOCKED)
Mode: shadow-first only (enforcement disabled in shadow)

Bounded scope:
    - This file is 1 of 2 authorized files in PPF-IMPLEMENTATION-002
    - The other is orchestrator.py (injection only)

Prohibited behavior:
    - Direct order creation
    - Direct submit/execution mutation
    - Direct production switch
    - Runtime parameter mutation
    - Hidden state expansion outside bounded wrapper scope
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TYPE_CHECKING

import numpy as np

from strategies.ppf.execution_ledger import (
    DivergenceSeverity,
    DivergenceType,
    ExecutionObservation,
    ExecutionPath,
    classify_divergence,
    compute_execution_interpretation,
)
from strategies.ppf.gate import PPFGate
from strategies.ppf.session_ledger import SessionFailureBudgetLedger

if TYPE_CHECKING:
    from strategies.ppf.logging_schema import PPFLogEntry


logger = logging.getLogger("ppf.gate_handler")


# ---------------------------------------------------------------------------
# Deny Reason Code System (LOCKED -- 9 codes, v1)
# ---------------------------------------------------------------------------

class DenyReasonCode(str, enum.Enum):
    """Deny reason code set -- LOCKED at 9 codes, version v1.

    Rules:
    - All deny outcomes must map to one of the 9 codes
    - No ad-hoc deny code creation is allowed in this chain
    - Unknown deny states must map to INTERNAL_GATE_ERROR
    - Shadow mode may log deny outcomes without enforcing execution block
    """

    DATA_STALE = "DATA_STALE"
    DATA_MISSING = "DATA_MISSING"
    CONSTITUTION_DEACTIVATED = "CONSTITUTION_DEACTIVATED"
    SESSION_ABORTED = "SESSION_ABORTED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    NOVELTY_BRAKE = "NOVELTY_BRAKE"
    SCORE_THRESHOLD_DENY = "SCORE_THRESHOLD_DENY"
    MODE_ENFORCEMENT_DISABLED = "MODE_ENFORCEMENT_DISABLED"
    INTERNAL_GATE_ERROR = "INTERNAL_GATE_ERROR"


DENY_REASON_CODE_VERSION = "v1"


# ---------------------------------------------------------------------------
# Mode Capability Manifest (LOCKED -- 6 booleans)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModeCapabilityManifest:
    """Capability manifest for PPF gate handler mode.

    LOCKED at 6 boolean fields. Frozen to enforce immutability.
    Recorded in implementation receipts and shadow summaries.
    """

    enforce_deny: bool = False
    record_lv2: bool = True
    record_lv3: bool = True
    allow_session_abort: bool = False
    allow_live_execution: bool = False
    require_micro_size: bool = False


# Predefined mode manifests

SHADOW_MANIFEST = ModeCapabilityManifest(
    enforce_deny=False,
    record_lv2=True,
    record_lv3=True,
    allow_session_abort=False,
    allow_live_execution=False,
    require_micro_size=False,
)

PAPER_MANIFEST = ModeCapabilityManifest(
    enforce_deny=True,
    record_lv2=True,
    record_lv3=True,
    allow_session_abort=True,
    allow_live_execution=False,
    require_micro_size=False,
)

GUARDED_MANIFEST = ModeCapabilityManifest(
    enforce_deny=True,
    record_lv2=True,
    record_lv3=True,
    allow_session_abort=True,
    allow_live_execution=True,
    require_micro_size=True,
)

LIVE_MANIFEST = ModeCapabilityManifest(
    enforce_deny=True,
    record_lv2=True,
    record_lv3=True,
    allow_session_abort=True,
    allow_live_execution=True,
    require_micro_size=False,
)


# ---------------------------------------------------------------------------
# Shadow Verification Axes (LOCKED -- 6 axes)
# ---------------------------------------------------------------------------

SHADOW_VERIFICATION_AXES = (
    "session_type",
    "symbol",
    "venue",
    "regime",
    "denial_reason",
    "severity",
)


# ---------------------------------------------------------------------------
# Log Prefixes (LOCKED -- 4 prefixes)
# ---------------------------------------------------------------------------

LOG_PREFIX_GATE_EVAL = "ppf_gate_eval"
LOG_PREFIX_GATE_DENY = "ppf_gate_deny"
LOG_PREFIX_SESSION_ABORT = "ppf_session_abort"
LOG_PREFIX_CONSTITUTION_VIOLATION = "ppf_constitution_violation"


# ---------------------------------------------------------------------------
# Gate Result
# ---------------------------------------------------------------------------

@dataclass
class PPFGateResult:
    """Result of PPF gate evaluation at Step 5.75.

    Contains effective gate decision, raw gate decision,
    deny metadata, mode manifest, and session status.
    """

    # Effective decision (respects manifest.enforce_deny)
    allowed: bool
    # Raw PPF gate decision (before manifest override)
    raw_gate_decision: bool
    # Deny reason code (None if raw decision was allow)
    deny_reason_code: Optional[DenyReasonCode] = None
    # Deny reason code version
    deny_reason_code_version: str = DENY_REASON_CODE_VERSION
    # PPF log entry from gate evaluation
    ppf_log_entry: Optional[Any] = None
    # Active mode capability manifest
    mode_manifest: Optional[ModeCapabilityManifest] = None
    # Session summary from LV-3 ledger
    session_summary: Optional[dict] = None
    # Shadow verification axes snapshot
    shadow_axes_snapshot: Optional[dict] = None
    # Gate evaluation timestamp
    gate_eval_ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Serialize to dict for logging and response embedding."""
        d = {
            "allowed": self.allowed,
            "raw_gate_decision": self.raw_gate_decision,
            "deny_reason_code": (
                self.deny_reason_code.value if self.deny_reason_code else None
            ),
            "deny_reason_code_version": self.deny_reason_code_version,
            "mode_manifest": (
                asdict(self.mode_manifest) if self.mode_manifest else None
            ),
            "session_summary": self.session_summary,
            "shadow_axes_snapshot": self.shadow_axes_snapshot,
            "gate_eval_ts": self.gate_eval_ts,
        }
        return d


# ---------------------------------------------------------------------------
# PPF Gate Handler
# ---------------------------------------------------------------------------

class PPFGateHandler:
    """Wrapper-level PPF gate injection handler (Step 5.75).

    Sits between SubmitLedger.submit_ready=True and OrderExecutor.execute_order()
    in the orchestrator pipeline.

    C7 lock:
        - core safety modules unchanged
        - wrapper injection only
        - no direct mutation to execution safety modules

    This handler:
        1. Evaluates PPF gate with OHLCV + risk_filter_pass
        2. Produces gate decision metadata (PPFGateResult)
        3. Records LV-2/LV-3 events as metadata pathways
        4. In shadow mode: logs but does NOT enforce (Step 6 proceeds)
        5. In enforce mode: deny blocks Step 6 execution

    Prohibited:
        - Direct order creation
        - Direct submit/execution mutation
        - Direct production switch
        - Runtime parameter mutation
        - Hidden state expansion
    """

    def __init__(
        self,
        ppf_gate: PPFGate,
        session_ledger: SessionFailureBudgetLedger,
        ohlcv_provider: Callable[
            [], Optional[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]
        ],
        manifest: ModeCapabilityManifest = SHADOW_MANIFEST,
    ) -> None:
        """Initialize PPF Gate Handler.

        Args:
            ppf_gate: PPF gate instance for evaluation.
            session_ledger: Session failure budget ledger for LV-3 tracking.
            ohlcv_provider: Callable returning (highs, lows, closes, volumes)
                or None if data unavailable.
            manifest: Mode capability manifest (default: SHADOW).
        """
        self._gate = ppf_gate
        self._session_ledger = session_ledger
        self._ohlcv_provider = ohlcv_provider
        self._manifest = manifest
        self._deny_reason_code_version = DENY_REASON_CODE_VERSION

    # -- Properties --

    @property
    def manifest(self) -> ModeCapabilityManifest:
        """Active mode capability manifest."""
        return self._manifest

    @property
    def deny_reason_code_version(self) -> str:
        """Deny reason code version string."""
        return self._deny_reason_code_version

    @property
    def session_ledger(self) -> SessionFailureBudgetLedger:
        """Session failure budget ledger."""
        return self._session_ledger

    @property
    def ppf_gate(self) -> PPFGate:
        """Underlying PPF gate instance."""
        return self._gate

    # -- Gate Evaluation (Step 5.75) --

    def check_gate(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        risk_filter_pass: bool = False,
    ) -> PPFGateResult:
        """Evaluate PPF gate at Step 5.75.

        Fail-closed: any error returns allowed=False with INTERNAL_GATE_ERROR.
        Shadow mode: effective allowed=True regardless of raw gate decision.

        Args:
            symbol: Trading symbol (for shadow axes).
            exchange: Exchange/venue (for shadow axes).
            risk_filter_pass: Engine risk filter result (read-only input).

        Returns:
            PPFGateResult with effective gate decision and metadata.
        """
        try:
            return self._check_gate_internal(symbol, exchange, risk_filter_pass)
        except Exception as exc:
            # Fail-closed: any error -> deny (but shadow overrides to allow)
            logger.error(
                "%s: unhandled error (fail-closed): %r",
                LOG_PREFIX_GATE_EVAL,
                exc,
            )
            raw_denied = False
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=raw_denied,
                deny_reason_code=DenyReasonCode.INTERNAL_GATE_ERROR,
                mode_manifest=self._manifest,
            )

    def _check_gate_internal(
        self,
        symbol: Optional[str],
        exchange: Optional[str],
        risk_filter_pass: bool,
    ) -> PPFGateResult:
        """Internal gate check. Exceptions propagate to caller."""

        # -- Pre-gate checks (session state) --

        # Constitution: silent continuation after abort is forbidden
        if self._session_ledger.is_aborted:
            logger.info(
                "%s: session aborted, session_id=%s, reason=%s",
                LOG_PREFIX_SESSION_ABORT,
                self._session_ledger.session_id,
                self._session_ledger.abort_reason,
            )
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.SESSION_ABORTED,
                mode_manifest=self._manifest,
                session_summary=self._session_ledger.summary(),
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "aborted",
                    DenyReasonCode.SESSION_ABORTED, "high",
                ),
            )

        # Constitution: cooldown re-entry must be denied
        if self._session_ledger.is_cooldown_active:
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.COOLDOWN_ACTIVE,
                mode_manifest=self._manifest,
                session_summary=self._session_ledger.summary(),
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "cooldown",
                    DenyReasonCode.COOLDOWN_ACTIVE, "high",
                ),
            )

        # Check PPF gate active (constitution)
        if not self._gate.is_active:
            logger.error(
                "%s: PPF gate deactivated by constitution violation",
                LOG_PREFIX_CONSTITUTION_VIOLATION,
            )
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.CONSTITUTION_DEACTIVATED,
                mode_manifest=self._manifest,
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "deactivated",
                    DenyReasonCode.CONSTITUTION_DEACTIVATED, "blocker",
                ),
            )

        # -- Data acquisition --

        ohlcv = self._ohlcv_provider()
        if ohlcv is None:
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.DATA_MISSING,
                mode_manifest=self._manifest,
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "unknown",
                    DenyReasonCode.DATA_MISSING, "medium",
                ),
            )

        highs, lows, closes, volumes = ohlcv

        # Validate data presence
        if len(closes) == 0:
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.DATA_MISSING,
                mode_manifest=self._manifest,
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "unknown",
                    DenyReasonCode.DATA_MISSING, "medium",
                ),
            )

        # -- PPF Gate Evaluation --

        raw_gate_allows = self._gate.evaluate(
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            risk_filter_pass=risk_filter_pass,
        )

        # Check if gate was deactivated during evaluation
        if not self._gate.is_active:
            logger.error(
                "%s: PPF gate deactivated during evaluation",
                LOG_PREFIX_CONSTITUTION_VIOLATION,
            )
            effective = not self._manifest.enforce_deny
            return PPFGateResult(
                allowed=effective,
                raw_gate_decision=False,
                deny_reason_code=DenyReasonCode.CONSTITUTION_DEACTIVATED,
                mode_manifest=self._manifest,
                shadow_axes_snapshot=self._build_shadow_axes(
                    symbol, exchange, "deactivated",
                    DenyReasonCode.CONSTITUTION_DEACTIVATED, "blocker",
                ),
            )

        # -- Build result --

        ppf_log = self._gate.last_log_entry
        deny_code: Optional[DenyReasonCode] = None

        if not raw_gate_allows:
            # Map PPF rejection to deny reason code
            if ppf_log and ppf_log.regime_novelty_flag:
                deny_code = DenyReasonCode.NOVELTY_BRAKE
            else:
                deny_code = DenyReasonCode.SCORE_THRESHOLD_DENY

            logger.info(
                "%s: symbol=%s, venue=%s, deny_code=%s, deny_code_version=%s",
                LOG_PREFIX_GATE_DENY,
                symbol,
                exchange,
                deny_code.value,
                self._deny_reason_code_version,
            )
        else:
            logger.info(
                "%s: symbol=%s, venue=%s, allowed=True",
                LOG_PREFIX_GATE_EVAL,
                symbol,
                exchange,
            )

        # Effective decision: shadow mode overrides deny to allow
        effective_allowed = raw_gate_allows or not self._manifest.enforce_deny

        # Build shadow axes snapshot
        regime_state = ppf_log.ppf_state if ppf_log else "unknown"
        severity = "none" if raw_gate_allows else "low"
        shadow_axes = self._build_shadow_axes(
            symbol, exchange, regime_state, deny_code, severity,
        )

        return PPFGateResult(
            allowed=effective_allowed,
            raw_gate_decision=raw_gate_allows,
            deny_reason_code=deny_code,
            deny_reason_code_version=self._deny_reason_code_version,
            ppf_log_entry=ppf_log,
            mode_manifest=self._manifest,
            session_summary=self._session_ledger.summary(),
            shadow_axes_snapshot=shadow_axes,
        )

    # -- Post-Execution Recording --

    def record_execution_outcome(
        self,
        order_status: Optional[str],
        expected_path: ExecutionPath = ExecutionPath.SUBMIT_ACK_FILL,
        reject_code: Optional[str] = None,
        timeout_flag: bool = False,
        venue_latency_ms: Optional[float] = None,
        partial_fill_qty: float = 0.0,
        final_fill_qty: float = 0.0,
    ) -> Optional[str]:
        """Record post-execution outcome in LV-2/LV-3 ledgers.

        Called after OrderExecutor returns. This is a metadata pathway only;
        it does not mutate execution state or produce orders.

        Args:
            order_status: OrderResult status (FILLED/REJECTED/TIMEOUT/etc.)
            expected_path: Expected execution path.
            reject_code: Venue reject code if applicable.
            timeout_flag: Whether order timed out.
            venue_latency_ms: Venue acknowledgment latency.
            partial_fill_qty: Partial fill quantity.
            final_fill_qty: Final fill quantity.

        Returns:
            abort_reason if session must abort, None otherwise.
        """
        if not self._manifest.record_lv2:
            return None

        # Map order status to actual execution path
        actual_path = self._map_status_to_path(
            order_status, reject_code, timeout_flag,
            partial_fill_qty, final_fill_qty,
        )

        # Build execution observation
        now_iso = datetime.now(timezone.utc).isoformat()
        obs = ExecutionObservation(
            order_submit_ts=now_iso,
            venue_ack_ts=now_iso if not timeout_flag else None,
            reject_code=reject_code,
            timeout_flag=timeout_flag,
            venue_latency_ms=venue_latency_ms,
            partial_fill_qty=partial_fill_qty,
            final_fill_qty=final_fill_qty,
            expected_path=expected_path,
            actual_path=actual_path,
        )

        # Classify divergence
        div_type = classify_divergence(obs)
        interp = compute_execution_interpretation(obs)

        # Record in LV-3 session ledger (which internally records LV-2)
        if self._manifest.record_lv3:
            abort_reason = self._session_ledger.record_execution_event(
                exec_obs=obs,
                divergence_severity=interp.divergence_severity,
                divergence_type=div_type,
            )

            if abort_reason and self._manifest.allow_session_abort:
                logger.warning(
                    "%s: session_id=%s, abort_reason=%s",
                    LOG_PREFIX_SESSION_ABORT,
                    self._session_ledger.session_id,
                    abort_reason,
                )
                return abort_reason

        return None

    # -- Internal Helpers --

    @staticmethod
    def _map_status_to_path(
        order_status: Optional[str],
        reject_code: Optional[str],
        timeout_flag: bool,
        partial_fill_qty: float,
        final_fill_qty: float,
    ) -> ExecutionPath:
        """Map OrderResult status to ExecutionPath."""
        if order_status is None:
            return ExecutionPath.NO_SUBMIT

        status = order_status.upper()

        if status == "FILLED":
            return ExecutionPath.SUBMIT_ACK_FILL
        elif status == "PARTIAL":
            return ExecutionPath.SUBMIT_ACK_PARTIAL_FILL
        elif status == "REJECTED":
            return ExecutionPath.SUBMIT_REJECT
        elif status == "TIMEOUT":
            return ExecutionPath.SUBMIT_ACK_TIMEOUT
        elif status == "ERROR":
            if timeout_flag:
                return ExecutionPath.SUBMIT_TIMEOUT
            return ExecutionPath.SUBMIT_REJECT
        elif status == "CANCELLED":
            return ExecutionPath.SUBMIT_ACK_CANCEL

        return ExecutionPath.NO_SUBMIT

    @staticmethod
    def _build_shadow_axes(
        symbol: Optional[str],
        exchange: Optional[str],
        regime: str,
        deny_code: Optional[DenyReasonCode],
        severity: str,
    ) -> dict:
        """Build shadow verification axes snapshot (6 axes, LOCKED)."""
        return {
            "session_type": "shadow",
            "symbol": symbol or "unknown",
            "venue": exchange or "unknown",
            "regime": regime,
            "denial_reason": deny_code.value if deny_code else None,
            "severity": severity,
        }


# ---------------------------------------------------------------------------
# Scope Lock Hash
# ---------------------------------------------------------------------------

def compute_scope_lock_hash() -> str:
    """Compute scope_lock_hash from canonical manifest.

    The manifest includes:
        - allowed files (2)
        - forbidden critical files (5)
        - allowed actions (8)
        - forbidden actions (9)
        - C7 locked wording (3)
        - deny reason code set (9)
        - shadow verification axes (6)
        - mode capability manifest fields (6)

    Returns:
        SHA-256 hex digest of the canonical manifest.
    """
    manifest = {
        "allowed_files": [
            "ppf_gate_handler.py",
            "orchestrator.py",
        ],
        "forbidden_critical_files": [
            "order_executor.py",
            "submit_ledger.py",
            "execution_ledger.py",
            "action_ledger.py",
            "governance_gate.py",
        ],
        "allowed_actions": [
            "create_ppf_gate_handler",
            "inject_step_5_75",
            "add_optional_dependency_wiring",
            "read_ohlcv_arrays",
            "read_risk_filter_pass",
            "produce_gate_result_metadata",
            "record_shadow_logging",
            "preserve_handler_absent_behavior",
        ],
        "forbidden_actions": [
            "direct_edit_execution_safety_module",
            "order_generation_by_ppf",
            "live_execution_policy_expansion",
            "runtime_parameter_adaptation",
            "change_existing_step_semantics",
            "change_handler_absent_behavior",
            "enable_paper_guarded_live",
            "add_test_files",
            "hidden_refactor",
        ],
        "c7_locked_wording": [
            "core safety modules unchanged",
            "wrapper injection only",
            "no direct mutation to execution safety modules",
        ],
        "deny_reason_codes": [
            "DATA_STALE",
            "DATA_MISSING",
            "CONSTITUTION_DEACTIVATED",
            "SESSION_ABORTED",
            "COOLDOWN_ACTIVE",
            "NOVELTY_BRAKE",
            "SCORE_THRESHOLD_DENY",
            "MODE_ENFORCEMENT_DISABLED",
            "INTERNAL_GATE_ERROR",
        ],
        "shadow_verification_axes": [
            "session_type",
            "symbol",
            "venue",
            "regime",
            "denial_reason",
            "severity",
        ],
        "mode_capability_manifest_fields": [
            "enforce_deny",
            "record_lv2",
            "record_lv3",
            "allow_session_abort",
            "allow_live_execution",
            "require_micro_size",
        ],
    }

    canonical = json.dumps(
        manifest, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
