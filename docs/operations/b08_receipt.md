# B-08 Receipt — AI Assist 데이터 소스 연결

## Status

DONE

## Scope

AI Assist가 사용할 내부 ops_summary 계열 데이터 소스를 read-only 방식으로 연결하고 정규화

## Source Model Chosen

C — A 기반(기존 내부 데이터) + ops 요약 추가, 화면 노출 최소

### Why C

1. 기존 내부 데이터 연결이 이미 95% 이상 존재
2. ops 요약 추가만으로 AI Assist 참조 기반 완성
3. 외부 API 신규 연결 불필요
4. 화면 변경 최소화 가능

## Connected Sources

| 소스 | 데이터 | 출처 |
|------|--------|------|
| ops_summary | I-01~I-07 상태 요약 (status_word, gate, preflight, approval, policy 등) | 각 카드 러너 |
| signal_pipeline | 24h 신호 통계 (total, validated, rejected, executed, pending, rejection_rate) | v2 payload |
| position_overview | 포지션 개요 (count, value, PnL, exchanges connected) | v2 payload |
| evidence_summary | evidence 건수/governance 활성/orphan 수 (원문 미노출) | evidence_store |

## Excluded Sources

| 소스 | 이유 | 다음 카드 |
|------|------|-----------|
| 실시간 호가/스프레드/오더북 | B-09 범위 | B-09 |
| agent_analysis 원문 | 보안 (내부 추론 노출 금지) | 미정 |
| guard condition 상세 | 보안 (보안 경계) | 미정 |
| AI 추천/판단/실행 | 이번 카드 범위 밖 | 후속 |
| 외부 API 신규 소스 | 이번 카드에서 금지 | B-09/B-10 |

## Fix / Connection Summary

- `app/schemas/ai_assist_schema.py`: 4개 정규화 모델 (OpsSummary, SignalPipelineSummary, PositionOverview, EvidenceSummary) + AIAssistSources 통합
- `app/core/ai_assist_source.py`: read-only 수집 서비스 (ops_summary + evidence_summary, fail-closed)
- `app/api/routes/dashboard.py`: v2 payload에 `ai_assist_sources` 통합 + `/api/ai-sources` 엔드포인트
- 화면 변경 없음 (Tab 2 AI Workspace가 v2 payload 소비 → 자동 참조 가능)

## Constitutional Check

| 항목 | 확인 |
|------|------|
| 거래 실행 로직 없음 | 확인 |
| write/destructive action 없음 | 확인 |
| read-only source 연결 | 확인 |
| AI 추천/판단/실행 자동화 없음 | 확인 |
| B-09/B-10 혼합 없음 | 확인 |
| hidden side effect 없음 | 확인 |
| fail-closed 유지 | 확인 |
| 민감 원문 노출 없음 | 확인 |

## Tests

- B-08 전용 테스트: 18 passed
- Dashboard 회귀: 243 passed

## Remaining Risk

- signal_pipeline과 position_overview는 sync 컨텍스트에서 빈 값 반환, v2 async 컨텍스트에서 enrichment 필요 (이미 v2에서 처리됨)
- ops_summary 수집 시 각 러너 호출 비용 — 캐싱 미적용 (이번 카드 범위 밖)

## Final Decision

B-08은 AI Assist가 사용할 내부 ops_summary 계열 데이터 소스를 read-only 방식으로 연결하고 정규화하여, 실행 경로를 추가하지 않은 상태에서 안전한 참조 기반을 마련하였다.
