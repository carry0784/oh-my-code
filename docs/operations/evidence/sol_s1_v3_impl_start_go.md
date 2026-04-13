# SOL S-1 V-3 — Shadow Implementation Start GO

**발행일:** 2026-04-10
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3 implementation start
**previous_receipts:**
- `sol_s1_v3_design.md` (CLOSED/ACCEPT)
- `sol_s1_v3_go_receipt.md` (V-3 explicit GO)
- `sol_s1_v3_impl_scope_lock.md` (구현 범위 잠금)

**authorization_scope:** 구현만 허가, 실행(run) 계속 금지

---

## 목적

V-3 shadow drift verification의 실행 스크립트/모듈 **구현 착수**를 허가한다. 본 GO는 구현만 허가하며, shadow 실행(run)과 PASS/FAIL 판정은 허가하지 않는다.

---

## Explicit Implementation Start GO — Verbatim

```text
V-3 SHADOW IMPLEMENTATION START GO

목적
V-3 shadow drift verification의 실행 스크립트/모듈 구현 착수를 허가한다.
이번 GO는 구현만 허가하며, shadow 실행(run)과 PASS/FAIL 판정은 허가하지 않는다.

참조 문서
- 설계 기준: docs/operations/evidence/sol_s1_v3_design.md
- 구현 범위 잠금 기준: docs/operations/evidence/sol_s1_v3_impl_scope_lock.md

구현 허가 범위
- 기본 구현 형태는 단일 스크립트 1개로 한다:
  scripts/sol_s1_v3_shadow_run.py
- helper 분리가 불가피한 경우에만 아래 prefix 신규 파일을 추가 허용한다:
  scripts/sol_s1_v3_shadow_*.py
- evidence 산출물 파일은 아래만 허용한다:
  docs/operations/evidence/sol_s1_v3_shadow_log.json
  docs/operations/evidence/sol_s1_v3_completion_receipt.md

구현 금지 범위
- 기존 V-1/V-2 산출물 수정 금지
- sealed design / GO receipt / scope lock 문서 수정 금지
- strategies/smc_wavetrend_strategy.py 및 부모 클래스 수정 금지
- backtesting/engine.py, fitness.py, performance.py 수정 금지
- N1 shadow 실행 구현 금지
- N3 비교/확장 구현 금지
- 수익성 최적화 로직 추가 금지
- baseline 값/기준 동적 변경 금지

필수 반영 사항
- evidence log 필수 필드는 18개로 고정한다
- design_version / go_receipt_id 필수 유지
- stop_reason enum 6개 외 추가 금지
- stop_reason_detail은 160자 이하, 단일 라인, 숫자/임계값/시점만 허용
- completion receipt에 baseline_mutation=false, fallback_executed=false 필수

구현 단계에서 허용되는 검증
- 문법 검증
- import 검증
- schema/enum/receipt field completeness 검증
- 파일 생성 및 경로 검증

구현 단계에서 금지되는 행위
- 96 bars shadow run 실행 금지
- Yellow/Red/Green 실측 판정 금지
- V-3 PASS/FAIL 선언 금지
- V-4 unlock 논의 금지

구현 완료 후 처리 절차
1. implementation completion receipt 작성
2. 변경 파일 목록 제출
3. evidence/log/enum/schema 잠금 준수 여부 제출
4. STATE = STANDBY
5. 다음 단계 = 별도 explicit GO 없이는 시작 금지
6. auto_advance = 금지

구현 completion receipt 필수 확인 항목
- implementation_started = true
- implementation_completed = true
- execution_started = false
- baseline_mutation = false
- fallback_executed = false
- required_fields_count = 18
- stop_reason_enum_count = 6
```

---

## 아이디어 3건 반영 조항 (리뷰 추가)

### 1. 구현 타임스탬프 필드 (아이디어 1)

Implementation completion receipt에 **타임스탬프 2개** 필수:

| 필드 | 타입 | 설명 |
|------|------|------|
| `implementation_started_at` | ISO8601 | 구현 착수 시각 |
| `implementation_completed_at` | ISO8601 | 구현 완료 시각 |

run receipt와 혼동 방지 목적.

### 2. `execution_started = false` 유지 (아이디어 2)

구현 단계에서는 반드시 `execution_started = false`여야 한다. 이 필드가 `true`이면:
- Implementation GO 위반 (실행 금지 조항 위반)
- Implementation completion receipt invalid
- 별도 run GO 없이 실행 발생 증거로 간주

**이 필드는 이번 GO의 핵심 잠금 장치이다.**

### 3. Module Split 추적 필드 (아이디어 3)

Helper 파일 분할 발생 시 completion receipt에 **분할 추적 2개** 필수:

| 필드 | 타입 | 설명 |
|------|------|------|
| `module_split_used` | bool | helper 파일이 1개 이상 생성되었는가 |
| `helper_file_count` | int | 생성된 helper 파일 개수 (0-2 권장) |

단일 스크립트 원칙 준수 여부 추적.

`helper_file_count ≥ 3`이면 단일 스크립트 원칙 위반 — 근거 문서화 필수.

---

## Implementation Completion Receipt 최종 필수 필드

본 GO + 이전 receipt 합산:

```json
{
  "implementation_started": true,
  "implementation_completed": true,
  "execution_started": false,
  "implementation_started_at": "ISO8601",
  "implementation_completed_at": "ISO8601",
  "baseline_mutation": false,
  "fallback_executed": false,
  "required_fields_count": 18,
  "stop_reason_enum_count": 6,
  "module_split_used": false,
  "helper_file_count": 0,
  "created_files": ["path1", "path2", ...],
  "modified_files": [],
  "design_version": "sol_s1_v3_design.md@2026-04-10",
  "go_receipt_id": "sol_s1_v3_impl_start_go.md",
  "scope_lock_id": "sol_s1_v3_impl_scope_lock.md"
}
```

**금지 조합:**
- `execution_started = true` → 즉시 invalid
- `modified_files != []` (read-only 파일 포함 시) → 즉시 invalid
- `baseline_mutation = true` → 즉시 invalid
- `fallback_executed = true` → 즉시 invalid

---

## 구현 단계 허용 검증 범위 (확정)

### 허용

| 검증 | 방법 |
|------|------|
| 문법 검증 | `python -m py_compile scripts/sol_s1_v3_shadow_run.py` |
| Import 검증 | `python -c "import scripts.sol_s1_v3_shadow_run"` (또는 module import test) |
| Schema 검증 | evidence log dataclass / dict schema 필드 완결성 확인 |
| Enum 검증 | stop_reason enum 6개 확인 |
| Receipt field 검증 | completion receipt 필수 필드 11개 존재 확인 |
| 파일 생성 검증 | 허용 경로 외 파일 생성 없음 확인 |

### 금지

| 금지 행위 | 근거 |
|----------|------|
| 96 bar shadow run 실행 | 실행은 별도 run GO 필요 |
| 실제 ECR/block_rate 측정 | 실행 금지의 연장 |
| Green/Yellow/Red 판정 | 실측 판정 금지 |
| V-3 PASS/FAIL 선언 | 실측 없는 선언 금지 |
| V-4 unlock 논의 | 본 GO 범위 외 |

---

## 권한 경계 (Authorization Matrix)

| 행위 | 본 GO 허가 | 다음 GO 필요 |
|------|-----------|-------------|
| 신규 스크립트 생성 | ✅ | — |
| Helper 모듈 생성 (최대 1-2개) | ✅ (불가피한 경우) | — |
| Evidence log schema 구현 | ✅ | — |
| Stop reason enum 구현 | ✅ | — |
| Completion receipt 템플릿 생성 | ✅ | — |
| 문법/import/schema 검증 | ✅ | — |
| 96 bar shadow run | ❌ | V-3 run GO |
| ECR/block_rate 실측 | ❌ | V-3 run GO |
| Green/Yellow/Red 판정 | ❌ | V-3 run GO |
| PASS/FAIL 선언 | ❌ | V-3 run GO |
| V-1/V-2 산출물 수정 | ❌ | 금지 (영구) |
| Strategy source 수정 | ❌ | 금지 (영구) |
| N1 shadow 실행 | ❌ | 별도 체인 |
| N3 확장 | ❌ | 금지 (영구) |

---

## GO 발행 헌법 확인

```
✓ V-3 설계서 CLOSED / ACCEPT
✓ V-3 explicit GO 발행 완료
✓ V-3 구현 범위 잠금 완료
✓ 단일 스크립트 우선 원칙 명시
✓ Helper 분할 허용 조건 명시 (1-2개)
✓ 구현 단계 허용 검증 범위 명시
✓ 실행(run) 금지 명시
✓ Implementation completion receipt 필수 필드 잠금
✓ Evidence log 필수 필드 18개 (이전 문서 정정)
✓ 타임스탬프 필드 추가 (아이디어 1)
✓ execution_started=false 핵심 잠금 유지 (아이디어 2)
✓ module_split 추적 필드 추가 (아이디어 3)
✓ Authorization matrix 명시
✓ auto_advance 금지 유지
```

---

## Chain 상태 갱신

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 | CLOSED | INFORMATIVE_FAIL |
| V-2 | CLOSED | PASS (C1C2_N2) |
| V-3 설계서 | CLOSED | ACCEPT |
| V-3 explicit GO | COMPLETE | `sol_s1_v3_go_receipt.md` |
| V-3 구현 범위 잠금 | COMPLETE | `sol_s1_v3_impl_scope_lock.md` (필드 수 18로 정정) |
| **V-3 구현 착수 허가** | **COMPLETE** | **본 receipt** |
| V-3 구현 실행 | 허가됨 (본 GO) | 구현 완료 시 STANDBY |
| V-3 shadow run | LOCKED | 별도 run GO 필요 |
| V-3 PASS/FAIL 판정 | LOCKED | run GO 필요 |
| V-4 | LOCKED | V-3 PASS + 추가 unlock 조건 |

---

## 봉인

- V-3 shadow 구현 착수가 본 receipt로 허가되었다
- 기본 구현 형태는 단일 스크립트 (`scripts/sol_s1_v3_shadow_run.py`)
- Helper 분할은 불가피한 경우에만 1-2개 허용 (3개 이상은 위반)
- Evidence log 필수 필드는 18개로 고정되었다 (이전 문서 17 표기 정정)
- Stop reason enum은 6개로 잠겨 있다
- Implementation completion receipt는 execution_started=false를 필수로 포함한다
- baseline_mutation, fallback_executed는 반드시 false여야 한다
- `implementation_started_at`, `implementation_completed_at` 타임스탬프 필수
- `module_split_used`, `helper_file_count` 추적 필수
- 구현 단계 허용 검증: 문법/import/schema/enum/field/파일생성만
- 구현 단계 금지: 96 bar run, 실측 ECR/block, Green/Yellow/Red 판정, PASS/FAIL 선언
- 구현 완료 후 STATE = STANDBY, run은 별도 explicit GO 필요
- auto_advance = 금지
