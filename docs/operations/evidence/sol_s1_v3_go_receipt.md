# SOL S-1 V-3 — Shadow Drift Verification Explicit GO

**발행일:** 2026-04-10
**chain:** Phase C Post-Closure — SOL S-1 Root-Cause Chain
**step:** V-3
**previous_chain:** V-2 (CLOSED / PASS — C1C2_N2 6/6 Primary + 2/2 Secondary)
**selection_reason:** drift_stability_verification_after_structural_bottleneck_passed
**design_reference:** `docs/operations/evidence/sol_s1_v3_design.md`

---

## Explicit GO — Verbatim

```text
V-3 SHADOW DRIFT VERIFICATION GO

목적
V-2에서 PASS한 C1C2_N2 config가 실시간 shadow 환경에서도 ECR / block_rate / same_direction_ratio / invalid run 기준을 유지하는지 검증한다.
이번 단계의 목적은 수익률 검증이 아니라 drift 안정성 검증이다.

공식 실행 범위
- Primary config = C1C2_N2 only
- Fallback N1 = candidate 기록만 허용, shadow 실행 금지
- 기준 설계서 = docs/operations/evidence/sol_s1_v3_design.md
- auto_advance = 금지

잠금 기준
- 최소 기간 = 96 bars
- Yellow 연장 = 최대 1회, +48 bars
- invalid run = 0
- 최소 trades = 10 이상

상태 전이 기준
- Green:
  ECR >= 60%
  block_rate <= 40%
  SD_ratio <= 80.9%
  invalid = 0

- Yellow:
  ECR 55% 이상 60% 미만 또는
  block_rate 40% 초과 45% 이하 또는
  SD_ratio 80.9% 초과 85.9% 이하
  12-bar rolling 기준 연속 3회 Yellow window 시 Yellow 확정
  Yellow는 즉시 실패가 아니라 관찰 연장 상태

- Red:
  ECR < 55% 또는
  block_rate > 45% 또는
  SD_ratio > 85.9% 또는
  invalid >= 1
  Red 진입 시 즉시 fail-closed 중단

Same-direction 기준선
- baseline_sd_ratio = 70.9%
- delta_pp = sd_ratio_shadow - 70.9
- delta_pp <= +10pp = Green
- +10pp ~ +15pp = Yellow
- > +15pp = Red

V-2 baseline 고정 참조값
- ECR = 64.3%
- block_rate = 35.7%
- same_direction_ratio = 70.9%
- fitness = 0.4428

허용 산출물
1. V-3 shadow 실행 스크립트 또는 모듈
2. shadow evidence log / receipt
3. V-3 completion receipt

금지 사항
- N=3 확장 금지
- same-direction 허용 구조 변경 금지
- SL/TP 최적화 금지
- 수익성 판정 금지
- fallback 자동 전환 금지
- 기준선 동적 변경 금지
- 설계서 기준 수치 임의 수정 금지

PASS 조건
1. 기간 충족 (>= 96 bars, invalid = 0, trades >= 10)
2. 최종 상태 = Green
3. ECR >= 60%
4. block_rate <= 40%
5. same_direction_delta <= +10pp
6. fitness_ratio >= 0.80
7. Yellow 연장 <= 1회 및 복귀 완료

V-4 unlock 조건
- V-3 PASS와 별도
- receipt completeness 100%
- Yellow 연장 0회
- 별도 explicit GO 필요

종료 규칙
- completion receipt 작성 후 STANDBY 복귀
- V-4 또는 fallback N1 검증은 별도 explicit GO 없이는 시작 금지
```

---

## 아이디어 3건 반영 조항 (리뷰 추가)

### 1. 허용 수정 대상 파일/모듈 범위 (아이디어 1)

**허용 수정:**
- V-3 shadow 전용 script 또는 module (신규 파일)
- V-3 전용 receipt / evidence log 관련 파일
- `docs/operations/evidence/sol_s1_v3_*.{md,json}` 산출물만

**금지 수정:**
- V-2 baseline 산출물 (`sol_s1_v2_*.{md,json}`)
- sealed design 문서 (`sol_s1_v3_design.md` 본문 수정 금지 — 참조만)
- `strategies/smc_wavetrend_strategy.py` 등 strategy parameter source
- `scripts/sol_s1_v1_*.py`, `scripts/sol_s1_v2_*.py` (기존 backtest)
- `CLAUDE.md`, 헌법/거버넌스 문서

### 2. Completion Receipt 필수 필드 (아이디어 2)

V-3 completion receipt에 아래 4개 필드를 **반드시** 포함:

```json
{
  "final_state": "GREEN" | "YELLOW" | "RED",
  "yellow_extension_count": int,
  "same_direction_delta_pp": float,
  "receipt_completeness_pct": float
}
```

이 4개는 V-4 unlock 판정의 직접 입력이 된다.

### 3. V-3 종료 후 STANDBY 문구 강제 (아이디어 3)

V-3 completion receipt의 마지막 줄은 반드시 다음 중 하나:

```
STATE = STANDBY
다음 단계 = 별도 explicit GO 없이는 시작 금지
auto_advance = 금지
```

PASS가 나와도 다음 단계 자동 제안 금지. 체인이 촘촘하므로 STANDBY 강제.

---

## GO 발행 헤더

| 항목 | 값 |
|------|---|
| `chain` | Phase C Post-Closure — SOL S-1 Root-Cause Chain |
| `step` | V-3 (Shadow Drift Verification) |
| `candidate` | C1C2_N2 (N=2, max_positions=2, size=1%) |
| `fallback_candidate` | C1C2_N1 (candidate 기록만) |
| `verification_type` | Shadow drift stability (수익률 검증 아님) |
| `previous_step` | V-2 CLOSED / PASS |
| `design_reference` | `sol_s1_v3_design.md` |
| `auto_advance` | **false** |
| `scope_violation_allowed` | **false** |
| `b1_core_modification_allowed` | **false** |

---

## GO 발행 헌법 확인

```
✓ V-2 PASS 확인 (6/6 Primary + 2/2 Secondary)
✓ V-3 설계서 CLOSED / ACCEPT
✓ 4개 숫자 잠금 완료 (shadow 기간, state 수치, SD 공식, fallback 규칙)
✓ 금지영역 7건 명시
✓ PASS 조건 7개 / V-4 unlock 조건 분리
✓ auto_advance 금지 유지
✓ 허용 수정 범위 잠금 추가 (아이디어 1)
✓ completion receipt 필수 필드 잠금 (아이디어 2)
✓ STANDBY 강제 (아이디어 3)
```

---

## Chain 상태 갱신

| 단계 | 상태 | 비고 |
|------|------|------|
| Root-Cause Analysis | CLOSED | COMPLETE |
| V-1 (Candidate 1 only) | CLOSED | INFORMATIVE_FAIL — 병목 전환 |
| V-2 (Candidate 1+2) | CLOSED | PASS — C1C2_N2 best |
| **V-3 (Shadow drift)** | **GO 발행 / NOT STARTED** | 본 receipt |
| V-4 (Paper) | LOCKED | V-3 PASS + 추가 unlock 조건 |

---

## 봉인

- V-3는 C1C2_N2 config의 shadow drift 감시 검증이다
- 설계서는 `sol_s1_v3_design.md`에 CLOSED/ACCEPT 상태로 고정되어 있다
- 공식 실행 범위는 C1C2_N2 단일이다 — N1 자동 전환 금지
- 잠금 기준: 96 bars, invalid=0, trades≥10, Yellow 연장 최대 1회
- Green/Yellow/Red 상태 전이는 숫자 기반으로 잠겨 있다
- Same-direction 급증 기준선 = 70.9% (V-2 baseline 고정)
- V-4 unlock 조건은 V-3 PASS와 별도로 분리되어 있다
- 허용 수정 범위는 V-3 전용 산출물로 제한된다
- completion receipt에 final_state, yellow_extension_count, same_direction_delta_pp, receipt_completeness_pct 필수
- 종료 후 STANDBY 강제 — auto_advance 금지
- 다음 합법 단계는 V-3 shadow 실행 스크립트/모듈 범위 잠금이다
