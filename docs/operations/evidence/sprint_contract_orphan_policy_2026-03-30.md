# Sprint Contract Card — CARD-2026-0330-ORPHAN

> **작성자**: Claude Code A
> **날짜**: 2026-03-30
> **등급**: Level C (고위험 — 교차 Ledger 접근, Dashboard 연동)
> **상태**: ACTIVE

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | AB-01~06, EB-01~07, SB-01~08 (Ledger 봉인 3종) |
| 선행 작업 | Cleanup Policy (COMPLETE, C-GO), Stale Detection (COMPLETE) |

---

## 1. 작업명

> Orphan Detection Policy — 교차 Ledger lineage 검증을 통한 고아(orphan) 제안 탐지 및 Dashboard 경고 연결

---

## 2. 목표

현재 `get_board()`의 `orphan_count`는 단순히 GUARDED 상태 제안 수를 센다. 이것은 "pending" 카운트이지 진정한 orphan이 아니다. 진정한 orphan은 **lineage가 끊긴 제안**이다.

1. **Orphan 정의**: 상위 제안 ID가 해당 Ledger에 존재하지 않는 제안
2. **교차 Ledger 검증**: ExecutionLedger의 agent_proposal_id가 ActionLedger에 없으면 orphan, SubmitLedger의 execution_proposal_id가 ExecutionLedger에 없으면 orphan
3. **탐지 서비스**: 읽기 전용 서비스로 구현 (Ledger 내부 변경 최소화)
4. **Dashboard 연결**: 4-Tier Board에 orphan 상세 노출

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 | 보호 여부 |
|---|--------------|----------|----------|
| 1 | `app/services/orphan_detection_service.py` | NEW — 교차 Ledger orphan 탐지 서비스 | NO |
| 2 | `app/schemas/four_tier_board_schema.py` | MODIFY — orphan 상세 필드 추가 | NO |
| 3 | `app/services/four_tier_board_service.py` | MODIFY — orphan 탐지 연결 | NO |
| 4 | `tests/test_orphan_detection.py` | NEW — Orphan Detection 전용 테스트 | NO |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | `app/agents/action_ledger.py` | 기존 orphan_count 동작 보존. 내부 수정 불필요 |
| 2 | `app/services/execution_ledger.py` | 내부 수정 불필요. get_proposals()로 외부에서 읽기만 |
| 3 | `app/services/submit_ledger.py` | 내부 수정 불필요. get_proposals()로 외부에서 읽기만 |
| 4 | _TRANSITIONS 구조 (3개 Ledger 모두) | 상태 머신 봉인 보호 |
| 5 | propose_and_guard / record_receipt / record_failure | 핵심 경로 변경 금지 |
| 6 | GovernanceGate / OrderExecutor | 이 작업과 무관 |

> **핵심 원칙**: Orphan 탐지는 **외부 서비스**에서 수행한다. Ledger 내부를 수정하지 않는다. 3개 Ledger의 `get_proposals()`를 읽기만 하여 교차 검증한다.

---

## 5. 완료 기준

- [ ] orphan_detection_service.py 생성 — 읽기 전용, 교차 Ledger 검증
- [ ] ExecutionLedger orphan: agent_proposal_id가 ActionLedger에 없는 제안 탐지
- [ ] SubmitLedger orphan: execution_proposal_id가 ExecutionLedger에 없는 제안 탐지
- [ ] ActionLedger orphan: (단일 Ledger이므로 교차 검증 없음, 기존 orphan_count 유지)
- [ ] 4-Tier Board에 교차 검증 orphan 결과 노출
- [ ] Ledger 내부 파일 변경 없음 (소스 diff 검증)
- [ ] 전용 테스트 최소 20개, 6축 이상
- [ ] 기존 Control Total (467개) 회귀 0
- [ ] 전체 스위트 회귀 0 (기존 실패 제외)
- [ ] 봉인 위반 0

---

## 6. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | Ledger 내부 코드 수정 | 봉인 보호 — 외부 서비스에서만 읽기 |
| 2 | Ledger에 write 메서드 호출 | read-only 원칙 |
| 3 | Orphan 제안 자동 삭제/전이 | append-only + 상태 머신 보호 |
| 4 | Orphan 판정이 실행 흐름 차단 | orphan = 경고, 차단 아님 |
| 5 | _proposals 직접 접근 | get_proposals() 공개 API만 사용 |

---

## 7. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| AXIS 1: Orphan 탐지 정확성 | 4 | 정상 lineage = orphan 아님, 끊긴 lineage = orphan |
| AXIS 2: 교차 Ledger 검증 | 4 | Exec→Agent 검증, Submit→Exec 검증 |
| AXIS 3: 빈 Ledger 처리 | 3 | 일부/전부 None인 경우 fail-safe |
| AXIS 4: read-only 보장 | 3 | write 메서드 미호출 (소스 스캔) |
| AXIS 5: 4-Tier Board 연결 | 3 | orphan 결과가 대시보드에 포함 |
| AXIS 6: 경계 케이스 | 3 | 중복 ID, 빈 proposals, terminal orphan |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | 467 (현재 기준) |
| Full Suite | PASS 필수 (기존 실패 제외) |

---

## 8. 출력 형식

| # | 산출물 | 형식 |
|---|--------|------|
| 1 | 변경 보고서 | DOC-L2-HARNESS §4.3 형식 (5개 고정 섹션) |
| 2 | tests/test_orphan_detection.py | 최소 20개 테스트, 6축 |
| 3 | 전체 스위트 결과 | PASS 수 / FAIL 수 |

---

## 9. Claude Code C 검수 중점

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | Ledger 내부 파일(3개) 변경 여부 | 금지 조항 최우선 검증 |
| 2 | _proposals 직접 접근 여부 | 공개 API(get_proposals) 만 사용해야 함 |
| 3 | write 메서드 호출 여부 | read-only 원칙 |
| 4 | Orphan 판정이 실행 흐름에 영향 주는지 | 경고 전용 |
| 5 | 교차 검증 로직의 정확성 | False positive/negative 확인 |

---

## 10. 설계 가이드 (Claude Code B 참고용)

### Orphan 정의

```
Tier 1 (Agent):     교차 검증 없음 (최상위 Ledger)
Tier 2 (Execution): agent_proposal_id가 ActionLedger에 없으면 orphan
Tier 3 (Submit):    execution_proposal_id가 ExecutionLedger에 없으면 orphan
```

### 구현 위치

```
app/services/orphan_detection_service.py (NEW)
  - detect_orphans(action_ledger, execution_ledger, submit_ledger) -> OrphanReport
  - 읽기 전용: get_proposals()만 호출
  - Ledger가 None이면 해당 tier 검증 skip
```

### 4-Tier Board 연결

```
four_tier_board_service.py에서 orphan_detection_service 호출
→ TierSummary에 cross_tier_orphan_count 필드 추가
→ 기존 orphan_count (pending 카운트)와 분리 유지
```

---

> Contract version: 1.0
> Source: DOC-L2-HARNESS (claude-code-harness-constitution.md)
> Level: C (고위험 — 교차 Ledger 접근)
