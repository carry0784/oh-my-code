"""
Mandatory Ledger — K-Dexter AOS v4

18 Mandatory items (M-01~M-18) with enforcement points.
Each item maps to a specific State/Gate enforcement point in the Main Loop.
See: docs/architecture/mandatory_enforcement_map.md

Static registry + runtime satisfaction checker.
Items are immutable — they are never added/removed at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from kdexter.state_machine.work_state import WorkStateContext


# ─────────────────────────────────────────────────────────────────────────── #
# Loop type (for exemption table)
# ─────────────────────────────────────────────────────────────────────────── #

class LoopType(Enum):
    MAIN = "MAIN"
    SELF_IMPROVEMENT = "SELF_IMPROVEMENT"
    EVOLUTION = "EVOLUTION"
    RECOVERY = "RECOVERY"


# ─────────────────────────────────────────────────────────────────────────── #
# Mandatory item
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class MandatoryItem:
    """One of 18 mandatory governance items."""
    item_id: str                              # "M-01" ~ "M-18"
    name: str                                 # short name
    description: str                          # what it enforces
    enforcement_state: Optional[str]          # WorkState where enforced (None = all)
    enforcement_gate: Optional[str]           # Gate ID (G-xx) if any
    validating_check_index: Optional[int]     # 1~10 index within VALIDATING, None if N/A
    responsible_layer: str                    # "L3", "L4", ...
    governance: str                           # "A", "B1", "B2"


# ─────────────────────────────────────────────────────────────────────────── #
# 18 items (from mandatory_enforcement_map.md Section 2)
# ─────────────────────────────────────────────────────────────────────────── #

_ALL_ITEMS: list[MandatoryItem] = [
    MandatoryItem("M-01", "clarify", "실행 전 의도 명확화",
                  "CLARIFYING", None, None, "L4", "B2"),
    MandatoryItem("M-02", "spec twin", "스펙 쌍 생성",
                  "SPEC_READY", None, None, "L4", "B2"),
    MandatoryItem("M-03", "risk check", "리스크 검사",
                  "PLANNING", "G-03", None, "L3", "B1"),
    MandatoryItem("M-04", "security check", "보안 검사",
                  "PLANNING", "G-04", None, "L3", "B1"),
    MandatoryItem("M-05", "rollback plan", "롤백 계획",
                  "PLANNING", "G-02", None, "L26", "A"),
    MandatoryItem("M-06", "recovery simulation", "복구 시뮬레이션",
                  "PLANNING", "G-02", None, "L26", "A"),
    MandatoryItem("M-07", "evidence", "모든 변경에 증거 첨부",
                  None, "G-05", None, "L10", "A"),
    MandatoryItem("M-08", "budget check", "예산 한도 확인",
                  "VALIDATING", "G-22", 7, "L29", "B2"),
    MandatoryItem("M-09", "compliance check", "준수율 검사",
                  "VALIDATING", "G-04", 3, "L13", "B2"),
    MandatoryItem("M-10", "provenance", "출처 기록",
                  None, "G-18", None, "L12", "B2"),
    MandatoryItem("M-11", "drift check", "의도 이탈 감지",
                  "VALIDATING", "G-19", 4, "L15", "B2"),
    MandatoryItem("M-12", "conflict check", "규칙 충돌 검사",
                  "VALIDATING", "G-20", 5, "L16", "B2"),
    MandatoryItem("M-13", "pattern check", "실패 패턴 대조",
                  "VALIDATING", "G-21", 6, "L17", "B2"),
    MandatoryItem("M-14", "trust refresh", "신뢰 상태 갱신",
                  "VALIDATING", "G-23", 8, "L19", "B2"),
    MandatoryItem("M-15", "loop health", "루프 건강 상태 확인",
                  "VALIDATING", "G-24", 9, "L28", "B2"),
    MandatoryItem("M-16", "completion check", "완성 검증",
                  "VERIFY", "G-25", None, "L21", "B2"),
    MandatoryItem("M-17", "spec lock check", "스펙 잠금 확인",
                  "VALIDATING", "G-26", 10, "L22", "B1"),
    MandatoryItem("M-18", "research", "변경 전 리서치",
                  "PLANNING", "G-27", None, "L23", "B2"),
]

_ITEM_MAP: dict[str, MandatoryItem] = {item.item_id: item for item in _ALL_ITEMS}


# ─────────────────────────────────────────────────────────────────────────── #
# Recovery Loop exemptions (mandatory_enforcement_map.md Section 4 표 기준)
# 문서 본문은 "8개"라고 했으나 표에는 10개 X. 표를 신뢰한다.
# ─────────────────────────────────────────────────────────────────────────── #

_RECOVERY_EXEMPTIONS: frozenset[str] = frozenset({
    "M-01",  # clarify — 긴급 복구, 의도 사전 확정
    "M-02",  # spec twin
    "M-05",  # rollback plan — 롤백 자체가 목적
    "M-06",  # recovery simulation
    "M-11",  # drift check — drift가 복구 원인일 수 있음
    "M-12",  # conflict check
    "M-13",  # pattern check
    "M-15",  # loop health — 루프 자체가 비정상 상태
    "M-17",  # spec lock check — Recovery는 Lock 우선 해제
    "M-18",  # research
})

# Self-Improvement, Evolution, Main: 모두 18개 전부 적용 (면제 없음)
_EXEMPTIONS: dict[LoopType, frozenset[str]] = {
    LoopType.MAIN: frozenset(),
    LoopType.SELF_IMPROVEMENT: frozenset(),
    LoopType.EVOLUTION: frozenset(),
    LoopType.RECOVERY: _RECOVERY_EXEMPTIONS,
}


# ─────────────────────────────────────────────────────────────────────────── #
# Satisfaction checker: M-xx → WorkStateContext field mapping
# ─────────────────────────────────────────────────────────────────────────── #

def _check_m01(ctx: WorkStateContext) -> bool:
    return bool(ctx.intent)

def _check_m02(ctx: WorkStateContext) -> bool:
    return bool(ctx.spec_twin_id)

def _check_m03(ctx: WorkStateContext) -> bool:
    return ctx.risk_checked

def _check_m04(ctx: WorkStateContext) -> bool:
    return ctx.security_checked

def _check_m05(ctx: WorkStateContext) -> bool:
    return ctx.rollback_plan_ready

def _check_m06(ctx: WorkStateContext) -> bool:
    return ctx.recovery_simulation_done

def _check_m07(ctx: WorkStateContext) -> bool:
    # M-07 is checked at EvidenceStore level, not WorkStateContext
    # Always True here — actual enforcement is in EvidenceStore + G-05
    return True

def _check_m08(ctx: WorkStateContext) -> bool:
    # Budget check done via VALIDATING [7] BUDGET_CHECK hook
    # No WorkStateContext field — always True at Ledger level
    return True

def _check_m09(ctx: WorkStateContext) -> bool:
    # Compliance check via VALIDATING [3] COMPLIANCE_CHECK hook
    return True

def _check_m10(ctx: WorkStateContext) -> bool:
    return ctx.provenance_recorded

def _check_m11(ctx: WorkStateContext) -> bool:
    # Drift check via VALIDATING [4] DRIFT_CHECK hook
    return True

def _check_m12(ctx: WorkStateContext) -> bool:
    # Conflict check via VALIDATING [5] CONFLICT_CHECK hook
    return True

def _check_m13(ctx: WorkStateContext) -> bool:
    # Pattern check via VALIDATING [6] PATTERN_CHECK hook
    return True

def _check_m14(ctx: WorkStateContext) -> bool:
    # Trust check via VALIDATING [8] TRUST_CHECK hook
    return True

def _check_m15(ctx: WorkStateContext) -> bool:
    # Loop check via VALIDATING [9] LOOP_CHECK hook
    return True

def _check_m16(ctx: WorkStateContext) -> bool:
    return ctx.completion_score >= ctx.completion_threshold

def _check_m17(ctx: WorkStateContext) -> bool:
    # Spec lock via VALIDATING [10] LOCK_CHECK hook
    return True

def _check_m18(ctx: WorkStateContext) -> bool:
    return ctx.research_complete


_CHECKERS: dict[str, callable] = {
    "M-01": _check_m01, "M-02": _check_m02, "M-03": _check_m03,
    "M-04": _check_m04, "M-05": _check_m05, "M-06": _check_m06,
    "M-07": _check_m07, "M-08": _check_m08, "M-09": _check_m09,
    "M-10": _check_m10, "M-11": _check_m11, "M-12": _check_m12,
    "M-13": _check_m13, "M-14": _check_m14, "M-15": _check_m15,
    "M-16": _check_m16, "M-17": _check_m17, "M-18": _check_m18,
}


# ─────────────────────────────────────────────────────────────────────────── #
# Mandatory Ledger
# ─────────────────────────────────────────────────────────────────────────── #

class MandatoryLedger:
    """
    Static registry of 18 mandatory governance items.
    Provides satisfaction checking against WorkStateContext.
    """

    def get_item(self, item_id: str) -> MandatoryItem:
        """Get a single mandatory item. Raises KeyError if not found."""
        return _ITEM_MAP[item_id]

    def get_all(self) -> list[MandatoryItem]:
        """Get all 18 mandatory items."""
        return list(_ALL_ITEMS)

    def is_exempt(self, item_id: str, loop_type: LoopType) -> bool:
        """Check if item is exempt for a given loop type."""
        return item_id in _EXEMPTIONS.get(loop_type, frozenset())

    def get_required_items(self, loop_type: LoopType) -> list[MandatoryItem]:
        """Get mandatory items required for a given loop type (excluding exemptions)."""
        exemptions = _EXEMPTIONS.get(loop_type, frozenset())
        return [item for item in _ALL_ITEMS if item.item_id not in exemptions]

    def check_satisfied(self, item_id: str, ctx: WorkStateContext) -> bool:
        """Check if a single mandatory item is satisfied in the current context."""
        checker = _CHECKERS.get(item_id)
        if checker is None:
            raise KeyError(f"No checker for {item_id}")
        return checker(ctx)

    def list_unsatisfied(
        self,
        loop_type: LoopType,
        ctx: WorkStateContext,
    ) -> list[MandatoryItem]:
        """List mandatory items that are NOT satisfied for the given loop type."""
        required = self.get_required_items(loop_type)
        return [item for item in required
                if not self.check_satisfied(item.item_id, ctx)]

    def all_satisfied(
        self,
        loop_type: LoopType,
        ctx: WorkStateContext,
    ) -> bool:
        """True if all required items for this loop type are satisfied."""
        return len(self.list_unsatisfied(loop_type, ctx)) == 0
