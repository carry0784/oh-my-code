# Mandatory Enforcement Map
**K-Dexter AOS — v1.0 | Step 3 of v4 Architecture Work**

이 문서는 18개 Mandatory 항목 각각이 실행 흐름의 어느 시점에서 강제되는지를 명시한다.
v3 문서 Gap #5 해소. "Mandatory Ledger가 선언일 뿐 실행 시점 누락" 문제를 해결한다.
v3 Gap #3(Work State 과잉)에 대한 압축 결정도 포함한다.

---

## 1. Work State CHECK 단계 압축 결정 (v3 Gap #3 해소)

### 결정: 10개 CHECK 상태 → 단일 VALIDATING 상태로 압축

v3 정상 실행 경로의 10개 연속 CHECK 상태:
```
MANDATORY_CHECK → FORBIDDEN_CHECK → COMPLIANCE_CHECK → DRIFT_CHECK →
CONFLICT_CHECK → PATTERN_CHECK → BUDGET_CHECK → TRUST_CHECK →
LOOP_CHECK → LOCK_CHECK
```

**압축 후 Main Loop 경로 (20단계 → 12단계):**
```
DRAFT → CLARIFYING → SPEC_READY → PLANNING → VALIDATING → RUNNING →
EVALUATING → APPROVAL_PENDING → EXECUTING → VERIFY → MONITOR
```

**VALIDATING 내부 체크리스트 (순서 고정, 모두 PASS 필요):**
```
[1] FORBIDDEN_CHECK    — 금지 항목 위반 여부 (차단 우선)
[2] MANDATORY_CHECK    — 18개 Mandatory 항목 충족 여부
[3] COMPLIANCE_CHECK   — 헌법/정책 준수율 확인
[4] DRIFT_CHECK        — Intent Drift 감지
[5] CONFLICT_CHECK     — Rule 충돌 검사
[6] PATTERN_CHECK      — Failure Pattern 대조
[7] BUDGET_CHECK       — 예산 한도 확인
[8] TRUST_CHECK        — Trust 상태 갱신 및 확인
[9] LOOP_CHECK         — 루프 건강 상태 확인
[10] LOCK_CHECK        — Spec Lock 확인
```

**압축 근거:**
- 10개 모두 PLANNING → RUNNING 사이에 순차 실행되므로 상태 분리 실익 없음
- 하나라도 실패 시 Work State → BLOCKED (차이 없음)
- 전환 조건 정의 부담 19개 → 2개 (PLANNING→VALIDATING, VALIDATING→RUNNING)
- VALIDATING 내부 체크리스트는 코드 레벨에서 관리 (상태머신 외부)

---

## 2. 18개 Mandatory 항목 × Enforcement Point 매핑

| # | Mandatory 항목 | 강제 시점 (State) | 강제 시점 (Gate) | 담당 레이어 | 거버넌스 | 미충족 시 결과 |
|---|---------------|------------------|-----------------|-------------|----------|----------------|
| M-01 | **clarify** — 실행 전 의도 명확화 | CLARIFYING (진입 조건) | - | L4 Clarify & Spec | B2 | CLARIFYING 탈출 불가 |
| M-02 | **spec twin** — 스펙 쌍 생성 | SPEC_READY (진입 조건) | - | L4 Clarify & Spec | B2 | SPEC_READY 탈출 불가 |
| M-03 | **risk check** — 리스크 검사 | PLANNING | G-03 Risk Control | L3 Security | B1 | BLOCKED |
| M-04 | **security check** — 보안 검사 | PLANNING | G-04 Constitution Compliance | L3 Security | B1 | BLOCKED |
| M-05 | **rollback plan** — 롤백 계획 | PLANNING | G-02 State Recovery | L26 Recovery Engine | A | PLANNING 탈출 불가 |
| M-06 | **recovery simulation** — 복구 시뮬레이션 | PLANNING (B2 Sandbox) | G-02 State Recovery | L26 Recovery Engine | A/B2 | PLANNING 탈출 불가 |
| M-07 | **evidence** — 모든 변경에 증거 첨부 | 모든 상태 전환 시 | G-05 Audit Completeness | L10 Audit / Evidence Store | A | Evidence 없으면 전환 차단 |
| M-08 | **budget check** — 예산 한도 확인 | VALIDATING [7] BUDGET_CHECK | G-22 Budget Gate | L29 Cost Controller | B2 | BLOCKED |
| M-09 | **compliance check** — 준수율 검사 | VALIDATING [3] COMPLIANCE_CHECK | G-04, G-16 | L13 Compliance Engine | B2 | BLOCKED |
| M-10 | **provenance** — 출처 기록 | Rule Ledger 쓰기 시 | G-18 Provenance Gate | L12 Rule Provenance Store | B2 | Rule 등록 거부 |
| M-11 | **drift check** — 의도 이탈 감지 | VALIDATING [4] DRIFT_CHECK | G-19 Drift Gate | L15 Intent Drift Engine | B2 | BLOCKED (drift_high 초과 시) |
| M-12 | **conflict check** — 규칙 충돌 검사 | VALIDATING [5] CONFLICT_CHECK | G-20 Conflict Gate | L16 Rule Conflict Engine | B2 | BLOCKED |
| M-13 | **pattern check** — 실패 패턴 대조 | VALIDATING [6] PATTERN_CHECK | G-21 Pattern Gate | L17 Failure Pattern Memory | B2 | BLOCKED (PATTERN 감지 시) |
| M-14 | **trust refresh** — 신뢰 상태 갱신 | VALIDATING [8] TRUST_CHECK | G-23 Trust Gate | L19 Trust Decay Engine | B2 | BLOCKED (ISOLATED/STALE) |
| M-15 | **loop health** — 루프 건강 상태 확인 | VALIDATING [9] LOOP_CHECK | G-24 Loop Gate | L28 Loop Monitor | B2 | BLOCKED |
| M-16 | **completion check** — 완성 검증 | VERIFY | G-25 Completion Gate | L21 Completion Engine | B2 | VERIFY 탈출 불가 |
| M-17 | **spec lock check** — 스펙 잠금 확인 | VALIDATING [10] LOCK_CHECK | G-26 Spec Lock Gate | L22 Spec Lock System | B1/B2 | BLOCKED |
| M-18 | **research** — 변경 전 리서치 | PLANNING (선행 조건) | G-27 Research Gate | L23 Research Engine | B2 | PLANNING 탈출 불가 |

---

## 3. Enforcement Point 상세

### 3.1 CLARIFYING (M-01)

```
진입 조건: DRAFT 상태에서 실행 의도 입력
강제 내용: 의도(intent)가 명확히 기술되어야 SPEC_READY로 전환 허용
미충족:   의도 필드 비어 있으면 CLARIFYING 유지
담당:     L4 Clarify & Spec (B2)
```

### 3.2 SPEC_READY (M-02)

```
진입 조건: CLARIFYING 완료 후 Spec Twin 생성
강제 내용: (실행 스펙, 검증 스펙) 쌍이 모두 존재해야 PLANNING으로 전환 허용
미충족:   Spec Twin 불완전 시 SPEC_READY 유지
담당:     L4 Clarify & Spec (B2)
```

### 3.3 PLANNING (M-03, M-04, M-05, M-06, M-18)

```
강제 내용:
  M-03 risk check         → L3가 리스크 한도 확인 완료 표시 필요
  M-04 security check     → L3가 보안 상태 NORMAL/RESTRICTED 확인 필요
  M-05 rollback plan      → Recovery Engine이 rollback anchor 지정 필요
  M-06 recovery simulation → Sandbox에서 복구 시뮬레이션 1회 이상 실행 필요
  M-18 research           → L23 Research Engine이 research_complete 표시 필요
미충족:   5개 중 하나라도 미완 시 PLANNING → VALIDATING 전환 차단
담당:     L3 (B1), L26 (A), L23 (B2)
```

### 3.4 VALIDATING (M-08~M-17, M-09, M-11~M-15, M-17)

```
실행 순서 (고정):
  [1] FORBIDDEN_CHECK   → ForbiddenLedger 위반 시 즉각 BLOCKED (나머지 생략)
  [2] MANDATORY_CHECK   → M-01~M-18 체크리스트 완료 여부 확인
  [3] COMPLIANCE_CHECK  → M-09: Compliance Engine 준수율 임계값 이상
  [4] DRIFT_CHECK       → M-11: drift_score < drift_high_threshold
  [5] CONFLICT_CHECK    → M-12: Rule Conflict 없음
  [6] PATTERN_CHECK     → M-13: 알려진 실패 패턴 미감지
  [7] BUDGET_CHECK      → M-08: 예산 잔여 > 실행 예상 비용
  [8] TRUST_CHECK       → M-14: Trust State ≠ ISOLATED / STALE
  [9] LOOP_CHECK        → M-15: 4개 루프 모두 건강 상태
  [10] LOCK_CHECK       → M-17: Spec Lock 잠금 상태 확인

모두 PASS → RUNNING 전환 허용
하나라도 FAIL → Work State: BLOCKED, 실패한 체크 ID 기록
```

### 3.5 모든 상태 전환 시 (M-07 evidence)

```
강제 내용: 모든 Work State 전환 시 EvidenceBundle 생성 필수
           bundle_id, trigger, actor, action, before_state, after_state 포함
미충족:   EvidenceBundle 없으면 상태 전환 자체를 거부 (트랜잭션 롤백)
담당:     L10 Audit / Evidence Store (A)
게이트:   G-05 Audit Completeness Gate
```

### 3.6 Rule Ledger 쓰기 시 (M-10 provenance)

```
강제 내용: Rule 등록/수정/삭제 시 provenance 필드 필수
           {source_incident, author_layer, timestamp, rationale} 포함
미충족:   provenance 없는 Rule → Rule Ledger 등록 거부
담당:     L12 Rule Provenance Store (B2)
게이트:   G-18 Provenance Gate
동시성:   Rule Ledger Write Lock 보유 중에만 쓰기 허용 (concurrency.py)
```

### 3.7 VERIFY (M-16 completion check)

```
강제 내용: EXECUTING 완료 후 completion score 확인
           completion score ≥ completion_threshold 이어야 MONITOR 전환
미충족:   VERIFY 유지 또는 Self-Improvement Loop 발동
담당:     L21 Completion Engine (B2)
게이트:   G-25 Completion Gate
미정의:   completion score 공식 (OQ-7), completion_threshold (OQ-9)
```

---

## 4. 루프별 Mandatory 적용 범위

Main Loop와 달리 Self-Improvement / Evolution / Recovery Loop는 일부 Mandatory를 면제한다.
면제는 속도가 아니라 루프 목적상 중복 또는 역순이 되는 항목에 한정한다.

| Mandatory 항목 | Main Loop | Self-Improvement | Evolution | Recovery |
|---------------|:---------:|:----------------:|:---------:|:--------:|
| M-01 clarify | ✅ | ✅ | ✅ | ❌ (긴급 복구, 의도 사전 확정) |
| M-02 spec twin | ✅ | ✅ | ✅ | ❌ |
| M-03 risk check | ✅ | ✅ | ✅ | ✅ |
| M-04 security check | ✅ | ✅ | ✅ | ✅ |
| M-05 rollback plan | ✅ | ✅ | ✅ | ❌ (롤백 자체가 목적) |
| M-06 recovery simulation | ✅ | ✅ | ✅ | ❌ |
| M-07 evidence | ✅ | ✅ | ✅ | ✅ (항상 필수) |
| M-08 budget check | ✅ | ✅ | ✅ | ✅ |
| M-09 compliance check | ✅ | ✅ | ✅ | ✅ |
| M-10 provenance | ✅ | ✅ | ✅ | ✅ (항상 필수) |
| M-11 drift check | ✅ | ✅ | ✅ | ❌ (drift가 복구 원인일 수 있음) |
| M-12 conflict check | ✅ | ✅ | ✅ | ❌ |
| M-13 pattern check | ✅ | ✅ | ✅ | ❌ |
| M-14 trust refresh | ✅ | ✅ | ✅ | ✅ |
| M-15 loop health | ✅ | ✅ | ✅ | ❌ (루프 자체가 비정상 상태) |
| M-16 completion check | ✅ | ✅ | ✅ | ✅ |
| M-17 spec lock check | ✅ | ✅ | ✅ | ❌ (Recovery는 Lock 우선 해제) |
| M-18 research | ✅ | ✅ | ✅ | ❌ |

**Recovery Loop 면제 8개 근거:** 복구는 시간이 핵심 — 사전 연구·스펙·드리프트 검사 등은 복구 완료 후 Self-Improvement/Evolution Loop에서 소급 처리.

---

## 5. Gate ↔ Mandatory 연결 요약

| Gate | 연결 Mandatory | 기준 상태 |
|------|---------------|-----------|
| G-02 State Recovery | M-05, M-06 | 기준 정의 완료 |
| G-03 Risk Control | M-03 | 기준 정의 완료 |
| G-04 Constitution Compliance | M-04, M-09 | 기준 정의 완료 |
| G-05 Audit Completeness | M-07 | 기준 정의 완료 |
| G-16 Compliance Gate | M-09 | **기준 미정의** |
| G-18 Provenance Gate | M-10 | **기준 미정의** |
| G-19 Drift Gate | M-11 | **기준 미정의 (OQ-4)** |
| G-20 Conflict Gate | M-12 | **기준 미정의** |
| G-21 Pattern Gate | M-13 | **기준 미정의** |
| G-22 Budget Gate | M-08 | **기준 미정의** |
| G-23 Trust Gate | M-14 | **기준 미정의 (OQ-5)** |
| G-24 Loop Gate | M-15 | **기준 미정의 (OQ-6)** |
| G-25 Completion Gate | M-16 | **기준 미정의 (OQ-7)** |
| G-26 Spec Lock Gate | M-17 | **기준 미정의** |
| G-27 Research Gate | M-18 | **기준 미정의** |

---

## 6. Open Questions (v4 확정 필요)

| # | 항목 | 관련 Mandatory | 현재 상태 |
|---|------|---------------|-----------|
| OQ-4 | drift_high_threshold 수치 | M-11 | 미정의 |
| OQ-5 | Trust 감소 함수 | M-14 | 미정의 |
| OQ-6 | loop_count 상한 | M-15 | 미정의 |
| OQ-7 | completion score 공식 | M-16 | 미정의 |
| OQ-9 | completion_threshold 수치 | M-16 | 미정의 |
| OQ-10 | G-16~G-22, G-24~G-27 통과 기준 수치 | M-08~M-18 | 미정의 (일괄) |

---

## 7. 연관 파일

| 파일 | 연관 이유 |
|------|-----------|
| `src/kdexter/ledger/mandatory_ledger.py` | 18개 항목 + enforcement_point 필드 구현 |
| `src/kdexter/state_machine/work_state.py` | VALIDATING 상태 + 내부 체크리스트 구현 |
| `src/kdexter/loops/main_loop.py` | 압축된 12단계 Work State 실행 |
| `src/kdexter/loops/recovery_loop.py` | 면제 8개 항목 적용 |
| `src/kdexter/audit/evidence_store.py` | M-07 모든 상태 전환 시 EvidenceBundle |
| `src/kdexter/gates/gate_registry.py` | G-16~G-27 기준 정의 시 업데이트 |
| `docs/architecture/failure_taxonomy.md` | M-13 Pattern Check 분류 기준 연동 |
| `docs/architecture/governance_layer_map.md` | Mandatory 항목별 담당 거버넌스 계층 |
