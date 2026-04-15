# VAL-PDC-002 Preflight Input Checklist

**Document Type**: Preflight Checklist (pre-evaluation preparation)
**Issue Date**: 2026-04-16
**Version**: v0.1 (초안, P3 종료 전까지 수정 가능)
**Status**: DRAFT (집행 금지, input 준비 전용)
**Authority**: 사용자 analysis response 2026-04-16 — 3단계 "VAL-PDC-002 입력 체크리스트 초안 작성"
**Framework**: 최소 안전장치 v2
**transition_class**: LOCAL_ONLY

---

## 0. 본 문서의 경계 (명시)

| 항목 | 값 |
|---|---|
| `operation_type` | **input preparation checklist** |
| `scope` | VAL-PDC-002 실행 전 필요한 입력 / 전제조건 확인 체크리스트만 |
| `evaluation_execution` | **금지** (P3 종료 전 실행 금지, FT-06 "P3 윈도우 수동 단축 금지" 유지) |
| `judgment` | **금지** (결과 판정은 VAL-PDC-002 실행 이후 별도 receipt) |
| `auto_transition` | **금지** (`P3_END != AUTO_PROMOTION`, 아이디어 3 채택) |
| `ops_state_change` | **없음** (checklist draft 는 readonly prep) |

본 문서는 P3 종료 시점에 "무엇이 준비되어 있어야 하는가"를 미리 고정하기 위한 것이며, 평가 자체를 미리 수행하는 것이 아니다.

---

## 1. VAL-PDC-002 개요 (재확인)

- **대상**: CR-NEW v3.1 post-seal window `P3_POSTSEAL_2026-04-15`
- **실행 조건 게이트**: P3 종료 (`2026-04-28T21:24:18Z`) 이후
- **근거**: `k_v3_residual_items_countermeasures.md` A-02, `REEVAL-PLAN-D001` §1, `FT-06`
- **7 criteria**: MIN_BARS ≥ 336 외 6 개 (각 기준은 `app/services/ppf_val_pdc_002.py` 또는 해당 모듈 참조)

---

## 2. Input 체크리스트

### 2.1 Observation 입력

| # | 필드 | 요구 | 현재 (2026-04-16) | 충족 예상 시점 |
|---|---|---|---|---|
| O-1 | `new_window_started_at` | 기록 완료 | ✅ `2026-04-14T21:24:18Z` | 완료 |
| O-2 | `new_window_baseline_at` | 기록 완료 | ✅ `2026-04-14T21:24:18Z` | 완료 |
| O-3 | `expected_close_at` | 기록 완료 | ✅ `2026-04-28T21:24:18Z` | 완료 |
| O-4 | MIN_BARS ≥ 336 (14D × 24h) | 실관측 | ⏳ 진행 중 | 2026-04-28 |
| O-5 | novelty events ≥ 10 | 실관측 | ⏳ 시장 의존 (외부 요인) | 2026-04-28 가능, 미달 시 별도 판정 |
| O-6 | zero-failure 유지 | 실관측 | ⏳ 관측 중 | 2026-04-28 |
| O-7 | Celery beat scheduler 정상가동 | 검증 | ⏳ worker_pid=187248 / beat_pid=184284 | 주기 확인 |

### 2.2 Registry / Data 정합 입력

| # | 필드 | 요구 | 현재 | 비고 |
|---|---|---|---|---|
| R-1 | REGISTRY structural issue resolved | SSOT | ✅ `cr_new_p3_structural_resolved_declaration_2026-04-15.md` | 확정 |
| R-2 | DATA structural issue resolved | SSOT | ✅ 동일 receipt | 확정 |
| R-3 | PROBE auth deferred 선언 유지 | SSOT | ✅ 동일 receipt | deferred (out of scope for VAL-PDC-002) |
| R-4 | `bar_count` post-seal 기준선 정합 | ops_state.json | ✅ `"0/24 (post-seal)"` (`changelog/0007`) | 완료 |

### 2.3 Gate / Prohibition 입력

| # | 필드 | 요구 | 현재 | 비고 |
|---|---|---|---|---|
| G-1 | `activation_gate.status` | LOCKED 유지 | ✅ LOCKED | VAL-PDC-002 실행으로 unlock 없음 |
| G-2 | `writes_consumed` | 0 | ✅ 0 | 불변 |
| G-3 | `write_budget` | 1 | ✅ 1 | 불변 |
| G-4 | `production_authorized` | FALSE | ✅ FALSE | 불변 |
| G-5 | `DATA_ONLY` 계약 | 훼손 없음 | ✅ 불변 | |
| G-6 | `ETH` 운영 금지 | 유지 | ✅ 해당 없음 (SOL/USDT 대상) | |
| G-7 | `CR-049 P3` 금지 | 유지 | ✅ 불변 | H 보류와 별개 |

### 2.4 Code / Test / Infra 입력

| # | 항목 | 요구 | 현재 | 비고 |
|---|---|---|---|---|
| C-1 | `app/services/ppf_val_pdc_002.py` 존재 | 파일 존재 | 점검 필요 | P3 종료 전 dry-read 권장 |
| C-2 | 7 criteria 스크립트 / 절차 | 사전 점검 | 점검 필요 | dry-run 준비 |
| C-3 | 판정 template receipt 양식 | 사전 준비 | **본 문서에 포함 §4** | DRAFT |
| C-4 | `pytest` 통과 (local) | 녹색 | 본 세션 push 후 미검증 | PR open 시 CI 확인 |
| C-5 | `ruff check` / `ruff format --check` | 녹색 | 미검증 | 동상 |
| C-6 | `typecheck-blocking` (tier 1) | 녹색 | 미검증 | PR open 시 CI |

### 2.5 Docs / Governance 입력

| # | 항목 | 요구 | 현재 | 비고 |
|---|---|---|---|---|
| D-1 | `cr_new_p3_new_window_launch_2026-04-14.md` | sealed | ✅ PR #105 merged | |
| D-2 | `cr_new_p3_structural_resolved_declaration_2026-04-15.md` | sealed | ✅ PR #106 merged | |
| D-3 | `trackedness_preflight_rule.md` | v1.0 | ✅ `changelog/0008` | |
| D-4 | `evidence_index.md` | 최신 (§17 delta) | ✅ `changelog/0005` | |
| D-5 | 최소 안전장치 v2 framework | active | ✅ `changelog/0006` | |

### 2.6 Forbidden Preconditions (금지조항 확인)

VAL-PDC-002 실행 전 아래가 **전부 '준수' 상태** 여야 함:

- ✅ `CR-049 Phase 3` 구현 없음
- ✅ `SEALED PASS` 재개방 없음
- ✅ `DATA_ONLY` 계약 훼손 없음
- ✅ `ETH` 운영 경로 터치 없음
- ✅ `L3·L4` 변경 별도 CR 없이 금지 준수
- ✅ `Gate 무단 개방` 없음
- ✅ `CRNEW_CARRYOVER_FORBIDDEN` 준수 (pre-new-window 데이터 invalidated_runs 로 분리됨)

---

## 3. Output 예상 template (DRAFT)

VAL-PDC-002 실행 결과 receipt 에 들어갈 필드:

```yaml
val_pdc_002_result:
  evaluated_window: P3_POSTSEAL_2026-04-15
  evaluation_started_at: <UTC>
  evaluation_completed_at: <UTC>
  criteria:
    - name: MIN_BARS
      threshold: ">= 336"
      measured: <N>
      pass: true | false
    - name: NOVELTY_COUNT
      threshold: ">= 10"
      measured: <N>
      pass: true | false
    - name: (...5 more criteria...)
  overall:
    criteria_passed: <N> / 7
    verdict: PASS | HOLD (YELLOW) | BLOCK (RED)
  next_allowed_action:
    - PASS → check_paper_entry(tier) 8-conjunction 점검
    - HOLD → 추가 관측 윈도우 설계
    - BLOCK → 원인 분석 + CR 발행
  invariants_unchanged:
    activation_gate_status: LOCKED
    writes_consumed: 0
    production_authorized: FALSE
```

---

## 4. 자동전이 금지 규칙 (아이디어 3 채택)

### 4.1 본 문서에 명문화

> **`P3_END != AUTO_PROMOTION`**
> **`P3_END => eligibility_recheck_only`**

즉, P3 창 종료 이벤트 자체로는 어떤 상향 전이도 발동하지 않는다. P3 종료는 단지 VAL-PDC-002 **실행 허용** 상태로 전환할 뿐이며, promotion / unlock / live path 전이는 별도 사건.

### 4.2 금지 시나리오

다음은 전부 **금지**:

- P3 종료 시점에 자동으로 VAL-PDC-002 실행 (operator or claude-code 수동 실행만 허용)
- VAL-PDC-002 PASS 결과만으로 `activation_gate` unlock
- VAL-PDC-002 PASS 결과만으로 paper trading 진입
- `check_paper_entry()` 내부 조건 우회
- 8-conjunction 일부만 충족하여 promotion 강행

### 4.3 허용 시나리오

- 운영자 또는 claude-code 가 **수동으로** VAL-PDC-002 실행 (별도 receipt)
- 결과에 따라 **별도 판정 receipt + 별도 change control** 수행
- 결과가 PASS 여도 `check_paper_entry()` 8-conjunction **전부** 충족해야 paper trading 진입

### 4.4 관련 기존 금지조항

- `FT-06 P3 윈도우 수동 단축 금지` — 시간적 조기 실행 금지
- `FZ-07 Paper entry HARD_BLOCK` — `state == VAL_PDC_002_ISSUED AND tier == GREEN` 이외 진입 금지

본 규칙(§4.1)은 위 기존 조항과 충돌 없음. 오히려 보강.

---

## 5. Preflight 체크리스트 수행 시점

- **지금 (2026-04-16)**: 본 문서 초안 (DRAFT) 상태, 입력 §2 의 ⏳ 항목은 시간 경과 대기
- **P3 종료 1~2일 전 (2026-04-26~27)**: 입력 §2 모든 항목 재점검, 미충족 항목 대응 절차 수립
- **P3 종료 시점 (2026-04-28)**: 입력 §2 최종 확인, VAL-PDC-002 실행 여부 별도 판단
- **VAL-PDC-002 실행 이후**: §3 output template 기반 실 receipt 작성

---

## 6. 4-Gate (v2) 미저촉

| Gate | 저촉 |
|---|---|
| G1 파괴적 삭제 | ✗ |
| G2 실배포 / 실거래 | ✗ (preparation 문서) |
| G3 비가역 변경 | ✗ (DRAFT, revert 가능) |
| G4 원격 공개 | ✗ (본 문서 commit, push 별도) |

---

## 7. Revision 정책

- v0.1 (2026-04-16): 초안
- 본 문서는 P3 종료 전까지 revision 허용 (append-only 권장)
- P3 종료 후에는 사실상 freeze, VAL-PDC-002 실제 receipt 가 primary

---

## 8. Cross-References

- `docs/operations/evidence/k_v3_residual_items_countermeasures.md` A-02, A-03, A-04, A-05
- `docs/operations/evidence/cr_new_p3_new_window_launch_2026-04-14.md` (새 창 identity)
- `docs/operations/evidence/cr046_sol_stageb_post_seal_reset_2026-04-16.md` (bar_count 기준선)
- `docs/operations/trackedness_preflight_rule.md` (input 경로 분류 시 사용)
- `docs/operations/changelog/0006_framework-revision-g4-adoption_2026-04-16.md` (framework v2)
