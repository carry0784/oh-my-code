# 예외 승인 레지스터

**작성일:** 2026-04-04
**관리 권한:** A

---

## 등록 규칙

- 모든 절차 예외 승인은 본 레지스터에 기록
- 각 건은 일회성이며 선례로 사용 금지
- 재발 시 기본 원칙: revert 검토 우선

---

## 예외 목록

### EX-001: ops.py L2 선반영

| 항목 | 값 |
|------|-----|
| **예외 ID** | EX-001 |
| **발생 시점** | 2026-04-04, Guarded Release 24h LOCK 구간 |
| **변경 파일** | `app/api/routes/ops.py` |
| **변경 등급** | L2 (운영 API 정책 표현) |
| **허용 범위** | L0/L1 only |
| **실제 리스크** | 없음 — 읽기 전용 관측 API, write path 무관 |
| **회귀** | 4444/4444 PASS |
| **승인 사유** | revert 시 /baseline-check HARD_DRIFT 왜곡, 실질 무해, 관측 정확성 유지 |
| **승인 유형** | 사후 예외 승인 (retroactive exception) |
| **A 판정** | APPROVED — 경로 B |
| **재발 방지** | GR-RULE-01, GR-RULE-02, GR-RULE-03 채택 |
| **선례 사용** | **금지** — 일회성 예외로 봉인 |
| **정리서 위치** | `docs/operations/evidence/guarded_release_l2_exception_note_2026-04-04.md` |

### EX-002: runtime_strategy_loader.py Casing Alignment

| 항목 | 값 |
|------|-----|
| **예외 ID** | EX-002 |
| **발생 시점** | 2026-04-04, Limited L3 Model Skeleton 작업 중 |
| **변경 파일** | `app/services/runtime_strategy_loader.py` |
| **변경 등급** | L3 (런타임 인접 서비스 상수) |
| **허용 범위** | Model skeleton only (모델 4종 + Alembic + 모델 테스트) |
| **변경 내용** | `LOADABLE_STRATEGY_STATUSES` frozenset 문자열 3개 lowercase→UPPERCASE |
| **변경 라인** | Line 56-58 (3줄) |
| **실제 리스크** | 없음 — beat disabled, DATA_ONLY, 실행 경로 도달 불가, 테스트에서만 호출 |
| **로직 변화** | 없음 — 문자열 리터럴 케이싱만, 분기/함수/호출 구조 무변경 |
| **불가피성** | 높음 — PromotionStatus enum UPPERCASE 전환의 cascading effect |
| **회귀** | 4593/4593 PASS |
| **승인 사유** | 모델 enum 정렬의 파급 수정, revert 시 3건 FAIL 재발 + 추가 workaround 필요, 운영 리스크 없음 |
| **승인 유형** | 사후 예외 승인 (retroactive exception) |
| **A 판정** | APPROVED — 변경 유지 승인 |
| **재발 방지** | enum cascading impact checklist 도입, `app/services/*` 변경 시 사전 예외 승인 필수 |
| **선례 사용** | **금지** — 일회성 예외로 봉인, 동일 사유 자동 승인 불가 |
| **정리서 위치** | `docs/operations/evidence/EX-002_runtime_strategy_loader_casing.md` |

---

## RI-2B-1 예외 (0건)

> RI-2B-1 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> FROZEN/RED 접촉 0건. DB write = INSERT only (shadow_write_receipt). business table write 0.
> dry_run=True, executed=False, business_write_count=0: 강제 고정. receipt-only.

---

## RI-2B-2a 예외 (0건)

> RI-2B-2a 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> FROZEN/RED 접촉 0건. 기존 RI-2B-1 코드 수정 0줄. 모델/마이그레이션 변경 0건.
> EXECUTION_ENABLED=False 하드코딩. 실제 business table write 불가.
> execute_bounded_write, rollback_bounded_write 코드 존재만 확인. 실행 권한 미생성.
> execution_enabled False→True 전환은 RI-2B-2b 별도 A 승인 필요.

---

## RI-2A-2b 예외 (0건)

> RI-2A-2b 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> FROZEN/RED 접촉 0건. SEALED 서비스 수정 0줄. business table write 0.
> DRY_SCHEDULE=True 하드코딩. beat entry 주석 상태. purge 함수 미구현.
> 3중 차단 해제는 각각 별도 A 승인 필요.
> 초기 bind=True 실패 → 수정 후 4회 연속 5456/5456 PASS (superseded failure).

---

## RI-2A-2a 예외 (0건)

> RI-2A-2a 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> FROZEN/RED 접촉 0건. DB write = INSERT only (shadow_observation_log). business table write 0. manual trigger only.

---

## Stage 3B-2 예외 (0건)

> Stage 3B-2 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> RED/AMBER 파일 접촉 0건. FROZEN 함수 변경 0줄.

---

## Stage 3B-1 관찰 항목 (Observation Items)

> Stage 3B-1 봉인 시 예외 0건. 아래는 관찰 항목(비차단).

### OBS-001: AsyncMockMixin RuntimeWarning (10건)

| 항목 | 값 |
|------|-----|
| **관찰 ID** | OBS-001 |
| **발생 시점** | Stage 2B 이후 지속 (Stage 3B-1 신규 아님) |
| **발생 파일** | `tests/test_asset_service_phase2b.py` (10개 테스트) |
| **경고 위치** | `app/services/asset_service.py` L146, L251 |
| **경고 유형** | RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited |
| **원인** | Stage 2B async mock 패턴에서 `self.db.add()` 호출 시 AsyncMock coroutine 미대기 |
| **Stage 3B-1 관련** | **없음** — Stage 3B-1은 asset_service.py UNTOUCHED |
| **운영 리스크** | **없음** — 테스트 전용 mock 경고, 운영 코드 무관 |
| **분류** | **PRE-EXISTING observation item** (봉인 비차단) |
| **향후 조치** | Stage 2B 테스트 리팩터링 시 AsyncMock 패턴 정리 가능 (우선순위 낮음) |

---

## Stage 4A 예외 (0건)

> Stage 4A 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (clean rerun에서 PASS, carried flaky 유지).
> Note: clean rerun 5248/5248 달성.

---

## Stage 4B 예외 (0건)

> Stage 4B 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> Clean run 5260/5260. RED/AMBER 파일 접촉 0건. 운영 코드 변경 0줄.

---

## RI-1 예외 (0건)

> RI-1 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> Clean run 5299/5299. FROZEN/RED 파일 접촉 0줄. 운영 코드 변경 0줄.
> pipeline_shadow_runner.py는 read-only shadow 전용, DB write 0, state change 0.

---

## RI-2A-1 예외 (0건)

> RI-2A-1 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> Clean run 5330/5330. FROZEN/RED 파일 접촉 0건. DB write 0. read-through SELECT only.
> shadow_readthrough.py는 read-through 비교 전용, 운영 반영 계층 아님, 2 tables LIMIT 1 bounded.

---

## RI-2A-2a 예외 (0건)

> RI-2A-2a 봉인 시 예외 0건. 신규 경고 0건. OBS-001 유지 (10건, PRE-EXISTING).
> Clean run 5354/5354. FROZEN/RED 파일 접촉 0건.
> DB write = INSERT only (shadow_observation_log). business table write 0. manual trigger only.
> shadow_observation_service.py는 append-only observation 전용, 운영 판단 근거 아님, UPDATE/DELETE 영구 금지.
