# B-13 Receipt — Alert Priority / Escalation Summary

## Status

DONE

## Scope

read-only alert priority / escalation summary 계층 추가

## Policy Model Chosen

A — 기존 source 유지 + `/api/alert-summary` + `v2.alert_health` 경량

## Referenced Sources

- ops aggregate (B-10)
- governance summary (B-11)
- market feed (B-09)
- active_constraints_count
- stale/unavailable source counts

## Excluded Scope

- raw alert/receipt/audit 원문
- ack/write/mute/snooze/retry
- notification delivery
- execution action
- AI 추천/판단/실행

## Priority Rules

| Priority | 조건 | Escalation |
|----------|------|------------|
| P1 | governance BLOCKED / execution BLOCKED / ops UNHEALTHY | critical |
| P2 | governance DEGRADED / execution GUARDED / ops DEGRADED / unavailable source | escalated |
| P3 | stale source / constraints > 0 | watch |
| INFO | 나머지 | none |

## Summary Fields

- v2 `alert_health`: top_priority + escalation_state + top_reason + alert_count + updated_at (5필드)
- `/api/alert-summary`: 상세 breakdown + ops/gov/market state + constraints/stale/unavailable counts

## Constitutional Check

| 항목 | 확인 |
|------|------|
| 거래 실행 없음 | 확인 |
| ack/write 없음 | 확인 |
| mute/snooze 없음 | 확인 |
| retry 없음 | 확인 |
| notification 없음 | 확인 |
| raw 원문 미노출 | 확인 |
| read-only | 확인 |
| fail-closed | 확인 |

## Tests

- B-13 전용: 15 passed
- Dashboard 회귀: 243 passed

## Remaining Risk

- sync 컨텍스트에서 market_trust가 보수적 "STALE" 고정 (async context에서 정확한 값)

## Final Decision

B-13은 기존 ops/governance/market 상태를 바탕으로 read-only alert priority / escalation summary를 추가하여, 실행 경로를 변경하지 않은 상태에서 운영자 우선순위 가시성을 강화하였다.
