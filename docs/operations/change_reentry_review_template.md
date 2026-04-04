# Change Re-entry Review Template — 변경 착수 검토서

**양식 버전**: v1.0
**작성일**: 2026-04-03

---

> 변경 착수 전 반드시 이 양식을 작성한다.
> L3 이상은 A 승인 전까지 착수 금지.

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| **CR / 작업 ID** | |
| **제목** | |
| **요청자** | |
| **요청일** | |
| **승인자** | |
| **승인일** | |

---

## 1. 변경 목적

> 왜 이 변경이 필요한가? (1~3문장)

---

## 2. 변경 범위

### 변경 대상 파일

| 파일 | 변경 내용 (요약) |
|------|----------------|
| | |

### 위험도 등급 판정

| 항목 | 판정 |
|------|------|
| **최고 등급** | L0 / L1 / L2 / L3 / L4 |
| **판정 근거** | |

> 참조: `docs/operations/change_scope_matrix.md`

---

## 3. Baseline 영향 분석

### 영향 받는 기준선 항목

| 항목 | 현재 기준값 | 변경 후 예상값 | 영향 여부 |
|------|-----------|-------------|:--------:|
| `operational_mode` | `BASELINE_HOLD` | | O / X |
| `exchange_mode` | `DATA_ONLY` | | O / X |
| `blocked_api_count` | `5` | | O / X |
| `disabled_beat_tasks` | `3` | | O / X |
| `forbidden_beat_tasks_absent` | 0 in schedule | | O / X |
| `startup_log_consistency` | both emit | | O / X |

### 영향 받는 규칙

- [ ] BL-EXMODE01
- [ ] BL-OPS-RESTART01
- [ ] 해당 없음

### 금지 사항 위반 여부

- [ ] 신규 구현 CR 착수 금지 — 위반 없음
- [ ] Phase 3 구현 금지 — 위반 없음
- [ ] SEALED PASS 범위 재개방 금지 — 위반 없음
- [ ] DATA_ONLY 계약 훼손 금지 — 위반 없음
- [ ] ETH 운영 경로 금지 — 위반 없음

---

## 4. 사전 검증 (착수 전 확인)

| # | 체크 | 결과 |
|---|------|------|
| 1 | `GET /api/v1/ops/baseline-check` → drift_status = HOLD | |
| 2 | 회귀 테스트 PASS (ops_visibility, restart_hygiene, ops_checks, restart_drill) | |
| 3 | Baseline Hold 해제 승인 (L3 이상만) | |

---

## 5. 검증 계획 (변경 중/후)

### 변경 중 점검

| 주기 | 점검 항목 |
|------|----------|
| 매 커밋 | baseline-check 6/6 HOLD |
| 매 커밋 | 영향 범위 밖 기준선 불변 확인 |

### 변경 후 필수 검증

| # | 검증 | 필요 여부 |
|---|------|:--------:|
| 1 | baseline-check | O / X |
| 2 | 회귀 테스트 | O / X |
| 3 | restart drill | O / X |
| 4 | 25 adapter test | O / X |
| 5 | Flower 감시 | O / X |
| 6 | 전면 재검증 | O / X |

> 참조: `docs/operations/change_scope_matrix.md` § 필수 검증 묶음

---

## 6. 롤백 계획

| 조건 | 롤백 방법 |
|------|----------|
| baseline-check HARD_DRIFT | |
| 변경 범위 밖 기준선 깨짐 | |
| 회귀 테스트 FAIL | |
| A 중단 지시 | |

---

## 7. 판정

| 항목 | 결과 |
|------|------|
| **착수 승인** | 승인 / 보류 / 거부 |
| **승인자** | |
| **승인일** | |
| **조건** | |

---

**양식 작성 완료 후 A 검토 요청.**
