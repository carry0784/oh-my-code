# Track 4 대시보드 검수 보고서

```
문서 유형  : 헌법 조항 대조 검수본
트랙      : Track 4 — L0/L1 운영 대시보드
작성일    : 2026-03-23
baseline  : governance-go-baseline (7eb9ad8)
검수 결과  : 44 passed, 0 failed, 1 skipped (test_dashboard.py)
전체 결과  : 385 passed, 0 failed, 1 skipped
```

---

## 1. 수정 파일 및 영향 범위 (정확 기술)

### 신규 생성 파일

| 파일 | 역할 | baseline 영향 |
|------|------|-------------|
| `app/templates/dashboard.html` | 대시보드 HTML 템플릿 | 없음 (신규 경로) |
| `app/static/css/dashboard.css` | 대시보드 CSS | 없음 (신규 경로) |
| `app/api/routes/dashboard.py` | 대시보드 라우트 + 데이터 API | 없음 (신규 라우터, 기존 라우트 미변경) |
| `tests/test_dashboard.py` | 검수 테스트 45건 | 없음 (신규 테스트) |
| `docs/DASHBOARD_GUIDE.md` | 대시보드 운영 문서 | 없음 |
| `.claude/launch.json` | 로컬 편의 파일 (프리뷰 서버) | 없음 (.gitignore 제외) |

### 수정된 기존 파일

| 파일 | 변경 내용 | baseline 영향 |
|------|----------|-------------|
| `app/main.py` | L3~4: `from pathlib import Path`, `from fastapi.staticfiles import StaticFiles` import 추가. L11: `from app.api.routes.dashboard import router as dashboard_router` import 추가. L85~90: `app.include_router(dashboard_router, ...)`, `app.mount("/static", ...)` 추가 | **간접 영향**: 앱 시작 시 dashboard 모듈 로드. 기존 `/api/v1` 라우트, `/health` 엔드포인트, lifespan, 거버넌스 초기화 로직은 변경 없음 |
| `requirements.txt` | `jinja2>=3.1.3` 1줄 추가 | 없음 (신규 의존성, 기존 패키지 미변경) |
| `.gitignore` | `.claude/` 1줄 추가 (IDE 섹션) | 없음 |

### 변경하지 않은 baseline 보호 파일

| 파일 | 보호 상태 |
|------|----------|
| `app/agents/governance_gate.py` | 미변경 |
| `app/agents/orchestrator.py` | 미변경 |
| `app/models/signal.py` | 미변경 |
| `app/schemas/signal.py` | 미변경 |
| `app/services/signal_service.py` | 미변경 |
| `app/agents/signal_validator.py` | 미변경 |
| `tests/test_agent_governance.py` | 미변경 |

---

## 2. 요구 조항 반영 확인

| # | 요구 조항 | 반영 위치 | 테스트 ID | 결과 |
|---|-----------|-----------|-----------|------|
| 1 | /dashboard 라우트 HTML 응답 | `dashboard.py` L37~46 | T-D01-a~g | 7/7 PASS |
| 2 | static CSS 서빙 | `main.py` L87~90, `dashboard.css` | T-D02-a~c | 3/3 PASS |
| 3 | connected/disconnected/empty/loading 상태 렌더 | `dashboard.css` L233~244, `dashboard.html` JS | T-D03-a~i | 9/9 PASS |
| 4 | BLOCKED/FAILED 시각 분리 | `dashboard.css` L280~291 | T-D04-a~g | 7/7 PASS |
| 5 | orphan_count 상시 노출 | `dashboard.html` L14, JS L481~494 | T-D05-a~c | 3/3 PASS |
| 6 | raw prompt/reasoning/error_class 비노출 | `dashboard.py` 전체, `dashboard.html` 전체 | T-D06-a~f | 6/6 PASS |
| 7 | launch.json 판정 | `.gitignore`에 `.claude/` 추가 | T-D09-a~b | 1 PASS, 1 SKIP |
| 8 | 보고서 표현 정확성 | 본 문서 Section 1 | — | 반영 |

---

## 3. 금지 조항 확인 (시각화 헌법 대조)

| 헌법 금지 조항 | 코드 준수 여부 | 증적 |
|--------------|-------------|------|
| P-01: BLOCKED를 녹색으로 표시 금지 | ✅ 준수 | `--blocked-text: #f59e0b` (amber), T-D04-b |
| P-02: FAILED를 주황으로 표시 금지 | ✅ 준수 | `--failed-text: #ef4444` (red), T-D04-c |
| P-03: ALLOWED/BLOCKED/FAILED 합산 금지 | ✅ 준수 | 별도 CSS 클래스, 합산 UI 없음 |
| P-04: orphan_count 숨김 금지 | ✅ 준수 | L0 배너 항상 표시 (null → "-"), T-D05-a~c |
| P-05: production에서 debug 암시 금지 | ✅ 준수 | `{% if debug_mode %}` 조건부, T-D01-e |
| P-06: evidence_id 없이 decision_code만 표시 금지 | ✅ 해당없음 | 현재 대시보드는 거래소 패널 중심, evidence 개별 표시 없음 |
| P-07: raw 원문 "더보기" 접근 금지 | ✅ 준수 | 원문 표시 UI 없음, T-D06-a~f |
| P-08: PRE-only를 정상 완료 표시 금지 | ✅ 해당없음 | evidence 개별 렌더링 미포함 |
| P-09: production에서 L2 접근 경로 금지 | ✅ 준수 | L2 경로 자체 미구현 |
| P-10: production에서 hash 표시 금지 | ✅ 준수 | hash 필드 API 응답 미포함, T-D08-b |
| P-11: debug 환경에서 production 배너 혼동 금지 | ✅ 준수 | debug 시 `[DEBUG]` 배지 표시 |

---

## 4. 상태 전이 / 렌더 규칙

### 4.1 연결 상태 전이

| 상태 | CSS 클래스 | 색상 | 전이 조건 |
|------|-----------|------|-----------|
| 조회 중 (초기) | `conn-loading` | amber 점멸 | 페이지 로드 시 |
| 연결됨 | `conn-connected` | green + glow | API 응답 `status=connected` |
| 연결 실패 | `conn-disconnected` | gray | API 응답 `status=disconnected` |
| 데이터 없음 | `st-empty` | muted | `positions.length === 0` |

### 4.2 L0 배너 상태 전이

| SecurityState | 배너 CSS | 색상 | 문구 |
|---------------|---------|------|------|
| NORMAL | `.l0-banner.normal` | green 배경 | `Governance: NORMAL` |
| RESTRICTED | `.l0-banner.restricted` | amber 배경 | `Governance: RESTRICTED` |
| QUARANTINED | `.l0-banner.quarantined` | red 배경 | `Governance: QUARANTINED — sandbox only` |
| LOCKDOWN | `.l0-banner.lockdown` | red 점멸 | `Governance: LOCKDOWN — human override required` |

### 4.3 거버넌스 배지 렌더 규칙

| DecisionCode | CSS 클래스 | 배경 | 텍스트 |
|-------------|-----------|------|--------|
| ALLOWED | `gov-allowed` | `#16291a` (dark green) | `#22c55e` (green) |
| BLOCKED | `gov-blocked` | `#2d2310` (dark amber) | `#f59e0b` (amber) |
| FAILED | `gov-failed` | `#2d1515` (dark red) | `#ef4444` (red) |

---

## 5. 로그 / Audit 필드

### 대시보드 API 노출 필드 (허용)

| 필드 | 소스 | 용도 |
|------|------|------|
| `security_state` | `SecurityStateContext` | L0 배너 |
| `orphan_count` | 계산 (PRE - linked) | L0 배너 |
| `evidence_total` | `len(bundles)` | L0 배너 |
| `enabled` | `governance_gate is not None` | 활성 여부 |

### 대시보드 API 비노출 필드 (금지)

| 필드 | 금지 이유 | 테스트 |
|------|-----------|--------|
| `artifacts` | 원문 데이터 노출 | T-D08-a |
| `check_matrix` | 내부 구조 노출 | T-D08-a |
| `prompt_hash` | 추적 정보 노출 | T-D08-b |
| `reasoning_hash` | 추적 정보 노출 | T-D08-b |
| `traceback_hash` | 추적 정보 노출 | T-D08-b |
| `error_class` | 내부 구조 노출 | T-D06-e |
| `error_severity` | 내부 분류 노출 | T-D06-e |
| `exception_message` | 스택 정보 노출 | T-D06-e |
| `prompt` / `reasoning` 원문 | 민감정보 | T-D06-d |

---

## 6. 미해결 리스크

| # | 리스크 | 심각도 | 현재 상태 | 해소 방안 |
|---|--------|--------|----------|-----------|
| R-01 | `app/main.py` 수정으로 대시보드 import 실패 시 전체 앱 시작 불가 | 중간 | dashboard.py는 독립 모듈이므로 import 실패 가능성 낮음. 단, 템플릿 경로 오류 시 런타임 500 | 통합 테스트에서 `/dashboard` HTTP 200 확인 추가 가능 |
| R-02 | DB 미연결 상태에서 `/dashboard/api/data` 호출 시 500 | 낮음 | `_get_exchange_panel_data`의 except 절에서 disconnected 반환. 단, `get_db()` 의존성 자체가 실패하면 500 | FastAPI `Depends(get_db)` 레벨 에러 핸들러 추가 가능 |
| R-03 | `_get_governance_info()`가 `app.main.app.state`에 직접 접근 | 낮음 | 순환 import 아님 (함수 내 지연 import). 단, 앱 구조 변경 시 깨질 수 있음 | DI 패턴으로 전환 가능 (별도 이슈) |
| R-04 | `.claude/launch.json`이 이미 커밋되었을 수 있음 | 낮음 | `.gitignore`에 `.claude/` 추가했으나 이미 tracked 파일이면 효과 없음 | `git rm --cached .claude/launch.json` 필요 시 별도 실행 |
| R-05 | 한투/키움/Bitget/UpBit 패널은 정적 HTML로 "미연결" 고정 | 의도됨 | 어댑터 미구현이므로 정확한 표현 | 어댑터 추가 시 JS 동적 렌더링으로 전환 필요 |

---

## 7. launch.json 판정

| 항목 | 결과 |
|------|------|
| 파일 위치 | `.claude/launch.json` |
| 판정 | **로컬 편의 파일** (프로젝트 산출물 아님) |
| 근거 | `.claude/`는 Claude Code 도구 전용 디렉토리. 서버 실행 설정은 개발자 환경마다 다름 |
| 조치 | `.gitignore`에 `.claude/` 추가 완료 |
| 테스트 | T-D09-a PASS, T-D09-b SKIP (`.gitignore` 반영 전 작성된 테스트) |

---

## 8. 테스트 분류표

| 테스트 클래스 | 건수 | 검수 영역 |
|-------------|------|-----------|
| TestDashboardRoute | 7 | 라우트 존재, HTML 구조, 6패널, L0 배너, READ-ONLY, 쓰기 금지 |
| TestStaticCSS | 3 | CSS 파일 존재, 변수 정의, 템플릿 참조 |
| TestStateRendering | 9 | 4상태 CSS 분리, 색상 검증, 템플릿/JS 사용 |
| TestGovernanceVisualSeparation | 7 | BLOCKED/FAILED 색상 분리, ALLOWED 녹색, 4 SecurityState, LOCKDOWN 점멸 |
| TestOrphanCountExposure | 3 | L0 배너 orphan 표시, null 처리, API 필드 |
| TestSensitiveDataNonExposure | 6 | raw prompt/reasoning/error_class 비노출, 필드 제한 |
| TestDataAPIStructure | 5 | API 키 구조, status 필드, None vs 0 |
| TestGovernanceFieldRestriction | 3 | artifacts/hash 비노출, 건수 한정 |
| TestLaunchJsonClassification | 2 | 로컬 편의 파일 판정 |
| **합계** | **45** | |
