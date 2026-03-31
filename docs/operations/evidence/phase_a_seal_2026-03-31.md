# Phase A Seal — 기준선 무경고화 + 계약 typed 강화 + 운영 관찰 카드

Sealed: 2026-03-31
Full Suite: **2845 PASS / 0 FAIL / 0 WARNING**
Cycles: 13 (10 original + A-1/A-2/A-3)
New Tests: 405

---

## 1. Phase A 변경 요약

| Phase | 목표 | 핵심 변경 | Tests |
|-------|------|----------|-------|
| A-1 | Pydantic deprecation warning 제거 | `o.model_fields` → `OpsSummary.model_fields` (인스턴스→클래스) | 0 (fix) |
| A-2 | observation_summary typed schema | `ObservationSummarySchema` 도입, board `dict` → typed | 43 |
| A-3 | REVIEW volume 운영 관찰 카드 | `ReviewVolumeSchema` + board 통합 | 46 |

---

## 2. 파일별 반영 내용

### A-1: Warning Zero

| 파일 | 변경 |
|------|------|
| `tests/test_ai_assist_source.py` | Line 37: 인스턴스→클래스 model_fields 접근 |

### A-2: Observation Summary Typed Schema

| 파일 | 변경 |
|------|------|
| `app/schemas/observation_summary_schema.py` | **신규** — ObservationSummarySchema, ObservationSafety, ReasonActionEntry, TopPriorityCandidate |
| `app/services/observation_summary_service.py` | `to_schema()` 메서드 추가 |
| `app/schemas/four_tier_board_schema.py` | `observation_summary: dict` → `ObservationSummarySchema` |
| `app/services/four_tier_board_service.py` | `.to_dict()` → `.to_schema()` |
| `tests/test_observation_summary.py` | 3개 테스트 dict→attribute 접근 수정 |
| `tests/test_observation_summary_schema.py` | **신규** — 43 tests, 7 axes |

### A-3: REVIEW Volume + Board Integration

| 파일 | 변경 |
|------|------|
| `app/schemas/review_volume_schema.py` | **신규** — ReviewVolumeSchema, TierDistribution, ReasonDistribution, BandDistribution, DensitySignal, ReviewVolumeSafety |
| `app/services/review_volume_service.py` | **신규** — build_review_volume(), _build_density_signal() |
| `app/schemas/four_tier_board_schema.py` | `review_volume: ReviewVolumeSchema` 필드 추가 |
| `app/services/four_tier_board_service.py` | `build_review_volume()` 호출 + board 응답 연결 |
| `tests/test_review_volume.py` | **신규** — 46 tests, 8 axes |

---

## 3. Board Contract 변화 전/후

### FourTierBoardResponse 필드 변화

| 필드 | Before | After |
|------|--------|-------|
| `observation_summary` | `dict` | `ObservationSummarySchema` |
| `review_volume` | (없음) | `ReviewVolumeSchema` |
| `decision_summary` | `DecisionSummarySchema` | (변경 없음) |
| `decision_card` | `Optional[DecisionCard]` | (변경 없음) |

### 외부 계약 경로

| Layer | Dataclass→Board 경로 | 방식 |
|-------|---------------------|------|
| L4 Observation | `ObservationSummary.to_schema()` → board | typed schema |
| L5 Decision | `DecisionSummary.to_schema()` → board | typed schema |
| L6 Decision Card | `build_decision_card()` → board | typed schema |
| REVIEW Volume | `build_review_volume()` → board | typed schema (direct) |

---

## 4. Safety Invariant 유지 증거

### Safety 모델 현황 (Phase A 종료 시점)

| 모델 | 필드 | 값 |
|------|------|-----|
| `DecisionSafety` | action_allowed, suggestion_only, read_only | False, True, True |
| `ObservationSafety` | read_only, simulation_only, no_action_executed, no_prediction | True, True, True, True |
| `ReviewVolumeSafety` | read_only, simulation_only, no_action_executed, no_prediction | True, True, True, True |
| `SafetyBar` | action_allowed, suggestion_only, read_only | False, True, True |

### 금지 키워드 검증 (소스 코드)

모든 서비스 소스에서 다음 키워드 부재 확인:
- `propose_and_guard` / `record_receipt` / `transition_to` / `.delete(` / `.write(`

---

## 5. 금지 항목 위반 없음 확인

| 금지 항목 | A-1 | A-2 | A-3 |
|-----------|-----|-----|-----|
| sealed 계층 변경 | 없음 | 없음 | 없음 |
| action_allowed=True | 없음 | 없음 | 없음 |
| write path 추가 | 없음 | 없음 | 없음 |
| 예측/추천/자동판단 | 없음 | 없음 | 없음 |
| threshold 값 변경 | 없음 | 없음 | 없음 |
| 신규 회귀 | 0 | 0 | 0 |

---

## 6. `to_dict()` 잔존 경로 분석

### 분류

| 분류 | 파일 수 | 설명 |
|------|---------|------|
| **Sealed Ledger 내부** | 3 | action_ledger, execution_ledger, submit_ledger — Proposal.to_dict() |
| **Orchestrator 내부** | 1 | orchestrator.py — proposal 직렬화 |
| **Simulation/Orphan 내부** | 2 | cleanup_simulation, orphan_detection — candidate/entry 직렬화 |
| **Notification/Retry 내부** | 4 | notification_flow, receipt_store, retry_plan_store — 내부 데이터 직렬화 |
| **API Route** | 1 | agents.py — report.to_dict() |
| **Governance** | 1 | governance_monitor_tasks — report.to_dict() |
| **Order Executor** | 1 | order_executor — result 직렬화 |
| **Tests** | 17 | backward compatibility 테스트 |

### 퇴역 판정

| 경로 | 판정 | 이유 |
|------|------|------|
| Sealed Ledger 내부 | **보류 (건드리지 않음)** | sealed 계층 — 수정 금지 |
| Orchestrator/API | **보류** | 외부 인터페이스 — 별도 typed 전환 카드 필요 |
| Simulation/Orphan 내부 | **보류** | 내부 데이터 구조 — 현재 정상 동작 |
| Notification/Retry | **보류** | 별도 도메인 — Phase A 범위 외 |
| Observation `to_dict()` | **퇴역 준비 완료** | `to_schema()` 병행, 외부 경로는 이미 schema |
| Decision `to_dict()` | **퇴역 준비 완료** | `to_schema()` 병행, 외부 경로는 이미 schema |
| Tests (17건) | **유지** | backward compatibility 검증 용도 |

### 퇴역 규칙

- **신규 코드에서 to_dict() 사용 금지**
- 외부 board/API 경로: `to_schema()` only
- Observation/Decision dataclass의 `to_dict()`는 후속 카드에서 제거 가능
- Sealed Ledger의 `to_dict()`는 절대 수정 금지

---

## 7. 미해결 리스크

| 리스크 | 심각도 | 대응 |
|--------|--------|------|
| `to_dict()` 잔존 → 향후 dict 소비 경로 재유입 | 낮음 | 신규 금지 규칙으로 통제 |
| density description drift | 낮음 | 템플릿 4패턴 잠금 권고 (후속) |
| `>66%` concentration 기준 미문서화 | 낮음 | 후속 운영 규약에 포함 |
| safety 라벨 불균일 (레이어마다 필드셋 다름) | 중간 | 3단계 통일 작업 필요 |

---

## 8. 다음 Phase 착수 조건

### 허용 범위

- 관찰 카드 간 safety 라벨 통일
- description 템플릿 잠금
- `to_dict()` 점진적 퇴역 (Observation/Decision만)
- board schema 정리/일관성 검증
- 신규 read-only 관찰 카드 추가 (typed schema 의무)

### 금지 범위

- sealed 계층 수정
- action_allowed=True 설정
- write path 추가
- 예측/추천/자동판단 도입
- to_dict() 신규 사용
- description에 명령형/action verb 사용

---

## 헌법 조항 대조

| 조항 | 요구 | 충족 |
|------|------|------|
| warning 0 | Full Suite 무경고 | 2845 PASS / 0 WARNING |
| typed schema | observation_summary typed 강화 | ObservationSummarySchema 도입 |
| REVIEW 관찰 | read-only 사실 기반 | ReviewVolumeSchema + no_prediction |
| board 통합 | 응답 계약에 편입 | 두 schema 모두 board에 연결 |
| safety 유지 | 모든 safety 라벨 True | 4개 Safety 모델 모두 검증 |
| 봉인 보존 | sealed 계층 무변경 | 변경 0건 |
| 회귀 없음 | Full Suite 통과 | 2845 PASS / 0 FAIL |

---

> Phase A sealed: 2026-03-31
> 13 cycles, 405 new tests, ALL GO
> 2845 PASS / 0 FAIL / 0 WARNING
