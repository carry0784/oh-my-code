"""
K-Dexter Order Executor (External Caller)

Sits OUTSIDE the 4-tier seal chain. Responsible for actual order submission.
Reads submit_ready from SubmitLedger, calls Exchange API, records results.

Position:
  [Seal Chain] SubmitLedger.submit_ready=True -> [THIS] OrderExecutor -> Exchange API

Design principles:
  - NOT a seal layer. No state machine, no guard checks, no seal document.
  - Read-only access to SubmitLedger (never writes to any Ledger).
  - Side-effect handler: the ONLY module that calls exchange APIs.
  - Idempotent: same submit_proposal_id returns cached result.
  - dry_run mode: simulates execution without exchange calls.
  - Append-only history for audit trail.
  - Default dry_run=True: real execution requires explicit opt-in.

Safety mechanisms:
  OE-01: submit_ready=False -> ExecutionDeniedError (fail-closed)
  OE-02: Idempotent (duplicate proposal -> return cached result)
  OE-03: dry_run default True (explicit opt-in for real execution)
  OE-04: Exchange allowlist re-check (SUPPORTED_EXCHANGES_ALL)
  OE-05: Timeout handling (exchange call timeout)
  OE-06: Ledger write forbidden (read-only access)
  OE-07: History append-only (no deletion, no mutation)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import SUPPORTED_EXCHANGES_ALL


# -- Exceptions ------------------------------------------------------------ #


class ExecutionDeniedError(Exception):
    """Raised when submit_ready is False or execution preconditions not met."""

    pass


# -- Data Model ------------------------------------------------------------ #


@dataclass
class OrderResult:
    """Immutable record of an order execution attempt."""

    order_id: str  # OX-YYYYMMDDHHMMSS-xxxxxx
    submit_proposal_id: str  # SP-* (lineage)
    execution_proposal_id: str  # EP-* (lineage)
    agent_proposal_id: str  # AP-* (lineage)
    exchange: str
    symbol: str
    side: str  # "buy" | "sell"
    order_type: str  # "limit" | "market"
    requested_size: float
    executed_size: Optional[float] = None
    executed_price: Optional[float] = None
    status: str = "PENDING"  # FILLED | PARTIAL | REJECTED | TIMEOUT | ERROR
    exchange_order_id: Optional[str] = None
    error_detail: Optional[str] = None
    dry_run: bool = True
    created_at: str = ""
    executed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# -- Order Executor -------------------------------------------------------- #


class OrderExecutor:
    """
    External Caller: reads submit_ready, executes orders via exchange.

    NOT a singleton. Injected via dependency.
    NEVER writes to SubmitLedger, ExecutionLedger, or ActionLedger.
    """

    def __init__(self, default_timeout: float = 30.0):
        self._history: list[OrderResult] = []
        self._executed_proposals: dict[str, str] = {}  # submit_proposal_id -> order_id
        self._default_timeout = default_timeout

    async def execute_order(
        self,
        submit_proposal: Any,
        side: str,
        order_type: str = "market",
        price: Optional[float] = None,
        dry_run: bool = True,
    ) -> OrderResult:
        """
        Execute order for a submit-ready proposal.

        Steps:
          1. Verify submit_ready (fail-closed: False -> ExecutionDeniedError)
          2. Check idempotency (duplicate -> return cached result)
          3. Validate exchange in allowlist
          4. If dry_run: return simulated result
          5. Call ExchangeFactory.create(exchange).create_order(...)
          6. Build OrderResult from exchange response
          7. Append to _history

        Raises:
          ExecutionDeniedError: if submit_ready is False
        """
        # [1] submit_ready 검증 (fail-closed, 최상단)
        if not getattr(submit_proposal, "submit_ready", False):
            raise ExecutionDeniedError(
                f"Cannot execute: submit_ready is False for {submit_proposal.proposal_id}. "
                f"Current status: {getattr(submit_proposal, 'status', 'UNKNOWN')}"
            )

        sp_id = submit_proposal.proposal_id
        ep_id = getattr(submit_proposal, "execution_proposal_id", "UNKNOWN")
        ap_id = getattr(submit_proposal, "agent_proposal_id", "UNKNOWN")
        exchange = getattr(submit_proposal, "exchange", None)
        symbol = getattr(submit_proposal, "symbol", None)
        size_info = getattr(submit_proposal, "risk_result_summary", {}) or {}
        requested_size = size_info.get("position_size", 0) or 0

        # [2] 멱등성: 이미 실행된 proposal이면 기존 결과 반환
        if sp_id in self._executed_proposals:
            existing_oid = self._executed_proposals[sp_id]
            existing = self.get_order(existing_oid)
            if existing is not None:
                return existing

        # [3] exchange allowlist 재확인
        if exchange not in SUPPORTED_EXCHANGES_ALL:
            return self._record_result(
                sp_id=sp_id,
                ep_id=ep_id,
                ap_id=ap_id,
                exchange=exchange or "",
                symbol=symbol or "",
                side=side,
                order_type=order_type,
                requested_size=requested_size,
                status="ERROR",
                error_detail=f"Unsupported exchange: '{exchange}'. Allowed: {list(SUPPORTED_EXCHANGES_ALL)}",
                dry_run=dry_run,
            )

        # [4] dry_run 모드
        if dry_run:
            return self._record_result(
                sp_id=sp_id,
                ep_id=ep_id,
                ap_id=ap_id,
                exchange=exchange,
                symbol=symbol or "",
                side=side,
                order_type=order_type,
                requested_size=requested_size,
                status="FILLED",
                executed_size=requested_size,
                executed_price=0.0,
                exchange_order_id=f"DRY-{uuid.uuid4().hex[:8]}",
                dry_run=True,
            )

        # [5] 실제 거래소 호출
        try:
            from exchanges.factory import ExchangeFactory

            ex = ExchangeFactory.create(exchange)

            order_response = await asyncio.wait_for(
                ex.create_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=requested_size,
                    price=price,
                ),
                timeout=self._default_timeout,
            )

            return self._record_result(
                sp_id=sp_id,
                ep_id=ep_id,
                ap_id=ap_id,
                exchange=exchange,
                symbol=symbol or "",
                side=side,
                order_type=order_type,
                requested_size=requested_size,
                status="FILLED",
                executed_size=order_response.get("filled", requested_size),
                executed_price=order_response.get("price"),
                exchange_order_id=str(order_response.get("id", "")),
                dry_run=False,
            )

        except asyncio.TimeoutError:
            return self._record_result(
                sp_id=sp_id,
                ep_id=ep_id,
                ap_id=ap_id,
                exchange=exchange,
                symbol=symbol or "",
                side=side,
                order_type=order_type,
                requested_size=requested_size,
                status="TIMEOUT",
                error_detail=f"Exchange API timeout ({self._default_timeout}s)",
                dry_run=False,
            )

        except Exception as e:
            return self._record_result(
                sp_id=sp_id,
                ep_id=ep_id,
                ap_id=ap_id,
                exchange=exchange,
                symbol=symbol or "",
                side=side,
                order_type=order_type,
                requested_size=requested_size,
                status="ERROR",
                error_detail=f"{type(e).__name__}: {e}",
                dry_run=False,
            )

    # -- Internal ---------------------------------------------------------- #

    def _record_result(
        self,
        sp_id: str,
        ep_id: str,
        ap_id: str,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        requested_size: float,
        status: str,
        executed_size: Optional[float] = None,
        executed_price: Optional[float] = None,
        exchange_order_id: Optional[str] = None,
        error_detail: Optional[str] = None,
        dry_run: bool = True,
    ) -> OrderResult:
        """Create OrderResult, append to history, register idempotency key."""
        now_iso = datetime.now(timezone.utc).isoformat()
        result = OrderResult(
            order_id=f"OX-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            submit_proposal_id=sp_id,
            execution_proposal_id=ep_id,
            agent_proposal_id=ap_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_size=requested_size,
            executed_size=executed_size,
            executed_price=executed_price,
            status=status,
            exchange_order_id=exchange_order_id,
            error_detail=error_detail,
            dry_run=dry_run,
            created_at=now_iso,
            executed_at=now_iso,
        )
        self._history.append(result)
        self._executed_proposals[sp_id] = result.order_id
        return result

    # -- Query ------------------------------------------------------------- #

    def get_history(self) -> list[dict]:
        """Get all order results as dicts. Append-only, no deletion."""
        return [r.to_dict() for r in self._history]

    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """Get single order result by order_id."""
        for r in self._history:
            if r.order_id == order_id:
                return r
        return None

    def get_order_by_proposal(self, submit_proposal_id: str) -> Optional[OrderResult]:
        """Get order result by submit_proposal_id (for lineage trace)."""
        oid = self._executed_proposals.get(submit_proposal_id)
        if oid:
            return self.get_order(oid)
        return None

    @property
    def count(self) -> int:
        return len(self._history)
