"""
CR-048 Observatory — Read-only observation API for CR-048 design contracts.

L2 scope: read-only, no write paths, no DB mutations, no service logic.
Exposes design document contracts, policy matrices, and promotion state
definitions as observable endpoints for dashboard/operator consumption.

All data is derived from:
- Design documents (Phase 0 + Phase 1)
- ops_state.json (file-backed, A-only edits)
- test_cr048_design_contracts.py contract constants

Source of truth for each response is explicitly tagged.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

# ── Governance State File (read-only) ────────────────────────────────
_OPS_STATE_PATH = Path(__file__).resolve().parents[3] / "ops_state.json"


def _read_ops_state() -> dict:
    """Read ops_state.json. Returns empty dict on error."""
    try:
        return json.loads(_OPS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════
# Contract Constants — single source of truth for CR-048 design
# Mirror of tests/test_cr048_design_contracts.py constants
# ═══════════════════════════════════════════════════════════════════════

_FORBIDDEN_BROKERS = frozenset({"ALPACA", "KIWOOM_US"})

_ALLOWED_BROKERS = {
    "CRYPTO": sorted(["BINANCE", "BITGET", "UPBIT"]),
    "US_STOCK": ["KIS_US"],
    "KR_STOCK": sorted(["KIS_KR", "KIWOOM_KR"]),
}

_FORBIDDEN_SECTORS = frozenset(
    {
        "MEME",
        "GAMEFI",
        "LOW_LIQUIDITY_NEW_TOKEN",
        "HIGH_VALUATION_PURE_SW",
        "WEAK_CONSUMER_BETA",
        "OIL_SENSITIVE",
        "LOW_LIQUIDITY_THEME",
    }
)

_ALLOWED_SECTORS = {
    "CRYPTO": sorted(["LAYER1", "DEFI", "AI", "INFRA"]),
    "US_STOCK": sorted(["TECH", "HEALTHCARE", "ENERGY", "FINANCE"]),
    "KR_STOCK": sorted(["SEMICONDUCTOR", "IT", "FINANCE_KR", "AUTO"]),
}

_TRADING_HOURS = {
    "BINANCE": {"type": "24_7"},
    "BITGET": {"type": "24_7"},
    "UPBIT": {"type": "24_7"},
    "KIS_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIWOOM_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIS_US": {"type": "weekday", "tz": "US/Eastern", "open": "09:30", "close": "16:00"},
}

_PROMOTION_STATES = [
    "DRAFT",
    "REGISTERED",
    "BACKTEST_PASS",
    "BACKTEST_FAIL",
    "PAPER_PASS",
    "QUARANTINE",
    "GUARDED_LIVE",
    "LIVE",
    "RETIRED",
    "BLOCKED",
]

_VALID_TRANSITIONS = {
    "DRAFT": ["REGISTERED"],
    "REGISTERED": ["BACKTEST_PASS", "BACKTEST_FAIL"],
    "BACKTEST_FAIL": ["REGISTERED"],
    "BACKTEST_PASS": ["PAPER_PASS", "BACKTEST_FAIL"],
    "PAPER_PASS": ["GUARDED_LIVE"],
    "GUARDED_LIVE": ["LIVE", "QUARANTINE"],
    "LIVE": ["QUARANTINE", "RETIRED"],
    "QUARANTINE": ["GUARDED_LIVE", "BLOCKED"],
    "RETIRED": [],
    "BLOCKED": [],
}

_REQUIRES_APPROVAL = {
    "PAPER_PASS → GUARDED_LIVE": "APPROVER",
    "GUARDED_LIVE → LIVE": "APPROVER",
    "QUARANTINE → GUARDED_LIVE": "APPROVER",
    "QUARANTINE → BLOCKED": "APPROVER",
    "LIVE → RETIRED": "APPROVER",
}

_STRATEGY_BANKS = {
    "Research": {"states": ["DRAFT", "REGISTERED"], "description": "연구 중"},
    "Qualified": {"states": ["BACKTEST_PASS"], "description": "백테스트 통과"},
    "Paper": {"states": ["PAPER_PASS"], "description": "Paper Shadow 통과"},
    "Quarantine": {"states": ["QUARANTINE"], "description": "이상 징후 격리"},
    "Live": {"states": ["GUARDED_LIVE", "LIVE"], "description": "실전 운영"},
    "Retired": {"states": ["RETIRED"], "description": "정상 은퇴"},
    "Blocked": {"states": ["BLOCKED"], "description": "영구 차단"},
}

_EXPOSURE_CAPS = {
    "market_active_strategies": {"max": 5, "unit": "per market"},
    "symbol_concurrent_strategies": {"max": 3, "unit": "per symbol"},
    "strategy_symbol_concurrent": {"max": 30, "unit": "total"},
    "market_total_symbols": {"max": 20, "unit": "per market"},
    "theme_symbols": {"max": 5, "unit": "per theme"},
    "single_symbol_capital_pct": {"max": 10, "unit": "%"},
    "single_theme_capital_pct": {"max": 25, "unit": "%"},
    "single_market_capital_pct": {"max": 50, "unit": "%"},
}

_GATEWAY_CHECKS = [
    {"step": 1, "check": "forbidden_broker", "fail_code": "FORBIDDEN_BROKER"},
    {"step": 2, "check": "forbidden_sector", "fail_code": "FORBIDDEN_SECTOR"},
    {"step": 3, "check": "dependency_verification", "fail_code": "MISSING_DEPENDENCY"},
    {"step": 4, "check": "version_checksum", "fail_code": "VERSION_MISMATCH"},
    {"step": 5, "check": "manifest_signature", "fail_code": "SIGNATURE_INVALID"},
    {"step": 6, "check": "market_matrix_compatibility", "fail_code": "MATRIX_INCOMPATIBLE"},
]

_INDICATOR_CATALOG = [
    {
        "name": "RSI",
        "category": "MOMENTUM",
        "warmup_bars": 14,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {
        "name": "MACD",
        "category": "MOMENTUM",
        "warmup_bars": 34,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {
        "name": "Bollinger Bands",
        "category": "VOLATILITY",
        "warmup_bars": 20,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {
        "name": "ATR",
        "category": "VOLATILITY",
        "warmup_bars": 14,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {"name": "OBV", "category": "VOLUME", "warmup_bars": 1, "status": "DESIGN", "cr_ref": "CR-038"},
    {
        "name": "SMA",
        "category": "TREND",
        "warmup_bars": 200,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {
        "name": "EMA",
        "category": "TREND",
        "warmup_bars": 200,
        "status": "DESIGN",
        "cr_ref": "CR-038",
    },
    {
        "name": "WaveTrend",
        "category": "OSCILLATOR",
        "warmup_bars": 21,
        "status": "DESIGN",
        "cr_ref": "CR-046",
    },
    {
        "name": "ADX",
        "category": "TREND",
        "warmup_bars": 14,
        "status": "DESIGN",
        "cr_ref": "PLANNED",
    },
    {
        "name": "VWAP",
        "category": "VOLUME",
        "warmup_bars": 1,
        "status": "DESIGN",
        "cr_ref": "PLANNED",
    },
]

_FEATURE_PACK_CATALOG = [
    {
        "name": "trend_pack_v1",
        "indicators": ["EMA200", "ADX14", "ATR14"],
        "target_strategy": "Momentum",
        "status": "DESIGN",
    },
    {
        "name": "oscillator_pack_v1",
        "indicators": ["RSI14", "MACD", "WaveTrend"],
        "target_strategy": "SMC+WaveTrend",
        "status": "DESIGN",
    },
    {
        "name": "mean_rev_pack_v1",
        "indicators": ["BB20", "RSI14", "ATR14"],
        "target_strategy": "Mean Reversion",
        "status": "DESIGN",
    },
    {
        "name": "volume_pack_v1",
        "indicators": ["OBV", "VWAP"],
        "target_strategy": "shared",
        "status": "DESIGN",
    },
]

_STRATEGY_CATALOG = [
    {
        "name": "SMC+WaveTrend",
        "asset_classes": ["CRYPTO"],
        "exchanges": ["BINANCE", "BITGET"],
        "regime": "추세",
        "status": "DESIGN",
    },
    {
        "name": "RSI Cross",
        "asset_classes": ["CRYPTO", "US_STOCK", "KR_STOCK"],
        "exchanges": ["ALL_ALLOWED"],
        "regime": "전체",
        "status": "DESIGN",
    },
    {
        "name": "Mean Reversion",
        "asset_classes": ["US_STOCK", "KR_STOCK"],
        "exchanges": ["KIS_US", "KIS_KR"],
        "regime": "횡보",
        "status": "DESIGN",
    },
    {
        "name": "Momentum",
        "asset_classes": ["US_STOCK", "KR_STOCK"],
        "exchanges": ["KIS_US", "KIS_KR"],
        "regime": "상승",
        "status": "DESIGN",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Endpoints — all GET, all read-only
# ═══════════════════════════════════════════════════════════════════════


@router.get("/registry/indicators")
async def get_indicator_registry():
    """
    CR-048 Indicator Registry — design catalog.

    Returns planned indicators from design_indicator_registry.md.
    All items are in DESIGN status (not yet implemented).
    """
    return {
        "source_of_truth": "design_document",
        "document": "docs/architecture/design_indicator_registry.md",
        "cr_ref": "CR-048 Phase 1",
        "scope": "L2 read-only observation",
        "total": len(_INDICATOR_CATALOG),
        "items": _INDICATOR_CATALOG,
        "categories": sorted({i["category"] for i in _INDICATOR_CATALOG}),
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/registry/feature-packs")
async def get_feature_pack_registry():
    """
    CR-048 Feature Pack Registry — design catalog.

    Returns planned feature packs from design_feature_pack.md.
    All items are in DESIGN status.
    """
    return {
        "source_of_truth": "design_document",
        "document": "docs/architecture/design_feature_pack.md",
        "cr_ref": "CR-048 Phase 1",
        "scope": "L2 read-only observation",
        "total": len(_FEATURE_PACK_CATALOG),
        "items": _FEATURE_PACK_CATALOG,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/registry/strategies")
async def get_strategy_registry():
    """
    CR-048 Strategy Registry — design catalog.

    Returns planned strategies from design_strategy_registry.md.
    All items are in DESIGN status.
    """
    return {
        "source_of_truth": "design_document",
        "document": "docs/architecture/design_strategy_registry.md",
        "cr_ref": "CR-048 Phase 1",
        "scope": "L2 read-only observation",
        "total": len(_STRATEGY_CATALOG),
        "items": _STRATEGY_CATALOG,
        "strategy_banks": _STRATEGY_BANKS,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/promotion-states")
async def get_promotion_states():
    """
    CR-048 Promotion State — state machine definition.

    Returns the 10-state promotion model, valid transitions,
    approval requirements, and bank classification.
    """
    return {
        "source_of_truth": "design_document",
        "document": "docs/architecture/design_promotion_state.md",
        "cr_ref": "CR-048 Phase 1",
        "scope": "L2 read-only observation",
        "states": _PROMOTION_STATES,
        "state_count": len(_PROMOTION_STATES),
        "valid_transitions": _VALID_TRANSITIONS,
        "requires_approval": _REQUIRES_APPROVAL,
        "terminal_states": [s for s, t in _VALID_TRANSITIONS.items() if not t],
        "strategy_banks": _STRATEGY_BANKS,
        "bank_count": len(_STRATEGY_BANKS),
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/injection-policy-summary")
async def get_injection_policy_summary():
    """
    CR-048 Injection Policy Summary — consolidated view.

    Aggregates broker matrix, exclusion baseline, gateway checks,
    exposure caps, and governance state into a single observation.
    """
    gov = _read_ops_state()
    release_info = gov.get("release_info", {})

    return {
        "source_of_truth": "policy_matrix",
        "documents": [
            "docs/architecture/injection_constitution.md",
            "docs/architecture/broker_matrix.md",
            "docs/architecture/exclusion_baseline.md",
        ],
        "cr_ref": "CR-048 Phase 0",
        "scope": "L2 read-only observation",
        "broker_matrix": {
            "allowed_brokers": _ALLOWED_BROKERS,
            "forbidden_brokers": sorted(_FORBIDDEN_BROKERS),
            "trading_hours": _TRADING_HOURS,
        },
        "exclusion_baseline": {
            "forbidden_sectors": sorted(_FORBIDDEN_SECTORS),
            "forbidden_sector_count": len(_FORBIDDEN_SECTORS),
            "allowed_sectors": _ALLOWED_SECTORS,
            "symbol_states": sorted(["CORE", "WATCH", "EXCLUDED"]),
        },
        "gateway_checks": _GATEWAY_CHECKS,
        "exposure_caps": _EXPOSURE_CAPS,
        "governance_state": {
            "source_of_truth": "ops_state",
            "operational_mode": gov.get("operational_mode", "UNKNOWN"),
            "gate_status": release_info.get("gate_status", "UNKNOWN"),
            "allowed_scope": release_info.get("allowed_scope", []),
            "blocked_scope": release_info.get("blocked_scope", []),
            "prohibitions": gov.get("prohibitions", []),
            "rules": gov.get("rules", []),
        },
        "paper_shadow_min_days": 14,
        "llm_live_path": "PERMANENTLY_FORBIDDEN",
        "ai_execution_judgment": "PERMANENTLY_FORBIDDEN",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
