# B-10 Receipt — 종합 운영 강화

## Status

DONE

## Scope

기존 source 유지 + 종합 운영 aggregate read-only 추가

## Integration Model Chosen

A — 기존 유지 + `/api/ops-aggregate` + `v2.ops_health` 경량

### Why A

1. v2에 이미 15개 소스 존재
2. 기존 소비자 불변
3. aggregate는 summary/health 전용 endpoint로 분리
4. v2에는 경량 4필드만 추가

## Integrated Sources

| # | Source | Status in dev |
|---|--------|---------------|
| 1 | ops_summary | STALE (governance partial) |
| 2 | signal_pipeline | STALE (sync context) |
| 3 | position_overview | OK |
| 4 | evidence_summary | depends on governance |
| 5 | market_feed | STALE (async only) |
| 6 | runtime_status | depends on governance |

## Excluded Scope

- raw agent_analysis 원문
- raw guard condition 원문
- raw receipt 본문
- execution path / strategy / order placement
- full orderbook
- AI 추천/판단/실행

## Aggregate Rules

| 조건 | overall_status |
|------|----------------|
| 모든 source OK | HEALTHY |
| stale/unavailable 1+ | DEGRADED |
| unavailable 2+ | UNHEALTHY |

- `source_coverage`: sources_total / ok / stale / unavailable
- `dominant_reason`: 왜 DEGRADED/UNHEALTHY인지 1문장
- v2 `ops_health`: overall_status + coverage + dominant_reason + updated_at (경량만)
- 상세: `/api/ops-aggregate`에만

## Constitutional Check

| 항목 | 확인 |
|------|------|
| 거래 실행 없음 | 확인 |
| AI 추천/판단 없음 | 확인 |
| write action 없음 | 확인 |
| raw 원문 미노출 | 확인 |
| read-only aggregate | 확인 |
| fail-closed | 확인 |
| hidden side effect 없음 | 확인 |

## Tests

- B-10 전용: 13 passed
- Dashboard 회귀: 243 passed

## Remaining Risk

- 개발 환경에서 일부 source가 STALE/UNAVAILABLE → aggregate = DEGRADED/UNHEALTHY
- 운영 환경(governance + async context)에서 HEALTHY 달성 가능

## Final Decision

B-10은 기존 source를 유지한 상태에서 종합 운영 aggregate를 read-only로 추가하고, v2에는 경량 ops_health만 노출함으로써 실행 경로를 추가하지 않은 운영 관측 강화를 달성하였다.
