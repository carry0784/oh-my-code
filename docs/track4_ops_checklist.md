# K-DEXTER Track 4 — 종료 선언 및 운영 전환 체크리스트

> **Track 4 Status: GO**
> **Historical Stats Infra: 8 / 8**
> **Historical Stats Ready: time-based growth**

---

## 종료 선언문

### 완료 범위

| 항목 | 내용 | 상태 |
|------|------|------|
| 거래소 패널 | Binance, Bitget, UpBit (CCXT) | ✅ 완료 |
| 국내 증권사 패널 | 한국투자증권, 키움증권 (httpx REST) | ✅ 완료 |
| 총 자산 통계 | 8개 시간 창 + min_samples 규칙 | ✅ 완료 |
| L0 거버넌스 바 | Governance 상태 + orphan + evidence | ✅ 완료 |
| 한국시간 시계 | `현재 YYYY년 MM월 DD일 HH시 mm분 ss초 X요일` | ✅ 완료 |
| 자동 갱신 | 30초 데이터 + 1초 시계 | ✅ 완료 |
| 4-state 렌더링 | connected / disconnected / empty / loading | ✅ 완료 |
| Snapshot 인프라 | 모델 + Celery beat 5분 + migration | ✅ 완료 |
| 테스트 | 156 dashboard + 341 기타 = 497 passed | ✅ 완료 |

### 보호축 유지 사항

| # | 보호축 | 확인 |
|---|--------|------|
| 1 | GovernanceGate baseline 4건 변경 금지 | ✅ 유지 |
| 2 | Read-Only — 대시보드에서 거래 실행 불가 | ✅ 유지 |
| 3 | 미연결/미집계 구분 — 데이터 없을 때 0 표시 금지 | ✅ 유지 |
| 4 | BLOCKED/FAILED 시각 분리 — 색상 구분 유지 | ✅ 유지 |
| 5 | 원문 미노출 — raw prompt/reasoning/error_class 비표시 | ✅ 유지 |

### 운영 진입 조건

```
1. alembic upgrade head              → asset_snapshots 테이블 생성
2. celery -A workers.celery_app worker  → 태스크 실행기 기동
3. celery -A workers.celery_app beat    → 5분 스냅샷 스케줄 기동
4. uvicorn app.main:app --port 8000     → 대시보드 서빙
5. /dashboard 200 OK                    → 화면 정상 확인
```

### 후속 이슈 목록

| # | 항목 | 심각도 | 비고 |
|---|------|--------|------|
| H-01 | Position.symbol_name 필드 보강 | LOW | 현재 `'-'` fallback |
| H-02 | datetime.utcnow() → timezone-aware 전환 | 기술부채 | 34 warnings, 39개 파일 |
| H-03 | Historical Stats ready 전환 관찰 | 운영 | 시간 경과 후 자동 해소 |
| H-04 | kdexter pip 패키징 (PYTHONPATH 의존) | MINOR | F-05 연계 |
| H-05 | UpBit SPOT 패널 설명 문구 정제 | INFO | 현물형 데이터 매핑 명시 |

---

## 1. 운영 전환 확인 항목

| # | 항목 | 확인 방법 | 기대 결과 |
|---|------|-----------|-----------|
| O-01 | 포트 8000 단독 리스너 | `netstat -ano \| findstr :8000` | LISTENING 1건만 |
| O-02 | `/dashboard` 응답 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/dashboard` | `200` |
| O-03 | Clock 마크업 존재 | HTML 내 `<span id="clock">` | 존재 |
| O-04 | Clock JS 갱신 | `setInterval(updateClock, 1000)` | 1초 간격 갱신 |
| O-05 | Clock 실화면 표시 | 브라우저 상단 우측 | `현재 YYYY년 MM월 DD일 HH시 mm분 ss초 X요일` |
| O-06 | 거버넌스 바 렌더 | 브라우저 상단 좌측 | `Governance: NORMAL`, orphan/evidence 표시 |
| O-07 | API 데이터 응답 | `curl http://127.0.0.1:8000/api/v1/dashboard` | JSON (binance, bitget, upbit, kis, kiwoom, windows) |
| O-08 | Alembic migration 적용 | `alembic upgrade head` | asset_snapshots 테이블 생성 |
| O-09 | Celery beat 스케줄 등록 | `celery -A workers.celery_app beat` 로그 | `record-asset-snapshot-every-5m` 등록 |
| O-10 | 첫 snapshot 적재 | DB: `SELECT count(*) FROM asset_snapshots` | ≥ 1 (beat 시작 5분 후) |

---

## 2. 일일 점검 항목

| 시간 | 점검 내용 | 정상 기준 |
|------|-----------|-----------|
| 09:00 | `/dashboard` 200 OK | 응답 < 2s |
| 09:00 | Clock 한국시간 표시 | KST 기준 정확 |
| 09:00 | 각 패널 상태 | 연결: 데이터 표시 / 미연결: `미연결` 표시 |
| 09:00 | 총 자산 통계 창 | 실시간 행 존재, 시간 창별 미집계 or 수치 |
| 09:05 | snapshot 적재 확인 | 최근 5분 내 snapshot 1건 이상 |
| 18:00 | 12h 창 전환 확인 | `미집계` → 수치 (min_samples=2 충족 시) |

### Historical Stats 전환 예상 시점

| 시간 창 | min_samples | 예상 ready 시점 (beat 시작 기준) |
|---------|-------------|-------------------------------|
| 실시간 | 0 | 즉시 |
| 12시간 | 2 | 10분 |
| 24시간 | 4 | 20분 |
| 60시간 | 10 | 50분 |
| 1주 | 20 | 1시간 40분 |
| 1달 | 80 | 6시간 40분 |
| 3개월 | 200 | 16시간 40분 |
| 6개월 | 400 | 33시간 20분 |

---

## 3. 장애 발생 시 1차 확인 순서

```
1단계: 포트 확인
  netstat -ano | findstr :8000
  → 리스너 없음: 서버 재시작
  → 리스너 2건 이상: stale 프로세스 종료 (PID 확인 후 kill)

2단계: 서버 응답 확인
  curl -I http://127.0.0.1:8000/dashboard
  → 404: 라우트 미등록 → app/api/routes/dashboard.py 확인
  → 500: 서버 에러 → uvicorn 로그 확인

3단계: HTML 요소 확인
  curl -s http://127.0.0.1:8000/dashboard | grep 'id="clock"'
  → 없음: 템플릿 렌더링 실패 → Jinja2 에러 확인

4단계: JS 갱신 확인
  브라우저 DevTools Console → updateClock 호출 여부
  → 에러 발생: JS 문법 에러 → dashboard.html 스크립트 확인

5단계: API 데이터 확인
  curl http://127.0.0.1:8000/api/v1/dashboard | python -m json.tool
  → DB 연결 실패: DATABASE_URL 확인
  → 빈 데이터: Celery worker/beat 상태 확인

6단계: Snapshot 적재 확인
  DB: SELECT * FROM asset_snapshots ORDER BY snapshot_at DESC LIMIT 5;
  → 빈 결과: Celery beat 로그 확인
  → 오래된 데이터만: worker 중단 여부 확인
```

---

## 4. 연결 패널 현황

| 패널 | 유형 | 어댑터 | 데이터 소스 | 테이블 구조 |
|------|------|--------|-------------|-------------|
| Binance | Futures (CCXT) | `binance.py` | DB Position/Trade | 8열 선물 |
| Bitget | Futures (CCXT) | `bitget.py` | DB Position/Trade | 8열 선물 |
| UpBit | Spot (CCXT) | `upbit.py` | DB Position/Trade | 8열 통일 구조 (현물형 데이터 매핑) |
| 한국투자증권 | Spot (httpx) | `kis.py` | DB Position/Trade | 8열 국내주식 |
| 키움증권 | Spot (httpx) | `kiwoom.py` | DB Position/Trade | 8열 국내주식 |
| 총 자산 통계 | Aggregate | — | DB AssetSnapshot | 8행 시간 창 |

---

## 5. 운영 시작일 관찰 로그

```
2026-03-23 17:24 KST — Track 4 GO 확정
  [✅] clock 정상 표시: 현재 2026년 03월 23일 17시 24분 32초 월요일
  [✅] preview server 단독 (PID 충돌 해소)
  [✅] /dashboard 200 OK
  [✅] 거버넌스 바 정상: Governance: NORMAL
  [✅] 테스트 497 passed (보호축 미침해)
  [⏳] snapshot 미적재 (Celery beat 미시작 — migration 후 활성화)
  [⏳] 12h 창: 미집계 (min_samples=2 미충족)
  [⏳] alembic upgrade head 실행 대기

2026-03-23 17:39 KST — 운영 관찰 1회차
  [✅] /dashboard 200 OK (경로: /dashboard)
  [✅] clock 정상: 현재 2026년 03월 23일 17시 39분 49초 월요일
  [✅] L0 거버넌스 바 정상: Governance: NORMAL, orphan: -, evidence: -
  [✅] 6개 패널 렌더 정상 (KIS, Binance, Bitget, Kiwoom, UpBit, 총자산통계)
  [✅] READ-ONLY 배지 표시
  [✅] 데이터 조회 중... 표시 (DB 미연결 상태 — 정상 fallback)
  [⏳] snapshot 미적재 (Celery beat / DB 미기동 — 인프라 대기)
  [⏳] 12h 창: 미집계 (snapshot 누적 전)
  [ℹ️] 이상 없음 — 인프라 기동 후 자동 해소 예상
```
