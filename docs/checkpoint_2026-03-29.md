# K-V3 프로젝트 체크포인트 — 2026-03-29

> 목표 철학과 실제 구현 상태를 대조 검증한 체크포인트.
> 코드베이스 실사(code audit) 기반.

---

## 1. 핵심철학 체크 (Philosophy Alignment)

| # | 철학 원칙 | 목표 | 실제 상태 | 판정 |
|---|----------|------|----------|------|
| P-1 | 자율성은 허용하되 무제한 자유는 금지 | 승인 없는 자기변형 금지 | GovernanceGate 10-check 사전 심사, ForbiddenLedger 4개 금지 행위 등록, SecurityState LOCKDOWN 시 전면 차단 | ✅ **충족** |
| P-2 | 실행보다 통제가 먼저 | "해도 되는가"가 "할 수 있다"보다 선행 | `pre_check()` → agent 실행 → `post_record()` 순서 강제, BLOCKED 시 실행 불가 | ✅ **충족** |
| P-3 | 모든 실패는 자산이다 | 오류/실패를 학습 원천으로 축적 | FailurePatternMemory(L17) FIRST→REPEAT→PATTERN 분류, `post_record_error()`로 증거 저장 | ✅ **충족** |
| P-4 | 변경은 항상 검증을 통과해야 한다 | 재설계안 바로 반영 금지 | VALIDATING 10-check, verify_constitution.py, OPS-GATE 규칙 | ✅ **충족** |
| P-5 | 운영은 사람 개입 최소화 | 평상시 무인, 이상 시만 개입 | G-MON 6지표 자동 감시, Daily/Weekly 리포트, Discord 자동 알림 | ✅ **충족** |
| P-6 | 진화는 혁신이 아니라 규율이다 | 헌법 안에서만 진화 허용 | DOC-L2-AI-TOOL-ROLE 역할 헌법, Provider 거버넌스 R-01~R-06 | ✅ **충족** |

**철학 충족률: 6/6 (100%)**

---

## 2. 4계층 구축 상태 (Layer Assessment)

### 계층 1: 헌법 계층 — ✅ 강함

| 컴포넌트 | 파일 | 상태 |
|----------|------|------|
| ForbiddenLedger | `src/kdexter/ledger/forbidden_ledger.py` | 4개 금지 행위 등록 |
| MandatoryLedger | `src/kdexter/ledger/mandatory_ledger.py` | 18개 필수 항목 |
| DoctrineRegistry | `src/kdexter/governance/doctrine.py` | D-001~D-009 교리 |
| SecurityStateContext | `src/kdexter/state_machine/security_state.py` | NORMAL→LOCKDOWN 상태기계 |
| WorkStateContext | `src/kdexter/state_machine/work_state.py` | 12단계 작업 상태기계 |
| AOS 헌법 문서 | `docs/aos-constitution/` | 26개 문서, verify PASS |
| AI 도구 역할 헌법 | `docs/aos-constitution/ai-tool-role-constitution.md` | DOC-L2-AI-TOOL-ROLE |

**평가**: 헌법 프레임워크 완전 구축. 문서화·코드·검증 3중 일치.

### 계층 2: 운영 계층 — ✅ 강함

| 컴포넌트 | 파일 | 상태 |
|----------|------|------|
| GovernanceGate | `app/agents/governance_gate.py` | 10-check, Singleton, DI |
| CostController (L29) | `src/kdexter/engines/cost_controller.py` | BUDGET_CHECK 활성 |
| LoopMonitor (L28) | `src/kdexter/engines/loop_monitor.py` | 4루프 감시 |
| G-MON 감시 | `app/core/governance_monitor.py` | 6지표 자동 감시 |
| Daily/Hourly 점검 | `app/core/constitution_check_runner.py` | I-03 read-only 점검 |
| Celery Beat | `workers/celery_app.py` | 8개 주기 작업 |
| 알림 체계 | `app/core/notification_flow.py` | Discord/File/Console |
| OpsStatus API | `GET /api/ops-status` | 4존 실시간 상태 |

**평가**: 운영 자동화 완전 가동. 감시→알림→기록 파이프라인 동작 중.

### 계층 3: 학습 계층 — ⚠️ 중간 (구조 있음, 연결 부분적)

| 컴포넌트 | 파일 | 상태 |
|----------|------|------|
| FailurePatternMemory (L17) | `src/kdexter/engines/failure_router.py` | ✅ 구현 완료, GovernanceGate 연결 |
| FailureEvent 구조체 | `src/kdexter/loops/recovery_loop.py` | ✅ 실패 이벤트 모델 정의 |
| EvidenceStore | `src/kdexter/audit/evidence_store.py` | ✅ Append-only 증거 저장 |
| TrustDecay (L19) | `src/kdexter/engines/trust_decay.py` | ✅ 구현, GovernanceGate 미연결 (not_applicable) |
| IntentDrift (L15) | `src/kdexter/engines/intent_drift.py` | ✅ 구현, GovernanceGate 미연결 (not_applicable) |
| RuleConflict (L16) | `src/kdexter/engines/rule_conflict.py` | ✅ 구현, GovernanceGate 미연결 (not_applicable) |
| AssetSnapshot | `workers/tasks/snapshot_tasks.py` | ✅ 5분 주기 자산 스냅샷 |

**평가**: 실패 기록·증거 저장·패턴 분류는 작동 중. 그러나 축적된 경험이 "재설계 입력"으로 자동 변환되는 파이프라인은 아직 없음. **경험 수집 ○, 경험 활용 △**.

### 계층 4: 진화 계층 — ⚠️ 설계 완료, 통합 전

| 컴포넌트 | 파일 | 상태 |
|----------|------|------|
| **EvolutionLoop** | `src/kdexter/loops/evolution_loop.py` | ✅ 5단계 설계 완료 (GENERATE→SANDBOX→EVALUATE→GATE→PROMOTE) |
| **SelfImprovementLoop** | `src/kdexter/loops/self_improvement_loop.py` | ✅ 5단계 설계 완료 (ANALYZE→PROPOSE→BACKTEST→APPLY→VERIFY) |
| **RecoveryLoop** | `src/kdexter/loops/recovery_loop.py` | ✅ 5단계 설계 완료 (ISOLATE→REPLAY→ROLLBACK→REPAIR→RESUME) |
| **MainLoop** | `src/kdexter/loops/main_loop.py` | ✅ 12단계 작업 상태기계 |
| BudgetEvolution (L18) | `src/kdexter/engines/budget_evolution.py` | ✅ 비용 예산 자동 조정 제안 |
| ExecutionCell (L8) | `src/kdexter/strategy/execution_cell.py` | ✅ Signal→TCL 변환 |
| GateRegistry | `src/kdexter/gates/gate_registry.py` | ✅ B1 적합성 게이트 |
| LoopConcurrency | `src/kdexter/loops/concurrency.py` | ✅ 루프 상한·우선순위·잠금 |
| Strategy Pipeline | `src/kdexter/strategy/pipeline.py` | ✅ L4→L8 파이프라인 |

**평가**: 진화 루프 3종(Evolution, SelfImprovement, Recovery)의 **설계와 단독 구현은 완료**. 그러나 이 루프들이 FastAPI 운영 계층(app/)과 **실시간 연결(harness/scheduler 통합)은 아직 미완성**. `src/kdexter/` 엔진들과 `app/` 운영 서비스 사이의 브릿지가 다음 과제.

---

## 3. 검증 수치 (Hard Numbers)

| 지표 | 값 | 판정 |
|------|---|------|
| 총 테스트 | **2,273개** (2,260 PASS + 13 기존 실패) | ✅ |
| 거버넌스 테스트 | 29 PASS (6 axes) | ✅ |
| G-MON 테스트 | 11 PASS (6 classes) | ✅ |
| Market Feed 테스트 | 16 PASS | ✅ |
| 헌법 검증 | PASS (26 docs, 2,073 lines, 0 blockers) | ✅ |
| VALIDATING 10-check | 5 active, 5 not_applicable, **0 deferred** | ✅ |
| Celery Beat 작업 | 8개 (4 원본 + 2 ops + 2 G-MON) | ✅ |
| OKX 잔여 참조 | 0 (코드) / 1 (감사 추적용 RESOLVED) | ✅ |
| K-Dexter 엔진 수 | **18개** (`src/kdexter/engines/`) | ✅ |
| 루프 수 | **4개** (Main, Evolution, SelfImprovement, Recovery) | ✅ |
| 상태기계 수 | **3개** (Security, Work, Trust) | ✅ |

---

## 4. 단계 판정 (Stage Assessment)

```
0단계 수동 매매        ████████████ 완전 통과
1단계 자동 실행        ████████████ 완전 통과
2단계 거버넌스 자동매매  ████████████ 완전 통과
3단계 감시 자동화       ████████████ 완전 통과
3.5단계 학습 기반 축적  ████████░░░░ 80% (수집 ✅ 활용 △)
4단계 제한적 자기개선   ████░░░░░░░░ 40% (설계 ✅ 통합 △)
5단계 헌법형 자율 진화  ██░░░░░░░░░░ 20% (프레임 ✅ 실행 ✗)
```

**현재 단계: 3.5 → 4단계 진입 직전**

---

## 5. 강한 것 vs 약한 것 (Gap Analysis)

### ✅ 지금 강한 것

| 영역 | 근거 |
|------|------|
| 헌법 통제 | 26 헌법 문서 + 코드 연동 + verify 자동화 |
| 사전 심사 | GovernanceGate 10-check, ForbiddenLedger 4개 행위 |
| 비용 통제 | CostController → BUDGET_CHECK 실시간 |
| 실패 기록 | FailurePatternMemory → PATTERN_CHECK 실시간 |
| 운영 감시 | G-MON 6지표 Daily/Weekly 자동 리포트 |
| 증거 추적 | EvidenceStore append-only, 고아 검출 |
| 상태기계 | Security/Work/Trust 3중 상태 관리 |

### ⚠️ 지금 약한 것 (다음 과제)

| 영역 | 현재 상태 | 필요 |
|------|----------|------|
| 경험→재설계 변환 | 실패 패턴 축적만 됨 | FailurePatternMemory → EvolutionLoop 자동 트리거 |
| 진화 루프 통합 | `src/kdexter/loops/` 단독 구현 | `app/` FastAPI 서비스와 브릿지 |
| 실험 레인 분리 | ExecutionCell에 dry_run 모드 존재 | 운영/실험/심사 3레인 라우팅 |
| 심사 확정 프로토콜 | GateRegistry B1 게이트 존재 | 인간 승인 + 자동 승인 이원 구조 |
| 반영 후 사후감사 | AssetSnapshot 시계열 있음 | 변경 전/후 자동 비교 |

---

## 6. 핵심 질문 체크리스트

### 목표대로 가고 있는가?

- [x] 자율성보다 헌법 통제가 우선인가 → **예** (GovernanceGate가 모든 에이전트 호출 앞에 위치)
- [x] 모든 변경은 검증/심사 후 반영되는가 → **예** (VALIDATING 10-check + OPS-GATE)
- [x] 실패와 실수를 학습 자산으로 다루는가 → **예** (L17 + EvidenceStore)
- [x] 운영 중 평상시는 무인 감시, 이상 시만 개입인가 → **예** (G-MON + Discord)
- [x] 진화 루프 설계가 존재하는가 → **예** (EvolutionLoop + SelfImprovementLoop)
- [ ] 진화 루프가 실제 운영에 연결되어 있는가 → **아직 아님** (src↔app 브릿지 미완성)
- [ ] 경험이 자동으로 설계안으로 변환되는가 → **아직 아님** (축적만 됨)
- [ ] 심사 확정 후 실매매에 반영되는 폐쇄루프가 있는가 → **아직 아님**

### 순서가 맞는가?

- [x] 통제를 먼저 만들고 실행을 나중에 붙이는 순서인가 → **예** (정답 순서)
- [x] 불필요한 범위는 제거했는가 → **예** (OKX 삭제)
- [x] 선행 구현을 금지하고 있는가 → **예** (ops baseline CONDITION-BASED ONLY)

---

## 7. 최종 판정

```
┌──────────────────────────────────────────────────┐
│  K-V3 프로젝트 체크포인트 판정                      │
│                                                    │
│  목표 방향성:     ✅ 정확히 맞음                     │
│  구축 순서:       ✅ 정답 (통제 → 감시 → 진화)       │
│  헌법 계층 (L1):  ✅ 강함                           │
│  운영 계층 (L2):  ✅ 강함                           │
│  학습 계층 (L3):  ⚠️ 중간 (축적 ○, 활용 △)         │
│  진화 계층 (L4):  ⚠️ 설계 완료, 통합 전              │
│                                                    │
│  현재 단계:       3.5/5 (감시 완료, 진화 진입 직전)   │
│  다음 관문:       src/kdexter ↔ app/ 브릿지          │
│  위험도:          낮음 (기반이 탄탄)                  │
│  권고:            현재 기반 유지, 트리거 시에만 확장    │
└──────────────────────────────────────────────────┘
```

> **"K-V3는 자율 진화 매매 시스템의 뇌를 만들기 전에, 그 뇌가 폭주하지 않을 국가 시스템을 먼저 완성했다. 순서가 맞고, 기반이 강하며, 다음 단계 진입 준비가 되어 있다."**
