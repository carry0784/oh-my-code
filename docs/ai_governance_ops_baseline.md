# AI 거버넌스 통합 완료 후 운영 기준선 체크리스트

> **상태: Core Governance Integration COMPLETE**
> **Immediate Work Queue: EMPTY**
> **Deferred Backlog: 2 items (Low)**
> **Next Action Policy: New scope only**
> **기준일: 2026-03-29**

---

## 1. 완료된 항목 (Priority 1~6)

| # | 작업 | 커밋 | 검증 |
|---|------|------|------|
| 1 | GovernanceGate 에이전트 연결 | `099b42b` 이전 | 29 tests PASS, 6 axes |
| 2 | AI 도구 역할 헌법 (DOC-L2-AI-TOOL-ROLE) | `199fa90` | verify_constitution.py PASS (26 docs) |
| 3 | L29 CostController → BUDGET_CHECK 연결 | `199fa90` | deferred → passed/failed |
| 4 | Provider/Model 변경 거버넌스 (§7 R-01~R-06) | `199fa90` | ai-tool-role-constitution.md §7 |
| 5 | L17 FailurePatternMemory → PATTERN_CHECK 연결 | `199fa90` | deferred → passed/failed |
| 6 | OKX 거래소 통합 제거 | `d8be404`, `316eb88` | 코드 0 참조, 16 tests PASS |

### VALIDATING 10-check 최종 상태

| # | 검증 항목 | 상태 | 연결 컴포넌트 |
|---|----------|------|--------------|
| 1 | FORBIDDEN_CHECK | **active** | ForbiddenLedger |
| 2 | MANDATORY_CHECK | **active** | 필수 필드 검증 |
| 3 | COMPLIANCE_CHECK | **active** | D-002, D-008, D-009 |
| 4 | DRIFT_CHECK | not_applicable | MainLoop/L15 스코프 |
| 5 | CONFLICT_CHECK | not_applicable | RuleLedger/L16 스코프 |
| 6 | PATTERN_CHECK | **active** | FailurePatternMemory (L17/G-21) |
| 7 | BUDGET_CHECK | **active** | CostController (L29/G-22) |
| 8 | TRUST_CHECK | not_applicable | TrustState/L19 스코프 |
| 9 | LOOP_CHECK | not_applicable | LoopMonitor/L28 스코프 |
| 10 | LOCK_CHECK | not_applicable | SpecLock/L22 스코프 |

**Active: 5/10 | Not Applicable: 5/10 | Deferred: 0/10**

---

## 2. 금지된 선행 확장

아래 항목은 **현재 스코프에서 구현하지 않는다.** 실측 필요가 확인되기 전까지 선행 구현을 금지한다.

| 금지 항목 | 이유 |
|-----------|------|
| not_applicable 5개 검증의 선행 활성화 | 에이전트 스코프에 해당하지 않음 |
| Anthropic→OpenAI 자동 failover | 장애 실측 없이 복잡도만 증가 |
| GovernanceGate 검증 항목 추가 | 현재 10-check로 충분, 확장은 신규 스코프 승인 후 |
| 추가 거래소 통합 | 운영 필요 확인 후에만 진행 |
| LLM Agent 추가 (새 에이전트 타입) | 기존 2개(SignalValidator, RiskManager)로 충분 |

---

## 3. 낮은 긴급도 백로그

### Deferred-Low-01: not_applicable 검증 5개 리뷰

- **대상**: DRIFT_CHECK, CONFLICT_CHECK, TRUST_CHECK, LOOP_CHECK, LOCK_CHECK
- **Trigger**: 에이전트 스코프가 MainLoop/RuleLedger/TrustState/LoopMonitor/SpecLock 영역으로 확장될 때
- **Current Status**: Not needed now
- **Do not implement preemptively**

### Deferred-Low-02: Auto-failover 메커니즘

- **대상**: Anthropic → OpenAI 런타임 자동 전환
- **Trigger**: Anthropic API 장애가 운영에 실제 영향을 미칠 때
- **Current Status**: 수동 `provider` 파라미터로 전환 가능, 자동화 불필요
- **Do not implement preemptively**

---

## 4. 운영 중 감시 지표

| 지표 | 소스 | 임계값 | 대응 |
|------|------|--------|------|
| BUDGET_CHECK 실패 빈도 | GovernanceGate evidence | 연속 3회 | API_CALLS/LLM_TOKENS 한도 재검토 |
| PATTERN_CHECK 차단 빈도 | GovernanceGate evidence | 일 5회 이상 | 반복 실패 원인 분석 |
| FORBIDDEN_CHECK 차단 | GovernanceGate evidence | 1회라도 | 즉시 조사 (금지된 동작 시도) |
| LLM 토큰 사용량 | CostController | 일 한도 80% | 예산 조정 검토 |
| 에이전트 실행 성공률 | AgentOrchestrator 로그 | 90% 미만 | 파이프라인 점검 |
| verify_constitution.py | CI/수동 | FAIL | 헌법 문서 정합성 즉시 복구 |

---

## 5. 다음 착수 조건

새 작업은 아래 **하나 이상**에 해당할 때만 시작한다:

| 조건 | 예시 |
|------|------|
| 실제 운영 이슈 발생 | BUDGET_CHECK 연속 차단, 에이전트 실패율 급증 |
| 신규 스코프 승인 | 새 에이전트 타입 추가, 새 거래소 통합 결정 |
| 외부 요구사항 변경 | 규정 변경, 신규 API 연동 필요 |
| 장애/비용/성능 문제 실측 확인 | Anthropic API 장애 반복, 토큰 비용 초과 |

**"구현할 수 있으니까"는 착수 조건이 아니다.**

---

## 자동 운영 감시 체계 (G-MON)

| 구분 | 주기 | 내용 |
|------|------|------|
| Daily Report | 24h | 6-indicator OK/WARN/FAIL + WARN/FAIL 시 Discord 알림 |
| Weekly Summary | 7d | 7일 추세 분석 (성공률/비용/패턴 변화) |
| On-demand | API | `GET /agents/governance/monitor` |

**알림 채널**: Discord webhook (`NOTIFIER_WEBHOOK_URL`), File JSONL (`NOTIFIER_FILE_PATH`)

**Celery Beat 스케줄**:
- `governance-monitor-daily`: 24h
- `governance-monitor-weekly`: 7d

**리포트 저장**: `data/governance_reports.jsonl` (JSONL append)

---

## 검증 기준선 스냅샷

```
Date: 2026-03-29
test_agent_governance.py:    29 PASS (6 axes)
test_governance_monitor.py:  11 PASS (6 classes)
test_market_feed.py:         16 PASS
verify_constitution.py:      PASS (26 docs, 2073 lines, 0 blockers)
OKX code references:         0
Deferred checks:             0/10
```

---

## 최종 선언

```
K-Dexter AI Governance System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status:       OPERATIONAL (LOCKED)
Core:         COMPLETE
Work Queue:   EMPTY
Governance:   ENFORCED
Monitoring:   AUTOMATED (G-MON)
Expansion:    CONDITION-BASED ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mode:         Controlled Operation
Next Action:  Monitor Only
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
