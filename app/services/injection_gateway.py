"""
Injection Gateway — validates all registration requests before they enter
the Control Plane.  Enforces forbidden broker/sector rules, dependency
checks, checksum verification, and market-matrix compatibility.

This is the single entry point for strategy/indicator/feature-pack
registration.  If the gateway rejects a request, nothing downstream
(Backtest Qualification, Paper Shadow, Promotion Gate) ever sees it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator_registry import Indicator, IndicatorStatus
from app.models.feature_pack import FeaturePack, FeaturePackStatus
from app.models.strategy_registry import Strategy, AssetClass, PromotionStatus

logger = logging.getLogger(__name__)

# ── Constitution constants (shared source: app.core.constitution) ─────
# Re-exported here for backward compatibility with existing imports.

from app.core.constitution import (
    FORBIDDEN_BROKERS,
    ALLOWED_BROKERS,
    FORBIDDEN_SECTOR_VALUES,
    EXPOSURE_LIMITS,
)

# Gateway uses uppercase keys for sector comparison
FORBIDDEN_SECTORS: frozenset[str] = frozenset(s.upper() for s in FORBIDDEN_SECTOR_VALUES)


# ── Result types ──────────────────────────────────────────────────────


class GatewayVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class GatewayResult:
    verdict: GatewayVerdict
    violations: list[str] = field(default_factory=list)
    blocked_code: str | None = None  # e.g. FORBIDDEN_BROKER


# ── Gateway service ───────────────────────────────────────────────────


class InjectionGateway:
    """Validates registration requests against the constitution."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────

    async def validate_strategy(self, data: dict[str, Any]) -> GatewayResult:
        """Run all 7 checks on a strategy registration request.

        Validation order (design_strategy_registry.md §S-01):
          1. forbidden_broker check
          2. forbidden_sector check
          3. dependency verification (feature pack exists)
          4. version checksum verification
          5. manifest signature verification
          6. market-matrix broker compatibility
          7. feature pack status check (not BLOCKED/DEPRECATED)
        """
        violations: list[str] = []
        blocked_code: str | None = None

        exchanges = _parse_json_list(data.get("exchanges", "[]"))
        sectors = _parse_json_list(data.get("sectors") or "[]")
        asset_classes = _parse_json_list(data.get("asset_classes", "[]"))

        # Step 1. Forbidden broker check
        for ex in exchanges:
            if ex.upper() in FORBIDDEN_BROKERS:
                violations.append(f"Forbidden broker: {ex}")
                blocked_code = blocked_code or "FORBIDDEN_BROKER"

        # Step 2. Forbidden sector check
        for sec in sectors:
            if sec.upper() in FORBIDDEN_SECTORS:
                violations.append(f"Forbidden sector: {sec}")
                blocked_code = blocked_code or "FORBIDDEN_SECTOR"

        # Step 3. Feature pack dependency verification
        fp_id = data.get("feature_pack_id")
        fp: FeaturePack | None = None
        if fp_id:
            fp = await self._get_feature_pack(fp_id)
            if fp is None:
                violations.append(f"Feature pack not found: {fp_id}")
                blocked_code = blocked_code or "MISSING_DEPENDENCY"
        else:
            violations.append("feature_pack_id is required")
            blocked_code = blocked_code or "MISSING_DEPENDENCY"

        # Step 4. Version checksum verification
        if data.get("checksum") and data.get("expected_checksum"):
            if data["checksum"] != data["expected_checksum"]:
                violations.append("Version checksum mismatch")
                blocked_code = blocked_code or "VERSION_MISMATCH"

        # Step 5. Manifest signature verification
        if data.get("manifest_signature"):
            if not self._verify_manifest_signature(data):
                violations.append("Manifest signature invalid")
                blocked_code = blocked_code or "INVALID_SIGNATURE"

        # Step 6. Market-matrix broker compatibility
        for ac in asset_classes:
            allowed = ALLOWED_BROKERS.get(ac.lower(), frozenset())
            for ex in exchanges:
                if ex.upper() not in allowed:
                    violations.append(f"Broker {ex} not allowed for asset class {ac}")
                    blocked_code = blocked_code or "ASSET_BROKER_INCOMPATIBLE"

        # Step 7. Feature pack status check (if FP was found)
        if fp is not None:
            fp_status = fp.status
            if fp_status in (FeaturePackStatus.BLOCKED.value, "BLOCKED"):
                violations.append(f"Feature pack is BLOCKED: {fp_id}")
                blocked_code = blocked_code or "DEPENDENCY_BLOCKED"
            elif fp_status in (FeaturePackStatus.DEPRECATED.value, "DEPRECATED"):
                violations.append(f"Feature pack is DEPRECATED: {fp_id}")
                blocked_code = blocked_code or "DEPENDENCY_DEPRECATED"

        if violations:
            logger.warning("Gateway REJECTED strategy: %s", violations)
            return GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=violations,
                blocked_code=blocked_code,
            )

        return GatewayResult(verdict=GatewayVerdict.APPROVED)

    # ── Validation Constants ─────────────────────────────────────────

    GATEWAY_CHECK_STEPS: tuple[str, ...] = (
        "forbidden_broker",
        "forbidden_sector",
        "dependency_verification",
        "version_checksum",
        "manifest_signature",
        "market_matrix_compatibility",
        "feature_pack_status",
    )
    """7-step Gateway validation order (design_strategy_registry.md §S-01)."""

    async def validate_indicator(self, data: dict[str, Any]) -> GatewayResult:
        """Validate indicator registration — lightweight check."""
        violations: list[str] = []
        if not data.get("name"):
            violations.append("Indicator name is required")
        if not data.get("version"):
            violations.append("Indicator version is required")
        if not data.get("compute_module"):
            violations.append("Indicator compute_module is required")

        if violations:
            return GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=violations,
            )
        return GatewayResult(verdict=GatewayVerdict.APPROVED)

    async def validate_feature_pack(self, data: dict[str, Any]) -> GatewayResult:
        """Validate feature pack — check all referenced indicators exist."""
        violations: list[str] = []

        indicator_ids = _parse_json_list(data.get("indicator_ids", "[]"))
        if not indicator_ids:
            violations.append("Feature pack must reference at least one indicator")

        for ind_id in indicator_ids:
            ind = await self._get_indicator(ind_id)
            if ind is None:
                violations.append(f"Indicator not found: {ind_id}")
            elif ind.status == IndicatorStatus.BLOCKED:
                violations.append(f"Indicator is BLOCKED: {ind_id}")

        if violations:
            return GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=violations,
                blocked_code="MISSING_DEPENDENCY",
            )
        return GatewayResult(verdict=GatewayVerdict.APPROVED)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _verify_manifest_signature(data: dict[str, Any]) -> bool:
        """Verify manifest signature if present.

        Current implementation: signature is considered valid if non-empty.
        Full cryptographic verification deferred to Phase 4.
        """
        sig = data.get("manifest_signature", "")
        # Placeholder: accept any non-empty signature for now.
        # Full crypto verification in Phase 4.
        return bool(sig and len(sig) >= 8)

    async def _get_feature_pack(self, fp_id: str) -> FeaturePack | None:
        result = await self.db.execute(select(FeaturePack).where(FeaturePack.id == fp_id))
        return result.scalar_one_or_none()

    async def _get_indicator(self, ind_id: str) -> Indicator | None:
        result = await self.db.execute(select(Indicator).where(Indicator.id == ind_id))
        return result.scalar_one_or_none()


def _parse_json_list(val: str | list | None) -> list[str]:
    """Parse a JSON string or list into a list of strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
