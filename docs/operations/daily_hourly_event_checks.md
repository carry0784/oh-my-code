# Daily / Hourly / Event Checks
## 자동 점검 명세 v1.0

**Document Path:** `docs/operations/daily_hourly_event_checks.md`
**Parent Authority:** `Operating Constitution v1.0`
**Status:** ACTIVE
**Scope:** Daily/Hourly/Event 3종 자동 점검의 항목·결과 등급·산출물 세부화
**역참조:** 제23조~제31조

---

## 제약 선언

- 본 문서는 상위 헌법의 구현 세부화 문서이다.
- 본 문서는 새 권한을 추가하지 않는다.
- 본 문서는 자동 실행 권한을 부여하지 않는다.
- 본 문서는 상위 헌법과 충돌해서는 안 된다.
- 자동 점검은 복구 권한, 승격 권한을 직접 가지지 않는다.

---

## 1. 목적 (제23조)

자동 점검은 반복 운영 확인을 표준화하고, 증거를 남기며, 사람의 수동 편차를 제거하기 위한 통제 장치다.

---

## 2. 원칙 (제24조)

| 원칙 | 설명 |
|------|------|
| **Check, Don't Repair** | 점검만 수행하며, 복구를 실행하지 않는다 |
| **Evidence Mandatory** | 모든 점검은 증거를 남겨야 한다 |
| **Event-Aware** | 이벤트 발생 시 즉시 점검을 수행한다 |
| **Fail-Closed Reporting** | 점검 불능 시 실패로 보고한다 |
| **Promotion Support Only** | 승격 판단의 보조 자료로만 사용한다 |

---

## 3. 점검 종류 (제25조)

| 종류 | 주기 | 용도 |
|------|------|------|
| Daily Check | 매일 1회 | 시스템 기본 상태 확인 |
| Hourly Check | 매시간 1회 | 연속 운영 상태 감시 |
| Event Check | 이벤트 발생 시 즉시 | 복구/승격 전 차단 판단 |

---

## 4. Daily Check (제26조)

다음 9개 항목을 점검해야 한다.

1. APP_ENV = production
2. Phase = prod
3. `/health` = 200
4. `/status` = 200
5. `/dashboard` = 200
6. 로그 증가 여부
7. evidence 생성 여부
8. crash loop 부재
9. monitoring active 여부

---

## 5. Hourly Check (제27조)

다음 7개 항목을 점검해야 한다.

1. 최근 API poll 정상 여부
2. stale data 여부
3. snapshot age
4. latency 상태
5. alert backlog
6. 로그/디스크 이상 증가
7. recent warning/critical 변화

---

## 6. Event Check (제28조)

다음 6개 시점에 즉시 수행해야 한다.

1. 프로세스 재시작 직후
2. DB 재연결 직후
3. API 복구 직후
4. LOCKDOWN 해제 직전
5. 실거래 승격 직전
6. 자본 확대 직전

Event Check는 복구 전/승격 전 차단 판단 용도로 사용한다.

---

## 7. 결과 등급 (제29조)

자동 점검 결과는 다음 4등급으로 제한한다.

| 등급 | 의미 |
|------|------|
| `OK` | 모든 항목 통과 |
| `WARN` | 일부 항목 경고, 운영 가능 |
| `FAIL` | 점검 실패, 조치 필요 |
| `BLOCK` | 승격/복구/확대 차단 |

---

## 8. 산출물 (제30조)

모든 자동 점검은 반드시 다음 산출물을 남겨야 한다.

1. **콘솔 요약** — 점검 결과 즉시 확인용
2. **파일 evidence** — 영구 기록용
3. **필요 시 알림 전송** — WARN 이상 시

### Evidence 최소 필드

| 필드 | 설명 |
|------|------|
| check_type | Daily / Hourly / Event |
| timestamp | 점검 수행 시각 (ISO 8601) |
| result | OK / WARN / FAIL / BLOCK |
| items | 각 항목별 결과 |
| failures | 실패 항목 상세 |
| evidence_id | 고유 식별자 |

---

## 9. 금지 사항 (제31조)

1. 상태 임의 수정 금지
2. 거래 재개 자동 실행 금지
3. 자본 확대 자동 실행 금지
4. evidence 누락 상태 PASS 처리 금지
5. 실패 은폐 금지

추가 제약:
- 점검 결과만으로 자동 승격 실행 금지
- 점검 결과만으로 LOCKDOWN 해제 허용 금지
- 점검 불능 또는 evidence 누락 시 OK 처리 금지
- 점검은 복구 권한, 승격 권한을 직접 가지지 않는다.
