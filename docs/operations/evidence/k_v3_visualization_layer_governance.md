# K-V3 시각화 계층 거버넌스 (Visualization Layer Governance)

> **발행일**: 2026-04-14  
> **적용 기준**: STANDBY 상태, P3 ACTIVE (~2026-04-28)  
> **기준선**: `48915d2`  
> **핵심 원칙**: **시각화는 포함하되, 시각화는 실행이 아니다**  
> **표현**: "증거는 DB/태스크/로그가 만들고, 화면은 그것을 보여주기만 해야 한다"

---

## 1. 운영 구조 4계층 정의

| 계층 | 구성 | 역할 | 권한 | 현재 상태 |
|------|------|------|------|----------|
| **핵심 운영층** | Celery worker + beat + PostgreSQL + P3 누적 로직 | 시스템 본체, 증거 생성 | 쓰기 필수 | ✅ ACTIVE |
| **검증층** | Flower UI + DB 직접 조회 + 로그 파일 | 본체 정상 동작 검증 | read-only | ✅ ACTIVE (Flower:5555, PG:5432) |
| **시각화층** | FastAPI + `/dashboard` | 사람이 보기 쉬운 상태 요약 | **read-only projection only** | ❌ OFFLINE (승인 대기) |
| **실행층** | POST /orders, POST /signals, 배포, 재구성 | 시스템 변경 | P3 ACTIVE 중 차단 | ❌ BLOCKED |

**불변 규칙**:
```
핵심층 = 증거 생산자
검증층 = 증거 확인자
시각화층 = 증거 표현자
실행층 = P3 중 봉인
```

---

## 2. 시각화 헌법 (Visualization Constitution, VC-01~04)

| 조항 | 규정 | 의미 |
|------|------|------|
| **VC-01** | Visualization has no execution authority. | 시각화는 실행권 없음 |
| **VC-02** | Visualization may display, summarize, and compare only. | 표시·요약·비교만 가능 |
| **VC-03** | Visualization cannot authorize transitions. | 상태 전이 승인권 없음 |
| **VC-04** | Visualization must fail closed when source data is unavailable. | 소스 데이터 없으면 fail-closed |

**강제 방식:**
- VC-01: `app/api/routes/dashboard.py` 헤더에 명시 ("NO write actions, NO trade execution, NO order submission")
- VC-02: 모든 dashboard endpoint가 `GET` 메서드 (POST는 manual-action 경로에 한정, 별도 승인)
- VC-03: `check_live_entry()`, `production_authorized` 등은 시각화층과 분리된 거버넌스 엔진 소관
- VC-04: Missing data → "-" 또는 "미연결" 표시, never faked as 0

---

## 3. 옵션 A (Dashboard 서버 기동) 허용 조건 — 6항 동시 충족

옵션 A를 승인하려면 아래 6개 조건이 **전부** 만족되어야 합니다.

| # | 조건 | 검증 방법 |
|---|------|----------|
| 1 | **시각화 목적이 명확할 것** | "어떤 판정을 위해 화면이 필요한가" 사전 명시 |
| 2 | **read-only route만 사용할 것** | POST 경로 호출 금지, GET만 |
| 3 | **POST/write 호출 금지 확인** | 세션 시작 시 write 차단 체크리스트 확인 |
| 4 | **lifespan 초기화 영향 기록** | 기동 시간, GovernanceGate generation 증가 여부 기록 |
| 5 | **신규 프로세스 추가를 환경 변화로 인정할 것** | uvicorn PID 기록, 종료 시 PID 확인 |
| 6 | **DB/Flower 기반 근거가 먼저 확보될 것** | 2단계 검증층 결과 없이 3단계로 건너뛰기 금지 |

**조건 미충족 시**: 옵션 A 차단, 옵션 B+C로 대체.

---

## 4. 시각화 계층 금지영역 — 5항

| # | 금지 행위 | 근거 |
|---|----------|------|
| 1 | 시각화 계층에서 POST/write 경로 사용 | VC-01, VC-02 |
| 2 | "대시보드가 보이니 운영 가능"이라는 오판 | 시각화 ≠ 실행 |
| 3 | 신규 프로세스 추가를 무조건 무해하다고 보는 것 | 옵션 A 조건 5 |
| 4 | P3 ACTIVE 중 관측과 무관한 서버 재구성 | P3 non-interference |
| 5 | 시각화 부족을 시스템 실패로 오판하는 것 | 핵심/검증층이 본체 |

---

## 5. 3단계 관제 표준 (3-Tier Observation Standard)

운영 확인은 반드시 아래 순서로 진행. 건너뛰기 금지.

```
┌─────────────────────────────────────────────┐
│ 1단계: Evidence Check (DB)                   │
│  → 사실 확인 (가장 직접적인 증거)             │
│  → SELECT COUNT(*) FROM shadow_observation  │
│  → SELECT COUNT(*) FROM ppf_novelty_event   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 2단계: Runtime Check (Flower + logs)         │
│  → 실행 상태 확인                            │
│  → Flower http://localhost:5555              │
│  → tail logs/celery_worker.log              │
│  → tail logs/celery_beat.log                │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 3단계: Human View (Dashboard) — 선택적        │
│  → 시각적 요약만                             │
│  → http://localhost:8000/dashboard          │
│  → 근거 생성 아님, 근거 표현물                │
│  → 조건부 승인 후에만                        │
└─────────────────────────────────────────────┘
```

**상호대조 원칙**:
- Dashboard 값 ≠ DB 값 → **DB가 기준**, Dashboard 오류로 판정
- Flower 상태 ≠ DB 기록 → DB 기준, Flower는 보조 힌트

---

## 6. 운영 판정 코드 (Operational Verdict Codes)

| 코드 | 조건 | 조치 |
|------|------|------|
| **P3_CONTINUE_HEALTHY** | DB 증가 정상 + Flower 정상 + 로그 이상 없음 | 관측 지속, 비간섭 유지 |
| **P3_CONTINUE_VISUALIZATION_OPTIONAL** | DB 증가 정상 + Flower 정상 + Dashboard 미가동 | 관측 지속, 시각화는 선택 |
| **P3_WARN_INVESTIGATE** | DB 증가 정지 또는 failures 존재 | 원인 분석, 증거 수집, 판정 보류 |
| **P3_BLOCK_VISUALIZATION** | write 경로 노출/오사용 위험 확인 | 옵션 A 차단, B+C만 사용 |

**현재 판정**: `P3_CONTINUE_VISUALIZATION_OPTIONAL`
- Worker PID 88008 ✅ alive
- Beat PID 97588 ✅ alive
- Postgres 5432 ✅ connected
- Flower 5555 ✅ running
- Dashboard 8000 ❌ offline (허용 범위, 옵션 A 필요 없음)

---

## 7. 상태 전이 규칙 (slot rules)

```
worker_alive && beat_alive
  → P3_OBSERVATION_ACTIVE

dashboard_down && observation_active
  → VISUALIZATION_UNAVAILABLE_ONLY
  → 시스템 실패 아님, 시각화 미가동일 뿐

flower_ok || db_read_ok
  → VISIBILITY_PARTIAL_AVAILABLE
  → 검증층은 확보됨

uvicorn_started
  → VISUALIZATION_ACTIVE_WITH_ENV_CHANGE
  → 환경 변화로 인정, 근거 기록 필수
```

---

## 8. 시각화 품질 검수 기준 (UI Quality Standards)

Dashboard이 운영에 도움이 되려면 아래 기준 필수 (향후 개선 로드맵):

| # | 기준 | 현재 상태 |
|---|------|----------|
| 1 | Source timestamp 표시 | 확인 필요 |
| 2 | Data freshness 표시 | 확인 필요 |
| 3 | Stale/unknown 시 경고 배너 | 일부 구현 (VC-04 기반) |
| 4 | DB count vs 화면 count 차이 검출 | 미구현 |
| 5 | Task failure indicator 표시 | 확인 필요 |
| 6 | Read-only mode 명시 | ✅ 헤더에 명시됨 |

**부족 항목은 향후 Safe Mode Dashboard 설계 시 포함.**

---

## 9. 향후 Safe Mode Dashboard 설계 지침

P3 이후 정식 운영 시 Dashboard를 "Safe Mode"로 제한 권장:

- No POST buttons (UI에 버튼 자체 제거)
- No mutation endpoints exposed
- Only observation/novelty/status cards
- Source freshness 강제 표시
- Stale data 시 fail-closed banner
- Manual action 경로는 별도 인증 레이어 경유

**구현 우선순위**: post-P3, 대시보드 개선 작업 시 적용.

---

## 10. 봉인 선언

```
VISUALIZATION_LAYER_GOVERNANCE = DEFINED
VC-01~04 = ENFORCED (via dashboard.py header + route definitions)
OPTION_A_ALLOWED_CONDITIONS = 6 (conjunction required)
OPTION_A_PROHIBITED_ZONES = 5
OBSERVATION_STANDARD = 3-TIER (DB → Flower/logs → Dashboard)
CURRENT_VERDICT = P3_CONTINUE_VISUALIZATION_OPTIONAL
DEFAULT_PATH = B + C (Flower + DB direct)
OPTION_A_STATUS = CONDITIONAL (승인 대상)

CORE_PRINCIPLE = "시각화는 포함하되, 시각화는 실행이 아니다"
PROOF_HIERARCHY = "DB가 기준, 화면은 표현"

production_authorized = FALSE (불변, 시각화와 무관)
P3_ACTIVE_NON_INTERFERENCE = TRUE (유지)
```

---

## 11. 참조 문서 연결

| 참조 | 문서 |
|------|------|
| 통합점검 기준선 | `k_v3_integrated_inspection_report.md` |
| 잔여 40항목 대책 | `k_v3_residual_items_countermeasures.md` |
| Advisory Ledger | `advisory_ledger_b001.md` |
| P3 재평가 계획 | `p3_post_eval_reevaluation_plan.md` |
| PPF 거버넌스 명세 | `ppf_integrated_governance_spec.md` |
| Dashboard 구현 | `app/api/routes/dashboard.py` (헤더 참조) |
| Dashboard 명세 | `docs/operations/dashboard_spec.md` |

---

*END OF DOCUMENT*
