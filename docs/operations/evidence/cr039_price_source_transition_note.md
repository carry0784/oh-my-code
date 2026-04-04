# CR-039 Price Source Transition Note

Date: 2026-04-01
Authority: A (Decision Authority)
Trigger: Binance testnet 502 장애 지속

---

## 1. 배경

CR-039 조건 (a) 수집 안정성 검증에서 Binance testnet이 502 Bad Gateway로 UNUSABLE.
price/OHLCV 수집 불가로 조건 (a) 충족 불가 상태.

A의 Option B 승인: **mainnet read-only를 CR-039 관측용으로 한정 사용.**

---

## 2. 전환 내용

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 모니터 source | 6개 (testnet 포함) | **7개** (testnet + mainnet_readonly) |
| price 관측 | testnet only → UNUSABLE | testnet + **mainnet_readonly** |
| 운영 코드 | 변경 없음 | **변경 없음** |
| config | `binance_testnet=True` | `binance_testnet=True` (유지) |

### 변경된 파일

| 파일 | 변경 | 용도 |
|------|------|------|
| `scripts/cr039_collection_monitor.py` | `check_binance_mainnet_readonly()` 추가 | 관측 모니터 전용 |

### 변경되지 않은 파일 (운영 경로)

- `app/services/market_data_collector.py` — 변경 없음
- `exchanges/binance.py` — 변경 없음 (testnet=True 유지)
- `app/core/config.py` — 변경 없음 (binance_testnet=True)
- `workers/tasks/data_collection_tasks.py` — 변경 없음
- `workers/tasks/sol_paper_tasks.py` — 미생성 (CR-046 HOLD)
- `workers/tasks/btc_paper_tasks.py` — 미생성 (CR-046 HOLD)

---

## 3. 안전 경계

### 허용

- `scripts/cr039_collection_monitor.py`에서 mainnet public ticker 조회
- CR-039 조건 (a) 안정성 증거 수집
- latency/success rate 관측

### 금지

- CR-046 Stage B paper trading 근거로 mainnet_readonly 사용
- 운영 코드에서 mainnet 직접 호출
- `binance_testnet=False` 설정 변경
- mainnet에 인증 키 전달 (read-only, no auth)

### 라벨링 (모든 출력에 반영)

```python
price_source = "binance_mainnet_readonly"
source_semantics = "observational_only"
not_valid_for_cr046_stage_b = True
```

---

## 4. 복구 계획

| 조건 | 행동 |
|------|------|
| testnet 복구 시 | testnet source 재검증 → 3/3 성공 시 CR-046 HOLD 해제 검토 |
| testnet 미복구 지속 | CR-039 관측은 mainnet_readonly로 계속, CR-046은 HOLD 유지 |
| A가 mainnet 운영 승인 시 | 별도 CR 등록 필요, 현 승인 범위에 포함 안 됨 |

---

```
CR-039 Price Source Transition
Type: Observation-only mainnet read-only addition
Scope: scripts/cr039_collection_monitor.py ONLY
Operational code: UNCHANGED
Date: 2026-04-01
```
