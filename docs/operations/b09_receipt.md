# B-09 Receipt — 실시간 호가/스프레드 피드 연결

## Status

DONE

## Scope

기존 best bid/ask/spread 수집 기능을 read-only market feed 서비스로 승격하고 정규화

## Feed Model Chosen

C — 기존 인프라 서비스 분리 + AI 노출, 최소 외부 연결

### Why C

1. 기존 수집 로직(`_get_quote_data()`)이 이미 존재
2. 기존 adapter 재사용으로 외부 연결 리스크 최소
3. 독립 서비스 계층으로 승격 시 재사용성 증가
4. full orderbook/execution으로 확장하지 않고 최소 범위 유지

## Connected Exchanges

| 거래소 | bid/ask | spread | trust state |
|--------|---------|--------|-------------|
| Binance | 지원 | 지원 | 6단계 |
| OKX | 지원 | 지원 | 6단계 |
| UpBit | 지원 | 지원 | 6단계 |
| Bitget | 지원 | 지원 | 6단계 |

## Excluded Scope

| 범위 | 이유 |
|------|------|
| KIS | bid/ask 미지원 |
| Kiwoom | bid/ask 미지원 |
| full orderbook depth | B-09 범위 밖 |
| execution path | 거래 실행 금지 |
| strategy reaction | 전략 반응 금지 |
| B-10 종합 강화 | 별도 카드 |

## Feed / Normalization Summary

- `app/schemas/market_feed_schema.py`: QuoteEntry + VenueFeedSummary + MarketFeedSummary + MarketFeedResponse
- `app/core/market_feed_service.py`: `build_market_feed_from_quote_data()` — 기존 quote_data를 정규화 변환
- `app/api/routes/dashboard.py`: v2 payload에 `market_feed` 통합 + `/api/market-feed` 독립 엔드포인트
- stale threshold: 120초 (기존 일관)
- trust state: LIVE/STALE/NOT_AVAILABLE/UNAVAILABLE/DISCONNECTED/NOT_QUERIED

## Constitutional Check

| 항목 | 확인 |
|------|------|
| 거래 실행 로직 없음 | 확인 |
| write/destructive action 없음 | 확인 |
| read-only feed 유지 | 확인 |
| AI 추천/판단/실행 없음 | 확인 |
| B-10 혼합 없음 | 확인 |
| full orderbook 없음 | 확인 |
| hidden side effect 없음 | 확인 |
| fail-closed 유지 | 확인 |

## Tests

- B-09 전용: 16 passed
- Dashboard 회귀: 243 passed

## Remaining Risk

- market-feed 엔드포인트는 quote fetch가 포함되어 exchange API 호출 발생 (기존 v2와 동일 패턴)
- 거래소 API rate limit 또는 connectivity 문제 시 fail-closed 처리됨

## Final Decision

B-09는 기존 best bid/ask/spread 수집 기능을 read-only market feed 서비스로 승격하고 정규화하여, 실행 경로를 추가하지 않은 상태에서 시장 입력 계층을 안전하게 확장하였다.
