# K-V3 Dashboard Safe Mode Framework (시각화 문제 구조 해결 스펙)

> **발행일**: 2026-04-14
> **상위 거버넌스**: `k_v3_visualization_layer_governance.md` (VC-01~04)
> **기준선**: `48915d2` (PR #98)
> **적용 상태**: STANDBY, P3 ACTIVE (~2026-04-28)
> **현재 Stage**: **Stage 0** (Dashboard OFFLINE, B+C 경로 유지)
> **핵심 명제**: 시각화 문제는 UI 품질 문제가 아니라 **원본-표현 분리 · 신뢰도 표시 · 권한 혼합 · fail-closed 부재**의 구조 문제이다.

---

## 0. 본 문서의 위치

| 축 | 문서 |
|----|------|
| 헌법 (Why/What) | `k_v3_visualization_layer_governance.md` — VC-01~04, 4계층, 6조건, 5금지 |
| **구현 스펙 (How)** | **본 문서** — 상태 머신, UI 규칙, Safe Mode Stage, Integrity Ledger |
| 통합점검 기준선 | `k_v3_integrated_inspection_report.md` |
| 잔여 대책 | `k_v3_residual_items_countermeasures.md` |

본 문서는 헌법을 **실제 UI/운영 규칙으로 번역**한 실행 스펙이다.
코드 변경 없음. 설계 봉인만 수행.

---

## 1. 시각화 문제의 구조 정의 — 4축

대시보드 오판은 UI 디자인 결함이 아니라 아래 4개 구조 결함에서 발생한다.

| # | 축 | 결함 | 결과 |
|---|----|------|------|
| S1 | **원본-표현 분리** | DB 사실 ≠ 화면 표현 | Dashboard를 사실로 착각 |
| S2 | **신뢰도 표시 부재** | freshness/mismatch/failure 미표시 | stale/incomplete 데이터가 정상처럼 보임 |
| S3 | **권한 혼합** | 실행권/전이권이 시각화에 스며듦 | 화면 조작이 곧 운영 변경이 됨 |
| S4 | **fail-closed 부재** | 데이터 없어도 화면 정상 렌더 | 소스 장애 시 거짓 정상 |

**원칙**: 네 축 모두 해결되지 않으면 Dashboard는 운영 판단 경로에 포함될 수 없다.

---

## 2. Dashboard 상태 머신 (5-State Machine)

Dashboard는 **자기 상태를 먼저 선언**해야 한다. "정상 화면"만 보여주는 구조는 금지.

```
┌────────────┐
│  OFFLINE   │  ← 서버 미기동 (현재 상태, Stage 0)
└─────┬──────┘
      │ uvicorn_started (Option A 6조건 충족)
      ▼
┌────────────┐   source missing   ┌────────────┐
│  INCOMPLETE│ ←───────────────── │  BLOCKED   │
└─────┬──────┘                    └────────────┘
      │ all sources available
      ▼
┌────────────┐   stale / failure   ┌────────────┐
│  DEGRADED  │ ←───────────────── │   READY    │
└────────────┘   fresh + match     └────────────┘
```

| 상태 | 조건 | 허용 동작 |
|------|------|----------|
| **READY** | fresh + complete + no mismatch + no recent failure | 모든 read-only 뷰 |
| **DEGRADED** | stale OR recent task failure | compare-only, summary confidence 하향 |
| **INCOMPLETE** | 일부 source missing | 해당 카드 숨김 + 경고 배너 |
| **BLOCKED** | critical source missing (DB unreachable, unknown state) | 전체 blocked, fail-closed banner |
| **OFFLINE** | 서버 미기동 | 운영 정상, 시각화 미가동 (현재) |

**전이 규칙**:
- 상태 악화는 **즉시 반영**, 개선은 검증 후 반영
- `BLOCKED` → `READY` 직접 전이 금지, 반드시 `INCOMPLETE`/`DEGRADED` 경유

---

## 3. 시각화 신뢰도 헤더 (Trust Header) — 강제 필드

모든 Dashboard 뷰 상단에 **고정 표시** (숨김 금지, 축소 금지):

```
┌──────────────────────────────────────────────────────────┐
│ Data Source      : DB / Flower / logs                    │
│ Last Updated     : 2026-04-14T12:34:56Z                  │
│ Freshness        : FRESH / STALE / UNKNOWN               │
│ Integrity        : MATCHED / MISMATCH / INCOMPLETE       │
│ Mode             : Read-only Projection                  │
│ Authority        : No Execution Authority                │
│ Dashboard State  : READY / DEGRADED / INCOMPLETE / BLOCKED│
└──────────────────────────────────────────────────────────┘
```

**강제 조항**:
- 헤더 부재 → VC-02 위반 판정
- 헤더와 바디 불일치 → Dashboard 오류로 판정, DB가 기준

---

## 4. 카드 단위 Confidence 표시 — 숫자 + 상태문

숫자만 표시 금지. 모든 카드는 **신뢰도 상태문**을 함께 렌더.

| 카드 유형 | 숫자 예시 | 요구 상태문 |
|-----------|----------|------------|
| Observation card | `shadow_observation = 1,248` | `TRUSTED` / `DEGRADED` / `COMPARE_ONLY` / `BLOCKED` |
| Novelty card | `novelty_events = 4` | `TRUSTED` / `COUNT_UNMATCHED` / `BLOCKED` |
| Task card | `last_beat_tick = 2s ago` | `ACTIVE` / `FAILED_RECENT` / `UNKNOWN` |
| Summary card | `P3 status = ACTIVE` | `USABLE` / `DEGRADED` / `BLOCKED` |

**Confidence 상태문 4코드**:

| 코드 | 조건 | UI 행동 |
|------|------|--------|
| `TRUSTED` | fresh + matched + no failure | 정상 렌더 |
| `DEGRADED` | stale 또는 failure 최근 존재 | 노란 배너 + confidence 하향 |
| `COMPARE_ONLY` | DB 값과 불일치 감지 | summary 숨김, 비교 테이블만 |
| `BLOCKED` | critical missing / unknown | 카드 자체 blocked, fail-closed |

**금지**: 점수화(0-100) 기반 색상 표시. 예뻐 보여도 과신을 유발.

---

## 5. Fail-Closed UI 동작 규칙 — VC-04 구현

VC-04는 문장이 아니라 **실제 UI 동작**으로 강제.

| 조건 | 필수 UI 동작 |
|------|-------------|
| critical source missing | 요약 카드 숨김 + 경고 배너 전면 표시 |
| DB unreachable | 전체 Dashboard `BLOCKED`, 입력/네비 비활성 |
| freshness unknown | 비교/요약 기능 비활성 |
| mismatch detected | summary 사용 금지, compare-only mode 강제 |
| task failure recent | 해당 카드에 `FAILED_RECENT` 상태문 + 로그 링크 |

**핵심 원칙**: **데이터가 나쁘면 화면도 나빠져야 한다.** 데이터가 나쁜데 화면만 멀쩡한 것이 최악.

---

## 6. Mismatch 자동 대조 규칙 — DB-First

대시보드 수치는 **반드시** DB와 자동 대조. 통과 전에는 `TRUSTED` 표시 금지.

**필수 대조 항목**:

| # | 대조 쌍 | 허용 오차 |
|---|---------|----------|
| 1 | `dashboard.observation_count` vs `SELECT COUNT(*) FROM shadow_observation` | 0 (정확 일치) |
| 2 | `dashboard.novelty_count` vs `SELECT COUNT(*) FROM ppf_novelty_event` | 0 |
| 3 | `dashboard.latest_observed_at` vs `SELECT MAX(observed_at) FROM shadow_observation` | ±1s |
| 4 | `dashboard.latest_bar_ts` vs `SELECT MAX(bar_ts) FROM ohlcv_1h` | ±1s |
| 5 | `dashboard.last_task_success_at` vs Flower task history | ±5s |

**대조 실패 시**:
- 초록색 정상 표시 금지
- Summary confidence 자동 `COMPARE_ONLY` 전환
- mismatch banner 고정 표시
- mismatch 건은 Integrity Ledger에 자동 기록

---

## 7. Stage 구조 로드맵 (사용자 의도 반영 갱신판)

### 7.1 Stage 구조 재정의 (중요)

v1의 Stage 0~3 점진 확장 모델은 **폐기**. 사용자 의도는:
- Card는 P3 기간 중 임시 확인 도구 (현재 ~ 04-28)
- 04-28에 Card 폐기
- 04-28 이후 Dashboard는 **연속 확장이 아니라 전면 재설계**

따라서 Stage 모델을 다음과 같이 갱신:

```
Stage 0  (OFFLINE, 초기)
   ↓ [04-14 현재, 벗어남]
Stage PreEval  (TRCC + PLRAL 4-ledger, ~04-28)
   ↓ [04-28, TRCC 폐기 + PLRAL freeze + ORP/VRP 생성]
Stage Dashboard  (post-P3 전면 재설계, VRP 기반)
```

**v3 명명(2026-04-14 재설계)**:
- **TRCC** = Temporary Runtime Confirmation Card (분리된 카드)
- **PLRAL** = Passive Learning & Reference Accumulation Layer (분리된 학습층)
- **ORP** = Operations Reference Pack (post-P3, 운영 재료)
- **VRP** = Visualization Reference Pack (post-P3, Dashboard 재설계 재료)

### 7.2 Stage 0 — OFFLINE (이미 벗어남)

| 항목 | 상태 |
|------|------|
| Dashboard | OFFLINE |
| 운영 경로 | B (Flower :5555) + C (DB :5432 직접 조회) |
| 산출물 | 없음 |
| 상태 | 04-14 이전 (역사) |

### 7.3 Stage PreEval — TRCC + PLRAL (**현재**)

| 항목 | 내용 |
|------|------|
| 기간 | 2026-04-14 ~ 2026-04-28 (P3 기간) |
| 산출물 A (TRCC) | `scripts/health_check.py` (분리된 CLI Card, 6필드/3판정) |
| 산출물 B (PLRAL) | 4 ledger 파일 (`logs/preeval/{rhl,iwl,dql,vrl}.jsonl`) |
| 분리성 | TRCC ↔ PLRAL 단방향 커플링 (Card→PLRAL write-only) |
| 운영 경로 | B + C 유지 + TRCC 보조 |
| 간섭도 | 0 (uvicorn 없음, DB 쓰기 없음, 상주 없음) |
| 폐기 | 04-28 TRCC 삭제, PLRAL freeze, ORP/VRP 생성 |
| 상세 스펙 | `k_v3_system_health_card_spec.md` (v3 TRCC), `k_v3_preeval_learning_ledger_design.md` (v3 PLRAL) |

### 7.4 Stage Dashboard — post-P3 전면 재설계

| 항목 | 내용 |
|------|------|
| 개시 | 2026-04-28 이후 (P3 재평가 PASS 조건부) |
| 개념 | TRCC 연속 아님. 처음부터 다시 설계 |
| 입력 자료 | **VRP** (Visualization Reference Pack, PLRAL 4 ledger 분석 결과) |
| 보조 입력 | **ORP** (Operations Reference Pack, 운영 표준 정비용 — Dashboard 설계 직접 인용 금지) |
| 참조 원칙 | 본 문서의 5-state 머신, Trust Header 7필드, Mismatch 5항, Integrity Ledger, 워터마크, 검수표 8항 = **모두 유지** |
| 거버넌스 | VC-01~04 + Option A 6조건 + 검수표 + 별도 승인 |
| 형태 | 미정 (재평가 후 결정) |

**Pack 경계 규칙**: ORP 와 VRP 는 교차 인용 금지. Dashboard 설계는 VRP 만 인용. 운영 표준은 ORP 만 인용. 양쪽 필요 항목은 각 pack 에 중복 기재.

**이전 Stage 1~3 (snapshot/limited/extended)**: **참조 원칙으로만 유지**, 실제 진입 경로로는 사용하지 않음. Dashboard 재설계 시 필요 시 인용.

### 7.5 현재 허용 및 금지

| # | 항목 | 상태 |
|---|------|------|
| 1 | Stage PreEval TRCC 실행 (수동) | 사용자 승인 후 허용 |
| 2 | PLRAL RHL/DQL append | TRCC 실행 경유만 (무조건) |
| 3 | PLRAL IWL append | TRCC verdict≠정상가동 시만 |
| 4 | PLRAL VRL append | 운영자 수동만 (TRCC 경유 금지) |
| 5 | uvicorn 기동 | **금지** (Option A 6조건 미충족) |
| 6 | Dashboard route 수정 | **금지** (P3 비간섭) |
| 7 | cron/systemd 자동화 | **금지** (상주성) |
| 8 | PLRAL→TRCC read back | **금지** (단방향 커플링) |
| 9 | PLRAL→운영 시스템 write | **금지** (DP-4 학습층 실행 권한 없음) |
| 10 | ORP/VRP 교차 인용 | **금지** (Pack 경계 규칙) |
| 11 | Stage Dashboard 진입 | **금지** (04-28 이전) |

---

## 8. Visualization Integrity Ledger — 신규 장부 스펙

시각화의 신뢰도를 **장부화**하여 감사/학습 가능하게 한다.

### 스키마 (설계만, 구현은 post-P3)

```sql
CREATE TABLE visualization_integrity_ledger (
    id                        BIGSERIAL PRIMARY KEY,
    ts                        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dashboard_state           VARCHAR(16) NOT NULL,  -- READY/DEGRADED/INCOMPLETE/BLOCKED/OFFLINE
    freshness_state           VARCHAR(16) NOT NULL,  -- FRESH/STALE/UNKNOWN
    integrity_state           VARCHAR(16) NOT NULL,  -- MATCHED/MISMATCH/INCOMPLETE
    mismatch_detected         BOOLEAN NOT NULL,
    mismatch_detail           JSONB,                 -- {field, dashboard_value, db_value, delta}
    fail_closed_triggered     BOOLEAN NOT NULL,
    fail_closed_reason        VARCHAR(128),
    last_verified_against_db_at TIMESTAMPTZ,
    source_age_seconds        INTEGER,
    viewer_session_id         VARCHAR(64),           -- 감사용, 개인정보 아님
    notes                     TEXT
);
```

### 기록 시점

- Dashboard 상태 전이 시점마다
- mismatch 감지 시
- fail-closed 트리거 시
- 운영자가 판단 근거로 쓰겠다고 선언한 스냅샷 시

### 용도

- 감사: 어느 시점에 어떤 화면이 표시되었는가
- 학습: 어떤 카드가 오판을 자주 만들었는가
- 증거: 운영 판정 시점의 시각화 신뢰도 기록

**주의**: 장부는 **시각화의 증거성 확보**이지, 시각화가 DB를 대체하는 것이 아니다. DB-first 원칙 불변.

---

## 9. 화면 캡처 증거성 규칙 — 오남용 방지

Dashboard 스크린샷이 증거처럼 공유되는 오남용을 방지.

**상태별 필수 워터마크**:

| 상태 | 화면 고정 문구 |
|------|----------------|
| `DEGRADED` | `NOT DECISION GRADE — SOURCE VERIFICATION REQUIRED` |
| `INCOMPLETE` | `PARTIAL DATA — NOT FOR AUDIT` |
| `BLOCKED` | `VISUALIZATION BLOCKED — USE DB DIRECTLY` |
| `OFFLINE` | (해당 없음, 화면 자체 없음) |
| `READY` | `READ-ONLY PROJECTION — DB IS THE SOURCE OF TRUTH` |

**원칙**: 모든 Dashboard 캡처는 워터마크 포함. 제거 시 증거로 사용 불가.

---

## 10. 시각화 검수표 (UI Compliance Checklist) — 8항

Dashboard 기동 전/후 반드시 아래 8항 검수. 하나라도 미충족 시 기동 차단.

| # | 검수 항목 | 검증 방법 |
|---|----------|----------|
| 1 | source timestamp visible | 헤더 `Last Updated` 필드 표시 확인 |
| 2 | freshness visible | 헤더 `Freshness` 상태 표시 확인 |
| 3 | integrity visible | 헤더 `Integrity` 상태 표시 확인 |
| 4 | read-only mode visible | 헤더 `Mode: Read-only Projection` 표시 확인 |
| 5 | no execution control | 모든 route GET 확인, POST 버튼 부재 확인 |
| 6 | mismatch handling verified | DB 수정 → Dashboard 자동 `COMPARE_ONLY` 전환 확인 |
| 7 | fail-closed verified | DB 차단 → Dashboard `BLOCKED` 전환 확인 |
| 8 | DB-first ordering respected | Dashboard 조회 전 DB 조회 절차 문서화 |

**검수 주체**: 기동 승인자 (Option A 6조건 확인자와 동일)
**검수 주기**: Stage 전환 시마다

---

## 11. Stage PreEval 실행 절차 (2026-04-14 ~ 04-28, 현재)

**목적**: 운영 절차로 "살아있는가/문제있는가" 즉시 확인 + 학습 자료 누적.

### 일일 점검 절차 (3단계 + CLI 보조)

```
1단계 DB (사실)
   psql -h localhost -U postgres -c "SELECT COUNT(*) FROM shadow_observation WHERE observed_at > NOW() - INTERVAL '1 hour';"
   psql -h localhost -U postgres -c "SELECT COUNT(*) FROM ppf_novelty_event WHERE event_ts > NOW() - INTERVAL '1 hour';"

2단계 Flower/logs (실행)
   curl -s http://localhost:5555/api/workers | jq '.[] | {status, active}'
   tail -n 50 logs/celery_worker.log
   tail -n 50 logs/celery_beat.log

3단계 TRCC (분리된 CLI Card, Stage PreEval 보조)
   python scripts/health_check.py
   → PLRAL RHL + DQL 에 각 1 라인 append (무조건)
   → PLRAL IWL 에 1 라인 append (verdict≠정상가동 시)
   → PLRAL VRL 은 별개 (운영자 수동 기록)
```

### 판정 코드

- 1+2+3 정상 → `P3_CONTINUE_VISUALIZATION_OPTIONAL` (현재)
- 1 비정상 → `P3_WARN_INVESTIGATE`
- 2 비정상 + 1 정상 → `P3_WARN_INVESTIGATE` (관측)
- TRCC verdict `점검필요` → `P3_WARN_INVESTIGATE` + PLRAL IWL 이벤트 자동 기록
- write 경로 노출 의심 → `P3_BLOCK_VISUALIZATION`

---

## 12. Stage Dashboard 전면 재설계 절차 (2026-04-28 이후)

**원칙**: TRCC 연속 확장 금지. **처음부터 다시 설계**. **VRP (Visualization Reference Pack)** 를 입력 자료로 사용.

### 1단계 — Stage PreEval 종료 (04-28, PLRAL §11 전이 절차 5단계 적용)

- 수집 중단 선언 → TRCC 실행 중단 + VRL 수동 기록 중단 안내
- PLRAL 4 ledger freeze (read-only 권한, `.frozen_YYYYMMDD` 마커)
- Integrity snapshot (SHA256 4 파일, 라인 수, 첫/마지막 ts) → `logs/preeval/integrity_snapshot.json`
- ORP / VRP 생성 (분석 스크립트 실행)
- TRCC 폐기 (`scripts/health_check.py` git rm)

### 2단계 — PLRAL 4 ledger 분석 → ORP & VRP

- RHL: verdict 분포, worker/beat/db 건강 추이
- IWL: 카테고리별 발생 빈도, 반복 발생 패턴, 수동 조치 필요 건
- DQL: observation/novelty 누적, freshness 위반, source 품질
- VRL: Dashboard 후보, 자주 본 항목, 불필요 정보, 경고 표현 가이드
- 산출: `p3_post_operations_reference_pack.md` (ORP) + `p3_post_visualization_reference_pack.md` (VRP)

### 3단계 — Dashboard 요구사항 재수집 (VRP 전용 인용)

- VRP 내 "자주 본 항목" → Dashboard 우선 순위 필드
- VRP 내 "불필요했던 정보" → Dashboard 제외 목록
- VRP 내 "필요했던 패널" → 신규 패널 후보
- VRP 내 "경고 표현 방식" → 경고 문구 표준
- VRP 내 "freshness/integrity 표시 기준" → 임계값 표준안
- **ORP 인용 금지** (Pack 경계 규칙)

### 4단계 — 새 Dashboard 설계

- VC-01~04 (헌법) 준수 필수
- 본 문서의 참조 원칙 (5-state 머신, Trust Header, Mismatch, Integrity Ledger, 워터마크, 검수표 8항) 준수
- 구현 방식 결정 (uvicorn / Streamlit / Grafana / 기타)
- 검수표 8항 + Option A 6조건 재적용

### 5단계 — 기동 및 관찰

- 별도 거버넌스 라운드 승인 후 기동
- Shadow 적용 → 제한적 채택 단계는 기존 틀 유지
- Dashboard 단독 판정 여전히 금지

**중요**: 4단계의 "새 Dashboard"는 TRCC 의 확장이 아니다. TRCC 는 04-28 에 폐기되었고, 새 Dashboard 는 **VRP** 를 입력으로 하여 독립적으로 설계된다. ORP 는 운영 표준 정비에 쓰되 Dashboard 설계에는 인용하지 않는다.

---

## 13. 봉인 선언

```
DASHBOARD_SAFE_MODE_FRAMEWORK = DEFINED (v3, TRCC/PLRAL 분리 + 4 ledger + 2 pack)
STATE_MACHINE = 5-STATE (READY/DEGRADED/INCOMPLETE/BLOCKED/OFFLINE)
TRUST_HEADER = MANDATORY (7 fields)
CONFIDENCE_CODES = 4 (TRUSTED/DEGRADED/COMPARE_ONLY/BLOCKED)
FAIL_CLOSED_RULES = 5 (VC-04 구현)
MISMATCH_COMPARISON = 5 (DB-first auto-check)
STAGE_MODEL = (Stage 0 → Stage PreEval (TRCC+PLRAL) → Stage Dashboard (VRP 기반), 연속 아닌 폐기+재설계)
INTEGRITY_LEDGER = SPECIFIED (구현 post-P3)
TRCC_SPEC = DEFINED (k_v3_system_health_card_spec.md v3, 분리된 카드)
PLRAL_DESIGN = DEFINED (k_v3_preeval_learning_ledger_design.md v3, 4 ledger + 2 pack)
PLRAL_LEDGERS = 4 (RHL/IWL/DQL/VRL)
POST_P3_PACKS = 2 (ORP/VRP, 교차 인용 금지)
WATERMARK_RULES = 5 (상태별 증거성 방지)
COMPLIANCE_CHECKLIST = 8 (기동 전 전항 검증)

CURRENT_STAGE = Stage PreEval (TRCC + PLRAL)
PREEVAL_WINDOW = 2026-04-14 ~ 2026-04-28
STAGE_PREEVAL_INTERFACE = CLI only (uvicorn 금지)
STAGE_DASHBOARD_ENTRY = 2026-04-28 이후, 전면 재설계, TRCC 연속 아님, VRP 입력
COUPLING_DIRECTION = TRCC → PLRAL (write-only, 단방향)
PACK_CITATION_POLICY = ORP↔VRP 교차 인용 금지
CURRENT_VERDICT = P3_CONTINUE_VISUALIZATION_OPTIONAL

CORE_RULE = "데이터가 나쁘면 화면도 나빠져야 한다"
PRIORITY = "오판 방지 > UI 편의"
FIX_APPROACH = "강화가 아니라 제한"
STAGE_RULE = "TRCC 연속 확장 아님 → 04-28 폐기 후 VRP 기반 전면 재설계"
SEPARATION_RULE = "카드는 학습층을 읽지 않고, 학습층은 운영을 쓰지 않는다"

production_authorized = FALSE (불변)
P3_ACTIVE_NON_INTERFERENCE = TRUE (CLI 방식 + 단방향 커플링으로 보전)
```

---

## 14. 참조 문서 연결

| 관계 | 문서 |
|------|------|
| 상위 헌법 | `k_v3_visualization_layer_governance.md` (VC-01~04) |
| **Stage PreEval TRCC** | `k_v3_system_health_card_spec.md` (v3, 분리된 카드) |
| **Stage PreEval PLRAL** | `k_v3_preeval_learning_ledger_design.md` (v3, 4 ledger + 2 pack) |
| 통합점검 | `k_v3_integrated_inspection_report.md` |
| 잔여 대책 | `k_v3_residual_items_countermeasures.md` |
| Advisory Ledger | `advisory_ledger_b001.md` |
| P3 재평가 | `p3_post_eval_reevaluation_plan.md` |
| PPF 거버넌스 | `ppf_integrated_governance_spec.md` |
| Dashboard 코드 (수정 금지) | `app/api/routes/dashboard.py` |
| Dashboard 명세 | `docs/operations/dashboard_spec.md` |
| TRCC 구현 위치 (미생성, 승인 후) | `scripts/health_check.py` |
| PLRAL 데이터 위치 (미생성, 승인 후) | `logs/preeval/rhl.jsonl`, `logs/preeval/iwl.jsonl`, `logs/preeval/dql.jsonl`, `logs/preeval/vrl.jsonl` |
| PLRAL pack builder (설계만, post-P3) | `scripts/plral_pack_builder.py` |
| ORP/VRP 산출물 경로 (post-P3) | `docs/operations/evidence/p3_post_operations_reference_pack.md`, `p3_post_visualization_reference_pack.md` |

---

## 15. 적용 원칙 요약 (한 문장)

> **현재는 Dashboard 를 켜서 해결하지 않고 B+C + TRCC(CLI) 로 우회하며, PLRAL 4 ledger 에 P3 기간 운영 현실을 무간섭으로 누적하여, 04-28 에 TRCC 폐기 + PLRAL freeze + ORP/VRP 생성 후 VRP 를 입력으로 Dashboard 를 전면 재설계하되, DB-first · mismatch-visible · fail-closed · no-execution-authority · card-learning-separation 5원칙으로 시각화 문제를 구조적으로 봉쇄한다.**

---

*END OF DOCUMENT*
