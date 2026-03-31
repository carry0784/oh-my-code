# Sprint Contract Card — CARD-2026-0330-BOARD-OBS-UPGRADE

> **작성자**: Claude Code A
> **날짜**: 2026-03-30
> **등급**: Level B (중위험 — 스키마 확장, 신규 서비스, Dashboard 연동)
> **상태**: ACTIVE

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | AB-01~06, EB-01~07, SB-01~08 (Ledger 봉인 3종) |
| 선행 작업 | Cleanup Policy (C-GO), Orphan Detection (C-GO), Cleanup Simulation (C-GO) |

---

## 1. 작업명

> Dashboard Observation Upgrade — 관측 스택 결과를 우선순위화/압력지표화/요약하여 운영 해석력 향상

---

## 2. 목표

현재 4-Tier Board에는 stale/orphan/cleanup simulation 결과가 **개별 수치**로만 존재한다. 운영자가 "지금 어느 정도 압력인지, 어디를 먼저 봐야 하는지" 한눈에 판단하기 어렵다.

1. **Cleanup Pressure**: 단일 체감 레벨 (LOW / MODERATE / HIGH / CRITICAL)
2. **Observation Summary**: 관측 스택 전체를 1개 구조로 압축
3. **By-Reason × By-Action 교차 요약**: 원인별 행동등급 분포
4. **Read-Only 관측 경계 유지**: simulation only / no action executed 고정

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 |
|---|--------------|----------|
| 1 | `app/services/observation_summary_service.py` | NEW — 관측 요약 서비스 |
| 2 | `app/schemas/four_tier_board_schema.py` | MODIFY — observation summary 필드 추가 |
| 3 | `app/services/four_tier_board_service.py` | MODIFY — observation summary 연결 |
| 4 | `tests/test_observation_summary.py` | NEW — 전용 테스트 |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | `app/agents/action_ledger.py` | 봉인 보호 |
| 2 | `app/services/execution_ledger.py` | 봉인 보호 |
| 3 | `app/services/submit_ledger.py` | 봉인 보호 |
| 4 | `app/services/orphan_detection_service.py` | 이전 완료 작업 보호 |
| 5 | `app/services/cleanup_simulation_service.py` | 이전 완료 작업 보호 |
| 6 | _TRANSITIONS 구조 (3개 Ledger 모두) | 상태 머신 봉인 보호 |
| 7 | propose_and_guard / record_receipt / record_failure | 핵심 경로 변경 금지 |

---

## 5. 설계 가이드

### Cleanup Pressure 레벨

```
LOW      — candidates == 0 또는 전부 WATCH
MODERATE — REVIEW 존재, MANUAL 없음
HIGH     — MANUAL 존재, 비율 < 50%
CRITICAL — MANUAL 비율 >= 50% 또는 total_candidates >= 10
```

### ObservationSummary 구조

```python
@dataclass
class ObservationSummary:
    # -- Pressure --
    cleanup_pressure: str             # "LOW" | "MODERATE" | "HIGH" | "CRITICAL"

    # -- Counts --
    stale_total: int                  # 전 tier stale 합계
    orphan_total: int                 # cross-tier orphan 합계
    candidate_total: int              # cleanup candidate 합계

    # -- By-tier stale distribution --
    stale_by_tier: dict[str, int]     # {"agent": 2, "execution": 1, "submit": 0}

    # -- By-reason × by-action cross table --
    reason_action_matrix: list[dict]  # [{"reason": "STALE_AGENT", "action": "WATCH", "count": 2}, ...]

    # -- Top priority items --
    top_priority_candidates: list[dict]  # 최대 5개, MANUAL 우선 → REVIEW 우선

    # -- Safety labels --
    read_only: bool = True            # Always True
    simulation_only: bool = True      # Always True
    no_action_executed: bool = True   # Always True
```

### 데이터 수집 방법

```
1. simulate_cleanup() 결과 → candidates, by_action_class, by_reason
2. detect_orphans() 결과 → orphan_total
3. 각 Ledger get_board() → stale_count per tier
4. 위 데이터로 pressure 결정 + summary 생성
```

### Dashboard 연결

```
FourTierBoardResponse에 추가:
  observation_summary: dict = {}   # ObservationSummary.to_dict()
```

### Top Priority 정렬 기준

```
1순위: action_class == MANUAL_CLEANUP_CANDIDATE
2순위: action_class == REVIEW
3순위: stale_age_seconds (높을수록 우선)
최대 5개
```

---

## 6. 완료 기준

- [ ] observation_summary_service.py 생성 — 읽기 전용
- [ ] Cleanup Pressure 4단계 결정 로직
- [ ] reason × action 교차 요약
- [ ] stale_by_tier 분포
- [ ] top_priority_candidates (최대 5개)
- [ ] read_only / simulation_only / no_action_executed 항상 True
- [ ] 4-Tier Board에 observation_summary 연동
- [ ] Ledger/orphan/cleanup 기존 파일 변경 없음
- [ ] 전용 테스트 최소 25개, 7축 이상
- [ ] 기존 Control Total (323개) 회귀 0
- [ ] 봉인 위반 0

---

## 7. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | Ledger 내부 코드 수정 | 봉인 보호 |
| 2 | orphan_detection_service.py 수정 | 이전 완료 작업 보호 |
| 3 | cleanup_simulation_service.py 수정 | 이전 완료 작업 보호 |
| 4 | write 메서드 호출 | read-only 원칙 |
| 5 | 실행 버튼/자동 cleanup 암시 | simulation only 경계 |
| 6 | 상태 전이 유도 표현 | 관측 전용 |

---

## 8. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| AXIS 1: Pressure 결정 정확성 | 5 | LOW/MODERATE/HIGH/CRITICAL 경계값 |
| AXIS 2: Stale 분포 정확성 | 3 | stale_by_tier 집계 |
| AXIS 3: Reason×Action 교차표 | 4 | matrix 구조, 합산 일치 |
| AXIS 4: Top Priority 정렬 | 3 | MANUAL 우선, REVIEW 우선, 최대 5개 |
| AXIS 5: Safety Labels 보장 | 3 | read_only/simulation_only/no_action_executed |
| AXIS 6: Dashboard 연동 | 3 | observation_summary in board |
| AXIS 7: Edge Cases | 4+ | 빈 데이터, 전부 정상, 단일 tier만, 대량 |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | 323 (현재 기준) |

---

## 9. Claude Code C 검수 중점

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | 기존 파일(5개) 변경 여부 | 금지 조항 최우선 검증 |
| 2 | pressure 결정 로직 정확성 | 운영자 오판 유발 가능성 |
| 3 | safety labels 강제 여부 | 실행 유도 방지 |
| 4 | 실행 암시 표현 유무 | "clean", "execute", "remove" 같은 동사 |
| 5 | reason×action matrix 정합성 | 합산이 total과 일치하는지 |

---

> Contract version: 1.0
> Source: DOC-L2-HARNESS (claude-code-harness-constitution.md)
> Level: B (중위험 — 스키마 확장, 읽기 전용 서비스)
