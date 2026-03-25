# Tab 2 전체 구조 최종 정리본

---

## 1. Tab 2 전체 목적

Tab 2는 운영자가 현재 시스템 상태를 **"운영 맥락 + 관측 결과"** 관점에서 읽는 탭이다.

- 상단: 기존 Operator + AI Workspace (I-series 관측 + AI 분석)
- 중하단: **Operational Context Stack** (B-17~B-19)
- 하단: **Observation Layer** (B-20~B-22)

Tab 2는 **read-only 운영 가시화 계층**이다.
추천/예측/AI 판단/새 계산/실행 지시 생성을 **하지 않는다**.

---

## 2. 전체 구조

```
Tab 2: Operator + AI Workspace
│
├── [기존] Operator Workspace (좌)
│   Key Facts, Loop Ceiling, Quote Feed, Venue Status,
│   Freshness Timeline, Source Provenance, Triage Checklist,
│   Handoff Receipt, Incident Chronology, Receipt Review,
│   Flow Log, Audit Replay, Event Log, Checkpoints
│
├── [기존] AI Assist Workspace (우)
│   Confirmed Facts, Detected Anomalies, Possible Causes,
│   Risk Warnings, Recommended Checks, Immediate Actions
│
├── Operational Context Stack (B-17 ~ B-19)
│   ├── B-17 Exchange Environment Analysis
│   ├── B-18 Strategy Context
│   └── B-19 Execution Pipeline
│
├── Observation Layer (B-20 ~ B-22)
│   ├── B-20 Unified Timeline
│   ├── B-21 Risk Monitor
│   └── B-22 Scenario Viewer
│
└── Recent Key Events
```

---

## 3. 계층 정의

### Operational Context Stack (B-17 ~ B-19)

> 현재 시스템을 **어떤 맥락에서 읽어야 하는가**를 보여주는 상단 계층.

- B-17: 거래소 환경은 어떤가
- B-18: 신호/리스크/실행 가능성은 어떤가
- B-19: 실행 경로의 어디까지 진행되었는가

**성격**: 운영 맥락 구조화. 판단 수행 없음.

### Observation Layer (B-20 ~ B-22)

> 현재 상태를 기존 값 기준으로 **어떻게 관측하고 비교하는가**를 보여주는 하단 계층.

- B-20: 언제 무엇이 발생했는가 (시간축)
- B-21: 리스크 수치는 어떤가 (기존 값 스냅샷)
- B-22: 각 조건까지 거리는 어떤가 (조건 비교)

**성격**: 기존 값 기반 관측. 예측/추천 없음.

---

## 4. 카드별 역할 정의

### B-17 Exchange Environment Analysis

| 항목 | 내용 |
|------|------|
| 목적 | 거래소별 운영 환경 프로필 비교 |
| 질문 | 각 거래소의 유형·연결·품질·기능 지원은? |
| 역할 | 5거래소 프로필 카드 그리드 + 유형 요약 바 |
| 성격 | read-only, data/v2 기반, EX_META 상수 활용 |

### B-18 Strategy Context

| 항목 | 내용 |
|------|------|
| 목적 | 전략 파이프라인 상태·포지션 노출·실행 가능성 표시 |
| 질문 | 신호 파이프라인은? 포지션 노출은? 실행 가능한 상태인가? |
| 역할 | Signal Pipeline + Exposure Overview + Execution Readiness 3-column |
| 성격 | badge + count + list only, 설명 문장 금지, AI 추론 금지 |

### B-19 Execution Pipeline

| 항목 | 내용 |
|------|------|
| 목적 | 실행 파이프라인 6단계 흐름 상태 표시 |
| 질문 | 현재 실행 흐름에서 **어디가 막혔는가**? |
| 역할 | I-03→I-04→I-05→I-06→I-07→E-02 수평 흐름도 + 차단 지점 |
| 성격 | pipeline blockage 관측. 실행 트리거 금지. |

### B-20 Unified Timeline

| 항목 | 내용 |
|------|------|
| 목적 | 4소스 (EVENT/SIGNAL/FRESHNESS/VIOLATION) 시간순 통합 |
| 질문 | 언제 무엇이 발생했는가? |
| 역할 | 통합 타임라인 리스트 + 카테고리 필터 |
| 성격 | 시간순 병합, JS class toggle 필터, 원본 데이터 그대로 표시 |

### B-21 Risk Monitor

| 항목 | 내용 |
|------|------|
| 목적 | 리스크 관련 기존 수치를 4-panel 스냅샷으로 표시 |
| 질문 | 리스크 수치는 어떤가? |
| 역할 | Ops Score Summary / Governance Snapshot / Signal Quality / Dual Lock Snapshot |
| 성격 | **기존 값 표시만. 새 점수 계산 완전 금지.** |

### B-22 Scenario Viewer (State Comparison)

| 항목 | 내용 |
|------|------|
| 목적 | 사전 정의된 목표 상태와 현재 상태의 조건 차이를 비교 표시 |
| 질문 | 사전 정의된 목표 상태 기준으로 **무엇이 아직 부족한가**? |
| 역할 | Condition Gap Table (7조건 현재값 vs 필요값) + Readiness Progress (N/7) |
| 성격 | read-only condition comparison. 예측/추천/AI 판단 금지. |
| 공식 정의 | B-22 Scenario Viewer는 기존 data/v2 값만 사용하여, 사전 정의된 목표 상태와 현재 상태의 조건 차이를 read-only로 비교 표시하는 Observation 패널이다. |
| 금지선 | 추천, 예측, AI 판단, 신규 점수, 파생 지표, 성공/승인/거래 가능성 추정, next-step 자동 제안, 우선순위 재계산, 리스크 재해석, 미래 시뮬레이션 |

#### B-22 용어 정의

| 용어 | 의미 | **아닌 것** |
|------|------|-----------|
| scenario | 목표 상태 기준 현재 상태 비교 | 미래 예측 |
| gap | 조건 충족 여부 표시 | 예측 거리/확률 |
| readiness progress | 전체 조건 대비 충족 조건의 단순 비율 | 확률/승인 가능성/거래 가능성 |

---

## 5. B-19 / B-22 차이

| | B-19 Execution Pipeline | B-22 Scenario Viewer |
|---|---|---|
| 질문 | 현재 실행 흐름에서 어디가 막혔는가 | 기준 상태 대비 무엇이 아직 부족한가 |
| 관점 | **pipeline blockage** 관측 | **condition comparison** 관측 |
| 표시 | 6단계 순차 흐름도 + 차단 지점 | 7조건 현재값 vs 필요값 테이블 + N/7 바 |
| 예측 기능 | **없음** | **없음** |
| 둘 다 | 기존 data/v2 값만 사용하며, 미래 상태를 추정하지 않음 |

---

## 6. Tab 2 내부 역할 분리 요약표

| 구역 | 카드 | 핵심 질문 | 역할 |
|------|------|----------|------|
| Operational Context Stack | B-17 | 거래소 환경은? | 환경 프로필 비교 |
| | B-18 | 신호/리스크는? | 전략 컨텍스트 표시 |
| | B-19 | 실행 경로 어디까지? | 파이프라인 차단 관측 |
| Observation Layer | B-20 | 언제 무엇이? | 시간축 통합 |
| | B-21 | 리스크 수치는? | 기존 값 스냅샷 |
| | B-22 | 조건까지 거리는? | 조건 비교 표시 |

---

## 7. Tab 2 최종 완성 상태

| 카드 | 상태 |
|------|------|
| B-17 Exchange Environment | **DONE** |
| B-18 Strategy Context | **DONE** |
| B-19 Execution Pipeline | **DONE** |
| B-20 Unified Timeline | **DONE** |
| B-21 Risk Monitor | **DONE** |
| B-22 Scenario Viewer | **DONE** |

| 계층 | 상태 |
|------|------|
| Operational Context Stack | **COMPLETE** |
| Observation Layer | **COMPLETE** |
| **Tab 2 전체 구조** | **COMPLETE** |

---

## 8. Tab 2 공통 규칙

- 전체 read-only
- data/v2 단일 payload 기반
- 신규 endpoint 없음
- backend 변경 없음
- 추천/예측/AI 판단 금지
- 새 점수 계산 금지
- 실행/주문/승인/트리거 금지
- Observation Layer 공통 badge 색: EVENT(neutral) / SIGNAL(blue) / FRESHNESS(amber) / VIOLATION(red)
- Fallback Reason Registry 준수: NULL_FROM_API / NO_DATA / DISCONNECTED / KEY_ABSENT / QUERY_FAILED

---

---

## 9. B-23 Ops Summary Panel (STEP 1~3 추가)

B-23은 Tab 2 상단에 ops-safety-summary endpoint의 확장 필드를 8-cell 바로 표시하는 요약 패널이다.

| 필드 | 소스 | 새 계산 |
|------|------|--------|
| PIPELINE | pipeline_state (첫 차단 단계) | 기존 값 비교만 |
| CHECK | check_grade | 읽기만 |
| PREFLIGHT | preflight_decision | 읽기만 |
| GATE | gate_decision | 읽기만 |
| APPROVAL | approval_decision | 읽기만 |
| POLICY | policy_decision | 읽기만 |
| SCORE | ops_score | 읽기만 |
| CONDITIONS | conditions_met | 읽기만 |

---

## 10. Tab 2 Freeze 규칙

### 변경 규칙
- Tab 2 구조 변경 시 반드시 카드 발행 필요
- 기존 B-17~B-23 패널 삭제/이름 변경 금지
- 기존 ID rename 금지

### 수정 절차
1. 카드 발행 (implementation_cards.md)
2. 설계 정의본 제출
3. GO 승인
4. 구현
5. 헌법 조항 대조 검수본 제출
6. PASS 판정

### 금지 범위 (영구)
- 추천/예측/AI 판단 금지
- 새 점수 계산 금지
- 실행/주문/승인 트리거 금지
- backend 변경 없이 Tab 2 동작 변경 금지
- tab2_structure_seal.md 위반 금지

### 검수 규칙
- 모든 Tab 2 변경은 Dashboard 테스트 243+ passed 유지
- B-14 테스트 57 passed 유지
- B-23 테스트 14 passed 유지
- 전체 테스트 기준선: **314+**

---

## 11. Tab 2 Constitution Check 결과

| 항목 | 결과 |
|------|------|
| read-only 유지 | ✓ |
| B-22 정의 유지 | ✓ |
| 새 계산 없음 | ✓ (pipeline_state는 boolean 비교만) |
| 추천 없음 | ✓ |
| 예측 없음 | ✓ |
| 전체 테스트 | **1867 passed** (12 failed = 기존 Celery, Tab 2 무관) |
| 기준선 테스트 | **314 passed** (Dashboard 243 + B-14 57 + B-23 14) |

---

*문서 확정 시각: 2026-03-26*
*STEP 1~7 완료*
*코드 수정: STEP 1 (schema 확장) + STEP 2 (HTML/JS/CSS append) + STEP 3 (테스트 14건)*
*이 문서는 Tab 2 구조 기준선 확정 문서이다.*
