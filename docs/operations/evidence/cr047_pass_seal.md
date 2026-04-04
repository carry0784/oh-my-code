# CR-047 PASS Seal Document

**Status: SEALED**
**Date: 2026-04-01**
**Authority: A (Decision Authority)**

---

## 1. Seal Declaration

CR-047 (1H 시간봉 기반 CG-2B 재검증)은 7일 연속 PASS를 근거로 **확정 승인**한다.

---

## 2. CG-2B Proven Declaration

### Operational Exercisability = CLOSED

| Gate | Status | Evidence |
|------|--------|----------|
| **CG-2A** | **SEALED PASS** | CR-045 reShadow v2, 7/7 무결 운영 |
| **CG-2B-1** (Candidate Generation) | **PROVEN** | registry 5~10/day, fitness 0.42~0.88, 7/7 |
| **CG-2B-2** (Governance Exercisability) | **PROVEN** | governance 4 decisions/day, 28 total, 7/7 |

### 증거 요약

| Metric | CR-045 (5m) | CR-047 (1H) | Verdict |
|--------|-------------|-------------|---------|
| registry_size | 0 | 5~10/day | **PROVEN** |
| best_fitness | 0.0 | 0.42~0.88 | **PROVEN** |
| governance_decisions | 0 | 4/day | **PROVEN** |
| is_healthy | false | true | **PROVEN** |
| assessment | WATCH | PASS | **PROVEN** |

### Resolution

기준(min_trades=10)은 유지하고 관측 구조(5m->1H)를 전환하여 해결.
기준 완화 없이 CG-2B를 개방한 것이 핵심.

---

## 3. 안 B (Fallback Extension Path)

### 현재 상태: 실행하지 않음

안 B (1H signal / 5m execution observation)는 현재 불필요.
안 A만으로 CG-2B-1/2 모두 proven.

### 안 B 확장 조건표

| # | 조건 | 설명 |
|---|------|------|
| 1 | Phase 2에서 1H signal 기반 execution realism 부족 | 1H bar-close 진입이 실제 실행과 괴리 |
| 2 | Candidate generation OK but governance 품질 흔들림 | 후보는 나오나 거버넌스 판정 품질 저하 |
| 3 | Multi-asset/regime에서 1H/1H 구조 약화 | ETH/SOL 또는 bull/sideways에서 1H 부족 |
| 4 | Live-shadow에서 5m observation granularity 필요 | 실시간 관측 미세 해상도 요구 |

**위 조건 중 1개 이상 충족 전까지 안 B 실행 금지.**

---

## 4. 봉인 효과

| 항목 | 효과 |
|------|------|
| CG-2A 반복 검증 | 종료 (SEALED) |
| CG-2B 반복 검증 | 종료 (PROVEN) |
| Operational Exercisability | **CLOSED** |
| 후속 집중 | CR-046 Phase 2 (전략 타당성 검증) |
| 안 B | Fallback Extension Path (조건부) |

---

## 5. 헌법 조항 대조

| 요구 조항 | 반영 | 상태 |
|-----------|------|------|
| dry_run=True 유지 | HARDCODED | OK |
| PENDING_OPERATOR 유지 | 미변경 | OK |
| min_trades=10 유지 | 하향 안 함 | OK |
| live write path 금지 | 미변경 | OK |
| Version B canonical | pure-causal SMC 기준 | OK |
| 안 B 실행 금지 (조건 미충족) | 실행하지 않음 | OK |
| 시장 활성 구간 gate 사용 금지 | 1H 전환으로 구조적 해결 | OK |

---

## 6. 상태 전이 영향

| 전이 | 영향 |
|------|------|
| CG-2 -> CLOSED | 운영 exercisability 전체 증명 완료 |
| CR-046 Phase 1 -> Phase 2 | 전략 타당성 검증 단계 진입 |
| CR-047 -> SEALED | 1H 시간봉 기반 운영 확정 |

---

## 7. 미해결 리스크

| # | 리스크 | 심각도 | 대응 |
|---|--------|--------|------|
| 1 | CR-046 Phase 2 미완료 | Medium | 즉시 착수 승인됨 |
| 2 | Strategy D OOS 성능 미확인 | Medium | Phase 2에서 검증 |
| 3 | Multi-asset/regime 미검증 | Medium | Phase 3에서 검증 |
| 4 | 안 B 미사용으로 5m granularity 부재 | Low | 조건 충족 시 확장 |

---

## Signature

```
CR-047 PASS Seal + CG-2B Proven Declaration
CG-2A: SEALED PASS
CG-2B-1: PROVEN (candidate generation)
CG-2B-2: PROVEN (governance exercisability)
Operational Exercisability: CLOSED
Sealed by: A (Decision Authority)
Prepared by: B (Implementer)
Date: 2026-04-01
```
