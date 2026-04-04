"""Bundle Fingerprint Calculator — canonical artifact integrity hashing.

Phase 5B of CR-048.  Computes deterministic SHA-256 fingerprints for:
  - Strategy bundles (code module + version + parameters)
  - Feature Pack bundles (indicator composition + weights + version)
  - Combined strategy+feature_pack fingerprint for load verification

Canonical serialization: sorted JSON keys, no whitespace, UTF-8 encoded.
This ensures identical logical content always produces identical hashes.
"""

from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger(__name__)


def canonical_json(data: dict) -> str:
    """Produce deterministic JSON string for hashing.

    Rules:
      - Keys sorted recursively
      - No whitespace
      - Ensure_ascii=False for Unicode stability
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(content: str) -> str:
    """SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ── Strategy Bundle Fingerprint ────────────────────────────────────────


def compute_strategy_fingerprint(
    *,
    compute_module: str,
    version: str,
    asset_classes: str | list,
    exchanges: str | list,
    sectors: str | list | None,
    timeframes: str | list,
    max_symbols: int,
    extra: dict | None = None,
) -> str:
    """Compute canonical fingerprint for a strategy bundle.

    Inputs are the strategy's identity-defining fields.
    JSON-encoded fields (asset_classes, exchanges, etc.) are parsed first.
    """

    def _parse(val):
        if val is None:
            return None
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    payload = {
        "compute_module": compute_module,
        "version": version,
        "asset_classes": sorted(_parse(asset_classes) or []),
        "exchanges": sorted(_parse(exchanges) or []),
        "sectors": sorted(_parse(sectors) or []),
        "timeframes": sorted(_parse(timeframes) or []),
        "max_symbols": max_symbols,
    }
    if extra:
        payload["extra"] = extra

    return sha256_hex(canonical_json(payload))


# ── Feature Pack Bundle Fingerprint ────────────────────────────────────


def compute_feature_pack_fingerprint(
    *,
    name: str,
    version: str,
    indicator_ids: str | list,
    weights: str | dict | None,
) -> str:
    """Compute canonical fingerprint for a feature pack bundle.

    Inputs are the feature pack's identity-defining fields.
    """

    def _parse(val):
        if val is None:
            return None
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    parsed_ids = _parse(indicator_ids) or []
    parsed_weights = _parse(weights)

    payload = {
        "name": name,
        "version": version,
        "indicator_ids": sorted(parsed_ids),
        "weights": parsed_weights,
    }

    return sha256_hex(canonical_json(payload))


# ── Combined Load Fingerprint ──────────────────────────────────────────


def compute_load_fingerprint(
    strategy_fingerprint: str,
    feature_pack_fingerprint: str,
) -> str:
    """Combine strategy + feature pack fingerprints into a single load fingerprint.

    This is what the runtime loader verifies: if either component changes,
    the combined fingerprint changes.
    """
    combined = canonical_json(
        {
            "strategy": strategy_fingerprint,
            "feature_pack": feature_pack_fingerprint,
        }
    )
    return sha256_hex(combined)


# ── Convenience: compute from model objects ────────────────────────────


def fingerprint_from_strategy(strategy) -> str:
    """Compute strategy fingerprint from a Strategy model instance."""
    return compute_strategy_fingerprint(
        compute_module=strategy.compute_module,
        version=strategy.version,
        asset_classes=strategy.asset_classes,
        exchanges=strategy.exchanges,
        sectors=strategy.sectors,
        timeframes=strategy.timeframes,
        max_symbols=strategy.max_symbols,
    )


def fingerprint_from_feature_pack(feature_pack) -> str:
    """Compute feature pack fingerprint from a FeaturePack model instance."""
    return compute_feature_pack_fingerprint(
        name=feature_pack.name,
        version=feature_pack.version,
        indicator_ids=feature_pack.indicator_ids,
        weights=feature_pack.weights,
    )
