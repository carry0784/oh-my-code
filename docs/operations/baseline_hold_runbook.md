# Baseline Hold Runbook

**작성일**: 2026-04-03
**상태**: ACTIVE
**승인자**: A

---

## 1. 현재 기준선 값

| 항목 | 기준값 |
|------|--------|
| `operational_mode` | `BASELINE_HOLD` |
| `exchange_mode` | `DATA_ONLY` |
| `disabled_beat_tasks` | `3` |
| `blocked_api_count` | `5` |
| C15 | `CLOSED` |
| TEST-ORDERDEP-001 | `RESOLVED` (2026-04-03, 2계층 방어 봉합 완료) |

### 봉인 CR

| CR | 제목 | 봉인일 |
|----|------|--------|
| CR-038 | Market State Collection | 2026-04-03 |
| CR-048 | Strategy Cycle Runner | 2026-04-02 |
| CR-048A | Async Lifecycle | 2026-04-02 |
| CR-048B | Enum Contract Unification | 2026-04-03 |
| CR-049 Phase 1+2 | Exchange Mode Contract (DATA_ONLY) | 2026-04-03 |

### 적용 규칙

| 규칙 | 문서 위치 |
|------|-----------|
| BL-EXMODE01 | `docs/architecture/bl_exmode01.md` |
| BL-OPS-RESTART01 | `docs/architecture/bl_ops_restart01.md` |

### 금지 사항

- 신규 구현 CR 착수 금지
- Phase 3 구현 금지
- SEALED PASS 범위 재개방 금지
- DATA_ONLY 계약 훼손 금지
- ETH 운영 경로 금지 (CR-046)

---

## 2. 관측 항목 (6항목 고정 관찰표)

| # | 체크 | 기대값 | 관측 경로 |
|---|------|--------|-----------|
| 1 | governance-state | `BASELINE_HOLD` | `GET /api/v1/ops/governance-state` |
| 2 | /status | `BASELINE_HOLD` | `GET /status` → `operational_mode` |
| 3 | exchange-mode | `DATA_ONLY` | `GET /api/v1/ops/exchange-mode` |
| 4 | blocked-operations | `5` | `GET /api/v1/ops/blocked-operations` → `blocked_api_count` |
| 5 | 금지 beat 3개 | 발송 0회 / schedule 미등록 | Flower Tasks + beat schedule |
| 6 | startup logs | 양쪽 `BASELINE_HOLD` | FastAPI `governance_state_loaded` + Celery fingerprint |

### 금지 task 3개

| task | reason_code |
|------|-------------|
| `workers.tasks.market_tasks.sync_all_positions` | REQUIRES_PRIVATE_API |
| `workers.tasks.order_tasks.check_pending_orders` | REQUIRES_PRIVATE_API |
| `workers.tasks.sol_paper_tasks.run_sol_paper_bar` | CR046_STAGE_B_HOLD |

---

## 3. Drift 판정 규칙

### Hard Drift (즉시 이탈)

| 조건 | 판정 |
|------|------|
| `operational_mode != BASELINE_HOLD` | 즉시 이탈 |
| `exchange_mode != DATA_ONLY` | 즉시 이탈 |
| `blocked_api_count != 5` | 즉시 이탈 |
| 금지 3개 task 중 하나라도 beat/Flower에 나타남 | 즉시 이탈 |
| private API 호출 흔적 (fetch_balance, fetch_positions, fetch_order, cancel_order, create_order) | 즉시 이탈 |

### Soft Drift (교차확인 필요)

| 조건 | 의미 |
|------|------|
| `/status`와 `/governance-state` 값 불일치 | 상태원천 불일치 |
| 기동 로그엔 `BASELINE_HOLD`, API는 다른 값 | 반영 누락/로드 불일치 |
| Flower 최근 task 정상이나 로그에 경고 증가 | 사전 징후 |
| TEST-ORDERDEP-001 류 테스트 오염이 런타임으로 번지는 흔적 | 격리 붕괴 위험 |

---

## 4. 확인 순서 (이탈 의심 시)

### 1단계: API 재측정

```
GET /api/v1/ops/governance-state   → operational_mode = BASELINE_HOLD?
GET /status                         → operational_mode = BASELINE_HOLD?
GET /api/v1/ops/exchange-mode       → exchange_mode = DATA_ONLY?
GET /api/v1/ops/blocked-operations  → blocked_api_count = 5?
```

하나라도 다르면 **1차 이탈 증거**.

### 2단계: 기동 로그 확인

- FastAPI: `governance_state_loaded operational_mode=BASELINE_HOLD`
- Celery: `celery_worker/beat_startup_fingerprint operational_mode=BASELINE_HOLD`

둘 중 하나라도 다르면 **상태 파일 로드 불일치 또는 반영 누락**.

### 3단계: Flower + beat 확인

- Flower Tasks 탭 → 금지 3개 task 실행 흔적 확인
- 정상: 없음 / 이탈: 1회라도 나타남

### 4단계: side effect 확인

- 주문 생성/취소 흔적
- private API 호출 흔적
- 이것이 가장 강한 증거

### 5단계: 판정

| 상황 | 판정 |
|------|------|
| API 4개 기대값 일치 + 금지 task 미발송 | **대기 유지** |
| API 불일치 1개 | **Soft Drift 경고** |
| 금지 task 발송 or exchange_mode 변경 | **Hard Drift → 대기 해제 + 대응** |
| private API side effect 발생 | **Hard Drift → 대기 해제 + 대응** |

---

## 5. 대기 유지 조건

아래가 **모두** 참이면 대기 유지:

- [ ] `operational_mode == BASELINE_HOLD`
- [ ] `exchange_mode == DATA_ONLY`
- [ ] `blocked_api_count == 5`
- [ ] `disabled_beat_tasks == 3`
- [ ] 금지 3개 task Flower 미발견
- [ ] startup logs 양쪽 일관
- [ ] 신규 변경 요청 없음

---

## 6. 대기 해제 조건

아래 **중 하나라도** 발생하면 대기 해제:

| 조건 | 조치 |
|------|------|
| A가 신규 CR 착수 지시 | Change Re-entry Checklist 따라 진행 |
| Hard Drift 감지 | 즉시 원인 조사 + 복구 |
| Soft Drift 반복 (2회 이상) | 원인 조사 + A 보고 |

---

## 7. 관련 문서

| 문서 | 위치 |
|------|------|
| ops_state.json (거버넌스 상태) | 프로젝트 루트 |
| BL-EXMODE01 | `docs/architecture/bl_exmode01.md` |
| BL-OPS-RESTART01 | `docs/architecture/bl_ops_restart01.md` |
| CR-049 봉인 증거 | `docs/operations/evidence/cr049_sealed_pass.md` |
| TEST-ORDERDEP-001 | `docs/operations/evidence/test_orderdep_001.md` |
| Change Re-entry Checklist | `docs/operations/change_reentry_checklist.md` |

---

**Baseline Hold Runbook 작성 완료.**
