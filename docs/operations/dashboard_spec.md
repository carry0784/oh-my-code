# Dashboard Specification
## 운영 대시보드 명세 v1.0

**Document Path:** `docs/operations/dashboard_spec.md`
**Parent Authority:** `Operating Constitution v1.0`
**Status:** ACTIVE
**Scope:** 운영 대시보드 구성·표시 원칙·상태 문구 세부화
**역참조:** 제5조~제13조, 제41조~제42조

---

## 제약 선언

- 본 문서는 상위 헌법의 구현 세부화 문서이다.
- 본 문서는 새 권한을 추가하지 않는다.
- 본 문서는 자동 실행 권한을 부여하지 않는다.
- 본 문서는 상위 헌법과 충돌해서는 안 된다.
- 대시보드는 관찰 표면이며, 통제 표면이 아니다. (제11조)

---

## 1. 목적 (제5조)

운영 대시보드는 시스템의 단일 시각 진실 표면이다.
운영자는 대시보드를 통해 현재 상태, 거래 가능 여부, 정합성 신뢰도, 사고 개입 필요 여부를 즉시 판별할 수 있어야 한다.

대시보드는 **Read-Only** 표면으로 제한한다.
핵심 운영 상태 변경 기능(거래 재개, 자본 확대, 강등 해제, 자동 승인)을 대시보드에 두지 않는다.

---

## 2. 구역 구성 (제6조)

대시보드는 다음 4개 구역으로 구성한다.

| 구역 | 목적 | 역참조 |
|------|------|--------|
| 전역 상태 바 | 시스템 핵심 메타정보 고정 표시 | 제7조 |
| 무결성 패널 | 데이터 정합성 상태 표시 | 제8조 |
| 거래 안전 패널 | 거래 허용·차단 조건 표시 | 제9조 |
| 사고·증거 패널 | 최근 사고 및 증거 기록 표시 | 제10조 |

---

## 3. 전역 상태 바 (제7조)

다음 항목을 고정 표시해야 한다.

| 필드 | 설명 |
|------|------|
| APP_ENV | 현재 환경 (production) |
| Phase | 현재 운영 단계 |
| Enforcement State | 강제 상태 |
| Trading Permission | 거래 허용 여부 |
| Current Server Time | 서버 현재 시각 (절대시간) |
| Last Successful API Poll | 최근 성공 API 폴링 시각 |
| Link Lost Since | 연결 끊김 시점 (해당 시) |
| PROD_LOCK | 프로덕션 잠금 상태 |

---

## 4. 무결성 패널 (제8조)

다음 항목을 표시해야 한다.

- Exchange ↔ DB ↔ Engine ↔ Cache 정합성
- Snapshot age
- Position mismatch
- Open orders mismatch
- Balance mismatch
- Stale data 여부

---

## 5. 거래 안전 패널 (제9조)

다음 항목을 표시해야 한다.

- 허용 자본 비율
- 주문 성공률
- Reject 건수
- Cancel residual 여부
- Latency 상태
- Kill switch 상태
- 현재 거래 모드
- 거래 차단 사유

---

## 6. 사고·증거 패널 (제10조)

다음 항목을 표시해야 한다.

- Incident title
- Severity
- 최초 발생 시각
- 마지막 확인 시각
- 영향 범위
- 자동 조치 결과
- 운영자 조치 필요 여부
- Evidence/Receipt ID

---

## 7. 표시 원칙 (제11조)

1. 초록색은 완전 검증 상태에서만 허용한다.
2. Unknown, Stale, Disconnected, Unverified 상태는 초록색 사용을 금지한다.
3. 거래 가능 상태와 시스템 건강 상태를 단일 배지로 합쳐서는 안 된다.
4. 상태 불명확 시 NORMAL 유지가 아니라 UNVERIFIED 또는 BRAKE 관점으로 전이해야 한다.
5. 대시보드는 통제 표면이 아닌 관찰 표면이어야 하며, 핵심 운영 상태 변경 기능을 두지 않는다.

---

## 8. 허용 상태 문구 (제12조)

허용 상태 문구는 다음으로 제한한다. 이 목록 이외의 상태 문구는 사용할 수 없다.

| 문구 | 의미 |
|------|------|
| `HEALTHY` | 모든 검증 통과, 정상 운영 |
| `DEGRADED` | 일부 항목 경고, 운영 가능하나 주의 필요 |
| `UNVERIFIED` | 상태 확인 불가 또는 미검증 |
| `BRAKE` | 자동 제동 또는 수동 정지 상태 |
| `LOCKDOWN` | 전면 차단, 즉시 운영자 개입 필요 |

---

## 9. 시간 표준 (제13조)

- 모든 핵심 시각 정보는 **절대시간(ISO 8601)**을 우선 표시해야 한다.
- 상대시간("3분 전" 등)은 보조값으로만 병기할 수 있다.
- 절대시간 없이 상대시간만 표시해서는 안 된다.

---

## 10. Ops Score (제41조)

운영 대시보드에는 상태 문구와 별도로 Ops Score를 둘 수 있다.
Ops Score는 다음 4축으로 구성한다.

| 축 | 설명 |
|----|------|
| Integrity | 데이터 정합성 |
| Connectivity | 연결 상태 |
| Execution Safety | 실행 안전성 |
| Evidence Completeness | 증거 완전성 |

**제약:**
- Ops Score는 보조 지표이며, 단독으로 권한을 발생시키지 않는다.
- Ops Score 하락은 BRAKE 권고 근거로 사용할 수 있으나, 자동 차단을 실행하지 않는다.

---

## 11. Trading Authorized 이중 잠금 (제42조)

`System Healthy` 와 `Trading Authorized` 는 반드시 분리 표기해야 한다.

- 시스템이 살아 있어도 거래는 금지될 수 있다.
- 두 상태를 단일 배지로 합쳐서는 안 된다.
- 각각 독립적으로 `true/false` 를 표시해야 한다.

---

## 12. 금지 사항 (제4조, 제11조 종합)

- 대시보드에서 상태 변경 기능을 허용하는 명세 추가 금지
- 거래 재개, 자본 확대, 강등 해제, 자동 승인 기능 금지
- 상위 헌법에 없는 신규 상태 문구 추가 금지
- Unknown/Stale/Unverified 상태를 정상처럼 보이게 하는 낙관 표시 금지
- System Healthy와 Trading Authorized를 단일 배지로 합치는 명세 금지
