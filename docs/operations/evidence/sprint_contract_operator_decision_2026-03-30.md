# Sprint Contract Card — CARD-2026-0330-OPERATOR-DECISION

> **작성자**: Claude Code A
> **날짜**: 2026-03-30
> **등급**: Level B (중위험 — 신규 서비스, Board 연동, 판단 계층)
> **상태**: ACTIVE

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | AB-01~06, EB-01~07, SB-01~08 (Ledger 봉인 3종) |
| 선행 작업 | Cleanup Policy, Orphan Detection, Cleanup Simulation, Board Obs Upgrade (전부 C-GO) |

---

## 1. 작업명

> Operator Decision Layer — 관측 결과 기반 운영자 판단 가이드 서비스 (읽기 전용, 제안 전용)

---

## 2. 목표

현재 시스템은 "무엇이 문제인지"는 잘 보여주지만, "그래서 무엇을 해야 하는지"는 구조화되어 있지 않다.

1. **Decision Summary**: pressure/priority 기반 운영자 판단 가이드 생성
2. **Recommended Posture**: MONITOR / REVIEW / MANUAL_CHECK / URGENT_REVIEW 4단계
3. **Decision Reason Chain**: 판단 근거를 추적 가능한 체인으로 제공
4. **Risk Level**: LOW / MEDIUM / HIGH 3단계
5. **action_allowed = False**: 모든 decision에 실행 금지 라벨 고정
6. **Board 연결**: decision_summary를 4-Tier Board에 반영

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 |
|---|--------------|----------|
| 1 | `app/services/operator_decision_service.py` | NEW — 운영자 판단 가이드 서비스 |
| 2 | `app/schemas/four_tier_board_schema.py` | MODIFY — decision_summary 필드 추가 |
| 3 | `app/services/four_tier_board_service.py` | MODIFY — decision service 연결 |
| 4 | `tests/test_operator_decision.py` | NEW — 전용 테스트 |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | `app/agents/action_ledger.py` | 봉인 보호 |
| 2 | `app/services/execution_ledger.py` | 봉인 보호 |
| 3 | `app/services/submit_ledger.py` | 봉인 보호 |
| 4 | `app/services/orphan_detection_service.py` | 이전 완료 작업 보호 |
| 5 | `app/services/cleanup_simulation_service.py` | 이전 완료 작업 보호 |
| 6 | `app/services/observation_summary_service.py` | 이전 완료 작업 보호 |
| 7 | _TRANSITIONS 구조 (3개 Ledger 모두) | 상태 머신 봉인 보호 |

---

## 5. 설계 가이드

### Recommended Posture (4단계)

```
MONITOR       — 정상 또는 경미. 자동 해소 대기.
REVIEW        — 운영자 검토 필요. 수동 판단 대기.
MANUAL_CHECK  — 수동 확인 필요. cleanup 후보 존재.
URGENT_REVIEW — 긴급 검토. 높은 pressure + 다수 MANUAL.
```

### Risk Level (3단계)

```
LOW    — pressure LOW/MODERATE, orphan 0, candidate ≤ 2
MEDIUM — pressure HIGH 또는 orphan > 0 또는 candidate 3~9
HIGH   — pressure CRITICAL 또는 candidate ≥ 10
```

### Posture 결정 로직

```
pressure == LOW                           → MONITOR
pressure == MODERATE                      → REVIEW
pressure == HIGH                          → MANUAL_CHECK
pressure == CRITICAL                      → URGENT_REVIEW
```

### DecisionSummary 구조

```python
@dataclass
class DecisionSummary:
    recommended_posture: str        # "MONITOR" | "REVIEW" | "MANUAL_CHECK" | "URGENT_REVIEW"
    risk_level: str                 # "LOW" | "MEDIUM" | "HIGH"
    reason_chain: list[str]         # ["pressure=HIGH", "manual_count=3", "orphan_total=2"]
    decision_explanation: str       # Human-readable 1-2 sentence explanation
    candidate_total: int
    orphan_total: int
    stale_total: int
    cleanup_pressure: str           # 원본 pressure 전달

    # Safety labels — 항상 고정
    action_allowed: bool = False    # NEVER True
    suggestion_only: bool = True    # Always True
    read_only: bool = True          # Always True
```

### 데이터 수집

```
1. build_observation_summary() 결과 → pressure, stale_total, orphan_total, candidate_total
2. 위 데이터로 posture + risk_level + reason_chain 결정
3. DecisionSummary 생성
```

### Dashboard 연결

```
FourTierBoardResponse에 추가:
  decision_summary: dict = {}   # DecisionSummary.to_dict()
```

---

## 6. 완료 기준

- [ ] operator_decision_service.py 생성 — 읽기 전용, 제안 전용
- [ ] Recommended Posture 4단계 결정 로직
- [ ] Risk Level 3단계 결정 로직
- [ ] Reason Chain (추적 가능한 판단 근거)
- [ ] decision_explanation (사람이 읽을 수 있는 설명)
- [ ] action_allowed=False / suggestion_only=True / read_only=True 항상 고정
- [ ] 4-Tier Board에 decision_summary 연동
- [ ] 기존 6개 파일 변경 없음
- [ ] 전용 테스트 최소 25개, 7축 이상
- [ ] 기존 Control Total (342개) 회귀 0
- [ ] 봉인 위반 0

---

## 7. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | Ledger 내부 코드 수정 | 봉인 보호 |
| 2 | 기존 관측 서비스 3개 수정 | 이전 완료 작업 보호 |
| 3 | observation_summary_service 수정 | 이전 완료 작업 보호 |
| 4 | write 메서드 호출 | read-only 원칙 |
| 5 | action_allowed=True 허용 | 실행 금지 절대 원칙 |
| 6 | 자동 실행/자동 cleanup/상태 전이 | simulation only |
| 7 | "execute", "perform", "clean" 동사를 posture에 사용 | 실행 유도 방지 |

---

## 8. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| AXIS 1: Posture 결정 정확성 | 5 | MONITOR/REVIEW/MANUAL_CHECK/URGENT_REVIEW 경계값 |
| AXIS 2: Risk Level 결정 정확성 | 4 | LOW/MEDIUM/HIGH 경계값 |
| AXIS 3: Reason Chain 정확성 | 3 | 체인 항목 수, 내용 정합 |
| AXIS 4: Explanation 품질 | 3 | 사람 판독 가능, 실행 동사 미포함 |
| AXIS 5: Safety Labels 보장 | 4 | action_allowed=False, suggestion_only, read_only |
| AXIS 6: Dashboard 연동 | 3 | decision_summary in board |
| AXIS 7: Edge Cases | 3+ | 빈 데이터, 전부 정상, 극단값 |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | 342 (현재 기준) |

---

## 9. Claude Code C 검수 중점

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | 기존 파일(6개) 변경 여부 | 금지 조항 최우선 검증 |
| 2 | action_allowed=False 강제 여부 | 실행 금지 절대 원칙 |
| 3 | posture에 실행 동사 포함 여부 | "execute"/"clean"/"remove" 검출 |
| 4 | reason_chain 추적 가능성 | 운영자가 왜 이 판단인지 역추적 가능 |
| 5 | Board 표시가 실행 유도로 오해될 수 있는지 | UI semantics 검수 |

---

> Contract version: 1.0
> Level: B (중위험 — 신규 서비스, 읽기 전용 판단 가이드)
