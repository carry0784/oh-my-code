"""
Runtime Immutability Zone — Bundle contracts, canonical serialization,
and SHA-256 hash computation for the 4 immutable bundles.

Each bundle represents a set of configuration/code that MUST NOT change
at runtime without going through the Control Plane (new version + Promotion Gate).

Bundles:
  - Strategy Bundle: strategy code + params + version
  - Feature Pack Bundle: indicator set + weights + version
  - Broker Policy Bundle: allowed/forbidden broker lists + trading hours
  - Risk Limit Bundle: exposure limits + per-symbol/theme/market caps
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────


class BundleType(str, Enum):
    STRATEGY = "strategy"
    FEATURE_PACK = "feature_pack"
    BROKER_POLICY = "broker_policy"
    RISK_LIMIT = "risk_limit"


class DriftSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


# Severity mapping per bundle type
BUNDLE_SEVERITY: dict[BundleType, DriftSeverity] = {
    BundleType.STRATEGY: DriftSeverity.HIGH,
    BundleType.FEATURE_PACK: DriftSeverity.MEDIUM,
    BundleType.BROKER_POLICY: DriftSeverity.HIGH,
    BundleType.RISK_LIMIT: DriftSeverity.CRITICAL,
}


# ── Canonical serialization ──────────────────────────────────────────


def _canonicalize(obj: Any) -> str:
    """Deterministic JSON serialization.

    Rules:
      - Keys sorted alphabetically at every nesting level
      - No whitespace (separators=(",", ":"))
      - Strings as-is (no locale)
      - Booleans as JSON true/false
      - None values excluded from output
      - Lists preserve order (semantic order, not random)
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(canonical_json: str) -> str:
    """SHA-256 of a canonical JSON string. Returns hex digest."""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# ── Bundle contracts ─────────────────────────────────────────────────

# Each build_*_manifest function extracts the immutable fields from
# the source object/dict and returns a canonical dict (no timestamps,
# no mutable metadata).  The dict is then serialized and hashed.

# EXCLUDED fields (per bundle):
#   Strategy: id, created_at, updated_at, promoted_at, promoted_by,
#             champion_since, is_champion, status, description
#   Feature Pack: id, created_at, updated_at, status, description
#   Broker Policy: (none excluded — all fields are immutable policy)
#   Risk Limit: (none excluded — all fields are immutable limits)


@dataclass(frozen=True)
class BundleManifest:
    """Immutable snapshot of a bundle's canonical content + hash."""

    bundle_type: BundleType
    canonical_json: str
    hash: str
    severity: DriftSeverity


def build_strategy_manifest(
    name: str,
    version: str,
    compute_module: str,
    feature_pack_id: str,
    checksum: str | None,
    asset_classes: list[str],
    exchanges: list[str],
    sectors: list[str] | None,
    timeframes: list[str],
    regimes: list[str] | None,
    max_symbols: int,
) -> BundleManifest:
    """Build canonical Strategy Bundle manifest.

    Included fields (alphabetical):
      asset_classes, checksum, compute_module, exchanges, feature_pack_id,
      max_symbols, name, regimes, sectors, timeframes, version
    """
    payload: dict[str, Any] = {
        "asset_classes": sorted(asset_classes),
        "compute_module": compute_module,
        "exchanges": sorted(exchanges),
        "feature_pack_id": feature_pack_id,
        "max_symbols": max_symbols,
        "name": name,
        "timeframes": sorted(timeframes),
        "version": version,
    }
    if checksum is not None:
        payload["checksum"] = checksum
    if sectors is not None:
        payload["sectors"] = sorted(sectors)
    if regimes is not None:
        payload["regimes"] = sorted(regimes)

    canonical = _canonicalize(payload)
    return BundleManifest(
        bundle_type=BundleType.STRATEGY,
        canonical_json=canonical,
        hash=compute_hash(canonical),
        severity=BUNDLE_SEVERITY[BundleType.STRATEGY],
    )


def build_feature_pack_manifest(
    name: str,
    version: str,
    indicator_ids: list[str],
    weights: dict[str, float] | None,
    checksum: str | None,
) -> BundleManifest:
    """Build canonical Feature Pack Bundle manifest.

    Included fields:
      checksum, indicator_ids (sorted), name, version, weights (sorted keys)
    """
    payload: dict[str, Any] = {
        "indicator_ids": sorted(indicator_ids),
        "name": name,
        "version": version,
    }
    if checksum is not None:
        payload["checksum"] = checksum
    if weights is not None:
        payload["weights"] = dict(sorted(weights.items()))

    canonical = _canonicalize(payload)
    return BundleManifest(
        bundle_type=BundleType.FEATURE_PACK,
        canonical_json=canonical,
        hash=compute_hash(canonical),
        severity=BUNDLE_SEVERITY[BundleType.FEATURE_PACK],
    )


def build_broker_policy_manifest(
    allowed_brokers: dict[str, frozenset[str] | set[str] | list[str]],
    forbidden_brokers: frozenset[str] | set[str] | list[str],
) -> BundleManifest:
    """Build canonical Broker Policy Bundle manifest.

    Included fields:
      allowed_brokers (sorted keys, sorted values), forbidden_brokers (sorted)
    """
    payload: dict[str, Any] = {
        "allowed_brokers": {k: sorted(v) for k, v in sorted(allowed_brokers.items())},
        "forbidden_brokers": sorted(forbidden_brokers),
    }
    canonical = _canonicalize(payload)
    return BundleManifest(
        bundle_type=BundleType.BROKER_POLICY,
        canonical_json=canonical,
        hash=compute_hash(canonical),
        severity=BUNDLE_SEVERITY[BundleType.BROKER_POLICY],
    )


def build_risk_limit_manifest(
    exposure_limits: dict[str, int | float],
) -> BundleManifest:
    """Build canonical Risk Limit Bundle manifest.

    Included fields:
      All exposure limit keys (sorted), values as-is.
    """
    payload = dict(sorted(exposure_limits.items()))
    canonical = _canonicalize(payload)
    return BundleManifest(
        bundle_type=BundleType.RISK_LIMIT,
        canonical_json=canonical,
        hash=compute_hash(canonical),
        severity=BUNDLE_SEVERITY[BundleType.RISK_LIMIT],
    )
