# Change Gate Policy — 변경 허용/금지/승인 규칙

**작성일**: 2026-04-03
**상태**: ACTIVE
**승인자**: A

---

## 1. 목적

Baseline Hold 상태에서 어떤 변경이 허용되고, 어떤 변경이 금지되는지를 명시적으로 정의한다.
감이 아니라 등급과 규칙으로 판단한다.

---

## 2. 변경 위험도 등급 (L0~L4)

| 등급 | 이름 | 영향 범위 | Baseline Hold 중 허용 |
|------|------|----------|:-------------------:|
| **L0** | 문서/증빙 | md, evidence, runbook | ✅ 즉시 가능 |
| **L1** | 테스트 전용 | tests, fixtures, mocks | ✅ 운영 영향 0 증명 시 |
| **L2** | 관측 전용 | read-only API, log visibility, dashboard | ✅ 기준선 값 불변 보장 시 |
| **L3** | 런타임 영향 | schedule, ops_state, startup, guard 로직 | ⚠️ A 승인 필요 |
| **L4** | 정책/실행 영향 | exchange_mode, blocked API, beat task, 금지 경로 | ⛔ Baseline Hold 해제 없이 금지 |

---

## 3. 등급별 허용/금지 규칙

### L0 — 문서/증빙 (즉시 가능)

| 허용 | 조건 |
|------|------|
| docs/ 하위 문서 수정/추가 | 없음 |
| evidence 문서 작성 | 없음 |
| runbook/checklist 수정 | 없음 |
| CLAUDE.md 갱신 | 없음 |

### L1 — 테스트 전용 (조건부 허용)

| 허용 | 조건 |
|------|------|
| 테스트 파일 수정/추가 | 운영 코드 변경 없음 |
| fixture/mock 수정 | settings 오염 방지 확인 |
| conftest.py 수정 | 기존 테스트 회귀 PASS |

| 금지 | 사유 |
|------|------|
| 테스트에서 ops_state.json 직접 수정 | 상태원천 훼손 |
| 테스트에서 exchange_mode를 non-DATA_ONLY로 설정 후 미복원 | TEST-ORDERDEP-001 재발 |

### L2 — 관측 전용 (조건부 허용)

| 허용 | 조건 |
|------|------|
| 읽기 전용 API 추가 | 기준선 6항목 불변 + baseline-check PASS |
| 로그 출력 추가 | 상태 변경 없음 |
| 대시보드 조회 기능 추가 | 쓰기 경로 없음 |

| 금지 | 사유 |
|------|------|
| API에서 ops_state.json 쓰기 경로 추가 | A 전용 편집권 침해 |
| /status 응답 구조 변경 (기존 필드 제거) | 관측 경로 훼손 |

### L3 — 런타임 영향 (A 승인 필요)

| 변경 대상 | 승인 요건 |
|----------|----------|
| celery beat schedule 수정 | A 승인 + 재기동 drill |
| ops_state.json 값 변경 | A만 직접 편집 |
| startup 로그 시퀀스 변경 | A 승인 + 로그 검증 |
| guard 로직 수정 (_require_mode 등) | A 승인 + 25 adapter test 재실행 |

### L4 — 정책/실행 영향 (Baseline Hold 해제 없이 금지)

| 변경 | 상태 |
|------|------|
| exchange_mode 변경 (DATA_ONLY → PAPER/LIVE) | ⛔ 금지 |
| blocked API 해제 (5 → 감소) | ⛔ 금지 |
| disabled beat task 재활성화 (3 → 감소) | ⛔ 금지 |
| 금지 task beat schedule 등록 | ⛔ 금지 |
| private API 호출 경로 활성화 | ⛔ 금지 |
| 실주문 경로 활성화 | ⛔ 금지 |

---

## 4. Baseline Hold 해제 절차

L4 변경이 필요한 경우 아래 절차를 따른다:

| 단계 | 행동 | 승인 |
|------|------|------|
| 1 | 변경 목적/범위/영향 문서화 (재진입 검토 템플릿 작성) | 작업자 |
| 2 | baseline-check 6/6 HOLD 확인 | 작업자 |
| 3 | 회귀 테스트 전체 PASS 확인 | 작업자 |
| 4 | Baseline Hold 해제 요청 | 작업자 → A |
| 5 | **Baseline Hold 해제 승인** | **A** |
| 6 | 변경 실행 | 작업자 |
| 7 | baseline-check 재측정 + 회귀 재실행 | 작업자 |
| 8 | ops_state.json 갱신 (기준값 변경 시) | **A만 편집** |
| 9 | CR 봉인 판정 | **A** |
| 10 | Baseline Hold 재진입 | **A** |

---

## 5. 즉시 중단 조건

변경 작업 중 아래 발생 시 **즉시 중단 + 롤백**:

| 조건 | 조치 |
|------|------|
| baseline-check HARD_DRIFT | 변경 취소 + git revert |
| 변경 범위 밖 기준선 항목 깨짐 | 변경 취소 + 원인 조사 |
| 금지 task 재등장 | beat schedule 원복 |
| private API 호출 흔적 | 변경 취소 + A 보고 |
| 회귀 테스트 기존 항목 FAIL | 변경 취소 + 수정 후 재시도 |
| A가 중단 지시 | 즉시 중단 |

---

## 6. 파일 경로 기반 위험도 참조표

| 경로 패턴 | 기본 등급 |
|----------|----------|
| `docs/**` | L0 |
| `tests/**` | L1 |
| `app/api/routes/ops.py` (read-only 추가) | L2 |
| `app/api/routes/ops.py` (로직 변경) | L3 |
| `app/main.py` (lifespan) | L3 |
| `workers/celery_app.py` | L3~L4 |
| `exchanges/*.py` (guard 변경) | L4 |
| `app/core/config.py` (mode 변경) | L4 |
| `ops_state.json` | L3 (A만 편집) |

---

## 7. 상태 전이 정렬 변경 분류표 (GR-RULE-03)

| 변경 대상 | 변경 성격 | 등급 |
|----------|----------|------|
| `tests/*.py` 기대값 수정 | 테스트 정렬 | **L1** |
| `tests/*.py` assertion 완화/명확화 | 테스트 정렬 | **L1** |
| `tests/conftest.py` fixture 수정 | 테스트 인프라 | **L1** |
| `app/api/routes/ops.py` 정책 판단 로직 | 운영 API 정책 표현 | **L2** |
| `app/api/routes/ops.py` 신규 읽기 전용 API | 관측 확장 | **L2** |
| `app/main.py` lifespan 변경 | 런타임 영향 | **L3** |
| `workers/celery_app.py` schedule/fingerprint | 런타임/정책 | **L3-L4** |
| `ops_state.json` 값 변경 | 상태원천 | **L3** (A만 편집) |
| `exchanges/*.py` guard 변경 | 실행 경로 | **L4** |
| `app/core/config.py` mode 변경 | 정책 | **L4** |

---

## 8. 보호 구간 규칙 (GR-RULE-01~03)

| 규칙 | 내용 |
|------|------|
| **GR-RULE-01** | `ops_state.json` 상태 전이 전에 "연쇄 수정 등급 분석"을 수행한다. 전이로 인해 L2+ 코드 변경이 필요하면, 전이 자체를 L2+ 작업으로 분류한다. |
| **GR-RULE-02** | 보호 구간 중 L2+ 변경 필요 발견 시, 변경을 실행하지 않고 A에게 예외 승인을 먼저 요청한다. |
| **GR-RULE-03** | 상태 전이 정렬 변경 분류표(7절)를 기준으로 변경 등급을 판단한다. |

**재발 시 기본 원칙:** revert 검토 우선, 사후 승인은 예외적 경로.

---

## 9. 예외 승인 레지스터

모든 절차 예외는 `docs/operations/evidence/exception_register.md`에 기록.
각 건은 일회성이며 선례로 사용 금지.

---

**Change Gate Policy 작성 완료. (v2 — GR-RULE 추가, 2026-04-04)**
