# CR-046 SOL C1 — 신호 빈도 기대 기준선

**상태:** SEALED (운영 참고 기준선)
**일시:** 2026-04-08
**근거 문서:** `cr046_sol_c1_skip_signal_analysis.md`

---

## 기준선 정의

| 항목 | 값 | 단위 | 의미 | 근거 등급 |
|------|-----|------|------|-----------|
| 평균 신호 간격 | 110 | bars (4.6일) | Phase 3 SOL 39 trades / 4,320 bars | inferred_from_backtest |
| 경보 임계 (WARN) | 168 | bars (7일) | SIGNAL_DROUGHT_WARN 트리거 | inferred_from_backtest |
| 정지 임계 (HALT) | 336 | bars (14일) | HALT_REVIEW_REQUIRED 트리거 | inferred_from_backtest |

## 사용 원칙

1. **참고 기준선이며 봉인 근거가 아니다.** Phase 3 백테스트 기반 독립 가정 근사치이다. live 레짐과 백테스트 레짐 차이가 있을 수 있다.
2. **경보 임계 도달 시 자동 파라미터 조정이 아니라 파이프라인 점검을 수행한다.**
3. **정지 임계 도달 시 A 통보 후 대응을 결정한다.**
4. **진단 로그 구현 후 7일 관측 결과로 기준선을 재검증할 수 있다.** 재검증 시 근거 등급이 `observed_from_live_receipt`으로 승격된다.

## 상태 전이 규칙

```
NORMAL
  │
  ├─ 168 bars 연속 무신호 ──→ ALERT_NO_SIGNAL (WARN + 운영자 알림)
  │                              │
  │                              ├─ 신호 1회 발생 ──→ NORMAL (복귀)
  │                              │
  │                              └─ 336 bars 연속 무신호 ──→ HALT_REVIEW_REQUIRED
  │                                                           (ERROR + A 통보)
  │
  └─ 신호 발생 ──→ NORMAL (유지)
```

## 금지 사항

- 이 기준선을 근거로 전략 완화/파라미터 변경을 제안하는 것은 금지
- 기준선 미달(신호 빈도가 낮은 것)을 전략 FAIL로 단정하는 것은 금지
- 기준선 초과(신호 빈도가 높은 것)를 전략 PASS로 단정하는 것도 금지

## 재검증 계획

| 시점 | 조건 | 액션 |
|------|------|------|
| C1-A 구현 후 7일 | smc_sig=0 비율, wt_sig=0 비율 집계 | Phase 3 대조, 기준선 재검증 |
| 30일 누적 | 실측 신호 간격 분포 확보 | 평균/중위수/분산 업데이트 |
