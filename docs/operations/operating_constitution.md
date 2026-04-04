# Operating Constitution
## 운영 체계 헌법 v1.0

**Document Path:** `docs/operations/operating_constitution.md`
**Status:** ACTIVE
**Scope:** 운영 대시보드 / 알림 시스템 / 자동 점검 / 실거래 안정화
**Principle:** No Evidence, No Power

---

# 목차

- [제1장 총칙](#제1장-총칙)
- [제2장 운영 대시보드 헌법](#제2장-운영-대시보드-헌법)
- [제3장 알림 시스템 헌법](#제3장-알림-시스템-헌법)
- [제4장 자동 점검 헌법](#제4장-자동-점검-헌법)
- [제5장 실거래 안정화 헌법](#제5장-실거래-안정화-헌법)
- [제6장 운영 부칙 및 강화 조항](#제6장-운영-부칙-및-강화-조항)
- [제7장 시행 순서](#제7장-시행-순서)
- [부칙](#부칙)

---

# 제1장 총칙

## 제1조 목적
본 헌법은 운영 단계에서 시스템의 상태 가시성, 경보 전달, 자동 점검, 실거래 안정화 절차를 단일 운영 규범으로 고정하기 위해 제정한다.

## 제2조 적용 범위
본 헌법은 다음 영역에 적용한다.

1. 운영 대시보드
2. 알림 시스템
3. 자동 점검 체계
4. 실거래 안정화 절차

## 제3조 최상위 원칙
운영 체계는 다음 최상위 원칙을 따른다.

- **No Evidence, No Power**
- **Unknown ≠ Normal**
- **Fail-Closed**
- **Read-Only First**
- **Promotion by Evidence**
- **Any Critical Defect Resets Trust**

## 제4조 금지 원칙
다음 행위는 금지한다.

- 증거 없는 정상 판정
- 불명확 상태의 거래 허용
- 운영 표면에서 상태를 낙관적으로 위장하는 표시
- 자동 점검의 임의 복구 및 임의 승격
- 치명 결함 발생 후 무증거 신뢰 유지

---

# 제2장 운영 대시보드 헌법

## 제5조 목적
운영 대시보드는 시스템의 단일 시각 진실 표면이다.
운영자는 대시보드를 통해 현재 상태, 거래 가능 여부, 정합성 신뢰도, 사고 개입 필요 여부를 즉시 판별할 수 있어야 한다.

## 제6조 구성
운영 대시보드는 다음 4개 구역으로 구성한다.

1. 전역 상태 바
2. 무결성 패널
3. 거래 안전 패널
4. 사고·증거 패널

## 제7조 전역 상태 바
전역 상태 바는 다음 항목을 고정 표시해야 한다.

- APP_ENV
- Phase
- Enforcement State
- Trading Permission
- Current Server Time
- Last Successful API Poll
- Link Lost Since
- PROD_LOCK

## 제8조 무결성 패널
무결성 패널은 다음 항목을 표시해야 한다.

- Exchange ↔ DB ↔ Engine ↔ Cache 정합성
- Snapshot age
- Position mismatch
- Open orders mismatch
- Balance mismatch
- Stale data 여부

## 제9조 거래 안전 패널
거래 안전 패널은 다음 항목을 표시해야 한다.

- 허용 자본 비율
- 주문 성공률
- Reject 건수
- Cancel residual 여부
- Latency 상태
- Kill switch 상태
- 현재 거래 모드
- 거래 차단 사유

## 제10조 사고·증거 패널
사고·증거 패널은 다음 항목을 표시해야 한다.

- Incident title
- Severity
- 최초 발생 시각
- 마지막 확인 시각
- 영향 범위
- 자동 조치 결과
- 운영자 조치 필요 여부
- Evidence/Receipt ID

## 제11조 표시 원칙
운영 대시보드는 다음 원칙을 강제한다.

- 초록색은 완전 검증 상태에서만 허용한다.
- Unknown, Stale, Disconnected, Unverified 상태는 초록색 사용을 금지한다.
- 거래 가능 상태와 시스템 건강 상태를 단일 배지로 합쳐서는 안 된다.
- 상태 불명확 시 NORMAL 유지가 아니라 UNVERIFIED 또는 BRAKE 관점으로 전이해야 한다.
- 대시보드는 통제 표면이 아닌 관찰 표면이어야 하며, 핵심 운영 상태 변경 기능을 두지 않는다.

## 제12조 상태 문구
허용 상태 문구는 다음으로 제한한다.

- `HEALTHY`
- `DEGRADED`
- `UNVERIFIED`
- `BRAKE`
- `LOCKDOWN`

## 제13조 시간 표준
모든 핵심 시각 정보는 절대시간을 우선 표시해야 하며, 상대시간은 보조값으로만 병기할 수 있다.

---

# 제3장 알림 시스템 헌법

## 제14조 목적
알림 시스템은 로그 전달 수단이 아니라 운영 개입 유도 장치다.
알림은 위험을 즉시 전달하고, 경보 피로를 억제하며, 조치 방향을 명확히 제시해야 한다.

## 제15조 등급 체계
알림 등급은 다음 4단계로 제한한다.

- INFO
- WARNING
- CRITICAL
- PROMOTION

## 제16조 INFO
INFO는 즉시 개입이 필요하지 않으나 운영상 의미가 있는 상태를 알린다.

예:
- Daily Check OK
- Recovery complete
- 정상 상태 회복
- Observation 통과

## 제17조 WARNING
WARNING은 상태 악화가 감지되었으나 치명 차단 전 단계인 경우에 발송한다.

예:
- Snapshot stale
- API poll 연속 실패
- Latency 악화
- 부분 mismatch
- Evidence 생성 지연

## 제18조 CRITICAL
CRITICAL은 즉시 운영자 개입이 필요한 치명 상태에 발송한다.

예:
- LOCKDOWN 진입
- 거래 권한 차단
- 정합성 붕괴
- Ghost order 의심
- Kill switch 발동
- 무증거 거래 허용 시도

## 제19조 PROMOTION
PROMOTION은 승격, 보류, 강등, 자본 확대·축소 판단에 발송한다.

## 제20조 표준 필드
모든 알림은 다음 필드를 포함해야 한다.

- 레벨
- 시스템 상태
- 사건명
- 발생 시각
- 영향 범위
- 자동 조치 결과
- 운영자 해야 할 일
- Evidence/Receipt ID

## 제21조 알림 원칙
알림은 다음 원칙을 따른다.

- **Actionable First**
- **Noise Suppression**
- **State Change Driven**
- **Recovery Must Notify**
- **Evidence Attached**

## 제22조 억제 규칙
- 동일 WARNING 반복은 묶음 처리한다.
- 동일 CRITICAL 지속은 상태 변화 시에만 즉시 발송한다.
- 복구 알림은 생략할 수 없다.
- 단순 로그는 알림으로 승격할 수 없다.

---

# 제4장 자동 점검 헌법

## 제23조 목적
자동 점검은 반복 운영 확인을 표준화하고, 증거를 남기며, 사람의 수동 편차를 제거하기 위한 통제 장치다.

## 제24조 원칙
자동 점검은 다음 원칙을 따른다.

- **Check, Don't Repair**
- **Evidence Mandatory**
- **Event-Aware**
- **Fail-Closed Reporting**
- **Promotion Support Only**

## 제25조 점검 종류
자동 점검은 다음 3종으로 구분한다.

1. Daily Check
2. Hourly Check
3. Event Check

## 제26조 Daily Check
Daily Check는 다음 항목을 점검해야 한다.

- APP_ENV = production
- Phase = prod
- `/health` = 200
- `/status` = 200
- `/dashboard` = 200
- 로그 증가 여부
- evidence 생성 여부
- crash loop 부재
- monitoring active 여부

## 제27조 Hourly Check
Hourly Check는 다음 항목을 점검해야 한다.

- 최근 API poll 정상 여부
- stale data 여부
- snapshot age
- latency 상태
- alert backlog
- 로그/디스크 이상 증가
- recent warning/critical 변화

## 제28조 Event Check
Event Check는 다음 시점에 즉시 수행해야 한다.

- 프로세스 재시작 직후
- DB 재연결 직후
- API 복구 직후
- LOCKDOWN 해제 직전
- 실거래 승격 직전
- 자본 확대 직전

## 제29조 결과 등급
자동 점검 결과는 다음 4등급으로 제한한다.

- `OK`
- `WARN`
- `FAIL`
- `BLOCK`

## 제30조 산출물
모든 자동 점검은 반드시 다음 산출물을 남겨야 한다.

- 콘솔 요약
- 파일 evidence
- 필요 시 알림 전송

## 제31조 금지
자동 점검은 다음 행위를 해서는 안 된다.

- 상태 임의 수정
- 거래 재개 자동 실행
- 자본 확대 자동 실행
- evidence 누락 상태 PASS 처리
- 실패 은폐

---

# 제5장 실거래 안정화 헌법

## 제32조 목적
실거래 안정화의 목적은 수익 극대화가 아니라 운영 신뢰도 축적이다.
실거래는 증거 기반으로만 승격되어야 하며, 이상 발생 시 즉시 보수적으로 강등되어야 한다.

## 제33조 원칙
실거래 안정화는 다음 원칙을 따른다.

- **Promotion by Evidence**
- **Minimal Blast Radius**
- **Any Critical Defect Resets Trust**
- **No Silent Expansion**
- **Controlled Degradation**

## 제34조 단계
실거래 안정화 단계는 다음 4단계로 구성한다.

1. Frozen Observation
2. Micro Live
3. Controlled Live
4. Evidence-Based Expansion

## 제35조 Frozen Observation
Frozen Observation 단계에서는 다음을 우선한다.

- 대시보드 신뢰성 검증
- 알림 체계 검증
- 자동 점검 체계 검증
- 사고 탐지/기록 흐름 검증
- 운영 결함 제거

## 제36조 Micro Live
Micro Live 단계는 최소 자본, 최소 전략, 최소 포지션 수로만 운영한다.
이 단계의 목적은 수익이 아니라 실거래 환경에서 통제 체계가 유지되는지 확인하는 것이다.

## 제37조 Controlled Live
Controlled Live 단계는 제한적 범위에서 자본, 주문 수, 거래 시간대를 소폭 확장하여 안정성을 재검증하는 단계다.

## 제38조 Evidence-Based Expansion
Evidence-Based Expansion은 누적 증거가 충분할 때만 수행할 수 있다.
확장은 항상 작은 단위로 점진 수행해야 하며, 별도 심사 없이는 자본 확대를 허용할 수 없다.

## 제39조 승격 조건
다음 조건을 충족한 경우에만 다음 단계 승격을 검토할 수 있다.

- CRITICAL 0
- Ghost order 의심 0
- 핵심 정합성 위반 0
- evidence 누락 0
- 자동 점검 연속 통과
- UNVERIFIED 상태 거래 허용 이력 0
- 운영자 수동 개입 감소 추세

## 제40조 강등 조건
다음 중 하나라도 발생하면 즉시 강등 또는 재관찰을 검토해야 한다.

- CRITICAL 발생
- LOCKDOWN 진입
- Ghost order 의심
- Snapshot mismatch
- evidence 누락
- 복구 미검증 상태 거래 지속
- 대시보드/알림/점검 상태 모순
- 거래 허용 기준 위반

---

# 제6장 운영 부칙 및 강화 조항

## 제41조 Ops Score
운영 대시보드에는 상태 문구와 별도로 Ops Score를 둘 수 있다.
Ops Score는 최소 다음 4축으로 구성한다.

- Integrity
- Connectivity
- Execution Safety
- Evidence Completeness

Ops Score 하락은 BRAKE 권고 근거로 사용한다.

## 제42조 Trading Authorized 이중 잠금
`System Healthy` 와 `Trading Authorized` 는 분리 표기해야 한다.
시스템이 살아 있어도 거래는 금지될 수 있어야 하며, 두 상태를 단일 배지로 합쳐서는 안 된다.

## 제43조 Recovery Preflight 카드
복구 직전에는 별도 Recovery Preflight 카드를 강제한다.
최소 확인 항목은 다음과 같다.

- DB 연결 정상
- Exchange snapshot 확보
- Open orders 재조회
- Position sync 확인
- Last evidence 존재
- Lock reason 해소 확인

## 제44조 Incident Playback
최근 사고는 다음 순서로 재구성 가능한 타임라인을 유지해야 한다.

- 발생
- 탐지
- 자동조치
- 운영자조치
- 종료

이는 회고, 감사, 헌법 위반 추적의 기본 증거로 사용한다.

## 제45조 Promotion Review 양식
실거래 승격은 일반 운영 로그와 분리된 표준 심사 양식으로 관리해야 한다.
최소 포함 항목은 다음과 같다.

- 최근 운영 기간
- CRITICAL 수
- WARNING 추세
- 정합성 위반 수
- 수동 개입 빈도
- 자본 확대 허용 여부

---

# 제7장 시행 순서

## 제46조 적용 순서
운영 체계 적용 순서는 다음과 같다.

1. 대시보드 고정
2. 알림 체계 고정
3. 자동 점검 체계 고정
4. 실거래 안정화 착수

## 제47조 최종 원칙
증거 없는 정상은 허용되지 않는다.
불명확 상태의 거래는 허용되지 않는다.
치명 결함 발생 시 신뢰는 즉시 리셋된다.
운영 승격은 반드시 증거에 의해 통제되어야 한다.

---

# 부칙

## 부칙 제1조 문서 우선성
본 문서는 운영 단계의 상위 규범으로 적용한다.
운영 대시보드, 알림 체계, 자동 점검, 실거래 안정화 관련 세부 문서는 본 헌법과 충돌해서는 안 된다.

## 부칙 제2조 세부 문서 파생
본 헌법을 기준으로 다음 하위 문서를 파생 작성할 수 있다.

- `docs/operations/dashboard_spec.md`
- `docs/operations/alert_policy.md`
- `docs/operations/daily_hourly_event_checks.md`
- `docs/operations/live_stabilization_plan.md`
- `docs/operations/promotion_review_template.md`

## 부칙 제3조 개정 원칙
본 헌법의 개정은 운영 편의가 아니라 운영 통제 강화, 증거 명확화, 사고 예방 강화의 목적 아래에서만 허용한다.

## 부칙 제4조 시행
본 헌법은 승인 즉시 시행한다.
