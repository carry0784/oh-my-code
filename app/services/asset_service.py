"""Asset Service — CRUD + 3-state enforcement for the Symbol registry.

Phase 2, CR-048.  Provides:
  - Symbol CRUD with status transition rules
  - Excluded-sector guard (EXCLUDED_SECTORS → always EXCLUDED)
  - TTL expiry detection
  - Screening result append
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import (
    AssetSector,
    Symbol,
    SymbolStatus,
    SymbolStatusReason,
    ScreeningResult,
    SymbolStatusAudit,
    EXCLUDED_SECTORS,
)
from app.models.strategy_registry import AssetClass
from app.models.qualification import (
    QualificationResult,
    QualificationStatus,
)
from app.services.asset_validators import (
    validate_broker_policy,
    validate_status_transition,
)
from app.services.symbol_screener import ScreeningInput, ScreeningOutput, SymbolScreener
from app.services.backtest_qualification import (
    QualificationInput,
    QualificationOutput,
    BacktestQualifier,
)

logger = logging.getLogger(__name__)


class AssetService:
    """Stateless service operating on Symbol and ScreeningResult."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Read ─────────────────────────────────────────────────────────

    async def get_symbol(self, symbol: str) -> Symbol | None:
        result = await self.db.execute(select(Symbol).where(Symbol.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_symbol_by_id(self, symbol_id: str) -> Symbol | None:
        result = await self.db.execute(select(Symbol).where(Symbol.id == symbol_id))
        return result.scalar_one_or_none()

    async def list_symbols(
        self,
        status: SymbolStatus | None = None,
        asset_class: AssetClass | None = None,
    ) -> list[Symbol]:
        stmt = select(Symbol)
        if status is not None:
            stmt = stmt.where(Symbol.status == status)
        if asset_class is not None:
            stmt = stmt.where(Symbol.asset_class == asset_class)
        result = await self.db.execute(stmt.order_by(Symbol.symbol))
        return list(result.scalars().all())

    async def list_core_symbols(
        self,
        asset_class: AssetClass | None = None,
    ) -> list[Symbol]:
        return await self.list_symbols(
            status=SymbolStatus.CORE,
            asset_class=asset_class,
        )

    # ── Create ───────────────────────────────────────────────────────

    async def register_symbol(self, data: dict) -> Symbol:
        """Register a new symbol with excluded-sector and broker-policy enforcement.

        Stage 2B: added broker-policy validation via asset_validators.
        Fail-closed: validation failure → registration refused (no DB INSERT).
        """
        sector = data.get("sector")
        if isinstance(sector, str):
            sector = AssetSector(sector)

        # Stage 2B: Broker-policy validation (fail-closed: reject on violation)
        exchanges = data.get("exchanges", [])
        if isinstance(exchanges, str):
            exchanges = json.loads(exchanges)
        _ac = data.get("asset_class", "crypto")
        asset_class = _ac.value if hasattr(_ac, "value") else str(_ac)
        broker_violations = validate_broker_policy(exchanges, asset_class)
        if broker_violations:
            raise ValueError(f"Broker policy violation: {'; '.join(broker_violations)}")

        # Excluded-sector guard: force EXCLUDED status
        if sector in EXCLUDED_SECTORS:
            data["status"] = SymbolStatus.EXCLUDED.value
            data["status_reason_code"] = SymbolStatusReason.EXCLUSION_BASELINE.value
            if not data.get("exclusion_reason"):
                data["exclusion_reason"] = f"Sector {sector.value} is in exclusion baseline"

        # Serialize list fields to JSON
        if isinstance(data.get("exchanges"), list):
            data["exchanges"] = json.dumps(data["exchanges"])
        if isinstance(data.get("regime_allow"), list):
            data["regime_allow"] = json.dumps(data["regime_allow"])

        now = datetime.now(timezone.utc)
        sym = Symbol(
            symbol=data["symbol"],
            name=data["name"],
            asset_class=data.get("asset_class", AssetClass.CRYPTO),
            sector=sector,
            theme=data.get("theme", "none"),
            exchanges=data.get("exchanges", "[]"),
            market_cap_usd=data.get("market_cap_usd"),
            avg_daily_volume=data.get("avg_daily_volume"),
            status=data.get("status", SymbolStatus.WATCH),
            status_reason_code=data.get("status_reason_code"),
            exclusion_reason=data.get("exclusion_reason"),
            screening_score=data.get("screening_score", 0.0),
            regime_allow=data.get("regime_allow"),
            paper_allowed=data.get("paper_allowed", False),
            live_allowed=data.get("live_allowed", False),
            manual_override=data.get("manual_override", False),
            broker_policy=data.get("broker_policy"),
            created_at=now,
            updated_at=now,
        )
        self.db.add(sym)
        await self.db.flush()
        return sym

    # ── Status Transitions ───────────────────────────────────────────

    async def transition_status(
        self,
        symbol_id: str,
        new_status: SymbolStatus,
        reason_code: str,
        exclusion_reason: str | None = None,
        triggered_by: str = "system",
        approval_level: str | None = None,
    ) -> Symbol:
        """Transition symbol status with enforcement rules.

        Stage 2B: added validate_status_transition() guard + audit recording.
        Fail-closed: validation failure → transition refused (no DB flush).

        Rules:
          - EXCLUDED symbols cannot transition to CORE or WATCH
            unless manual_override is True.
          - EXCLUDED-sector symbols can never leave EXCLUDED.
          - EXCLUDED→CORE is always forbidden.
        """
        sym = await self.get_symbol_by_id(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        old_status = sym.status

        # Stage 2B: Unified transition validation (fail-closed)
        sector_value = sym.sector.value if sym.sector else None
        allowed, reason = validate_status_transition(
            current_status=old_status.value,
            target_status=new_status.value,
            manual_override=sym.manual_override,
            sector=sector_value,
        )
        if not allowed:
            raise ValueError(f"Status transition denied for {sym.symbol}: {reason}")

        # Apply transition
        sym.status = new_status
        sym.status_reason_code = reason_code
        if exclusion_reason is not None:
            sym.exclusion_reason = exclusion_reason
        sym.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Stage 2B: Record audit trail (append-only, fail-open for audit)
        try:
            await self._record_status_audit(
                symbol_id=sym.id,
                symbol=sym.symbol,
                from_status=old_status.value,
                to_status=new_status.value,
                reason_code=reason_code,
                reason_detail=exclusion_reason,
                triggered_by=triggered_by,
                approval_level=approval_level,
            )
        except Exception as exc:
            # Audit recording failure should NOT block the transition.
            # Log warning but let the transition stand.
            logger.warning(
                "Failed to record status audit for %s: %s",
                sym.symbol,
                exc,
            )

        return sym

    # ── Status Audit ────────────────────────────────────────────────

    async def _record_status_audit(
        self,
        symbol_id: str,
        symbol: str,
        from_status: str,
        to_status: str,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        triggered_by: str = "system",
        approval_level: str | None = None,
        context: str | None = None,
    ) -> SymbolStatusAudit:
        """Append a status audit record (Stage 2B).

        Append-only: no update or delete methods exist.
        """
        audit = SymbolStatusAudit(
            symbol_id=symbol_id,
            symbol=symbol,
            from_status=from_status,
            to_status=to_status,
            reason_code=reason_code,
            reason_detail=reason_detail,
            triggered_by=triggered_by,
            approval_level=approval_level,
            context=context,
            transitioned_at=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        await self.db.flush()
        return audit

    # ── TTL ──────────────────────────────────────────────────────────

    async def process_expired_ttl(
        self,
        max_count: int = 10,
        triggered_by: str = "operator",
    ) -> list[Symbol]:
        """Demote expired CORE symbols to WATCH (Stage 2B).

        Manual invocation only — NO Celery task / beat / scheduler.
        Fail-closed: DB error → abort, CORE status preserved.
        Max per call: capped at max_count (default 10) to prevent pool collapse.

        Returns list of demoted symbols.
        """
        if max_count > 10:
            raise ValueError(f"max_count={max_count} exceeds Stage 2B limit of 10")

        expired = await self.get_expired_candidates()
        demoted: list[Symbol] = []

        for sym in expired[:max_count]:
            try:
                await self.transition_status(
                    symbol_id=sym.id,
                    new_status=SymbolStatus.WATCH,
                    reason_code=SymbolStatusReason.TTL_EXPIRED.value,
                    triggered_by=triggered_by,
                )
                # Clear TTL after demotion
                sym.candidate_expire_at = None
                sym.updated_at = datetime.now(timezone.utc)
                await self.db.flush()
                demoted.append(sym)
                logger.info(
                    "TTL expired: %s demoted CORE→WATCH",
                    sym.symbol,
                )
            except Exception as exc:
                # Fail-closed: skip this symbol, preserve CORE status
                logger.warning(
                    "TTL demotion failed for %s, preserving CORE: %s",
                    sym.symbol,
                    exc,
                )

        return demoted

    async def get_expired_candidates(self) -> list[Symbol]:
        """Return CORE symbols whose candidate TTL has expired."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Symbol)
            .where(Symbol.status == SymbolStatus.CORE)
            .where(Symbol.candidate_expire_at != None)  # noqa: E711
            .where(Symbol.candidate_expire_at < now)
        )
        return list(result.scalars().all())

    # ── Screening ────────────────────────────────────────────────────

    async def record_screening(self, data: dict) -> ScreeningResult:
        """Append a screening result record."""
        result = ScreeningResult(
            symbol_id=data["symbol_id"],
            symbol=data["symbol"],
            stage1_exclusion=data.get("stage1_exclusion", False),
            stage2_liquidity=data.get("stage2_liquidity", False),
            stage3_technical=data.get("stage3_technical", False),
            stage4_fundamental=data.get("stage4_fundamental", False),
            stage5_backtest=data.get("stage5_backtest", False),
            all_passed=data.get("all_passed", False),
            score=data.get("score", 0.0),
            stage_reason_code=data.get("stage_reason_code"),
            detail=data.get("detail"),
            resulting_status=data.get("resulting_status", SymbolStatus.WATCH),
            screened_at=data.get("screened_at", datetime.now(timezone.utc)),
        )
        self.db.add(result)
        await self.db.flush()
        return result

    async def get_screening_history(self, symbol_id: str) -> list[ScreeningResult]:
        """Return screening results for a symbol, newest first."""
        result = await self.db.execute(
            select(ScreeningResult)
            .where(ScreeningResult.symbol_id == symbol_id)
            .order_by(ScreeningResult.screened_at.desc())
        )
        return list(result.scalars().all())

    # ── Screener Integration ─────────────────────────────────────────

    async def screen_and_update(
        self,
        symbol_id: str,
        screening_input: ScreeningInput,
        screener: SymbolScreener | None = None,
    ) -> ScreeningOutput:
        """Run screening, record result, and update symbol status.

        Returns the ScreeningOutput for inspection.
        """
        sym = await self.get_symbol_by_id(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        sc = screener or SymbolScreener()
        output = sc.screen(screening_input)

        # Record screening result (append-only)
        stages = output.stages
        now = datetime.now(timezone.utc)
        await self.record_screening(
            {
                "symbol_id": symbol_id,
                "symbol": sym.symbol,
                "stage1_exclusion": stages[0].passed if len(stages) > 0 else False,
                "stage2_liquidity": stages[1].passed if len(stages) > 1 else False,
                "stage3_technical": stages[2].passed if len(stages) > 2 else False,
                "stage4_fundamental": stages[3].passed if len(stages) > 3 else False,
                "stage5_backtest": stages[4].passed if len(stages) > 4 else False,
                "all_passed": output.all_passed,
                "score": output.score,
                "stage_reason_code": output.stage_reason_code.value
                if output.stage_reason_code
                else None,
                "detail": json.dumps(
                    {
                        "stages": [
                            {
                                "stage": s.stage,
                                "passed": s.passed,
                                "reason": s.reason_code.value if s.reason_code else None,
                            }
                            for s in stages
                        ],
                    }
                ),
                "resulting_status": output.resulting_status,
                "screened_at": now,
            }
        )

        # Update symbol status (respecting excluded-sector guard)
        if sym.sector in EXCLUDED_SECTORS:
            # Cannot leave EXCLUDED regardless of screening result
            sym.status = SymbolStatus.EXCLUDED
            sym.status_reason_code = SymbolStatusReason.EXCLUSION_BASELINE.value
        else:
            sym.status = output.resulting_status
            sym.status_reason_code = output.status_reason_code.value

        sym.screening_score = output.score

        # Set candidate TTL for CORE symbols
        if output.all_passed and sym.status == SymbolStatus.CORE:
            sym.candidate_expire_at = now + timedelta(hours=output.candidate_ttl_hours)
        elif sym.status != SymbolStatus.CORE:
            sym.candidate_expire_at = None

        sym.updated_at = now
        await self.db.flush()

        return output

    # ── Qualification Integration ────────────────────────────────────

    async def qualify_and_record(
        self,
        symbol_id: str,
        qualification_input: QualificationInput,
        qualifier: BacktestQualifier | None = None,
    ) -> QualificationOutput:
        """Run qualification, record result, and update symbol qualification_status.

        Returns the QualificationOutput for inspection.
        Does NOT change screening status (CORE/WATCH/EXCLUDED).
        """
        sym = await self.get_symbol_by_id(symbol_id)
        if sym is None:
            raise ValueError(f"Symbol not found: {symbol_id}")

        # Block qualification for EXCLUDED symbols
        if sym.status == SymbolStatus.EXCLUDED:
            raise ValueError(f"Symbol {sym.symbol} is EXCLUDED; qualification calls blocked")

        q = qualifier or BacktestQualifier()
        output = q.qualify(qualification_input)

        # Record qualification result (append-only)
        now = datetime.now(timezone.utc)
        checks = output.checks
        failed_checks_list = [c.check_name for c in checks if not c.passed]
        qr = QualificationResult(
            strategy_id=output.strategy_id,
            symbol=sym.symbol,
            timeframe=output.timeframe,
            dataset_fingerprint=qualification_input.dataset_fingerprint,
            bars_evaluated=qualification_input.total_bars,
            date_range_start=qualification_input.date_range_start,
            date_range_end=qualification_input.date_range_end,
            check_data_compat=checks[0].passed if len(checks) > 0 else False,
            check_warmup=checks[1].passed if len(checks) > 1 else False,
            check_leakage=checks[2].passed if len(checks) > 2 else False,
            check_data_quality=checks[3].passed if len(checks) > 3 else False,
            check_min_bars=checks[4].passed if len(checks) > 4 else False,
            check_performance=checks[5].passed if len(checks) > 5 else False,
            check_cost_sanity=checks[6].passed if len(checks) > 6 else False,
            all_passed=output.all_passed,
            qualification_status=output.qualification_status,
            disqualify_reason=(
                output.disqualify_reason.value if output.disqualify_reason else None
            ),
            failed_checks=(json.dumps(failed_checks_list) if failed_checks_list else None),
            metrics_snapshot=json.dumps(output.metrics_snapshot)
            if output.metrics_snapshot
            else None,
            detail=json.dumps(
                {
                    "checks": [
                        {
                            "name": c.check_name,
                            "passed": c.passed,
                            "reason": c.reason.value if c.reason else None,
                        }
                        for c in checks
                    ],
                }
            ),
            evaluated_at=now,
        )
        self.db.add(qr)
        await self.db.flush()

        # Update symbol qualification_status (independent of screening status)
        sym.qualification_status = output.qualification_status.value
        sym.updated_at = now
        await self.db.flush()

        return output

    async def get_qualification_history(
        self,
        symbol: str,
        strategy_id: str | None = None,
    ) -> list[QualificationResult]:
        """Return qualification results, newest first."""
        stmt = select(QualificationResult).where(QualificationResult.symbol == symbol)
        if strategy_id is not None:
            stmt = stmt.where(QualificationResult.strategy_id == strategy_id)
        result = await self.db.execute(stmt.order_by(QualificationResult.evaluated_at.desc()))
        return list(result.scalars().all())
