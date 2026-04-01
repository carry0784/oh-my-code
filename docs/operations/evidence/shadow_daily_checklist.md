# Shadow Run — Day 1 일일 점검표 (압축본)

---

## 실행 순서 (09:00 KST)

```
1. python scripts/shadow_run_cycle.py --day 1
2. 출력 확인 → 아래 체크리스트 기록
3. docs/operations/evidence/shadow_logs/day_01.json 저장 확인
4. 이 문서에 결과 기입 후 커밋
```

---

## 체크리스트

### A. 데이터 수집

| # | 항목 | 결과 |
|---|------|------|
| A-1 | CCXT 연결 성공 (fallback 아님) | [ ] YES / [ ] FALLBACK |
| A-2 | 수집 바 수 >= 100 | ___ bars |

### B. 진화 (Evolution)

| # | 항목 | 임계값 | 실측 | 판정 |
|---|------|--------|------|------|
| B-1 | status = OK | OK | ___ | [ ] |
| B-2 | generations_run >= 3 | 3 | ___ | [ ] |
| B-3 | registry_size >= 1 | 1 | ___ | [ ] |
| B-4 | best_fitness 기록 | — | ___ | — |

### C. 포트폴리오 (Portfolio)

| # | 항목 | 임계값 | 실측 | 판정 |
|---|------|--------|------|------|
| C-1 | status = OK 또는 SKIP | OK/SKIP | ___ | [ ] |
| C-2 | portfolio_sharpe 기록 | — | ___ | — |
| C-3 | max_dd 기록 | — | ___% | — |

### D. 오케스트레이터 (Orchestrator)

| # | 항목 | 임계값 | 실측 | 판정 |
|---|------|--------|------|------|
| D-1 | status = OK | OK | ___ | [ ] |
| D-2 | crash = 0 | 0 | ___ | [ ] |
| D-3 | governance_decisions >= 1 | 1 | ___ | [ ] |
| D-4 | PENDING_OPERATOR < 20 | <20 | ___ | [ ] |
| D-5 | block_ratio > 0% | >0% | ___% | [ ] |
| D-6 | is_healthy = True | True | ___ | [ ] |

### E. 조정 (Reconciliation)

| # | 항목 | 결과 |
|---|------|------|
| E-1 | lifecycle_states_valid | [ ] PASS / [ ] FAIL |
| E-2 | registry_lifecycle_aligned | [ ] PASS / [ ] FAIL |
| E-3 | transitions_have_governance | [ ] PASS / [ ] FAIL |
| E-4 | health_monitor_responsive | [ ] PASS / [ ] FAIL |
| E-ALL | 4/4 PASS | [ ] YES / [ ] NO |

### F. CG-2 기준 대조

| # | CG-2 기준 | 임계값 | Day 1 | 누적 |
|---|-----------|--------|-------|------|
| CG2-1 | 지속 기간 | >= 7일 | 1/7 | — |
| CG2-2 | 크래시 | 0 | ___ | ___ |
| CG2-3 | 옵티마이저 drift | < 20% | ___ | — |
| CG2-4 | 거버넌스 block rate | > 0% | ___% | — |
| CG2-5 | PENDING_OPERATOR | < 20/day | ___ | — |
| CG2-6 | 헬스 경고 | < 2/day avg | ___ | ___ |
| CG2-7 | 적합도 3일 MA | 비감소 | ___ | Day 3부터 |
| CG2-8 | 레지스트리 증가 | >= 1/2일 | ___ | ___ |
| CG2-9 | 일일 조정 | 4/4 pass | ___ | ___ |

---

## Day 판정

```
Day 1 Assessment: [ ] PASS  [ ] WATCH  [ ] FAIL

사유: _______________________________________________

운영자 메모: ________________________________________
```

---

## Mock Approval 연습 (1건)

```
Genome ID: _______________
현재 상태: PAPER_TRADING
Paper trades: ___
Paper Sharpe: ___
Paper win rate: ___
Paper max DD: ___
live_match_score: ___
System healthy: ___

Decision: [ ] APPROVE  [ ] HOLD  [ ] REJECT
Reason: _______________________________________________
```

---

## 7-Day Acceptance Board (누적)

| Day | Date | Registry | Block% | Warnings | Drift% | Fitness MA | Crashes | Assessment |
|-----|------|----------|--------|----------|--------|-----------|---------|------------|
| 1 | — | — | — | — | — | — | — | — |
| 2 | — | — | — | — | — | — | — | — |
| 3 | — | — | — | — | — | — | — | — |
| 4 | — | — | — | — | — | — | — | — |
| 5 | — | — | — | — | — | — | — | — |
| 6 | — | — | — | — | — | — | — | — |
| 7 | — | — | — | — | — | — | — | — |

---

## STOP 조건 (즉시 중단)

| 트리거 | 조치 |
|--------|------|
| dry_run 이 False로 변경됨 | **즉시 중단** |
| Orchestrator crash >= 1 | HOLD + 원인 조사 |
| Drift > 40% | HOLD + 원인 조사 |
| Block rate = 100% 24시간 지속 | HOLD + 거버넌스 점검 |
| PENDING_OPERATOR > 20/day | HOLD + 진화 품질 검토 |
| 헬스 경고 > 5/day | HOLD + 회로차단기 점검 |
| 적합도 3일 연속 감소 | HOLD + 진화 파라미터 검토 |
