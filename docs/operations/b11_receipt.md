# B-11 Receipt — Governance Summary

## Status

DONE

## Scope

기존 governance 상태 위에 read-only summary 계층 추가

## Summary Model Chosen

A — 기존 유지 + `/api/governance-summary` + `v2.governance_health` 경량

## Integrated Governance Signals

- security_state (NORMAL/RESTRICTED/QUARANTINED/LOCKDOWN)
- governance enabled state
- orphan state
- evidence state (exists/missing/total)

## Excluded Scope

- raw policy/doctrine/audit/receipt 원문
- guard condition 상세
- enforcement/guard 동작 변경
- execution path
- AI 추천/판단/실행

## Status Rules

| overall_status | 조건 |
|----------------|------|
| HEALTHY | NORMAL + enabled + no orphans + evidence exists |
| DEGRADED | RESTRICTED / orphans / evidence missing / enabled=false |
| BLOCKED | QUARANTINED / LOCKDOWN (최우선) |

| execution_state | 조건 |
|-----------------|------|
| ALLOWED | NORMAL |
| GUARDED | RESTRICTED |
| BLOCKED | QUARANTINED / LOCKDOWN |

## Dominant Reason Priority

lockdown_active > quarantined > restricted > orphan_detected > evidence_missing > governance_disabled

## Constraints Count

orphan + evidence missing + restricted + governance disabled (일반 ops warning 제외)

## Evidence Rules

- evidence exists = governance evidence 신호 존재 + 비어있지 않음
- None / empty / 필수 필드 누락 = evidence missing
- evidence missing 단독 → DEGRADED (BLOCKED는 security_state 우선)

## enabled=false Rule

- enabled=false → 최소 DEGRADED
- QUARANTINED/LOCKDOWN이면 BLOCKED 우선

## Constitutional Check

| 항목 | 확인 |
|------|------|
| enforcement 변경 없음 | 확인 |
| guard 변경 없음 | 확인 |
| write action 없음 | 확인 |
| raw 원문 미노출 | 확인 |
| read-only summary | 확인 |
| fail-closed | 확인 |

## Tests

- B-11 전용: 19 passed
- Dashboard 회귀: 243 passed

## Remaining Risk

- 개발 환경에서 governance_gate 미초기화 시 DEGRADED (governance_disabled)
- 운영 환경에서 governance 활성화 시 HEALTHY 달성 가능

## Final Decision

B-11은 기존 governance/guard/policy 상태를 read-only summary로 통합하고, v2에는 경량 governance_health만 노출함으로써 실행 경로를 변경하지 않은 통제 상태 가시성을 강화하였다.
