# CR-039 Prerequisite (a): Collection Stability Evidence

Date: 2026-04-01
Authority: A (Decision Authority)
Monitor script: `scripts/cr039_collection_monitor.py`

---

## 1. 해석 및 요약

수집 안정성 초기 검증(3 round, 5초 간격)을 실행했습니다.

**결과: 5/6 sources STABLE, 1 source UNUSABLE (Binance testnet)**

전체 snapshot grade는 **PARTIAL** (5/6) -- Binance testnet 502 장애로 price/OHLCV 수집 불가.
sentiment + on-chain sources는 모두 100% 안정적입니다.

---

## 2. Source별 성공률

| Source | 성공 | 실패 | 성공률 | 평균 Latency | Label |
|--------|------|------|--------|-------------|-------|
| alternative_me (Fear&Greed) | 3/3 | 0 | 100% | 589ms | **STABLE** |
| blockchain_com (hash/difficulty) | 3/3 | 0 | 100% | 45ms | **STABLE** |
| mempool_space_fees | 3/3 | 0 | 100% | 670ms | **STABLE** |
| mempool_space_stats | 3/3 | 0 | 100% | 672ms | **STABLE** |
| coingecko_global (mcap/dominance) | 3/3 | 0 | 100% | 398ms | **STABLE** |
| binance_testnet (CCXT) | 0/3 | 3 | 0% | 412ms | **UNUSABLE** |

---

## 3. Snapshot Quality Grade 분포

| Grade | Count | 비율 |
|-------|-------|------|
| FULL | 0 | 0% |
| PARTIAL | 3 | 100% |
| DEGRADED | 0 | 0% |
| UNUSABLE | 0 | 0% |

모든 snapshot이 PARTIAL -- Binance testnet 장애 때문.

---

## 4. Cadence 유지 여부

| 항목 | 값 |
|------|-----|
| 평균 간격 | 6.3s (테스트용 5s 설정) |
| 최대 간격 | 6.7s |
| 6분 초과 위반 | 0건 |

cadence 이탈 없음.

---

## 5. 미해결 리스크

### 리스크 1: Binance testnet 장애 (CRITICAL)

- 상태: 502 Bad Gateway (testnet.binance.vision)
- 영향: price, OHLCV, orderbook, funding rate, open interest 전부 수집 불가
- 결과: snapshot에 핵심 가격 데이터 누락 → PARTIAL grade 고정
- 대책: testnet 복구 대기 또는 **mainnet read-only 전환** (A 승인 필요)

### 리스크 2: 24~72H 장기 안정성 미검증

- 현재: 3 round 단기 검증만 완료
- 필요: 최소 288 round (24H at 5min) 연속 실행
- 대책: `python scripts/cr039_collection_monitor.py --rounds 288 --interval 300` 실행 필요
- 제약: 이 세션에서 24H 연속 실행은 불가능 (별도 프로세스 또는 Celery beat 필요)

### 리스크 3: CoinGecko rate limit

- 무료 API는 분당 10-50 요청 제한
- 5분 주기면 분당 0.2 요청이므로 안전
- 하지만 다수 심볼 수집 시 rate limit 위험

---

## 6. 조건 (a) 판정

### 24H 안정성: **미완료** (3 round 단기 검증만)

### 현재까지 확인된 것

| 항목 | 결과 |
|------|------|
| sentiment sources 안정성 | **STABLE** (5/5, 100%) |
| on-chain sources 안정성 | **STABLE** (포함) |
| Binance testnet | **UNUSABLE** (0%) |
| cadence 유지 | **OK** |
| 24~72H 연속 증거 | **미확보** |

### 조건 (a) 충족 여부: **PARTIAL -- 장기 검증 필요**

sentiment/on-chain sources는 STABLE이나, 핵심 price source가 UNUSABLE이므로 **조건 (a) 완전 충족 불가**.

### 다음 단계 선택지

| 옵션 | 설명 | A 승인 필요 |
|------|------|-----------|
| A. 대기 | testnet 복구 후 24H 검증 재실행 | 불필요 |
| B. mainnet read-only 전환 | `binance_testnet=False`로 변경, 읽기 전용만 | **필요** |
| C. 부분 충족 진행 | sentiment/on-chain만으로 (b)~(e) 설계 시작 | **필요** |

---

## 더 좋은 아이디어 반영

- source별 `STABLE/FLAKY/DEGRADED/UNUSABLE` 라벨링: **반영 완료**
- 24H 판정 + 72H 권고 관측 분리: **구조 준비 완료** (--rounds 288 for 24H, 864 for 72H)

---

```
CR-039 Prerequisite (a): Collection Stability
Status: PARTIAL (sentiment STABLE, price UNUSABLE)
Blocker: Binance testnet 502
Date: 2026-04-01
```
