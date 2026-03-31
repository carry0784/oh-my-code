# Sprint Contract Card — CARD-2026-0330-CLEANUP-SIM

> **작성자**: Claude Code A
> **날짜**: 2026-03-30
> **등급**: Level B (중위험 — 신규 서비스, Dashboard 연동, Ledger 읽기만)
> **상태**: ACTIVE

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | AB-01~06, EB-01~07, SB-01~08 (Ledger 봉인 3종) |
| 선행 작업 | Cleanup Policy (COMPLETE, C-GO), Orphan Detection (COMPLETE, C-GO) |

---

## 1. 작업명

> Cleanup Simulation & Operator Action Policy — stale/orphan 기반 정리 후보 분류 및 운영자 행동 제안 서비스

---

## 2. 목표

현재 stale/orphan은 탐지되지만, 운영 대응 방침이 없다.

1. **Cleanup Candidate 분류**: stale/orphan 제안을 정리 후보로 분류
2. **Operator Action Class**: INFO / WATCH / REVIEW / MANUAL_CLEANUP_CANDIDATE 4단계 분류
3. **Reason Code 표준화**: `STALE_EXECUTION`, `ORPHAN_SUBMIT_PARENT_MISSING` 등 고정 코드
4. **영향도 시뮬레이션**: candidate count, by tier, by severity 정량 표시
5. **Dashboard 연결**: cleanup simulation 결과를 4-Tier Board에 반영
6. **자동 정리 금지**: 시뮬레이션/추천만 — write path 절대 금지

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 | 보호 여부 |
|---|--------------|----------|----------|
| 1 | `app/services/cleanup_simulation_service.py` | NEW — 정리 시뮬레이션 서비스 | NO |
| 2 | `app/schemas/four_tier_board_schema.py` | MODIFY — cleanup simulation 필드 추가 | NO |
| 3 | `app/services/four_tier_board_service.py` | MODIFY — cleanup simulation 연결 | NO |
| 4 | `tests/test_cleanup_simulation.py` | NEW — 전용 테스트 | NO |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | `app/agents/action_ledger.py` | 봉인 보호 |
| 2 | `app/services/execution_ledger.py` | 봉인 보호 |
| 3 | `app/services/submit_ledger.py` | 봉인 보호 |
| 4 | `app/services/orphan_detection_service.py` | 이전 완료 작업 보호 |
| 5 | _TRANSITIONS 구조 (3개 Ledger 모두) | 상태 머신 봉인 보호 |
| 6 | propose_and_guard / record_receipt / record_failure | 핵심 경로 변경 금지 |
| 7 | GovernanceGate / OrderExecutor | 이 작업과 무관 |

---

## 5. 설계 가이드

### Operator Action Class (4단계)

```
INFO                    — 정상 또는 미미한 이상. 별도 행동 불필요.
WATCH                   — 관찰 필요. 자동 해소 가능성 있음.
REVIEW                  — 운영자 확인 필요. 수동 판단 대기.
MANUAL_CLEANUP_CANDIDATE — 수동 정리 후보. 운영자가 직접 결정.
```

### Reason Code (표준 코드)

```
STALE_AGENT              — Agent tier stale proposal
STALE_EXECUTION          — Execution tier stale proposal
STALE_SUBMIT             — Submit tier stale proposal
ORPHAN_EXEC_PARENT       — Execution tier: agent_proposal_id missing
ORPHAN_SUBMIT_PARENT     — Submit tier: execution_proposal_id missing
STALE_AND_ORPHAN         — stale + orphan 동시 해당
```

### Action Class 결정 로직

```
stale only (age < 2x threshold)  → WATCH
stale only (age >= 2x threshold) → REVIEW
orphan only                      → REVIEW
stale + orphan                   → MANUAL_CLEANUP_CANDIDATE
none                             → INFO (정상)
```

### 영향도 시뮬레이션 출력

```python
@dataclass
class CleanupSimulationReport:
    total_candidates: int
    by_tier: dict[str, int]           # {"agent": 2, "execution": 1, "submit": 3}
    by_action_class: dict[str, int]   # {"WATCH": 2, "REVIEW": 3, "MANUAL_CLEANUP_CANDIDATE": 1}
    by_reason: dict[str, int]         # {"STALE_EXECUTION": 2, "ORPHAN_SUBMIT_PARENT": 1, ...}
    candidates: list[dict]            # CleanupCandidate 목록
    write_impact: int = 0             # 항상 0 (write 금지)
    terminal_impact: int = 0          # 항상 0 (terminal 변경 금지)
    simulation_only: bool = True      # 항상 True
```

### CleanupCandidate 구조

```python
@dataclass
class CleanupCandidate:
    proposal_id: str
    tier: str                         # "agent" | "execution" | "submit"
    action_class: str                 # "WATCH" | "REVIEW" | "MANUAL_CLEANUP_CANDIDATE"
    reason_code: str                  # "STALE_EXECUTION" | "ORPHAN_SUBMIT_PARENT" | ...
    is_stale: bool
    is_orphan: bool
    stale_age_seconds: float          # 0.0 if not stale
    current_status: str
    proposal_id_display: str          # 짧은 표시용
```

### 데이터 수집 방법

```
1. 각 Ledger의 get_proposals() + is_stale() 호출 → stale 후보 수집
2. detect_orphans() 결과 → orphan 후보 수집
3. stale ∪ orphan → 전체 candidate 집합
4. 각 candidate에 action class + reason code 부여
5. 집계 → CleanupSimulationReport 생성
```

### Dashboard 연결

```
FourTierBoardResponse에 추가:
  cleanup_candidate_count: int = 0
  cleanup_action_summary: dict = {}   # {"WATCH": 2, "REVIEW": 1, ...}
```

---

## 6. 완료 기준

- [ ] cleanup_simulation_service.py 생성 — 읽기 전용, 시뮬레이션 전용
- [ ] CleanupCandidate 분류: stale/orphan 기반 4단계 action class
- [ ] Reason Code 6종 표준 코드 구현
- [ ] 영향도 시뮬레이션: by_tier, by_action_class, by_reason 집계
- [ ] write_impact=0, terminal_impact=0, simulation_only=True 항상 보장
- [ ] 4-Tier Board에 cleanup simulation 결과 연동
- [ ] Ledger 내부 파일 변경 없음
- [ ] orphan_detection_service.py 변경 없음
- [ ] 전용 테스트 최소 25개, 6축 이상
- [ ] 기존 Control Total (286개) 회귀 0
- [ ] 봉인 위반 0

---

## 7. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | Ledger 내부 코드 수정 | 봉인 보호 |
| 2 | Ledger에 write 메서드 호출 | read-only 원칙 |
| 3 | 제안 자동 삭제/자동 전이 | append-only + 상태 머신 보호 |
| 4 | cleanup이 실행 흐름 차단 | 시뮬레이션 전용 |
| 5 | _proposals 직접 접근 | get_proposals() 공개 API만 |
| 6 | orphan_detection_service.py 수정 | 이전 완료 작업 보호 |
| 7 | terminal 상태 변경 | _TERMINAL_STATES 보호 |

---

## 8. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| AXIS 1: Candidate 분류 정확성 | 5 | stale→WATCH/REVIEW, orphan→REVIEW, both→MANUAL |
| AXIS 2: Reason Code 정확성 | 4 | 6종 코드 정확 배정 |
| AXIS 3: Action Class 결정 로직 | 4 | 4단계 분류 경계값 |
| AXIS 4: 영향도 시뮬레이션 | 4 | by_tier, by_action, by_reason 집계 |
| AXIS 5: Read-Only 보장 | 3 | write 미호출, simulation_only=True |
| AXIS 6: Dashboard 연동 | 3 | cleanup_candidate_count, action_summary |
| AXIS 7: Edge Cases | 2+ | 빈 Ledger, 전부 정상, partial observation |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | 286 (현재 기준) |
| Full Suite | PASS 필수 (기존 실패 제외) |

---

## 9. Claude Code C 검수 중점

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | Ledger 내부 파일(3개) 변경 여부 | 금지 조항 최우선 검증 |
| 2 | orphan_detection_service.py 변경 여부 | 이전 완료 작업 보호 |
| 3 | write 메서드 호출 여부 | read-only 원칙 |
| 4 | simulation_only=True 강제 여부 | 자동 정리 방지 |
| 5 | action class 분류의 정확성 | 운영자 오판 유발 가능성 |
| 6 | reason code가 표준 6종 내인지 | 코드 확장 통제 |

---

> Contract version: 1.0
> Source: DOC-L2-HARNESS (claude-code-harness-constitution.md)
> Level: B (중위험 — 신규 서비스, Ledger 읽기만)
