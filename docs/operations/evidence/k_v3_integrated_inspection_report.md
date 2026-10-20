# K-V3 프로젝트 통합점검 보고서 (검수본)

> **발행일**: 2026-04-14  
> **검수 기준선**: `48915d2` (PR #98 squash-merge)  
> **상태**: STANDBY  
> **검수 범위**: 전체 시스템 (코드 / 인프라 / 전략 / 거버넌스 / 운영)  
> **검수 형식**: 헌법(C1-C11) + 금지구역(FZ-01~10) + 금지전이(FT-01~10) 대조 검수  
> **production_authorized**: **FALSE** (불변 상수)

---

## 프로젝트 규모 요약

| 항목 | 수치 |
|------|------|
| Python 소스 파일 (app/workers/exchanges/strategies/kdexter) | ~350+ |
| 테스트 파일 | 231 |
| SQLAlchemy 모델 | 25 |
| Pydantic 스키마 | 39 |
| 서비스 모듈 | 101 |
| 에이전트 | 7 (orchestrator, governance_gate, signal_validator, risk_manager 등) |
| Celery 태스크 | 13 |
| Exchange 커넥터 | 5 (Binance, UpBit, Bitget, KIS, Kiwoom) |
| K8s 매니페스트 | 6 yaml |
| Alembic 마이그레이션 | 29 |
| 문서 (.md) | 538+ |
| 증빙 문서 | 344 |
| kdexter 엔진 | 76 파일 (audit/engines/gates/governance/ledger/loops/state_machine/strategy/tcl) |

---

# 제1부. 체크리스트 점검

---

## 1. 완성된 것 (COMPLETED) — 32항목

| # | 항목 | 상태 | 증빙 |
|---|------|------|------|
| 1 | FastAPI 애플리케이션 코어 | COMPLETE | `app/main.py`, lifespan, 4 probe endpoints |
| 2 | SQLAlchemy ORM 모델 (25개: Order/Signal/Position/Trade + 21 확장) | COMPLETE | `app/models/`, migration 001~029 |
| 3 | Pydantic 스키마 (39 파일) | COMPLETE | `app/schemas/` |
| 4 | 서비스 레이어 (101 서비스 파일) | COMPLETE | `app/services/` |
| 5 | Exchange 통합 (Binance/UpBit/Bitget/KIS/Kiwoom) | COMPLETE | `exchanges/`, CCXT 기반, Factory 패턴 |
| 6 | Celery Worker/Beat (13 task 파일) | COMPLETE | `workers/tasks/` |
| 7 | 거버넌스 프레임워크 (GovernanceGate singleton + 76 kdexter 모듈) | COMPLETE | `src/kdexter/`, `app/agents/governance_gate.py` |
| 8 | PPF 시스템 (17 source, C1-C11 헌법) | COMPLETE | `strategies/ppf/` |
| 9 | PPF Governance Engine (상태기계 7-state + FC-01~10 + VAL-PDC-002) | COMPLETE | `app/services/ppf_governance_engine.py` |
| 10 | 전략 카탈로그 (SMC_WT OPERATIONAL + SMC_MACD/RSI EXPERIMENTAL) | COMPLETE | `strategies/catalog.py` |
| 11 | CI 파이프라인 (6 jobs: lint/test/typecheck-tier1/tier2-advisory/dep-audit/build) | COMPLETE | `.github/workflows/ci.yml` |
| 12 | K8s 배포 매니페스트 (namespace/deployment/service/configmap/networkpolicy/monitoring) | COMPLETE | `k8s/*.yaml` |
| 13 | Docker 멀티스테이지 빌드 + production compose (5 services) | COMPLETE | `Dockerfile`, `docker-compose.prod.yml` |
| 14 | Prometheus 메트릭 + 8 alert rule (3 health + 3 trading + 2 infra) | COMPLETE | `k8s/monitoring.yaml` |
| 15 | 테스트 스위트 (231 test files) | COMPLETE | `tests/` |
| 16 | 구조화 로깅 (structlog + 24-field secret redaction) | COMPLETE | `app/core/logging.py` |
| 17 | API Rate Limiting (slowapi 30/min on POST orders/signals) | COMPLETE | `app/api/routes/orders.py`, `signals.py` |
| 18 | Secret Key Fail-Fast (production 환경 default key 차단) | COMPLETE | `app/main.py` lifespan L99-104 |
| 19 | K8s NetworkPolicy (default-deny + 5 allow) | COMPLETE | `k8s/networkpolicy.yaml` |
| 20 | Celery Probes (Worker: startup/liveness/readiness, Beat: startup/liveness/readiness) | COMPLETE | `k8s/deployment.yaml` |
| 21 | Dependency Audit CI (pip-audit advisory job) | COMPLETE | `.github/workflows/ci.yml` |
| 22 | Phase A Closure Receipt | COMPLETE | `docs/operations/evidence/phase_a_closure_receipt.md` |
| 23 | Advisory Ledger (7/7 closed: 5 RESOLVED + 2 ACCEPTED_RISK) | COMPLETE | `docs/operations/evidence/advisory_ledger_b001.md` |
| 24 | Deployment Readiness Receipt (CONDITIONALLY_PREPARED_NOT_AUTHORIZED) | COMPLETE | `docs/operations/evidence/deployment_readiness_receipt.md` |
| 25 | P3 Post-Eval Reevaluation Plan (REEVAL-PLAN-D001) | COMPLETE | `docs/operations/evidence/p3_post_eval_reevaluation_plan.md` |
| 26 | PPF Integrated Governance Spec (FZ-01~10, FC-01~10, 상태기계 정의) | COMPLETE | `docs/operations/evidence/ppf_integrated_governance_spec.md` |
| 27 | Orchestrator Pipeline (7-step: Signal→Risk→Action→Execution→Submit→PPF→Order) | COMPLETE | `app/agents/orchestrator.py` |
| 28 | Receipt Store (in-memory + optional file persistence) | COMPLETE | `app/core/notification_receipt_store.py` |
| 29 | Flow Log (C-23 execution log) | COMPLETE | `app/core/notification_flow_log.py` |
| 30 | ops_state.json (GUARDED_RELEASE mode, L0-L2 allowed) | COMPLETE | `ops_state.json` |
| 31 | PPF Parameters Frozen Dataclass (C10 compliance) | COMPLETE | `strategies/ppf/parameters.py` @dataclass(frozen=True) |
| 32 | GovernanceGate Pre-Check Matrix (10 checks: forbidden/mandatory/compliance/pattern/budget) | COMPLETE | `app/agents/governance_gate.py` |

---

## 2. 미완성 / 대기 항목 (INCOMPLETE / PENDING) — 16항목

| # | 항목 | 상태 | 이유 / 차단 요인 |
|---|------|------|-----------------|
| 1 | P3 관측 윈도우 완료 | PENDING | ~2026-04-28 종료 대기 (최소 336 bars, 10 novelty events) |
| 2 | VAL-PDC-002 실행 | PENDING | P3 완료 후 실행 (REEVAL-PLAN-D001 절차) |
| 3 | POST-P3 재평가 판정 (HOLD/PASS/BLOCK) | PENDING | VAL-PDC-002 결과 의존 |
| 4 | Paper Trading 진입 | PENDING | VAL-PDC-002 PASS + GREEN tier 필요 (FZ-07) |
| 5 | Shadow → Paper 전환 | PENDING | P3 PASS + promotion prerequisites 8-conjunction 충족 필요 |
| 6 | Production Authorization | PERMANENTLY_FALSE | 코드 내 `production_authorized = FALSE` 하드코딩 (FZ-04) |
| 7 | Live Entry | PERMANENTLY_BLOCKED | `check_live_entry()` always HARD_BLOCK (FZ-03) |
| 8 | Track B (SMC_MACD_1H ETH) 검증 | NOT_STARTED | EXPERIMENTAL, validation_status = NOT_STARTED |
| 9 | Track C-v2 (대체 레짐 지표) | NOT_STARTED | realized vol, choppiness, directional efficiency 미검증 |
| 10 | LNS (유동성-서사 통합 시스템) 구현 | NOT_STARTED | 설계 CLOSED, 코드 매핑 미시작 |
| 11 | GitHub Actions Node 24 업그레이드 (PR-A) | NOT_STARTED | deadline 2026-06-02 |
| 12 | PR-B Phase 2 (Approvals > 0 enforcement) | NOT_STARTED | Phase 1 완료, Phase 2 대기 |
| 13 | Typecheck Tier 2 → Blocking 전환 | DEFERRED | 현재 advisory, 기술 부채 해소 후 전환 예정 |
| 14 | pip-audit → Blocking 전환 | DEFERRED | 현재 continue-on-error: true |
| 15 | Grafana 대시보드 배포 | NOT_DEPLOYED | alert rules 정의됨, 실제 배포 미완 |
| 16 | Secrets 관리 (db_password.txt) | MANUAL | `docker-compose.prod.yml` secrets file 수동 생성 필요 |

---

# 제2부. 행동 지침

---

## 3. 지금 해야 할 것 (DO NOW) — 4항목

| # | 항목 | 근거 |
|---|------|------|
| 1 | **관측 보전**: P3 윈도우 데이터 수집 상태 확인 | P3_ACTIVE_NON_INTERFERENCE = TRUE |
| 2 | **기준선 보존**: main branch `48915d2` 변경 금지 | STANDBY 상태, baseline freeze |
| 3 | **모니터링**: ops_state.json 정합성 확인 | GUARDED_RELEASE 모드 유지 확인 |
| 4 | **문서 갱신**: 통합점검 결과 evidence 디렉토리 보관 | 증빙 체인 연속성 |

---

## 4. 하지 말 것 (DO NOT) — 12항목

| # | 금지 행위 | 근거 (헌법/FZ/FT) |
|---|----------|-------------------|
| 1 | 코드 변경 (main branch) | STANDBY, P3 non-interference |
| 2 | Production 배포 | production_authorized = FALSE (FZ-04) |
| 3 | Live 거래 진입 | FZ-03: check_live_entry() always HARD_BLOCK |
| 4 | Baseline 수정/삭제 | FZ-01, FZ-02: freeze 후 수정/삭제 불가 |
| 5 | P3 윈도우 단축 | FT-06: 통계적 유효성 보호, override 경로 없음 |
| 6 | Shadow → Live 직접 전환 | FT-01: paper 단계 필수 |
| 7 | 자동 promotion | FT-02, FT-05: human-only gate, CR 필수 |
| 8 | HOLD → PAPER 전환 (PASS 없이) | FT-03: HOLD = 증거 불충분 |
| 9 | BLOCK → PAPER 전환 (해소 없이) | FT-04: BLOCK = CR + 조사 필요 |
| 10 | VAL-PDC-002 GO → production_authorized 추론 | FT-08: test PASS ≠ production approval |
| 11 | 조건부 blocker → RESOLVED (토폴로지 확인 없이) | FT-07: topology confirmation 필수 |
| 12 | PPF 파라미터 런타임 변경 | C10: frozen dataclass, 변경 시도 시 FrozenInstanceError |

---

# 제3부. 운영 현황

---

## 5. 현재 운영 중인 시스템 — 11항목

| # | 시스템 | 상태 | 상세 |
|---|--------|------|------|
| 1 | ops_state.json | GUARDED_RELEASE | L0-L2 allowed, L3-L4 blocked, Gate LOCKED |
| 2 | CI 파이프라인 | ACTIVE | 6 jobs (lint/test/typecheck×2/dep-audit/build) |
| 3 | P3 관측 윈도우 | ACTIVE | CR-046 SOL Stage B, baseline 2026-04-07 |
| 4 | PPF Shadow Mode | ACTIVE | shadow connect 진행 중, enforcement disabled |
| 5 | Advisory Ledger | SEALED | 7/7 closed (OPEN = 0) |
| 6 | Governance State Machine | ACTIVE | current state tracking |
| 7 | 전략 카탈로그 | ACTIVE | SMC_WT OPERATIONAL, SMC_MACD/RSI EXPERIMENTAL |
| 8 | Branch Protection | ACTIVE | PR 기반 변경 필수, status checks required |
| 9 | Secret Redaction | ACTIVE | structlog processor, 24 fields |
| 10 | Constitution Checker | ACTIVE | C1-C11 run_all_checks() fail-closed |
| 11 | Forbidden Ledger | ACTIVE | FA-AGENT-001~004 사전 등록 |

---

## 6. 14일 후 (~2026-04-28) 해야 할 것 — 9단계

| 단계 | 절차 | 판정 기준 |
|------|------|-----------|
| 1 | P3 관측 데이터 수집 완료 확인 | bars >= 336, novelty events 확인 |
| 2 | VAL-PDC-002 7개 criteria 실행 | MIN_BARS, DENY_RATE_DELTA, FPR_DELTA, STATE_JS_DIVERGENCE, MIN_NOVELTY_EVENTS, SEAL_INTEGRITY, NO_HARD_BLOCK |
| 3 | Promotion Tier 판정 | GREEN (novelty>=10, all PASS) / YELLOW (5-9) / RED (<5 or FAIL) |
| 4 | HOLD/PASS/BLOCK 판정 | 판정 기준: REEVAL-PLAN-D001 §5 |
| 5 | 판정 결과 receipt 봉인 | 20개 audit fields 기록 |
| 6 | PASS 시: Paper 진입 조건 8-conjunction 점검 | FZ-07: VAL_PDC_002_ISSUED + GREEN tier 필수 |
| 7 | HOLD 시: 추가 관측 윈도우 설계 | 새 P3 window 필요 |
| 8 | BLOCK 시: 원인 분석 + CR 발행 | 코드 변경 필요 시 새 feature branch |
| 9 | 결과와 무관: production_authorized = FALSE 유지 | FZ-04, FT-02 불변 |

**평가 입력 우선순위 (6-tier):**
1. P3 관측 데이터 (최고 우선)
2. VAL-PDC-002 보고서
3. 검증 체인 receipts
4. Advisory Ledger
5. Deployment Readiness Receipt
6. Topology confirmations

---

# 제4부. 제기되는 문제

---

## 7. 알려진 이슈 — 14항목

| # | 이슈 | 심각도 | 상태 | 대응 |
|---|------|--------|------|------|
| 1 | A3 SQL Injection surface (SQLAlchemy ORM 사용 중) | Low | ACCEPTED_RISK | ORM 파라미터화로 안전, 신규 `text()` 호출 코드리뷰 필수 |
| 2 | A5 Redis Auth (dev 환경 비밀번호 없음) | Low | ACCEPTED_RISK | dev 전용, prod는 `--requirepass` 적용 완료 |
| 3 | Typecheck Tier 2 advisory (전체 app/ 타입 체크 미강제) | Medium | DEFERRED | Tier 1 (15 strict files) 만 blocking, 점진 확대 예정 |
| 4 | pip-audit advisory (non-blocking) | Medium | DEFERRED | continue-on-error: true, CVE 발견 시 수동 대응 |
| 5 | Grafana 대시보드 미배포 | Low | NOT_DEPLOYED | alert rules만 정의, 시각화 미구성 |
| 6 | secrets/db_password.txt 수동 생성 | Medium | MANUAL | prod compose secrets 의존, 자동화 미구현 |
| 7 | CORS allow_origins=["*"] (debug mode) | Low | BY_DESIGN | debug=True 일 때만 전체 허용, prod에서 빈 배열 |
| 8 | P3 novelty events 최소 10개 미달 가능성 | Medium | MONITORING | 미달 시 YELLOW tier → HOLD 판정 |
| 9 | Track B (ETH SMC_MACD) 미검증 | Low | NOT_STARTED | EXPERIMENTAL, 별도 validation 필요 |
| 10 | Track C-v1 FAIL (ADX/BB/ATR 비효과) | Info | CLOSED | C-v2 대체 지표 연구 대기 |
| 11 | LNS 통합 시스템 코드매핑 미시작 | Low | DESIGN_ONLY | 설계 완료, 구현 미착수 |
| 12 | GitHub Actions Node 24 마이그레이션 | Low | PENDING | deadline 2026-06-02 |
| 13 | Worker/Beat probe exec 명령 길이 | Info | ACCEPTED | K8s exec probe yaml 복잡도, 기능상 정상 |
| 14 | Evidence DB 기본값 in-memory | Low | BY_DESIGN | EVIDENCE_DB_PATH 미설정 시 메모리, prod에서 SQLite 사용 |

---

# 제5부. 시스템 구조와 설계

---

## 8. 시스템 기본 핵심

```
┌─────────────────────────────────────────────────────┐
│                  K-V3 AI Trading System              │
│                                                     │
│  핵심 원칙: "코드는 검수하고, 운영은 흔들지 않는다"      │
│  불변 상수: production_authorized = FALSE             │
│  현재 상태: STANDBY (P3 관측 윈도우 진행 중)            │
│  기준선:    48915d2 (PR #98)                         │
└─────────────────────────────────────────────────────┘
```

**3대 핵심 축:**
1. **거버넌스 우선 (Governance-First)**: 모든 실행은 GovernanceGate pre_check 통과 필수
2. **증빙 기반 판단 (Evidence-Based)**: 판단의 근거는 receipt + ledger + observation
3. **단계적 승격 (Staged Promotion)**: Shadow → Paper → Live, 각 단계 human gate 필수

---

## 9. 전체 시스템 아키텍처

```
                          ┌──────────────────┐
                          │   FastAPI (8000)  │
                          │   app/main.py     │
                          ├──────────────────┤
                          │ /health /ready    │
                          │ /startup /status  │
                          │ /api/v1/*         │
                          │ /dashboard/*      │
                          └────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼──────┐  ┌────────▼────────┐  ┌───────▼────────┐
    │  API Routes     │  │  Orchestrator   │  │  Dashboard     │
    │  orders/signals │  │  (7-step pipe)  │  │  (Jinja2 UI)  │
    │  positions/...  │  │  + PPF Step 5.75│  │  read-only     │
    └─────────┬──────┘  └────────┬────────┘  └────────────────┘
              │                  │
    ┌─────────▼──────┐  ┌───────▼──────────────────────────┐
    │  Services (101) │  │  Agent Pipeline                  │
    │  order_service  │  │  Step 1: SignalValidator          │
    │  signal_service │  │  Step 2: RiskManager              │
    │  market_data    │  │  Step 2.5: ActionLedger           │
    │  ppf_*  (7)     │  │  Step 3-5.5: Guards + Receipts   │
    │  shadow_* (4)   │  │  Step 5.75: PPF Gate (wrapper)   │
    │  strategy_* (6) │  │  Step 6: OrderExecutor            │
    └─────────┬──────┘  └───────┬──────────────────────────┘
              │                  │
    ┌─────────▼──────┐  ┌───────▼──────────┐
    │  GovernanceGate │  │  PPF System      │
    │  (singleton)    │  │  strategies/ppf/ │
    │  10-check       │  │  C1-C11 헌법      │
    │  pre/post       │  │  D1-D6 상태기계    │
    │  evidence store │  │  frozen params    │
    └─────────┬──────┘  └──────────────────┘
              │
    ┌─────────▼──────────────────────────────┐
    │  kdexter Engine (76 modules)           │
    │  ├─ audit/     (evidence + backends)   │
    │  ├─ engines/   (29 modules)            │
    │  ├─ gates/     (criteria + evaluator)  │
    │  ├─ governance/(constitution + doctrine)│
    │  ├─ ledger/    (forbidden + mandatory) │
    │  ├─ loops/     (main + recovery + evo) │
    │  ├─ state_machine/ (security/trust/work)│
    │  ├─ strategy/  (pipeline + risk)       │
    │  └─ tcl/       (exchange adapters)     │
    └────────────────────────────────────────┘
              │
    ┌─────────▼──────┐  ┌──────────────────┐
    │  PostgreSQL     │  │  Redis            │
    │  (async, 29     │  │  (broker + cache) │
    │   migrations)   │  │                   │
    └────────────────┘  └──────────────────┘
              │
    ┌─────────▼──────┐
    │  Exchanges (5)  │
    │  Binance/UpBit  │
    │  Bitget/KIS     │
    │  Kiwoom         │
    │  (CCXT Factory) │
    └────────────────┘
```

---

## 10. Orchestrator 파이프라인 상세

```
Signal 수신
    │
    ▼
[Step 1] SignalValidator — LLM 기반 신호 품질 평가 (approved/rejected)
    │
    ▼
[Step 2] RiskManager — 포지션 사이징, 포트폴리오 위험 평가
    │
    ▼
[Step 2.5] ActionLedger Guard — 에이전트 행동 감사
    │
    ▼
[Step 3] Would-Execute Marker — 실행 승인 마커
    │
    ▼
[Step 3.5] Agent Approval Receipt
    │
    ▼
[Step 4] ExecutionLedger Guard — 실행 원장 검증
    │
    ▼
[Step 4.5] Execution Receipt
    │
    ▼
[Step 5] SubmitLedger Guard — 제출 원장 검증
    │
    ▼
[Step 5.5] Submit Receipt
    │
    ▼
[Step 5.75] PPF Gate Handler — 패턴 투영 필터 (wrapper injection)
    │         ├─ C1: 주문 생성 안 함 (gate-only)
    │         ├─ C9: 단독 거래 금지
    │         └─ Shadow mode: 기록만, enforcement 없음
    │
    ▼
[Step 6] OrderExecutor — Exchange 주문 실행
    │
    ▼
[Step 6.25] PPF Execution Outcome — LV-2/LV-3 메타데이터 기록
```

---

# 제6부. 운영 원칙

---

## 11. 설계 원칙 — 10조

| # | 원칙 | 설명 |
|---|------|------|
| 1 | **Governance-First** | 모든 실행 경로는 GovernanceGate pre_check 통과 필수 |
| 2 | **Evidence-Based** | 판단은 receipt + ledger + observation 근거 기반 |
| 3 | **Fail-Closed** | 헌법 위반 시 PPF 비활성화, 거버넌스 위반 시 LOCKDOWN |
| 4 | **Singleton Control Boundary** | GovernanceGate 단일 인스턴스, split-brain 방지 |
| 5 | **Frozen Parameters** | PPF 파라미터 런타임 변경 불가 (C10 frozen dataclass) |
| 6 | **Wrapper Injection Only** | PPF는 외부 래퍼, 코어 안전 모듈 직접 수정 금지 (C7) |
| 7 | **Handler-Absent Safe** | PPF 핸들러 부재 시 안전 통과 (null-safe guard) |
| 8 | **Staged Promotion** | Shadow → Paper → Live, 각 단계 human gate |
| 9 | **Readiness ≠ Authorization** | 준비 완료가 승인을 의미하지 않음 |
| 10 | **Non-Interference** | P3 관측 윈도우 중 시스템 변경 금지 |

---

## 12. 운영 원칙 — 10조

| # | 원칙 | 설명 |
|---|------|------|
| 1 | **1작업 1폐루프** | 각 작업은 독립적 closed loop, 완료까지 추적 |
| 2 | **자동 전이 금지** | Phase/State 전이는 반드시 사용자 승인 |
| 3 | **증빙 체인 연속성** | phase_a → advisory → deployment → reevaluation 순서 보전 |
| 4 | **production_authorized = FALSE 불변** | 코드 내 하드코딩, 어떤 판정도 이를 변경 불가 |
| 5 | **P3 Non-Interference** | 관측 윈도우 중 코드/인프라/설정 변경 금지 |
| 6 | **Advisory → Resolution** | 각 advisory 항목은 개별 closed loop로 해소 |
| 7 | **Topology-Dependent Resolution** | 조건부 blocker는 실제 환경 확인 후에만 해소 |
| 8 | **PR 기반 변경** | main branch 직접 push 금지, feature branch + squash merge |
| 9 | **CI PASS 필수** | lint + test + typecheck-tier1 + build 전부 통과 |
| 10 | **봉인 후 변경 불가** | receipt/ledger 봉인 후 수정 금지, 새 문서만 발행 가능 |

---

## 13. 운영 방법

### 일상 운영 (STANDBY 상태)
```
1. 관측 데이터 자동 수집 (Celery beat scheduler)
2. CI 파이프라인 자동 실행 (PR 기반)
3. ops_state.json 상태 모니터링
4. 코드 변경 금지 (P3 window)
```

### 변경 절차
```
1. Feature branch 생성
2. 코드 변경 + 테스트
3. PR 생성 (gh pr create)
4. CI 6-job 통과 확인
5. Squash merge to main
6. 증빙 문서 갱신
```

### 비상 절차
```
1. K8s rollback: kubectl rollout undo deployment/kdexter-api
2. Docker rollback: docker-compose -f docker-compose.prod.yml down && docker-compose up
3. DB rollback: alembic downgrade -1
4. ops_state rollback: 이전 버전 복원
```

---

# 제7부. 장점과 부족점

---

## 14. 장점 — 10항목

| # | 장점 | 근거 |
|---|------|------|
| 1 | **다층 거버넌스** | GovernanceGate(10-check) + PPF Constitution(C1-C11) + FZ(10) + FT(10) = 41개 안전 장벽 |
| 2 | **증빙 기반 의사결정** | EvidenceStore + receipt chain + advisory ledger로 모든 판단 추적 가능 |
| 3 | **Fail-Closed 설계** | 헌법 위반 → PPF 비활성화, 거버넌스 위반 → LOCKDOWN, 기본값 = 거부 |
| 4 | **Singleton 제어 경계** | GovernanceGate 단일 인스턴스 + generation counter로 split-brain 완전 방지 |
| 5 | **포괄적 프로브 체계** | API(3-tier HTTP) + Worker(exec) + Beat(exec) = 모든 컴포넌트 상태 감시 |
| 6 | **네트워크 격리** | default-deny + 5 allow NetworkPolicy로 lateral movement 차단 |
| 7 | **비밀 보호 3중** | Secret redaction(24 fields) + env validation(fail-fast) + prod Redis auth |
| 8 | **전략 카탈로그 분리** | OPERATIONAL/EXPERIMENTAL 명확 분리, 미검증 전략 실행 차단 |
| 9 | **점진적 CI 강화** | Tier 1(blocking) + Tier 2(advisory) + dep-audit(advisory) 단계적 전환 구조 |
| 10 | **5개 거래소 통합** | CCXT Factory 패턴으로 Binance/UpBit/Bitget/KIS/Kiwoom 균일 인터페이스 |

---

## 15. 부족점 — 10항목

| # | 부족점 | 영향 | 완화 방안 |
|---|--------|------|-----------|
| 1 | **Live entry 영구 차단** | 실제 운영 불가 | 의도적 설계, human CR로만 해제 가능한 별도 경로 필요 |
| 2 | **Typecheck 부분 적용** | 전체 app/ 중 15 파일만 strict | Tier 2 advisory → blocking 점진 전환 |
| 3 | **pip-audit non-blocking** | 취약 의존성 무시 가능 | blocking 전환 예정, 현재 수동 모니터링 |
| 4 | **Grafana 미배포** | 시각적 모니터링 부재 | alert rules 정의 완료, 배포만 필요 |
| 5 | **secrets 수동 관리** | 자동화 부재, 인적 오류 가능 | Vault/sealed-secrets 도입 검토 |
| 6 | **Evidence DB 기본값 in-memory** | 재시작 시 증빙 소실 | prod에서 EVIDENCE_DB_PATH 필수 설정 |
| 7 | **Track B/C-v2 미검증** | 전략 다양성 부족 | P3 이후 별도 validation track |
| 8 | **LNS 미구현** | 유동성-서사 통합 기능 부재 | 설계 완료, 구현 별도 계획 필요 |
| 9 | **P3 novelty 미달 리스크** | YELLOW/RED tier → HOLD/BLOCK | 시장 환경 의존, 통제 불가 |
| 10 | **단일 asset 운영** | SOL/USDT만 OPERATIONAL | BTC는 guarded, ETH는 excluded |

---

# 제8부. 헌법 대조 검수

---

## 16. C1-C11 헌법 준수 감사

| 조항 | 규정 | 코드 근거 | 판정 |
|------|------|-----------|------|
| C1 | PPF는 주문을 생성하지 않음 (gate-only) | `ppf_gate_handler.py`: `check_gate()` returns PPFGateResult (bool allowed), 주문 생성 메서드 없음 | **PASS** |
| C2 | "predict" 언어 사용 금지 | Output labels: "hypothesis", 코드 내 predict 미사용 확인 | **PASS** |
| C3 | 시장 프로파일별 독립 설정 | `constitution.py`: `check_c3_independent_profiles()` 구현 | **PASS** |
| C4 | Path quality D5 진입 조건 | `gate.py`: path_quality 체크 후 D5_ARMED 전이 | **PASS** |
| C5 | Shadow 검증 후 paper/live | Governance state machine: SHADOW 단계 필수 경유 | **PASS** |
| C6 | K >= MIN_K (단일 패턴 금지) | `constitution.py`: `check_c6_k_minimum()`, `constants.py`: MIN_K=2 | **PASS** |
| C7 | 실행 엔진 파일 무결성 (sha256 diff=0) | `constitution.py`: `check_c7_engine_diff()` sha256 checksum 검증 | **PASS** |
| C8 | Output은 "hypothesis" 라벨 | PPF output 구조 확인, prediction 라벨 미사용 | **PASS** |
| C9 | PPF 단독 거래 금지 | `orchestrator.py`: PPF는 Step 5.75 wrapper, 독립 실행 경로 없음 | **PASS** |
| C10 | 런타임 파라미터 변경 불가 | `parameters.py`: `@dataclass(frozen=True)`, 변경 시 FrozenInstanceError | **PASS** |
| C11 | Novelty brake (O9=True → PPF 비활성화) | `constitution.py`: `check_c11_novelty_brake()`, O9=True → D1_IDLE 강제 | **PASS** |

**C1-C11 결과: 11/11 PASS**

---

## 17. FZ-01~10 금지 구역 감사

| ID | 금지 구역 | 코드 근거 | 판정 |
|----|----------|-----------|------|
| FZ-01 | Baseline 수정 (freeze 후) | `PPFBaselineManager.freeze_baseline()`: 2nd call → `ALREADY_FROZEN` 반환, UPDATE 경로 없음 | **PASS** |
| FZ-02 | Baseline 삭제 | `PPFBaselineManager`: DELETE 경로 없음, `invalidate_baseline()` → `invalidated=True` only | **PASS** |
| FZ-03 | Live entry (모든 경로) | `PPFGovernanceEngine.check_live_entry()`: always returns `HARD_BLOCK`, 조건부 분기 없음 | **PASS** |
| FZ-04 | Live authorization via VAL-PDC-002 | `ValPDC002Judge.check_live_authorized()`: always `False`, `live_authorized` 하드코딩 False | **PASS** |
| FZ-05 | Test PASS → production approval 추론 | `ValPDC002Report.live_authorized = False` 하드코딩, GO verdict ≠ live authorization | **PASS** |
| FZ-06 | 무효 상태 전이 | `PPFGovernanceEngine.transition()`: 미등록 전이 → `ValueError`, VAL_PDC_002_ISSUED = terminal | **PASS** |
| FZ-07 | Paper entry without PASS+GREEN | `check_paper_entry(tier)`: state ≠ VAL_PDC_002_ISSUED OR tier ≠ GREEN → `HARD_BLOCK` | **PASS** |
| FZ-08 | Phase A without preflight PASS | FC-01 `check_phase_a_ready(False)` → `SOFT_BLOCK` | **PASS** |
| FZ-09 | Phase B without frozen baseline | FC-03 `check_phase_b_ready(False)` → `SOFT_BLOCK` | **PASS** |
| FZ-10 | Baseline freeze with unresolved >5% | FC-02 `check_baseline_freeze_ready()` → `SOFT_BLOCK` when rate > 0.05 | **PASS** |

**FZ-01~10 결과: 10/10 PASS**

---

## 18. FT-01~10 금지 전이 감사

| ID | 금지 전이 | 검증 방법 | 판정 |
|----|----------|-----------|------|
| FT-01 | SHADOW → LIVE (paper skip) | 상태기계에 직접 전이 경로 없음, paper 단계 필수 경유 | **PASS** |
| FT-02 | Auto production_authorized = TRUE | `production_authorized = TRUE` 설정 코드 경로 없음, human-only | **PASS** |
| FT-03 | HOLD → PAPER (PASS skip) | Reevaluation verdict PASS 필수, HOLD = 증거 불충분 | **PASS** |
| FT-04 | BLOCK → PAPER (resolution skip) | BLOCK 시 새 CR 필수, 자동 해소 경로 없음 | **PASS** |
| FT-05 | Auto promotion_open = TRUE | FZ-05 영구 금지, auto-promotion 코드 경로 없음 | **PASS** |
| FT-06 | P3 window 수동 단축 | 수동 override 경로 없음, 윈도우 크기 상수 | **PASS** |
| FT-07 | Conditional blocker → RESOLVED (no topology) | Advisory ledger: topology confirmation 필드 필수 | **PASS** |
| FT-08 | VAL-PDC-002 GO → production_authorized | FZ-04/FZ-05: `live_authorized` 항상 False, GO ≠ authorization | **PASS** |
| FT-09 | Reevaluation PASS → auto promotion | 별도 human-authorized CR 필수, auto-execute 경로 없음 | **PASS** |
| FT-10 | Hard blocker RESOLVED → production_authorized | Necessary but not sufficient, 추가 prerequisites 필요 | **PASS** |

**FT-01~10 결과: 10/10 PASS**

---

## 19. 거버넌스 게이트 감사

| 항목 | 요구사항 | 코드 근거 | 판정 |
|------|---------|-----------|------|
| Singleton 강제 | 단일 인스턴스만 허용 | `_instance`, `_creation_lock`, 2nd creation → RuntimeError | **PASS** |
| Pre-check 필수 | 모든 실행 전 거버넌스 체크 | `pre_check(task)` → 10-check matrix | **PASS** |
| Evidence 기록 | 모든 판단 증빙 저장 | `post_record()`, `post_record_error()` → EvidenceStore | **PASS** |
| Forbidden Action 사전등록 | FA-AGENT-001~004 | `__init__`에서 4개 FA rule 등록 | **PASS** |
| Production fail-fast | prod 환경 default key 차단 | `app/main.py` L99-104: RuntimeError on default secret_key | **PASS** |
| Governance 강제 | prod 환경 governance_enabled 필수 | `app/main.py` L107-111: RuntimeError when governance disabled | **PASS** |

**거버넌스 감사: 6/6 PASS**

---

## 20. 검수 총괄

```
┌──────────────────────────────────────────────────────┐
│              K-V3 통합점검 검수 결과 총괄               │
├──────────────────────────────────────────────────────┤
│                                                      │
│  헌법 C1-C11:           11/11 PASS                   │
│  금지구역 FZ-01~10:     10/10 PASS                   │
│  금지전이 FT-01~10:     10/10 PASS                   │
│  거버넌스 게이트:         6/6  PASS                   │
│  ─────────────────────────────────────               │
│  총합:                  37/37 PASS (100%)            │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  완성 항목:              32 COMPLETED                 │
│  미완성/대기:            16 PENDING                   │
│  알려진 이슈:            14 (0 Critical, 4 Medium)    │
│  Advisory:              7/7 CLOSED (0 OPEN)          │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  검수 판정:             PASS                          │
│  현재 상태:             STANDBY                       │
│  production_authorized: FALSE (불변)                  │
│  P3_NON_INTERFERENCE:   TRUE                         │
│  다음 액션:             ~2026-04-28 REEVAL-PLAN-D001  │
│                                                      │
│  검수자: AI Inspector                                │
│  검수일: 2026-04-14                                  │
│  기준선: 48915d2                                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

*END OF REPORT*
