# CR-039 Prerequisite (a) v2: Collection Stability (Mainnet Read-Only 포함)

Date: 2026-04-01
Authority: A (Decision Authority)
Previous: `cr039_prereq_a_collection_stability.md` (v1, testnet only)
Monitor script: `scripts/cr039_collection_monitor.py`

---

## 1. 변경 사항

A의 Option B 승인에 따라 `binance_mainnet_readonly` source를 CR-039 관측용으로 추가.

| 항목 | v1 | v2 |
|------|-----|-----|
| 총 source 수 | 6 | **7** |
| price source | binance_testnet only | binance_testnet + **binance_mainnet_readonly** |
| testnet 상태 | UNUSABLE (502) | UNUSABLE (502, 변함없음) |
| mainnet 상태 | 미측정 | **STABLE** (3/3, 100%) |
| price 관측 가능 여부 | 불가 | **가능** (mainnet read-only) |

---

## 2. Source별 성공률 (v2, 3 round)

| Source | 성공 | 실패 | 성공률 | 평균 Latency | Label |
|--------|------|------|--------|-------------|-------|
| alternative_me (Fear&Greed) | 3/3 | 0 | 100% | 610ms | **STABLE** |
| blockchain_com (hash/difficulty) | 3/3 | 0 | 100% | 37ms | **STABLE** |
| mempool_space_fees | 3/3 | 0 | 100% | 666ms | **STABLE** |
| mempool_space_stats | 3/3 | 0 | 100% | 666ms | **STABLE** |
| coingecko_global (mcap/dominance) | 3/3 | 0 | 100% | 338ms | **STABLE** |
| binance_mainnet_readonly | 3/3 | 0 | 100% | 1331ms | **STABLE** |
| binance_testnet (CCXT) | 0/3 | 3 | 0% | 380ms | **UNUSABLE** |

---

## 3. Snapshot Quality Grade 분포

| Grade | Count | 비율 |
|-------|-------|------|
| FULL | 0 | 0% |
| PARTIAL | 3 | 100% |
| DEGRADED | 0 | 0% |
| UNUSABLE | 0 | 0% |

PARTIAL = 6/7 (binance_testnet만 실패).
**주의**: mainnet_readonly가 STABLE이므로 price 관측은 가능. testnet 제외 시 실질 6/6 = FULL.

---

## 4. Source Trust Scope

A 지시에 따른 source 분류:

| Source | Trust Scope | 의미 |
|--------|------------|------|
| alternative_me | OPERATIONAL_ELIGIBLE | 운영 수집 가능 |
| blockchain_com | OPERATIONAL_ELIGIBLE | 운영 수집 가능 |
| mempool_space_fees | OPERATIONAL_ELIGIBLE | 운영 수집 가능 |
| mempool_space_stats | OPERATIONAL_ELIGIBLE | 운영 수집 가능 |
| coingecko_global | OPERATIONAL_ELIGIBLE | 운영 수집 가능 |
| binance_mainnet_readonly | **OBSERVATIONAL_ONLY** | CR-039 관측 전용, CR-046 Stage B 불가 |
| binance_testnet | **UNUSABLE** | 502 장애 |

---

## 5. 조건 (a) 재판정

### 24H 안정성: **미완료** (3 round 단기 검증만, 24H 장기 필요)

### 현재까지 확인된 것

| 항목 | v1 결과 | v2 결과 |
|------|---------|---------|
| sentiment sources 안정성 | STABLE (5/5) | **STABLE (5/5)** |
| on-chain sources 안정성 | STABLE (포함) | **STABLE (포함)** |
| price 관측 가능 여부 | 불가 (testnet 502) | **가능** (mainnet_readonly STABLE) |
| Binance testnet | UNUSABLE | **UNUSABLE** (변함없음) |
| cadence 유지 | OK | **OK** |
| 24~72H 연속 증거 | 미확보 | **미확보** (24H 실행 필요) |

### 조건 (a) 충족 여부: **PARTIAL → 24H 장기 검증 후 CONDITIONAL PASS 가능**

v1 대비 개선: price source가 mainnet_readonly로 관측 가능해짐.
**단, testnet 복구 전까지 CR-046 Stage B 운영 경로는 여전히 차단.**

### 다음 단계

1. `--rounds 288 --interval 300` (24H at 5min) 장기 실행
2. 7개 source 중 OPERATIONAL_ELIGIBLE 6개가 95%+ 유지 확인
3. mainnet_readonly latency 추이 모니터링 (현재 ~1.3s, 합리적)
4. 24H PASS 시 조건 (a) CONDITIONAL PASS 판정 → (b)~(e) 설계 진행

---

## 6. Mainnet Read-Only 제한 사항

A의 승인 조건 (엄격 준수):

| 항목 | 규칙 |
|------|------|
| 허용 범위 | CR-039 관측/수집 안정성 검증 **전용** |
| 금지 | CR-046 Stage B paper trading 진입 근거로 사용 금지 |
| 라벨 | `price_source=binance_mainnet_readonly` |
| | `source_semantics=observational_only` |
| | `not_valid_for_cr046_stage_b=true` |
| 운영 코드 변경 | 없음 (`binance_testnet=True` 유지) |

---

```
CR-039 Prerequisite (a) v2
Status: PARTIAL → 24H 검증 후 CONDITIONAL PASS 가능
Price Source: mainnet_readonly STABLE (관측용)
Testnet: UNUSABLE (502, CR-046 여전히 HOLD)
Date: 2026-04-01
```
