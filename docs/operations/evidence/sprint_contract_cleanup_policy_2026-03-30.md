# Sprint Contract Card — CARD-2026-0330-CLEANUP

> **작성자**: Claude Code A
> **날짜**: 2026-03-30
> **등급**: Level C (고위험 — 상태 머신 관련, Ledger 내부 정책 추가)
> **상태**: ACTIVE

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | AB-01~06, EB-01~07, SB-01~08 (Ledger 봉인 3종) |
| 선행 작업 | Dashboard 4-Tier Board (COMPLETE), OrderExecutor (COMPLETE) |

---

## 1. 작업명

> Orphan/Stale Cleanup Policy — 3개 Ledger의 비종료(non-terminal) 제안에 대한 시간 기반 만료 정책 및 대시보드 경고 연결

---

## 2. 목표

현재 3개 Ledger(ActionLedger, ExecutionLedger, SubmitLedger)의 GUARDED 상태 제안은 receipt 또는 failure가 기록되지 않으면 **영원히 GUARDED로 남는다**. 이를 해결하기 위해:

1. **Stale 정의**: GUARDED 상태에서 N분 이상 경과한 제안을 STALE로 표시
2. **Stale 탐지**: 시간 기반 staleness 판정 메서드 추가 (읽기 전용 판정)
3. **Dashboard 경고**: 4-Tier Board에 stale_count 노출 + 경고 임계값
4. **Terminal 보존**: BLOCKED/RECEIPTED/FAILED는 절대 건드리지 않음

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 | 보호 여부 |
|---|--------------|----------|----------|
| 1 | `app/agents/action_ledger.py` | MODIFY — stale 판정 메서드 추가 | YES (봉인 AB-*) |
| 2 | `app/services/execution_ledger.py` | MODIFY — stale 판정 메서드 추가 | YES (봉인 EB-*) |
| 3 | `app/services/submit_ledger.py` | MODIFY — stale 판정 메서드 추가 | YES (봉인 SB-*) |
| 4 | `app/schemas/four_tier_board_schema.py` | MODIFY — stale_count 필드 추가 | NO |
| 5 | `app/services/four_tier_board_service.py` | MODIFY — stale 집계 추가 | NO |
| 6 | `tests/test_cleanup_policy.py` | NEW — Cleanup Policy 전용 테스트 | NO |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | 상태 머신 _TRANSITIONS 구조 | 봉인 보호. 새로운 상태(STALE)를 상태 머신에 추가하지 않는다 |
| 2 | propose_and_guard() 로직 | 기존 가드 체크 변경 금지 |
| 3 | record_receipt() 로직 | 기존 receipt 경로 변경 금지 |
| 4 | record_failure() 로직 | 기존 failure 경로 변경 금지 |
| 5 | transition_to() 메서드 | 상태 전이 규칙 변경 금지 |
| 6 | GovernanceGate | 이 작업과 무관 |
| 7 | OrderExecutor | 이 작업과 무관 |
| 8 | Terminal 상태 제안 | BLOCKED/RECEIPTED/FAILED 제안을 삭제하거나 변경하지 않는다 |
| 9 | flush_to_file() | 기존 flush 메커니즘 변경 금지 |

> **핵심 금지**: STALE은 **상태 머신의 새로운 state가 아니다**. 별도의 판정 레이어(is_stale 프로퍼티 또는 메서드)로 구현한다. _TRANSITIONS에 "STALE"을 추가하면 안 된다.

---

## 5. 완료 기준

- [ ] 3개 Ledger 모두에 stale 판정 메서드 추가
- [ ] GUARDED 상태 + 경과 시간 > threshold = stale 판정
- [ ] Terminal 상태(BLOCKED/RECEIPTED/FAILED)는 절대 stale 판정되지 않음
- [ ] 상태 머신 _TRANSITIONS 변경 없음 (소스 스캔 검증)
- [ ] get_board()에 stale_count 추가
- [ ] 4-Tier Board에 stale_count 노출
- [ ] 전용 테스트 최소 20개, 6축 이상
- [ ] 기존 Control Total (222개) 회귀 0
- [ ] 전체 스위트 회귀 0 (기존 실패 제외)
- [ ] 봉인 위반 0

---

## 6. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | _TRANSITIONS에 "STALE" 상태 추가 | 상태 머신 봉인 보호 |
| 2 | GUARDED 제안을 자동 삭제 | append-only 원칙 위반 |
| 3 | GUARDED 제안을 BLOCKED/FAILED로 자동 전이 | 자동 상태 변경은 봉인 위반 |
| 4 | Terminal 상태 제안의 stale 판정 | BLOCKED/RECEIPTED/FAILED는 이미 종료됨 |
| 5 | stale 판정이 실행 흐름을 차단 | stale은 경고 표시이지 실행 차단이 아님 |
| 6 | 제안의 created_at 필드 변경 | 불변 이력 보호 |
| 7 | _proposals 리스트에서 항목 제거 | append-only 원칙 |

---

## 7. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| AXIS 1: Stale 판정 | 4 | threshold 이하 = not stale, 초과 = stale, 경계값 |
| AXIS 2: Terminal 보호 | 4 | BLOCKED/RECEIPTED/FAILED는 stale 판정 안 됨 |
| AXIS 3: Board 집계 | 3 | get_board()의 stale_count 정확성 |
| AXIS 4: 상태 머신 보존 | 3 | _TRANSITIONS 미변경, STALE 상태 없음 (소스 스캔) |
| AXIS 5: 4-Tier Board 연결 | 3 | stale_count가 대시보드 응답에 포함 |
| AXIS 6: 3개 Ledger 일관성 | 3 | Action/Execution/Submit 모두 동일 패턴 |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | 222 (현재 기준) |
| Full Suite | PASS 필수 (기존 실패 제외) |

---

## 8. 출력 형식

Claude Code B가 제출해야 할 산출물:

| # | 산출물 | 형식 |
|---|--------|------|
| 1 | 변경 보고서 | DOC-L2-HARNESS §4.3 형식 (5개 고정 섹션) |
| 2 | tests/test_cleanup_policy.py | 최소 20개 테스트, 6축 |
| 3 | 전체 스위트 결과 | PASS 수 / FAIL 수 |

---

## 9. Claude Code C 검수 중점

Claude Code C가 특히 확인해야 할 사항:

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | _TRANSITIONS에 STALE이 추가되지 않았는가 | 봉인 보호 최우선 |
| 2 | Terminal 상태가 stale로 판정되는 경로가 없는가 | terminal 불가침 |
| 3 | propose_and_guard/record_receipt/record_failure가 변경되지 않았는가 | 봉인 보호 |
| 4 | append-only 원칙이 유지되는가 (삭제/제거 메서드 없음) | 이력 보존 |
| 5 | stale 판정이 실행 흐름을 차단하지 않는가 | stale = 경고, 차단 아님 |
| 6 | 3개 Ledger 모두 동일 패턴으로 구현되었는가 | 일관성 |

---

## 10. 등급별 특기 사항

### Level C 전용

- Claude Code C **강검수** 필수 (평가표 필수, 봉인 대조 필수)
- 재작업 루프 최대 3회
- 인간 최종 승인 필수
- 소스 스캔으로 _TRANSITIONS 미변경 검증 필수

---

## 11. 설계 가이드 (Claude Code B 참고용)

> 아래는 방향성만 제시한다. 구체적 구현 방법은 Claude Code B가 결정한다.

### 핵심 설계 방향

**STALE은 상태가 아니라 판정이다.**

```
# 개념 (의사 코드)
proposal.status       # "GUARDED" (상태 머신 — 변경 없음)
proposal.is_stale     # True/False (시간 기반 판정 — 새로 추가)
```

### 가능한 접근법

1. **Proposal 클래스에 is_stale 프로퍼티 추가**: created_at과 현재 시각을 비교하여 판정
2. **Ledger 클래스에 stale 판정 메서드 추가**: 외부에서 threshold를 주입받아 판정
3. **get_board()에 stale_count 추가**: 기존 orphan_count 옆에 병렬 추가

### Stale Threshold 기본값

- 구체적 값은 Claude Code B가 결정
- 권장 범위: 5~30분
- 설정 가능(configurable)하면 좋지만 필수는 아님

---

> Contract version: 1.0
> Source: DOC-L2-HARNESS (claude-code-harness-constitution.md)
> Level: C (고위험 — Ledger 내부 변경)
