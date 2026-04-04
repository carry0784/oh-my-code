# CR-039 Phase 2 Prerequisites

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **HOLD -- 선행 조건 미충족**

---

## Context

CR-038 Phase 1 (관측/수집 계층)은 CHECKPOINT PASS.
CR-039 / Phase 2는 **해석 계층** (ML regime, 시계열 분석, 복합 점수, API 공개).
해석 계층은 데이터 품질이 검증된 후에만 착수 가능.

---

## 선행 조건 5개

### (a) 수집 안정성 증거

| 항목 | 기준 | 현재 |
|------|------|------|
| 연속 수집 로그 | 최소 24~72시간 | 미수집 |
| source별 성공률 | 각 source 90%+ | 미측정 |
| 실패/partial/degraded 비율 | <10% | 미측정 |

**검증 방법:**
- `collect_market_state` task를 24H+ 연속 실행
- source별 성공/실패 카운트 로그 수집
- 결과를 `cr039_stability_evidence.md`에 기록

---

### (b) Snapshot 품질 계약

MarketStateSnapshot에 아래 필드 추가 필요:

| 필드 | 타입 | 의미 |
|------|------|------|
| `quality_grade` | enum | `FULL` / `PARTIAL` / `DEGRADED` / `STALE` / `UNKNOWN` |
| `source_freshness` | dict | source별 마지막 성공 fetch 시각 |
| `completeness_pct` | float | non-null 필드 비율 (0.0~1.0) |
| `source_health` | dict | source별 성공/실패 상태 |

**규칙:**
- `quality_grade`는 snapshot 생성 시 자동 계산
- `DEGRADED` 이상이면 API 응답에 경고 포함
- `STALE` (>10분 미갱신)이면 regime 해석 금지

---

### (c) 저장 운영 정책

| 항목 | 정책 |
|------|------|
| Retention | 최소 30일 보관, 이후 집계(hourly aggregation) |
| Index | `(symbol, snapshot_at)` 복합 인덱스 |
| Purge | 90일 이전 raw_data 필드 NULL 처리 (스키마 보존) |
| Backfill | source 장애 후 복구 시 gap 감지 + 재수집 시도 |
| 중복 방지 | `(exchange, symbol, snapshot_at)` unique 또는 5분 내 중복 skip |

---

### (d) Regime 해석 경고

| 상태 | 허용 해석 | 금지 해석 |
|------|----------|----------|
| `UNKNOWN` | "분류 불가" 라벨 | 매매 방향 판단 |
| `DEGRADED` | "부분 데이터 기반 추정" | 확정적 regime 판정 |
| `PARTIAL` | "일부 source 누락" | 전체 시장 상태 결론 |
| `FULL` | 모든 해석 가능 | - |

**핵심 원칙:**
- Rule-based regime는 **초기 관측 라벨**일 뿐, 의사결정 엔진이 아님
- ML regime도 offline analysis -> shadow evaluation -> read-only API 순으로만
- 실행/주문/승격 경로 연결 절대 금지

---

### (e) API 노출 안전 경계

| 항목 | 규칙 |
|------|------|
| Endpoint | `/api/v1/market-state` |
| 성격 | **read-only observational** (추천/판정 아님) |
| 응답 필수 필드 | `quality_grade`, `source_freshness`, 경고 텍스트 |
| Stale 표시 | snapshot_at > 10분이면 `"warning": "stale_data"` 강제 |
| 금지 | "추천", "신호", "매수/매도" 등 action-suggestive 표현 |

---

## 강제 규칙

1. 실행 경로 연결 금지
2. 주문/승격/트레이딩 의사결정 연결 금지
3. ML regime는 offline/shadow 단계부터
4. API는 observational semantics만 허용
5. 선행 조건 5개 미충족 시 CR-039 등록 금지

---

## 충족 확인 체크리스트

| # | 조건 | 충족 여부 |
|---|------|----------|
| a | 24~72H 수집 안정성 증거 | [ ] |
| b | quality_grade / freshness / completeness 계약 | [ ] |
| c | retention / purge / backfill / index 정책 | [ ] |
| d | degraded / partial 해석 경고 규정 | [ ] |
| e | API read-only 안전 경계 | [ ] |

**5개 전부 체크 후에만 CR-039 등록 가능.**

---

```
CR-039 Prerequisites
Status: HOLD (0/5 conditions met)
Authority: A (Decision Authority)
Date: 2026-04-01
```
