# Failure Taxonomy
**K-Dexter AOS — v1.0 | Step 1 of v4 Architecture Work**

이 문서는 Failure 발생 시 Recovery Loop와 Evolution Loop 중 어느 쪽으로 라우팅할지 결정하는 분기 조건을 명세한다.
v3 문서 Gap #4 해소. `loops/recovery_loop.py` 및 `loops/concurrency.py` 구현의 선행 조건.

---

## 1. Failure 분류 체계 (3차원)

모든 Failure는 아래 3개 축으로 분류한다. 3개 축의 조합이 Loop 라우팅을 결정한다.

### 1.1 Failure Domain

| Domain | 정의 | 예시 |
|--------|------|------|
| `INFRA` | 시스템 인프라·외부 의존성 장애 | DB 연결 끊김, Exchange API 불가, OOM |
| `STRATEGY` | 트레이딩 전략·신호·성과 실패 | 손실 한도 초과, 신호 생성 실패, 예산 초과 |
| `GOVERNANCE` | 헌법·정책·게이트·Mandatory 위반 | 헌법 조항 위반, Gate 우회 시도, Forbidden 실행 |

### 1.2 Failure Severity

| Severity | 정의 | 즉각 조치 |
|----------|------|-----------|
| `CRITICAL` | 시스템 운영 불가 또는 데이터 정합성 파괴 | 즉각 LOCKDOWN |
| `HIGH` | 주요 기능 장애, 수동 개입 없으면 확대 가능 | QUARANTINED |
| `MEDIUM` | 부분 기능 장애, 자동 복구 가능 | RESTRICTED |
| `LOW` | 경미한 이상, 모니터링 수준 | NORMAL (경고만) |

### 1.3 Failure Recurrence

| Recurrence | 정의 | 판단 기준 |
|------------|------|-----------|
| `FIRST` | 해당 Failure Type 최초 발생 | Failure Pattern Memory 조회 결과 없음 |
| `REPEAT` | 동일 Failure Type 재발생 (패턴 미달) | 2회 이상, PATTERN 미달 |
| `PATTERN` | 동일 Failure Type 패턴 임계값 초과 | **3회 이상 OR 7일 내 2회** (v4 확정 전 임시값) |

> **Open Question #1:** PATTERN 임계값(횟수/기간)은 v4에서 운영 데이터 기반으로 확정 필요.

---

## 2. Loop 라우팅 결정 테이블

### 2.1 기본 라우팅

| Domain | Severity | Recurrence | 담당 Loop | Security State | Work State |
|--------|----------|------------|-----------|----------------|------------|
| INFRA | CRITICAL | any | **Recovery** | LOCKDOWN | ISOLATED |
| INFRA | HIGH | any | **Recovery** | QUARANTINED | FAILED |
| INFRA | MEDIUM | FIRST/REPEAT | **Recovery** | RESTRICTED | FAILED |
| INFRA | MEDIUM | PATTERN | **Recovery** + Evolution 예약 | RESTRICTED | FAILED |
| INFRA | LOW | any | Main Loop 내 처리 | NORMAL | MONITOR |
| STRATEGY | CRITICAL | any | **Recovery** | QUARANTINED | ISOLATED |
| STRATEGY | HIGH | FIRST | **Self-Improvement** | RESTRICTED | FAILED |
| STRATEGY | HIGH | REPEAT | **Self-Improvement** | RESTRICTED | FAILED |
| STRATEGY | HIGH | PATTERN | **Evolution** | RESTRICTED | FAILED |
| STRATEGY | MEDIUM | FIRST/REPEAT | **Self-Improvement** | NORMAL | FAILED |
| STRATEGY | MEDIUM | PATTERN | **Evolution** | RESTRICTED | FAILED |
| STRATEGY | LOW | any | Main Loop 내 처리 | NORMAL | MONITOR |
| GOVERNANCE | CRITICAL | any | **Recovery** + B1 Human Override | LOCKDOWN | ISOLATED |
| GOVERNANCE | HIGH | any | **Recovery** + B1 통보 | QUARANTINED | BLOCKED |
| GOVERNANCE | MEDIUM | FIRST/REPEAT | **Self-Improvement** | RESTRICTED | BLOCKED |
| GOVERNANCE | MEDIUM | PATTERN | **Evolution** + B1 통보 | RESTRICTED | BLOCKED |
| GOVERNANCE | LOW | any | Audit 기록 후 계속 | NORMAL | RUNNING |

### 2.2 라우팅 결정 흐름도

```
Failure 발생
     │
     ▼
[Failure Pattern Memory 조회 → Recurrence 판정]
     │
     ├─ Domain = INFRA ──────────────────────────────→ Recovery Loop
     │
     ├─ Domain = STRATEGY
     │       │
     │       ├─ Severity = CRITICAL ────────────────→ Recovery Loop
     │       ├─ Recurrence = PATTERN ───────────────→ Evolution Loop
     │       └─ 그 외 ──────────────────────────────→ Self-Improvement Loop
     │
     └─ Domain = GOVERNANCE
             │
             ├─ Severity = CRITICAL / HIGH ──────────→ Recovery Loop + B1 통보
             ├─ Recurrence = PATTERN ───────────────→ Evolution Loop + B1 통보
             └─ 그 외 ──────────────────────────────→ Self-Improvement Loop
                                                            │
                                                            ▼
                                               [Section 3: Concurrent Failure Protocol]
```

---

## 3. Concurrent Failure Protocol

4개 루프가 동시에 발동될 수 있는 상황에 대한 처리 규칙.

### 3.1 우선순위 (변경 불가)

```
Recovery Loop  >  Main Loop  >  Self-Improvement Loop  >  Evolution Loop
```

### 3.2 동시 발생 규칙

| 상황 | 처리 |
|------|------|
| Recovery 활성 중 Evolution 발동 | Evolution → Priority Queue 대기 (Recovery Resume 이후 실행) |
| Recovery 활성 중 Self-Improvement 발동 | Self-Improvement → Priority Queue 대기 |
| Recovery 활성 중 새 Recovery 발동 | 기존 Recovery에 병합 (새 Failure를 현재 Recovery 범위에 추가) |
| Evolution 활성 중 Self-Improvement 발동 | Self-Improvement → Priority Queue 대기 |
| Main Loop + Recovery 동시 | Main Loop 일시 중단 → Recovery 완료 후 Resume |

### 3.3 최대 동시 활성 루프

```
Recovery:         최대 1개 (병렬 Recovery 금지 — 신규 Failure는 병합 처리)
Main:             최대 1개
Self-Improvement: 최대 1개 (초과 시 Queue 대기)
Evolution:        최대 1개 (초과 시 Queue 대기)

동시 활성 최대: Recovery 1 + Main 1 = 2개
Self-Improvement / Evolution 은 Queue 대기
```

### 3.4 Deadlock 감지 조건

아래 조건이 모두 충족되면 Deadlock으로 판정 → Human Override 요청:

1. Recovery Loop가 Rule Ledger Write Lock 보유 중
2. Main Loop가 Rule Ledger Write Lock 대기 중
3. Recovery Loop가 Main Loop의 상태 결과를 대기 중
4. 대기 시간 > `timeout_deadlock` (Open Question #2)

### 3.5 Evolution Loop 지연 한도

Recovery 활성으로 Evolution이 대기 중일 때 무한 지연 방지:

- 최대 대기 시간: `timeout_evolution_defer` (Open Question #3)
- 초과 시: Human Override 알림 + Evolution Loop 강제 상태 보고 발행

---

## 4. Failure Type 카탈로그

### 4.1 INFRA Failures

| Failure ID | 이름 | Severity | 담당 Loop |
|------------|------|----------|-----------|
| F-I-001 | DB 연결 끊김 | HIGH | Recovery |
| F-I-002 | DB 데이터 정합성 파괴 | CRITICAL | Recovery |
| F-I-003 | Exchange API 불가 (일시) | MEDIUM | Recovery |
| F-I-004 | Exchange API 불가 (지속) | HIGH | Recovery |
| F-I-005 | 상태머신 불일치 (State Inconsistency) | HIGH | Recovery |
| F-I-006 | 외부 의존성 실패 (네트워크 등) | MEDIUM | Recovery |
| F-I-007 | 프로세스 크래시 / OOM | CRITICAL | Recovery |
| F-I-008 | Rule Ledger 동시성 충돌 | HIGH | Recovery |

### 4.2 STRATEGY Failures

| Failure ID | 이름 | Severity | 담당 Loop (FIRST → PATTERN) |
|------------|------|----------|---------------------------|
| F-S-001 | 손실 한도 초과 | HIGH | Self-Improvement → Evolution |
| F-S-002 | 신호 생성 실패 | MEDIUM | Self-Improvement → Evolution |
| F-S-003 | 반복 Policy 위반 (Drift 누적) | HIGH | Self-Improvement → Evolution |
| F-S-004 | Trust Decay 임계값 초과 | MEDIUM | Self-Improvement → Evolution |
| F-S-005 | 예산 초과 | HIGH | Self-Improvement → Evolution |
| F-S-006 | 포지션 롤백 실패 | CRITICAL | Recovery |

### 4.3 GOVERNANCE Failures

| Failure ID | 이름 | Severity | 담당 Loop |
|------------|------|----------|-----------|
| F-G-001 | 헌법 조항 직접 위반 | CRITICAL | Recovery + B1 |
| F-G-002 | Gate 우회 시도 | HIGH | Recovery + B1 |
| F-G-003 | Forbidden 항목 실행 | HIGH | Recovery |
| F-G-004 | Mandatory Check 누락 | MEDIUM | Self-Improvement |
| F-G-005 | Provenance 없는 Rule 등록 | MEDIUM | Self-Improvement |
| F-G-006 | Evidence Bundle 누락 | MEDIUM | Self-Improvement |
| F-G-007 | B1 비준 없는 Active 전환 시도 | CRITICAL | Recovery + B1 |

---

## 5. Failure → State 전환 매핑

| Failure Severity | Work State 전환 | Security State 전환 | 즉각 조치 |
|------------------|-----------------|---------------------|-----------|
| CRITICAL | → ISOLATED | → LOCKDOWN | Human Override 요청 |
| HIGH | → FAILED | → QUARANTINED | 담당 Loop 즉시 발동 |
| MEDIUM | → FAILED | → RESTRICTED | 담당 Loop 발동 |
| LOW | MONITOR 유지 | NORMAL 유지 | Audit 기록만 |

---

## 6. Open Questions (v4 확정 필요)

| # | 항목 | 현재 임시값 | 확정 방법 |
|---|------|-------------|-----------|
| OQ-1 | PATTERN 임계값 (횟수/기간) | 3회 이상 OR 7일 내 2회 | 운영 데이터 기반 역산 |
| OQ-2 | Deadlock 판정 `timeout_deadlock` | 미정의 | Recovery Engine 설계 시 결정 |
| OQ-3 | Evolution 최대 대기 `timeout_evolution_defer` | 미정의 | Concurrency 설계 시 결정 |

---

## 7. 연관 파일

| 파일 | 연관 이유 |
|------|-----------|
| `src/kdexter/loops/recovery_loop.py` | INFRA/CRITICAL Failure 처리 구현 |
| `src/kdexter/loops/evolution_loop.py` | PATTERN Failure 처리 구현 |
| `src/kdexter/loops/concurrency.py` | Priority Queue + Deadlock 감지 구현 |
| `src/kdexter/state_machine/work_state.py` | Failure → Work State 전환 |
| `src/kdexter/state_machine/security_state.py` | Failure → Security State 전환 |
| `docs/architecture/governance_layer_map.md` | GOVERNANCE Failure의 권한 귀속 |
