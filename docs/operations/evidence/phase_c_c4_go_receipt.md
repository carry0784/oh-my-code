# Phase C C-4 — GO Receipt (W-track, LIMITED)

**발행일:** 2026-04-10
**판정:** GO (C-4 한정, W-track forward stability 진단/검증 only)
**근거:** C-3 CLOSED (MAINTAINED_FAIL) + 사용자 C-4 only GO 선택
**selection_reason:** phase_progress_priority
**previous_chain:** C-3 CLOSED (MAINTAINED_FAIL: 양 자산 구조적 regime 편중)

---

## 경로 상태

| 경로 | 상태 | 비고 |
|------|------|------|
| **C-4 (W-track forward stability)** | **ACTIVE** | 본 GO 대상 |
| SOL S-1 follow-up | **HOLD** | C-4 완료 후 재평가 |
| R-track 재개방 | **HOLD** | 재개방 트리거 충족 시에만 |
| C-5 (종합 verdict) | LOCKED | C-4 완료 + 별도 GO 필요 |

---

## GO 선언문 (원문)

```
PHASE_C C-4 ONLY GO

승인 범위:
- 다음 단계는 C-4 only로 제한한다.
- 목적은 W-track forward stability 진단/검증이다.
- auto_advance_allowed = false 유지.
- SOL S-1 follow-up은 본 GO 범위에 포함하지 않는다.

전제 상태:
- C-1 = CLOSED (SUCCESS)
- C-2 = SEALED (ASYMMETRIC)
- C-3 = CLOSED (MAINTAINED_FAIL)
- C-3 canonical_run = blyaioqjb

허용 작업:
1. C-4 진단/검증 범위 확정
2. forward stability 관련 관측/해석 자료 수집
3. C-4 산출물 작성
4. C-4 completion receipt 작성

금지 작업:
- SOL S-1 follow-up 착수
- R-track 재개방
- 전략 로직 변경
- live 적용
- 별도 GO 없는 C-5 착수
- auto advance

잠금:
- SOL S-1 follow-up = HOLD
- C-5 = LOCKED

selection_reason:
- phase_progress_priority
```

---

## W-track 진단 범위 (GO package Section 5 기준)

### 문제 정의

WF efficiency가 양 자산 모두 음수이며, FW2에서 cliff 패턴이 발생한다.

| 지표 | SOL | BTC |
|------|-----|-----|
| WF efficiency | -0.4959 | -2.9074 |
| WF threshold | 0.50 | 0.50 |
| WF consistency | 0.4 | 0.2 |
| WF is_overfit | False | False |
| FW2 fitness (baseline) | 0.0000 | 0.0000 |
| Cliff 패턴 | FW2에서 fitness 급락 | FW2에서 fitness 급락 |

### 핵심 질문

GO package Section 5.1의 핵심 가설:
> cliff의 근본 원인은 **trade scarcity에 의한 fitness 0.0 penalty**이므로,
> S-track 완료 후 자연 해소 여부를 먼저 확인해야 한다.

C-2 결과에서:
- BTC S-3: FW2 trades 8→12 (min_trades 충족), FW2 fitness 0→0.90
- SOL S-3: FW2 trades 5→8 (min_trades 미달), FW2 fitness 여전히 0

따라서 C-4의 검증 목표는:
1. **BTC**: S-3 적용 시 WF efficiency가 자연 개선되는가?
2. **SOL**: scarcity 미해결 상태에서 WF efficiency 개선 가능한가?
3. **전체**: cliff 패턴이 scarcity penalty에 의한 인위적 현상인가, 전략 일반화 한계인가?

### 허용 접근 방식

| # | 접근 | 허용 여부 |
|---|------|-----------|
| W-1 | WF window 수 조정 (n_windows) | 조건부 허용 (별도 sub-GO) |
| W-2 | Train/Forward 비율 조정 | 조건부 허용 (S-3 연계) |
| W-3 | WF efficiency 임계값 하향 | **금지** |
| W-4 | WF overfit 판정 기준 완화 | **금지** |

---

## B-1 Core 보호

| 심볼 | 허용 |
|------|------|
| `FullCycleConfig` | 미변경 |
| `SegmentResult` | 미변경 |
| `FullCycleResult` | 미변경 |
| `SegmentSplitter` | 미변경 |
| `WalkForwardValidator` | **읽기 전용** |

---

## 상태 전이

```
C-4: NONE -> GO (W-track forward stability 진단/검증 only)
active_path: C-4 (W-track)
held_path: SOL S-1 follow-up, R-track reopen
next_unlocked_step: C-4 (진단/검증 only)
auto_advance_allowed: false
```

---

## 봉인

- 본 receipt는 C-4 한정 GO 증거이다
- W-track forward stability 진단/검증만 허용된다
- SOL S-1 follow-up은 HOLD 상태이다
- R-track 재개방은 별도 트리거 충족 시에만 가능하다
- C-5 착수 권한을 부여하지 않는다
- live 적용 권한을 부여하지 않는다
- B-1 core 이중 잠금(line + symbol)은 유지된다
