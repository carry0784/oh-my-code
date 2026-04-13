# Phase C C-3 — GO Receipt (R-track, LIMITED)

**발행일:** 2026-04-10
**판정:** GO (C-3 한정, R-track regime 진단 only)
**근거:** C-2 SEALED (ASYMMETRIC) + 사용자 C-3 only GO 선택
**selection_reason:** phase_progress_priority
**previous_chain:** C-2 SEALED (ASYMMETRIC: BTC=PASS / SOL=INFORMATIVE_FAIL)

---

## 경로 상태

| 경로 | 상태 | 비고 |
|------|------|------|
| **C-3 (R-track regime 진단)** | **ACTIVE** | 본 GO 대상 |
| SOL S-1 follow-up | **HOLD** | C-3 완료 후 재평가 |
| C-4 (W-track) | LOCKED | C-3 완료 + 별도 GO 필요 |
| C-5 (종합 verdict) | LOCKED | C-1~C-4 완료 필요 |

---

## GO 선언문 (원문)

```
PHASE_C C-3 ONLY GO

승인 범위:
- 다음 단계는 C-3 only로 제한한다.
- 목적은 R-track regime 진단이다.
- auto_advance_allowed = false 유지.
- SOL S-1 follow-up은 본 GO 범위에 포함하지 않는다.

허용 작업:
1. C-3 진단 범위 확정
2. regime 관련 관측/해석 자료 수집
3. C-3 산출물 작성
4. C-3 completion receipt 작성

금지 작업:
- SOL S-1 follow-up 착수
- S-track 추가 구현/확장
- live 적용
- 별도 GO 없는 후속 step 착수
- auto advance

잠금:
- SOL S-1 follow-up = HOLD
- C-2 봉인 상태 유지

selection_reason:
- phase_progress_priority
```

---

## C-3 진단 범위 (GO package Section 4 기준)

### 문제 정의

RegimeDetector(K-Means k=5)가 암호화폐 1H 데이터의 84-96%를 ranging으로 분류한다.
이는 탐지기의 문제인지 시장 자체의 특성인지 구분이 필요하다.

| 지표 | SOL | BTC |
|------|-----|-----|
| RDS | 0.274 | 0.076 |
| Ranging 비율 | 84.8% | 96.4% |
| RDS threshold | 0.55 | 0.55 |
| 달성 여부 | FAIL | FAIL |

### 허용 접근 방식

| # | 접근 | 허용 여부 |
|---|------|-----------|
| R-1 | 대안 regime 지표 연구 (realized vol, choppiness, DER) | **허용** |
| R-2 | RegimeDetector 파라미터 조정 (k값, 피처 벡터) | 조건부 허용 (별도 sub-GO) |
| R-3 | 멀티 타임프레임 regime (1H+4H/1D) | 허용 (연구 후 판단) |
| R-4 | RDS 임계값 하향 (0.55→0.40) | **금지** |
| R-5 | Regime 분류 자체 제거 | **금지** |

### 실행 단계

1. **진단 단계**: 대안 지표(realized vol, choppiness, DER)로 동일 데이터 regime 재분류
2. **비교 단계**: 현재 K-Means vs 대안 지표의 ranging/trending 비율 비교
3. **판단 단계**: "시장 자체가 ranging인가" vs "탐지기가 과도하게 ranging으로 분류하는가" 결론

### 합법적 종료 조건

C-3의 합법적 종료에는 아래 모두 포함된다:

- **개선 가능**: 대안 지표가 더 균형 잡힌 regime 분포를 산출 → 구현 sub-GO 필요
- **MAINTAINED_FAIL**: 시장 자체가 실제로 ranging 편중이라 RDS 0.55는 현 환경에서 달성 불가 → 정당한 종료

---

## C-3 종료 후 재평가 질문 (사전 고정)

C-3 completion 시점에서 아래 3개 질문에 대한 답변이 있어야 한다:

1. R-track이 **구조적 불가**인가? (시장 자체가 ranging 편중)
2. R-track 개선이 **S-1보다 먼저 다룰 가치**가 있는가?
3. R-track 진단 결과가 **S-track 미해결보다 정보 수익이 큰가**?

---

## B-1 Core 보호

| 심볼 | 허용 |
|------|------|
| `FullCycleConfig` | 미변경 |
| `SegmentResult` | 미변경 |
| `FullCycleResult` | 미변경 |
| `SegmentSplitter` | 미변경 |
| `RegimeDetector` | R-2 sub-GO 시에만 허용, C-3 진단에서는 **읽기 전용** |

---

## 상태 전이

```
C-3: NONE -> GO (R-track regime 진단 only)
active_path: C-3 (R-track)
held_path: SOL S-1 follow-up
next_unlocked_step: C-3 (진단/비교 only)
auto_advance_allowed: false
```

---

## 봉인

- 본 receipt는 C-3 한정 GO 증거이다
- 목적은 R-track regime 진단이며, 구현은 별도 sub-GO가 필요하다
- SOL S-1 follow-up은 HOLD 상태이며, C-3 완료 후 재평가한다
- S-track 추가 확장 권한을 부여하지 않는다
- C-4/C-5 착수 권한을 부여하지 않는다
- live 적용 권한을 부여하지 않는다
- B-1 core 이중 잠금(line + symbol)은 유지된다
- RegimeDetector는 C-3에서 읽기 전용이다
- selection_reason = phase_progress_priority
