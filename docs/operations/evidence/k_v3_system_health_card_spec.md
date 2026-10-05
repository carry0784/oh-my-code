# K-V3 Temporary Runtime Confirmation Card Specification (TRCC)

> **발행일**: 2026-04-14 (v3 재설계, 카드/학습층 분리 강화)
> **공식 명칭**: **Temporary Runtime Confirmation Card (TRCC)**
> **상위 헌법**: `k_v3_visualization_layer_governance.md` (VC-01~04)
> **상위 스펙**: `k_v3_dashboard_safe_mode_framework.md`
> **독립 동반 문서**: `k_v3_preeval_learning_ledger_design.md` (PLRAL, 학습층 — 카드와 **분리**)
> **적용 기간**: **2026-04-14 ~ 2026-04-28** (P3 기간 전용)
> **폐기 조건**: 2026-04-28 시점 git rm (흔적은 PLRAL에 남음)
> **후속 산출물**: 04-28 이후 **Detailed Dashboard Visualization** (Card 연속 아님, PLRAL 분석 기반 재설계)
> **구현 방식**: **CLI 스크립트 전용** (uvicorn 금지)

---

## 0. v1 → v2 → v3 재설계 궤적

| 버전 | 핵심 오해/개선 |
|------|---------------|
| v1 | Card를 post-P3 Stage 1 영구 산출물로 봉인 (틀림) |
| v2 | Card를 P3 임시 CLI 도구로 재정의, Learning Ledger 1개 통합 설계 |
| **v3** | **카드/학습층 엄격 분리 강화, 학습층 4 ledger 분리, 2 pack 이원화, Card lifecycle 상태머신 공식화** |

### v3 핵심 원칙 (2개)

1. **카드는 순수 표시기** — 현재 살아있음 확인만. 분석/학습/실행 금지.
2. **학습층은 카드 외부에 존재** — Card 로직에 학습 자료가 내장되지 않음. Card는 DB/Flower를 직접 읽고, 학습층(PLRAL)은 별도 파일로 독립 누적.

---

## 1. 카드 정체성 (v3 재정의)

### 1.1 카드의 역할

> **카드 = 현재 가동 여부를 확인하는 임시 검증용 런타임 센티넬 (Runtime Sentinel)**

- 운영 종결 도구 **아님**
- 상세 진단 도구 **아님**
- 운영 분석기 **아님**
- **단일 목적**: 런타임 생존 표시기

### 1.2 카드의 분리 선언

카드는 다음과 **섞이지 않는다**:

| 층 | 관계 |
|----|------|
| 학습층 (PLRAL) | **독립**. 카드는 PLRAL을 읽지 않음. PLRAL은 카드 실행 이벤트를 기록할 뿐. |
| 운영 판단 | **아래 단계**. 카드는 시작점만 제공, 판단은 B+C로 이관. |
| Dashboard | **후속**. 카드 확장이 아니라 04-28 이후 별개 설계. |
| 거버넌스 엔진 | **무관**. 카드는 GovernanceGate 호출하지 않음. |

### 1.3 카드 vs 학습층 경계 (중요)

```
┌────────────────────────────┐       ┌────────────────────────────┐
│  TRCC (Card)               │       │  PLRAL (Learning Layer)    │
│  scripts/health_check.py   │       │  logs/preeval/*.jsonl      │
├────────────────────────────┤       ├────────────────────────────┤
│  입력: DB + Flower + OS    │       │  입력: Card 실행 결과       │
│  출력: stdout 텍스트 카드   │──기록→│  출력: append-only JSONL   │
│  목적: 현재 가동 표시       │       │  목적: 학습 자료 축적       │
│  수명: ~2026-04-28         │       │  수명: 영구 (freeze 후 분석)│
└────────────────────────────┘       └────────────────────────────┘
       ↓                                    ↓
   04-28 폐기                          04-28 freeze
       ↓                                    ↓
   (흔적 없음)                    ORP + VRP 2 pack 생성
                                          ↓
                                  Detailed Dashboard 설계
```

**불변 규칙**:
- Card → PLRAL: write만 (append)
- PLRAL → Card: **read 금지**
- Card는 항상 stateless (과거 상태 참조 금지)

---

## 2. 카드 Lifecycle 상태머신 (v3 신규)

```
┌──────────┐   사용자 승인    ┌────────────────────┐   2026-04-28   ┌──────────┐
│ PLANNED  │─────────────────→│  ACTIVE_TEMPORARY  │───────────────→│ RETIRED  │
└──────────┘  (설계 봉인만)    └────────────────────┘  (git rm)       └──────────┘
   현재         (scripts 생성)      (실행 허용 기간)      (카드 삭제)     (흔적만)
```

| 상태 | 조건 | 허용 동작 | 파일 존재 |
|------|------|----------|----------|
| `PLANNED` | 설계 봉인 완료, 구현 전 | 문서 갱신만 | `scripts/health_check.py` 없음 |
| `ACTIVE_TEMPORARY` | 사용자 승인 + 파일 생성 | 수동 CLI 실행 허용 | 존재 |
| `RETIRED` | 2026-04-28 도달 | git rm 완료, 흔적만 PLRAL에 | 삭제됨 |

**현재 상태**: `PLANNED`

**상태 전이 규칙**:
- `PLANNED → ACTIVE_TEMPORARY`: 사용자 명시적 승인 필요
- `ACTIVE_TEMPORARY → RETIRED`: 2026-04-28 자동 전이 (수동 git rm 집행)
- 역전이 금지 (RETIRED → ACTIVE_TEMPORARY 절대 불가)

---

## 3. 필드 정의 — 6개 고정 (v3 네이밍 정리)

| # | 필드 (v3) | 이전 (v2) | 원천 | 확인 방법 |
|---|-----------|----------|------|----------|
| 1 | `core_runtime_status` | (합성) | 아래 5개 + 판정 | 종합 판정 결과 |
| 2 | `worker_status` | worker_alive | OS process | psutil.pid_exists + cmdline |
| 3 | `beat_status` | beat_alive | OS process | psutil.pid_exists + cmdline |
| 4 | `db_status` | db_connected | DB | SELECT 1 |
| 5 | `last_observation_age` | last_observation_at | DB | NOW() - MAX(observed_at) (seconds) |
| 6 | `issue_summary` | recent_critical_failure | Flower + logs | 없음/지연/실패/연결문제 |

**변경 이유**: v3는 "상태 판정" 중심 네이밍 (사용자 의도 반영). "현재 몇 초 전 관측" 대신 "몇 초 경과했는가"로 직관성 향상.

---

## 4. 판정 로직 — 3단계 (유지)

### 4.1 `정상가동`
AND: worker_status=정상 ∧ beat_status=정상 ∧ db_status=연결됨 ∧ last_observation_age < 2h ∧ issue_summary=없음

### 4.2 `주의`
프로세스는 살아있으나 OR: (last_observation_age ≥ 2h) ∨ (issue_summary ∈ {지연, 실패})

### 4.3 `점검필요`
OR: db_status=끊김 ∨ worker_status=다운 ∨ beat_status=다운 ∨ last_observation_age ≥ 4h ∨ 판정불가(VC-04)

**우선순위**: 점검필요 > 주의 > 정상가동

---

## 5. CLI 출력 레이아웃 (v3 문구 고정)

```
$ python scripts/health_check.py

┌──────────────────────────────────────────────────┐
│ K-V3 RUNTIME NOW                                 │
│ 2026-04-14T14:05:12Z                             │
├──────────────────────────────────────────────────┤
│ 상태         : 정상가동                            │
│ Worker       : 정상 (PID 88008)                   │
│ Beat         : 정상 (PID 97588)                   │
│ DB           : 연결됨 (localhost:5432)            │
│ 최근 관측 경과: 42s                               │
│ 문제요약     : 없음                                │
├──────────────────────────────────────────────────┤
│ 임시 검증용 카드 / 2026-04-28 이후 폐기           │
│ 상세 분석   : Flower :5555 + DB :5432            │
│ 학습 기록   : logs/preeval/{rhl,dql}.jsonl +1    │
└──────────────────────────────────────────────────┘
```

**하단 3줄 고정 규칙** (v3 신규, 폐기 예정 상시 고지):
- 줄 1: `임시 검증용 카드 / 2026-04-28 이후 폐기` — 카드 영구화 방지
- 줄 2: `상세 분석 : Flower + DB` — 다음 행동 안내
- 줄 3: `학습 기록 : ...` — PLRAL 기록 투명성

**Exit code**:
- 0: 정상가동
- 1: 주의
- 2: 점검필요
- 3: 실행 오류

---

## 6. 카드-학습층 커플링 규칙 (v3 신규)

Card 실행은 **반드시** PLRAL 2개 ledger에 append:

| Ledger | 기록 시점 | 기록 내용 |
|--------|----------|----------|
| RHL (Runtime Health Ledger) | **매 실행마다** | 6필드 + 판정 + PID + 타임스탬프 |
| DQL (Data Quality Ledger) | **매 실행마다** | 관측/이벤트 카운트 + freshness |

Card verdict에 따라 조건부 append:

| 조건 | 추가 Ledger |
|------|------------|
| verdict ∈ {주의, 점검필요} | **IWL (Incident & Warning Ledger)** 1 라인 |
| (항상) | **VRL (Visualization Reference Ledger)** 수동 기록은 Card 실행과 분리 |

**중요**: Card는 PLRAL을 읽지 않음. 오로지 append만. 각 ledger 상세는 `k_v3_preeval_learning_ledger_design.md` 참조.

---

## 7. 금지 조항 (v3 3분류로 재정리)

### 7.1 금지영역 A — 카드 비대화

| # | 금지 | 근거 |
|---|------|------|
| A1 | 6필드 초과 필드 추가 | 카드 범위 |
| A2 | 3판정 외 세분 점수 (confidence score 등) | 과신 유발 |
| A3 | 차트/표/그래프 | 카드 ≠ 대시보드 |
| A4 | 실행버튼/POST/mutation | VC-01 |
| A5 | 상태 전이 승인 버튼 | VC-03 |
| A6 | stale 데이터 정상 표시 | VC-04 |

### 7.2 금지영역 B — 학습-실행 혼합 (v3 신규)

| # | 금지 | 근거 |
|---|------|------|
| B1 | 학습 결과로 임계값 자동 변경 | 검증기간 무결성 |
| B2 | 학습 결과로 runtime state 전이 | P3 비간섭 |
| B3 | 학습 결과로 운영 승인 | VC-03 |
| B4 | Card가 PLRAL을 읽어 판정 변경 | 단방향 커플링 원칙 |
| B5 | PLRAL 분석 결과를 Card 로직에 주입 | 분리 원칙 |

### 7.3 금지영역 C — 검증기간 중 대시보드 과구축 (v3 신규)

| # | 금지 | 근거 |
|---|------|------|
| C1 | Card 외 시각화 신규 개발 | 04-28 이전 대시보드 금지 |
| C2 | Card에 상세 패널 추가하여 대시보드화 | 범위 잠금 |
| C3 | uvicorn 기동 | Option A 6조건 |
| C4 | cron/systemd 자동화 등록 | 상주성 부여 |
| C5 | 기존 app/api/routes/dashboard.py 수정 | P3 비간섭 |

---

## 8. 기동 전 검증 기준 — 6항 (v2 유지)

- [ ] CLI 출력과 DB 직접조회 일치
- [ ] CLI 출력과 Flower 상태 일치
- [ ] stale 상태를 `정상가동`으로 표시하지 않음
- [ ] 실행 기능 전혀 없음
- [ ] 실행 후 프로세스 종료 확인 (ps 결과 잔여 0)
- [ ] PLRAL RHL + DQL에 append 1 라인씩 확인

---

## 9. VC-01~04 준수 매핑

| 헌법 | TRCC 준수 |
|------|----------|
| VC-01 실행권 없음 | subprocess/POST/mutation 없음 |
| VC-02 display/summarize/compare only | stdout 텍스트 6필드 + 판정문만 |
| VC-03 no transition authority | 판정 표시만, 승인권 없음 |
| VC-04 fail closed | 수집 실패 시 `점검필요` 자동 전환 |

---

## 10. 04-28 폐기 절차 (v3 5단계)

### 단계 1 — 검증 창구 종료 확인
- P3 window 종료 (2026-04-28T00:00:00Z)
- VAL-PDC-002 재평가 착수 조건 확인

### 단계 2 — TRCC 상태 전이
- `ACTIVE_TEMPORARY → RETIRED`
- 최종 Card 실행 1회 수행 (마지막 RHL 라인 기록)

### 단계 3 — 물리 삭제
- `git rm scripts/health_check.py`
- commit message: `chore: retire TRCC at end of P3 (2026-04-28)`

### 단계 4 — PLRAL freeze
- 4 ledger 모두 append 중지
- 각 ledger 말미에 `meta.event=frozen` 라인 추가
- read-only chmod 적용 (옵션)

### 단계 5 — 전이 시작
- ORP + VRP 2 pack 생성 (분석 스크립트 실행)
- Detailed Dashboard 설계 라운드 개시
- 상세는 `k_v3_preeval_learning_ledger_design.md` §7 참조

---

## 11. 봉인 선언 (v3)

```
CARD_NAME = Temporary Runtime Confirmation Card (TRCC)
CARD_LIFECYCLE = PLANNED → ACTIVE_TEMPORARY → RETIRED
CARD_CURRENT_STATE = PLANNED (설계 봉인, 구현 전)
CARD_WINDOW = 2026-04-14 ~ 2026-04-28
CARD_INTERFACE = CLI (scripts/health_check.py)
CARD_FIELDS = 6 (v3 네이밍)
CARD_VERDICTS = 3 (정상가동/주의/점검필요)
CARD_DISPOSAL = 2026-04-28 git rm
CARD_SUCCESSOR = Detailed Dashboard Visualization (별개 설계)

SEPARATION_RULE = "카드는 PLRAL을 읽지 않는다"
COUPLING_DIRECTION = Card → PLRAL (write only)
FORBIDDEN_ZONES = 3 (A 카드비대화 / B 학습-실행 혼합 / C 검증기간 대시보드 과구축)
TOTAL_PROHIBITIONS = 16 (A:6 + B:5 + C:5)

LEARNING_LAYER = PLRAL (독립 문서 참조)
LEARNING_LEDGERS = 4 (RHL/IWL/DQL/VRL)
POST_P3_PACKS = 2 (ORP 운영참고팩 / VRP 시각화참고팩)

IMPLEMENTATION = 설계 완료, 실제 파일 생성은 사용자 승인 후
P3_ACTIVE_NON_INTERFERENCE = TRUE (CLI 방식)
production_authorized = FALSE (불변)
OPTION_A_uvicorn = NOT_REQUIRED
```

---

## 12. 원칙 요약 (한 문장)

> **TRCC는 2026-04-14부터 04-28까지 CLI로 "지금 살아있는가"만 표시하는 임시 런타임 센티넬이며, PLRAL(학습층)과 단방향 커플링(write-only)으로 완전 분리되어, 04-28에 물리 삭제되고 후속 Dashboard는 카드의 확장이 아니라 PLRAL 분석 기반으로 전면 재설계된다.**

---

## 13. 참조 문서

| 관계 | 문서 |
|------|------|
| 상위 헌법 | `k_v3_visualization_layer_governance.md` |
| 상위 스펙 | `k_v3_dashboard_safe_mode_framework.md` |
| **독립 동반 (학습층)** | `k_v3_preeval_learning_ledger_design.md` (PLRAL 4 ledger + 2 pack + 전이 5단계) |
| 통합점검 | `k_v3_integrated_inspection_report.md` |
| 구현 위치 (미생성) | `scripts/health_check.py` |
| PLRAL 데이터 경로 | `logs/preeval/{rhl,iwl,dql,vrl}.jsonl` |

---

*END OF DOCUMENT (v3, 카드/학습층 분리 강화본)*
