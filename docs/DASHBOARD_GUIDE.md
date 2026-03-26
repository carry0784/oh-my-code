# K-Dexter Operations Dashboard Guide

```
트랙 상태  : GO 확정 (Track 4 완료)
확정일    : 2026-03-23
baseline  : governance-go-baseline (7eb9ad8)
검수 결과  : 386 passed, 0 failed (전체) / 44 passed (대시보드 검수)
```

---

## 대시보드 위치

| 항목 | 값 |
|------|---|
| 접근 경로 | `http://localhost:8000/dashboard` |
| 데이터 API | `GET /dashboard/api/data` |
| HTML 템플릿 | `app/templates/dashboard.html` |
| CSS | `app/static/css/dashboard.css` |
| 라우트 | `app/api/routes/dashboard.py` |
| 검수 테스트 | `tests/test_dashboard.py` (45건) |
| 검수 보고서 | `docs/DASHBOARD_INSPECTION_REPORT.md` |
| 시각화 헌법 | `docs/VISUALIZATION_CONSTITUTION.md` |

---

## 완료 항목

| # | 항목 | 상태 | 증적 |
|---|------|------|------|
| 1 | 6패널 3×2 표 중심 레이아웃 | ✅ 완료 | T-D01-c (6패널 ID 확인) |
| 2 | L0 거버넌스 배너 (4 SecurityState) | ✅ 완료 | T-D04-f (4상태 CSS), T-D04-g (LOCKDOWN 점멸) |
| 3 | Binance 포지션 DB 연결 | ✅ 완료 | `_get_exchange_panel_data(db, "binance")` |
| 4 | 총 자산 통계 실시간 행 | ✅ 완료 | Binance 포지션 집계 |
| 5 | BLOCKED/FAILED 시각 분리 | ✅ 완료 | T-D04-a~d (색상값 비교) |
| 6 | orphan_count 상시 노출 | ✅ 완료 | T-D05-a~c (null→"-" 포함) |
| 7 | raw prompt/reasoning/error_class 비노출 | ✅ 완료 | T-D06-a~f, T-D08-a~c |
| 8 | connected/disconnected/empty/loading 4상태 | ✅ 완료 | T-D03-a~i |
| 9 | Read-Only 강제 (쓰기 엔드포인트 없음) | ✅ 완료 | T-D01-g |
| 10 | 반응형 3열→2열→1열 | ✅ 완료 | CSS @media 규칙 |
| 11 | `.claude/` 로컬 편의 파일 분리 | ✅ 완료 | `.gitignore` 추가 |
| 12 | 검수 테스트 45건 | ✅ 완료 | 44 passed, 1 skipped |
| 13 | 검수 보고서 | ✅ 완료 | `DASHBOARD_INSPECTION_REPORT.md` |

---

## 미연결 항목 (후속 이슈)

| # | 이슈 | 패널 | 필요 작업 | 우선순위 |
|---|------|------|-----------|---------|
| I-01 | 한국투자증권 어댑터 연결 | panel-kis | `ExchangeFactory`에 KIS API 어댑터 추가, DB sync 워커 추가 | 별도 |
| I-02 | 키움증권 어댑터 연결 | panel-kiwoom | `ExchangeFactory`에 Kiwoom API 어댑터 추가, DB sync 워커 추가 | 별도 |
| I-03 | Bitget 어댑터 연결 | panel-bitget | CCXT `bitget` 어댑터 추가, `_get_exchange_panel_data(db, "bitget")` 연결 | 별도 |
| I-04 | UpBit 어댑터 연결 | panel-upbit | CCXT `upbit` 어댑터 추가, 현물 데이터 모델 분기 | 별도 |
| I-05 | 총 자산 시계열 스냅샷 저장/집계 | panel-stats | 스냅샷 모델 + Celery beat 태스크 + 시계열 조회 API | 별도 |

각 이슈는 대시보드 코드 수정 없이 **어댑터 추가 → DB sync → API 자동 반영** 구조로 연결됩니다.

---

## 데이터 소스 구분

### 연결됨

| 패널 | 데이터 소스 | 모델 |
|------|------------|------|
| Binance | DB (Celery sync) | `Position`, `Trade` |
| 총 자산 통계 (실시간) | DB 집계 | `Position`, `Trade` |
| L0 거버넌스 배너 | `GovernanceGate` 인스턴스 | `SecurityStateContext`, `EvidenceStore` |

### 미연결

| 패널 | 현재 표시 | 사유 |
|------|-----------|------|
| 한국투자증권 | "데이터 소스 미연결" | KIS API 어댑터 없음 (I-01) |
| 키움증권 | "데이터 소스 미연결" | Kiwoom API 어댑터 없음 (I-02) |
| Bitget | "데이터 소스 미연결" | Bitget 어댑터 없음 (I-03) |
| UpBit | "데이터 소스 미연결" | UpBit 어댑터 없음 (I-04) |
| 총 자산 12h~6개월 | "-" | 스냅샷 테이블 없음 (I-05) |

---

## 실행 방법

```bash
# PYTHONPATH에 src 포함 필수 (kdexter 패키지)
PYTHONPATH=src uvicorn app.main:app --reload --port 8000

# 브라우저에서 접속
# http://localhost:8000/dashboard
```

---

## 변경 금지 규칙 (계속 유효)

### Baseline 보호축
- API `"metadata"` 하위 호환 유지
- rejection → BLOCKED 의미 유지
- execute governance 테스트 4건 보호
- 3대 merge gate 보호 (pytest, governance, constitution)

### 시각화 헌법 규칙
- BLOCKED를 녹색 표시 금지 (P-01)
- FAILED를 주황 표시 금지 (P-02)
- orphan_count 숨김 금지 (P-04)
- production에서 debug 암시 금지 (P-05)
- raw prompt/reasoning/error_class 노출 금지 (V-04, N-01~N-07)

### 대시보드 규칙
- Read-Only: 거래/주문/실행 버튼 추가 금지
- 미연결 = "미연결": 데이터 없으면 0으로 위장 금지
- 거래 엔진, 거버넌스 의미, 실행 로직 변경 금지
