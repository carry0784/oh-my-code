"""
Operational Visibility — Exchange Mode, Beat Tasks, Blocked Reason Codes,
Governance State.

CR-049 Phase 2 follow-up: read-only ops status for dashboard/operator consumption.
No state mutation. No recovery action. Observation only.

Governance state is file-backed (ops_state.json). Only A may edit the file.
This module exposes it read-only via API.
"""

import json
from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings
from exchanges.base import ExchangeMode

router = APIRouter()

# ── Governance State File (read-only source of truth) ──────────────
_OPS_STATE_PATH = Path(__file__).resolve().parents[3] / "ops_state.json"


# ── API Permission Matrix (CR-049 contract) ────────────────────────
_API_MATRIX = {
    "fetch_ticker": {ExchangeMode.DATA_ONLY, ExchangeMode.PAPER, ExchangeMode.LIVE},
    "fetch_ohlcv": {ExchangeMode.DATA_ONLY, ExchangeMode.PAPER, ExchangeMode.LIVE},
    "fetch_balance": {ExchangeMode.PAPER, ExchangeMode.LIVE},
    "fetch_positions": {ExchangeMode.PAPER, ExchangeMode.LIVE},
    "fetch_order": {ExchangeMode.PAPER, ExchangeMode.LIVE},
    "cancel_order": {ExchangeMode.PAPER, ExchangeMode.LIVE},
    "create_order": {ExchangeMode.LIVE},
}

# ── Beat Task Registry (source of truth for task visibility) ───────
# Each entry: task_name → { status, reason_code, cr_ref, requires_mode }
_BEAT_TASKS = [
    {
        "task": "workers.tasks.data_collection_tasks.collect_market_state",
        "schedule_label": "collect-market-state-every-5m (BTC)",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-038",
        "requires_mode": "DATA_ONLY",
    },
    {
        "task": "workers.tasks.data_collection_tasks.collect_market_state",
        "schedule_label": "collect-sol-market-state-every-5m (SOL)",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-046",
        "requires_mode": "DATA_ONLY",
    },
    {
        "task": "workers.tasks.signal_tasks.expire_signals",
        "schedule_label": "expire-old-signals",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": None,
        "requires_mode": None,  # DB only
    },
    {
        "task": "workers.tasks.snapshot_tasks.record_asset_snapshot",
        "schedule_label": "record-asset-snapshot-every-5m",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": None,
        "requires_mode": None,  # DB only
    },
    {
        "task": "workers.tasks.data_collection_tasks.collect_sentiment_only",
        "schedule_label": "collect-sentiment-hourly",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-038",
        "requires_mode": None,  # external API, not exchange
    },
    {
        "task": "workers.tasks.check_tasks.run_daily_ops_check",
        "schedule_label": "ops-daily-check",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "S-02",
        "requires_mode": None,
    },
    {
        "task": "workers.tasks.check_tasks.run_hourly_ops_check",
        "schedule_label": "ops-hourly-check",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "S-02",
        "requires_mode": None,
    },
    {
        "task": "workers.tasks.governance_monitor_tasks.run_daily_governance_report",
        "schedule_label": "governance-monitor-daily",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "G-MON",
        "requires_mode": None,
    },
    {
        "task": "workers.tasks.governance_monitor_tasks.run_weekly_governance_summary",
        "schedule_label": "governance-monitor-weekly",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "G-MON",
        "requires_mode": None,
    },
    {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule_label": "strategy-cycle-crypto-5m",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-048",
        "requires_mode": "DATA_ONLY",
    },
    {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule_label": "strategy-cycle-kr-stock-5m",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-048",
        "requires_mode": "DATA_ONLY",
    },
    {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule_label": "strategy-cycle-us-stock-5m",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-048",
        "requires_mode": "DATA_ONLY",
    },
    # ── DISABLED tasks ──
    {
        "task": "workers.tasks.market_tasks.sync_all_positions",
        "schedule_label": "sync-positions-every-minute",
        "status": "DISABLED",
        "reason_code": "REQUIRES_PRIVATE_API",
        "cr_ref": "CR-049",
        "requires_mode": "PAPER",
    },
    {
        "task": "workers.tasks.order_tasks.check_pending_orders",
        "schedule_label": "check-order-status-every-30s",
        "status": "DISABLED",
        "reason_code": "REQUIRES_PRIVATE_API",
        "cr_ref": "CR-049",
        "requires_mode": "PAPER",
    },
    {
        "task": "workers.tasks.sol_paper_tasks.run_sol_paper_bar",
        "schedule_label": "sol-paper-trading-hourly",
        "status": "ACTIVE",
        "reason_code": None,
        "cr_ref": "CR-046",
        "requires_mode": "PAPER",  # dry_run=True hardcoded, observation only
    },
]

# ── Blocked Reason Codes ───────────────────────────────────────────
_REASON_CODES = {
    "REQUIRES_PRIVATE_API": (
        "Task calls private/write exchange API (fetch_positions, fetch_order, etc.) "
        "which is blocked in DATA_ONLY mode. Re-enable when exchange_mode is PAPER or LIVE."
    ),
    "CR046_STAGE_B_HOLD": (
        "SOL paper trading is on HOLD pending Binance testnet recovery "
        "and Stage B activation conditions (CR-046)."
    ),
    "BINANCE_TESTNET_DEPRECATED": (
        "Binance futures testnet is officially deprecated (NotSupported). "
        "Spot testnet public endpoints work but private requires separate testnet keys."
    ),
}


def _resolve_mode() -> ExchangeMode:
    """Resolve current exchange mode from settings."""
    try:
        return ExchangeMode(settings.exchange_mode)
    except ValueError:
        return ExchangeMode.DATA_ONLY


@router.get("/exchange-mode")
async def get_exchange_mode():
    """
    Exchange Mode Contract (BL-EXMODE01) status.

    Returns:
      - current mode
      - API permission matrix (allowed/blocked per operation)
      - adapter list with mode enforcement status
    """
    mode = _resolve_mode()

    api_permissions = {}
    for api_name, allowed_modes in _API_MATRIX.items():
        api_permissions[api_name] = {
            "allowed": mode in allowed_modes,
            "required_modes": sorted([m.value for m in allowed_modes]),
        }

    adapters = ["binance", "bitget", "upbit", "kis", "kiwoom"]

    return {
        "exchange_mode": mode.value,
        "contract": "BL-EXMODE01",
        "cr_ref": "CR-049",
        "description": {
            "DATA_ONLY": "Public market data only. Private/write/futures blocked at adapter level.",
            "PAPER": "Public + private read + simulated execution. (Not yet implemented)",
            "LIVE": "Full access. Requires A approval. (Not yet implemented)",
        }[mode.value],
        "api_permissions": api_permissions,
        "adapters": [
            {"name": name, "guard": "_require_mode()", "enforcement": "adapter-level"}
            for name in adapters
        ],
        "binance_testnet_deprecated": True,
        "sandbox_mode_active": mode != ExchangeMode.DATA_ONLY and settings.binance_testnet,
    }


@router.get("/beat-tasks")
async def get_beat_tasks():
    """
    Beat task registry with status, reason codes, and mode requirements.

    Returns all registered beat tasks with their current operational state.
    """
    mode = _resolve_mode()

    active_count = sum(1 for t in _BEAT_TASKS if t["status"] == "ACTIVE")
    disabled_count = sum(1 for t in _BEAT_TASKS if t["status"] == "DISABLED")

    return {
        "exchange_mode": mode.value,
        "summary": {
            "total": len(_BEAT_TASKS),
            "active": active_count,
            "disabled": disabled_count,
        },
        "tasks": _BEAT_TASKS,
        "reason_codes": _REASON_CODES,
    }


@router.get("/blocked-operations")
async def get_blocked_operations():
    """
    List all operations currently blocked by exchange_mode policy.

    Combines API-level blocks and task-level blocks into a single view.
    """
    mode = _resolve_mode()

    blocked_apis = []
    for api_name, allowed_modes in _API_MATRIX.items():
        if mode not in allowed_modes:
            blocked_apis.append(
                {
                    "operation": api_name,
                    "blocked_by": f"exchange_mode={mode.value}",
                    "required_modes": sorted([m.value for m in allowed_modes]),
                    "exception": "OperationNotPermitted",
                    "enforcement": "adapter-level _require_mode() guard",
                }
            )

    blocked_tasks = []
    for task in _BEAT_TASKS:
        if task["status"] == "DISABLED":
            blocked_tasks.append(
                {
                    "task": task["task"],
                    "schedule_label": task["schedule_label"],
                    "reason_code": task["reason_code"],
                    "reason_detail": _REASON_CODES.get(task["reason_code"], "Unknown"),
                    "cr_ref": task["cr_ref"],
                    "re_enable_when": task["requires_mode"],
                }
            )

    return {
        "exchange_mode": mode.value,
        "blocked_api_count": len(blocked_apis),
        "blocked_task_count": len(blocked_tasks),
        "blocked_apis": blocked_apis,
        "blocked_tasks": blocked_tasks,
    }


def _load_ops_state() -> dict:
    """Load governance state from ops_state.json. Read-only. Fail-closed."""
    try:
        with open(_OPS_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {
            "operational_mode": "UNKNOWN",
            "description": "ops_state.json not found or unreadable",
            "error": True,
        }


@router.get("/governance-state")
async def get_governance_state():
    """
    Governance state — read-only exposure of ops_state.json.

    This file is the source of truth for operational mode,
    sealed CRs, open issues, prohibitions, and baseline values.
    Only A may edit the file directly. No write API exists.
    """
    return _load_ops_state()


# ── Baseline Drift Check (자동 기준선 점검) ─────────────────────────────


@router.get("/baseline-check")
async def baseline_drift_check():
    """
    Automated baseline drift check — measures all 6 observation items
    against expected baseline values from ops_state.json.

    Read-only. No state mutation. No recovery action.

    Returns:
      drift_status: "HOLD" | "SOFT_DRIFT" | "HARD_DRIFT"
      checks: list of { item, expected, actual, match, drift_type }
      summary: { total, passed, failed, hard_drift_count, soft_drift_count }
      measured_at: ISO timestamp
    """
    from datetime import datetime, timezone

    gov = _load_ops_state()
    baseline = gov.get("baseline_values", {})
    mode = _resolve_mode()

    checks = []

    # ── Check 1: operational_mode ──
    # Accept both BASELINE_HOLD and GUARDED_RELEASE as valid governed modes
    _VALID_GOVERNED_MODES = {"BASELINE_HOLD", "GUARDED_RELEASE"}
    actual_op_mode = gov.get("operational_mode", "UNKNOWN")
    expected_op_mode = (
        actual_op_mode if actual_op_mode in _VALID_GOVERNED_MODES else "BASELINE_HOLD"
    )
    match_op = actual_op_mode == expected_op_mode
    checks.append(
        {
            "item": "operational_mode",
            "source": "/api/v1/ops/governance-state",
            "expected": expected_op_mode,
            "actual": actual_op_mode,
            "match": match_op,
            "drift_type": None if match_op else "HARD",
        }
    )

    # ── Check 2: exchange_mode ──
    expected_ex_mode = baseline.get("exchange_mode", "DATA_ONLY")
    actual_ex_mode = mode.value
    match_ex = actual_ex_mode == expected_ex_mode
    checks.append(
        {
            "item": "exchange_mode",
            "source": "settings.exchange_mode + ExchangeMode enum",
            "expected": expected_ex_mode,
            "actual": actual_ex_mode,
            "match": match_ex,
            "drift_type": None if match_ex else "HARD",
        }
    )

    # ── Check 3: blocked_api_count ──
    expected_blocked = baseline.get("blocked_api_count", 5)
    actual_blocked = sum(1 for _, allowed_modes in _API_MATRIX.items() if mode not in allowed_modes)
    match_blocked = actual_blocked == expected_blocked
    checks.append(
        {
            "item": "blocked_api_count",
            "source": "/api/v1/ops/blocked-operations",
            "expected": expected_blocked,
            "actual": actual_blocked,
            "match": match_blocked,
            "drift_type": None if match_blocked else "HARD",
        }
    )

    # ── Check 4: disabled_beat_tasks ──
    expected_disabled = baseline.get("disabled_beat_tasks", 2)
    actual_disabled = sum(1 for t in _BEAT_TASKS if t["status"] == "DISABLED")
    match_disabled = actual_disabled == expected_disabled
    checks.append(
        {
            "item": "disabled_beat_tasks",
            "source": "_BEAT_TASKS registry",
            "expected": expected_disabled,
            "actual": actual_disabled,
            "match": match_disabled,
            "drift_type": None if match_disabled else "HARD",
        }
    )

    # ── Check 5: forbidden tasks not in beat schedule ──
    from workers.celery_app import celery_app

    schedule_keys = set(celery_app.conf.beat_schedule.keys())
    forbidden_keys = [
        "sync-positions-every-minute",
        "check-order-status-every-30s",
        "sol-paper-trading-hourly",
    ]
    leaked = [k for k in forbidden_keys if k in schedule_keys]
    match_forbidden = len(leaked) == 0
    checks.append(
        {
            "item": "forbidden_beat_tasks_absent",
            "source": "celery_app.conf.beat_schedule",
            "expected": "0 forbidden keys in schedule",
            "actual": f"{len(leaked)} found" + (f": {leaked}" if leaked else ""),
            "match": match_forbidden,
            "drift_type": None if match_forbidden else "HARD",
        }
    )

    # ── Check 6: startup log consistency (code-level) ──
    # Verify that lifespan and celery fingerprint both emit operational_mode
    import inspect
    from app.main import lifespan
    from workers.celery_app import _startup_fingerprint

    lifespan_src = inspect.getsource(lifespan)
    fingerprint_src = inspect.getsource(_startup_fingerprint)
    lifespan_has = "governance_state_loaded" in lifespan_src and "operational_mode" in lifespan_src
    fingerprint_has = "operational_mode" in fingerprint_src
    match_logs = lifespan_has and fingerprint_has
    checks.append(
        {
            "item": "startup_log_consistency",
            "source": "lifespan + _startup_fingerprint source inspection",
            "expected": "both emit operational_mode",
            "actual": f"lifespan={lifespan_has}, fingerprint={fingerprint_has}",
            "match": match_logs,
            "drift_type": None if match_logs else "SOFT",
        }
    )

    # ── Summary ──
    passed = sum(1 for c in checks if c["match"])
    failed = len(checks) - passed
    hard_count = sum(1 for c in checks if c["drift_type"] == "HARD")
    soft_count = sum(1 for c in checks if c["drift_type"] == "SOFT")

    if hard_count > 0:
        drift_status = "HARD_DRIFT"
    elif soft_count > 0:
        drift_status = "SOFT_DRIFT"
    else:
        drift_status = "HOLD"

    return {
        "drift_status": drift_status,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "hard_drift_count": hard_count,
            "soft_drift_count": soft_count,
        },
        "checks": checks,
        "baseline_source": "ops_state.json",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Change Gate (변경 재진입 Gate 상태 조회) ──────────────────────────────

# L0~L4 위험도 등급: 파일 경로 패턴 → 기본 등급
_PATH_RISK_MAP = [
    # (glob pattern prefix, default level, description)
    ("docs/", "L0", "문서/증빙"),
    ("CLAUDE.md", "L0", "문서/증빙"),
    ("tests/", "L1", "테스트 전용"),
    ("app/api/routes/ops.py", "L2-L3", "관측/런타임 (변경 내용에 따라)"),
    ("app/api/routes/dashboard", "L2", "관측 전용"),
    ("app/main.py", "L3", "런타임 영향 (lifespan)"),
    ("workers/celery_app.py", "L3-L4", "런타임/정책 (schedule/guard)"),
    ("ops_state.json", "L3", "런타임 영향 (A만 편집)"),
    ("exchanges/", "L4", "정책/실행 영향 (adapter guard)"),
    ("app/core/config.py", "L4", "정책/실행 영향 (mode/설정)"),
]


@router.get("/change-gate")
async def get_change_gate():
    """
    Change Re-entry Gate — current gate status for change control.

    Read-only. Reports whether changes are allowed, what approval is needed,
    and what risk levels are currently blocked.

    Returns:
      gate_status: "LOCKED" | "CONDITIONAL" | "OPEN"
      operational_mode: current mode from ops_state.json
      reentry_allowed: { L0..L4: true/false }
      approval_required: { L0..L4: description }
      blocked_reasons: [...] (why L3/L4 are locked)
      required_checks: [...] (what must pass before any change)
      path_risk_reference: [...] (file path → risk level mapping)
    """
    from datetime import datetime, timezone

    gov = _load_ops_state()
    op_mode = gov.get("operational_mode", "UNKNOWN")
    is_governed = op_mode in ("BASELINE_HOLD", "GUARDED_RELEASE")
    is_guarded_release = op_mode == "GUARDED_RELEASE"

    # Gate status determination
    if is_governed:
        gate_status = "LOCKED"  # L3/L4 blocked in both BASELINE_HOLD and GUARDED_RELEASE
    else:
        gate_status = "CONDITIONAL"  # all levels may proceed with approval

    # Per-level allowance — L2 allowed after 24h review approval (read from ops_state)
    _allowed = set(gov.get("release_info", {}).get("allowed_scope", ["L0", "L1"]))
    reentry_allowed = {
        "L0": True,
        "L1": True,
        "L2": "L2" in _allowed,  # governed by ops_state.json allowed_scope
        "L3": not is_governed,  # blocked during BASELINE_HOLD and GUARDED_RELEASE
        "L4": False,  # always requires explicit release + separate CR
    }

    # Per-level approval requirements
    approval_required = {
        "L0": "불필요 — 즉시 가능",
        "L1": "불필요 — 운영 영향 0 증명 시",
        "L2": "불필요 — 기준선 값 불변 보장 시"
        if "L2" in _allowed
        else "24시간 무-drift 후 재검토",
        "L3": "A 승인 필요",
        "L4": "별도 CR 필수",
    }

    # Blocked reasons
    blocked_reasons = []
    if is_governed:
        blocked_reasons.append(f"{op_mode} 상태: L3 변경은 A 승인 필요")
        blocked_reasons.append(f"{op_mode} 상태: L4 변경은 별도 CR 없이 금지")
        if "L2" not in _allowed:
            blocked_reasons.append("GUARDED_RELEASE: L2는 24시간 무-drift 후 재검토")
        for prohibition in gov.get("prohibitions", []):
            blocked_reasons.append(f"금지: {prohibition}")

    # Required checks before any change
    required_checks = [
        {
            "check": "baseline-check",
            "endpoint": "/api/v1/ops/baseline-check",
            "required_for": "L2+",
        },
        {
            "check": "회귀 테스트",
            "command": "pytest tests/test_ops_*.py tests/test_restart_drill.py",
            "required_for": "L1+",
        },
        {
            "check": "restart drill",
            "command": "pytest tests/test_restart_drill.py",
            "required_for": "L3+",
        },
        {
            "check": "Flower 감시",
            "description": "금지 3 task 미발송 확인",
            "required_for": "L3+ (schedule 변경 시)",
        },
        {
            "check": "전면 재검증",
            "description": "baseline-check + 회귀 + drill + adapter + Flower",
            "required_for": "L4",
        },
    ]

    return {
        "gate_status": gate_status,
        "operational_mode": op_mode,
        "reentry_allowed": reentry_allowed,
        "approval_required": approval_required,
        "blocked_reasons": blocked_reasons,
        "required_checks": required_checks,
        "path_risk_reference": [
            {"path": p, "level": l, "description": d} for p, l, d in _PATH_RISK_MAP
        ],
        "policy_doc": "docs/operations/change_gate_policy.md",
        "scope_matrix": "docs/operations/change_scope_matrix.md",
        "review_template": "docs/operations/change_reentry_review_template.md",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
