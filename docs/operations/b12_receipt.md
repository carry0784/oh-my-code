# B-12 Receipt — Operator / Alert / Status Banner / UI Health

## Status

DONE

## Scope

read-only Status Banner + Alert Strip + Operator Health Summary UI 추가

## UI Model Chosen

A — 기존 dashboard 구조 유지 + 상단 Status Banner + Alert Strip + Health Summary

### Why A

1. 기존 탭/대시보드 구조 불변
2. 기존 aggregate/summaries 재사용
3. read-only 시각화만 추가
4. operator 체감 가시성 즉시 개선

## Displayed Sources

| 소스 | 표시 위치 |
|------|-----------|
| ops_health (B-10) | Banner: ops status |
| governance_health (B-11) | Banner: gov status, execution_state |
| market_feed (B-09) | Health card: worst trust, live/stale |
| dominant_reason | Banner: 1문장 요약 |
| source_coverage | Strip: ok/total |
| active_constraints_count | Strip: constraints |

## UI Elements

| 요소 | 내용 |
|------|------|
| Status Banner | ops status + governance status + execution state + dominant_reason + updated_at |
| Alert Strip | stale count + unavailable count + constraints count + source coverage |
| Health Grid | Ops Aggregate card + Governance card + Market Feed card |

## Excluded Scope

- raw receipt/audit/policy/guard 원문
- acknowledge/mute/retry 버튼
- execution/write action 버튼
- AI 추천/판단/실행 UI
- 전체 dashboard redesign

## Constitutional Check

| 항목 | 확인 |
|------|------|
| 거래 실행 없음 | 확인 |
| write action 없음 | 확인 |
| alert 조작 없음 | 확인 |
| raw 원문 미노출 | 확인 |
| read-only UI | 확인 |
| forbidden buttons = 0 | 확인 |

## Tests

- Dashboard 회귀: 243 passed
- B-12 UI 검증: 19/19 요소 확인
- 금지 버튼: 0건

## Remaining Risk

- 개발 환경에서 ops/governance status가 DEGRADED/UNKNOWN → 정상 (운영 환경에서 해소 가능)
- dominant_reason이 비어있을 수 있음 (HEALTHY일 때 정상)

## Final Decision

B-12는 기존 ops aggregate와 governance summary를 기반으로 read-only status banner / alert summary / operator health UI를 추가하여, 실행 경로를 변경하지 않은 상태에서 운영자 가시성을 강화하였다.
