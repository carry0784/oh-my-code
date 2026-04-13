# Phase C C-2 — GO Receipt (LIMITED)

**발행일:** 2026-04-10
**판정:** GO (C-2 제한 승인, S-3 shadow/paper only)
**근거:** C-1 SUCCESS + 사용자 C-2 LIMITED GO 선언

---

## GO 선언문 (원문)

```
PHASE_C C-2 LIMITED GO

승인 범위:
- C-2는 S-3 후보만 대상으로 한다.
- 목적은 root-cause 해결이 아니라 low-blast density uplift 검증이다.
- 실행 범위는 shadow / paper only로 제한한다.
- auto_advance_allowed = false 유지.
- C-3 이상 자동 전진 금지.

허용 작업:
1. FW2 비율 10% -> 15% 조정
2. 관련 config / segment allocation 범위의 제한 수정
3. 측정용 비교표 및 receipt 작성
4. SOL / BTC 각각의 before-after density 검증

금지 작업:
- S-1 동시 착수
- S-2 멀티 TF 착수
- SMC/WT 신호 로직 수정
- BacktestingEngine occupancy rule 수정
- B-1 core 및 protected symbol 수정
- live 적용
- 별도 GO 없는 후속 step 착수

검증 항목:
- trade density uplift
- consensus uplift
- blocked-entry ratio 변화
- quality degradation 여부
- protected scope drift 여부

종료 판정:
- PASS: density uplift 확인 + quality hold + scope 위반 0건
- INFORMATIVE_FAIL: uplift 미약/부재이나 진단 자료 유효
- HOLD/BLOCK: scope 위반, live 확장, quality 급락, 보호영역 충돌

산출물:
- 변경 범위 증빙
- before/after density 비교표
- quality 유지 판정표
- C-2 completion receipt

후속 규칙:
- C-2 종료 후에도 다음 단계는 자동 해금하지 않는다.
- C-3 또는 S-1 확장은 별도 explicit GO가 필요하다.
```

---

## 상태 전이

```
C-2: NONE -> LIMITED_GO (S-3 shadow/paper only)
next_unlocked_step: C-2 (density validation only)
auto_advance_allowed: false
```

---

## 봉인

- 본 receipt는 C-2 제한 GO 증거이다
- S-3 shadow/paper 범위만 허용된다
- S-1/S-2/core logic/live 착수 권한을 부여하지 않는다
- C-3 이후 자동 전진을 허용하지 않는다
