# Sprint Contract: CARD-2026-0330-DECISION-BOARD-VISUAL

> **Level**: B (Implementation)
> **Date**: 2026-03-30
> **Status**: B-COMPLETE, C-PENDING

---

## Goal

Transform raw `decision_summary` dict into structured visualization elements
(PostureBadge, RiskBadge, ReasonCompact, SafetyBar, DecisionCard) for
immediate dashboard rendering. Presentation layer only — no new computation.

## Scope

| Included | Excluded |
|----------|----------|
| PostureBadge (posture + severity) | Execution buttons / auto-action |
| RiskBadge (risk + severity) | State transitions |
| ReasonCompact (max 3 lines) | Write path connections |
| SafetyBar (3 fixed labels) | Decision logic changes |
| DecisionCard (unified card) | observation_summary changes |
| Board integration | Sealed file modifications |
| 36 tests / 6 axes | |

## Files Changed

| File | Change |
|------|--------|
| `app/schemas/decision_card_schema.py` | **NEW** — PostureBadge, RiskBadge, ReasonCompact, SafetyBar, DecisionCard |
| `app/services/decision_card_service.py` | **NEW** — build_decision_card() |
| `app/schemas/four_tier_board_schema.py` | Added decision_card field |
| `app/services/four_tier_board_service.py` | Added build_decision_card() call |
| `tests/test_decision_card.py` | **NEW** — 36 tests, 6 axes |

## Safety Verification

| Check | Result |
|-------|--------|
| action_allowed=True in source | NOT FOUND |
| write method calls | NOT FOUND |
| _TRANSITIONS change | NOT FOUND |
| Sealed file modification | NOT FOUND |
| action verbs in labels | NOT FOUND |
| New regression | 0 |

## Test Summary

| AXIS | Tests | Description |
|------|-------|-------------|
| 1 | 7 | PostureBadge accuracy (4 posture → 4 severity) |
| 2 | 5 | RiskBadge accuracy (3 risk → 3 severity) |
| 3 | 6 | ReasonCompact (3-line limit, truncation) |
| 4 | 7 | SafetyBar fixed values + source verification |
| 5 | 6 | DecisionCard integration + serialization |
| 6 | 5 | Board integration + backward compatibility |
| **Total** | **36** | |

## Full Suite

- **2626 PASS, 12 FAIL** (pre-existing: b14/c13/ops_checks)
- New regression: **0**
- This change related failures: **0**
