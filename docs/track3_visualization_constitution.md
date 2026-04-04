# K-Dexter 시각화 헌법 — Track 3 수렴 완료본

> **이 문서는 기존 시각화 헌법 v1(`docs/VISUALIZATION_CONSTITUTION.md`)의 수렴 문서이며 새 규칙을 창작하지 않는다.**

```
문서 유형    : Track 3 시각화 헌법 수렴본 (독립 완료본)
트랙        : Track 3 — 시각화 헌법 문서
원본        : docs/VISUALIZATION_CONSTITUTION.md (v1, 2026-03-22)
baseline    : governance-go-baseline (7eb9ad8)
수렴일      : 2026-03-23
성격        : 기존 확정 규칙의 수렴·종결 문서. 새 정책을 제정하지 않는다.
```

---

## 1. 문서 지위 / 목적

> 출처: 원본 서두

본 문서는 Track 3(시각화 헌법)의 독립 완료본이다.

- 원본 `docs/VISUALIZATION_CONSTITUTION.md` v1에서 확정된 규칙만을 수렴하여 정리한다
- 새 규칙, 새 번호, 새 금지 조항, 새 강화 표현을 추가하지 않는다
- Track 4(L0/L1 운영 대시보드)는 본 헌법의 규칙을 구현한 결과물이며, 구현 세부는 Track 4 문서에 위임한다

시각화의 역할:
- 거버넌스 기록을 읽기 전용으로 표현
- 상태 분류를 의미 고정된 색상/아이콘으로 매핑
- evidence 간 링크(PRE→POST/ERROR)를 시각적으로 연결

시각화가 하지 않는 것:
- 거버넌스 판정을 변경하거나 재해석
- evidence를 삭제하거나 필터링하여 은폐
- 통계 집계 시 decision_code 의미를 재분류

---

## 2. 최상위 원칙

> 출처: 원본 §1.1

| # | 목적 | 설명 |
|---|------|------|
| V-01 | 운영자 오판 방지 | BLOCKED를 성공으로, FAILED를 단순 차단으로 오독하는 UI를 금지한다 |
| V-02 | 거버넌스 상태 즉시 판독 | 운영자가 화면 첫 진입 3초 이내에 현재 거버넌스 상태를 파악할 수 있어야 한다 |
| V-03 | evidence 추적성 보존 | 모든 시각 요소는 `governance_evidence_id`로 원본 evidence까지 역추적 가능해야 한다 |
| V-04 | 민감정보 비노출 | raw prompt, response, reasoning 원문, traceback 전문은 어떤 환경에서도 화면에 표시하지 않는다 |
| V-05 | production/debug 시각 경계 유지 | production에서는 debug 전용 정보의 존재 자체를 암시하지 않는다 |

---

## 3. 상태 의미 고정

> 출처: 원본 §2

### 3.1 DecisionCode 시각 매핑

| decision_code | 의미 | 색상 계열 |
|---------------|------|-----------|
| `ALLOWED` | 정상 허용 | 녹색 (green) |
| `BLOCKED` | 정책 차단 | 주황/황색 (amber) |
| `FAILED` | 시스템 이상 | 적색 (red) |

불변 규칙:
- `BLOCKED`와 `FAILED`는 시각적으로 구분되어야 한다. 같은 색상/아이콘 사용 금지
- `BLOCKED`를 녹색 계열로 표시하는 것은 금지
- `FAILED`를 주황 계열로 표시하는 것은 금지
- `ALLOWED`를 주황/적색으로 표시하는 것은 금지

### 3.2 PhaseCode 시각 매핑

| phase_code | 의미 | 타임라인 위치 |
|------------|------|-------------|
| `PRE` | 사전 검사 | 타임라인 좌측/상단 |
| `POST` | 사후 기록 | 타임라인 우측/하단 |
| `ERROR` | 오류 기록 | POST와 동일 위치, 별도 스타일 |

불변 규칙:
- PRE→POST 또는 PRE→ERROR 링크는 항상 시각적으로 연결되어야 한다
- POST와 ERROR가 동시에 존재하는 bundle은 없다 (상호 배타)
- PRE만 존재하고 POST/ERROR가 없는 경우 = orphan (별도 표시)

### 3.3 CheckStatus 시각 매핑

| status | 의미 | 시각 표현 |
|--------|------|-----------|
| `passed` | 실행 완료 — 통과 | 녹색 체크 |
| `failed` | 실행 완료 — 실패 | 적색 X |
| `not_applicable` | 해당 스코프 아님 | 회색 대시 |
| `deferred` | 후순위로 연기 | 회색 시계 |
| `unimplemented` | 미구현 | 회색 물음표 |

불변 규칙:
- `not_applicable`을 `passed`처럼 녹색으로 표시하는 것은 금지
- `deferred`를 `passed`처럼 녹색으로 표시하는 것은 금지

### 3.4 ReasonCode 표시 규칙

| reason_code | 표시 문구 (운영자용) | 심각도 표시 |
|-------------|---------------------|------------|
| `GOV-NONE` | 정상 통과 | 정보 |
| `GOV-LOCKDOWN-BLOCK` | 전역 LOCKDOWN 차단 | 긴급 |
| `GOV-QUARANTINE-BLOCK` | 전역 QUARANTINE 차단 | 경고 |
| `GOV-FORBIDDEN-ACTION` | 금지 행위 감지 | 긴급 |
| `GOV-MISSING-SYMBOL` | 필수값 누락: symbol | 경고 |
| `GOV-MISSING-EXCHANGE` | 필수값 누락: exchange | 경고 |
| `GOV-COMPLIANCE-D002` | D-002 준수 실패 | 경고 |
| `GOV-COMPLIANCE-D009` | D-009 준수 실패 | 경고 |
| `GOV-POST-EXCEPTION` | LLM 실행 중 예외 | 긴급 |

---

## 4. 필수 노출 항목

> 출처: 원본 §3.1

| # | 항목 | 소스 | 표시 형태 | 근거 |
|---|------|------|-----------|------|
| E-01 | `governance_evidence_id` | `AgentResponse.governance_evidence_id` | 클릭 가능 ID (추적용) | V-03 |
| E-02 | `decision_code` | artifact.decision_code | 색상 코딩된 배지 | V-01 |
| E-03 | `reason_code` | artifact.reason_code | 운영자용 표시 문구 | V-01 |
| E-04 | `phase_code` | artifact.phase | PRE/POST/ERROR 타임라인 | V-03 |
| E-05 | `coverage_summary` | artifact.coverage_meta | 실행/미실행/연기 건수 | 검사 범위 투명성 |
| E-06 | `orphan_count` | debug endpoint 계산 | 숫자 배지 (0이면 녹색, >0이면 주황) | V-01 |

---

## 5. 비노출 항목 (절대 금지)

> 출처: 원본 §3.2

| # | 항목 | 금지 이유 | 대체 표시 |
|---|------|-----------|-----------|
| N-01 | raw prompt 원문 | 민감정보 노출 (V-04) | `prompt_hash` (해시값만) |
| N-02 | raw response 원문 | 민감정보 노출 (V-04) | 없음 |
| N-03 | reasoning 원문 | 민감정보 노출 (V-04) | `reasoning_hash` (해시값만) |
| N-04 | `error_class` | 시스템 내부 구조 노출 | `decision_code=FAILED` 표시만 |
| N-05 | `error_severity` | 시스템 내부 분류 노출 | `phase_code=ERROR` 표시만 |
| N-06 | `exception_message` | 스택 정보 노출 가능 | `traceback_hash` (해시값만) |
| N-07 | `prompt_hash` 원문 추적 가능 정보 | 해시 역추적 금지 | 해시값 표시는 허용, 원문 복원 UI 금지 |

---

## 6. 환경별 노출 규칙

> 출처: 원본 §4

### 6.1 Production 환경

조건: `settings.is_production == True`

| 규칙 | 상세 |
|------|------|
| evidence endpoint | 존재하지 않음 (라우트 미등록 → 404) |
| debug 정보 암시 | 금지 — "debug 모드에서 확인 가능" 같은 문구 표시 금지 |
| 표시 가능 항목 | `AgentResponse` 필드만 (governance_evidence_id, success, confidence) |
| orphan_count | 표시 불가 (endpoint 자체가 없음) |
| coverage_summary | 표시 불가 (endpoint 자체가 없음) |
| 장애 표시 | `decision_code`와 `reason_code`만 |

### 6.2 Non-production / Debug 환경

조건: `settings.debug == True AND settings.is_production == False`

| 규칙 | 상세 |
|------|------|
| evidence endpoint | `GET /api/v1/agents/governance/evidence` 사용 가능 |
| 표시 가능 항목 | E-01~E-06 전체 + hash 값 |
| orphan_count | 표시 (0이면 녹색, >0이면 주황 배지) |
| coverage_summary | 10-check 상태 분류 표시 가능 |
| raw 원문 | 여전히 금지 (debug에서도 N-01~N-07 유지) |

### 6.3 환경 판별 시각 표시

| 환경 | 배너 색상 | 배너 문구 |
|------|-----------|-----------|
| production | 없음 (배너 자체 미표시) | — |
| non-production (debug) | 파란색 | `[DEBUG] Non-production governance view` |
| governance_enabled=False | 적색 경고 | `[WARNING] Governance disabled` |

---

## 7. 시각화 금지 조항

> 출처: 원본 §6

### 7.1 시각 의미 오염 금지

| # | 금지 조항 | 위반 예시 | 근거 |
|---|-----------|-----------|------|
| P-01 | BLOCKED를 성공처럼 보이게 하는 UI 금지 | BLOCKED를 녹색으로 표시, "처리 완료" 문구 사용 | V-01 |
| P-02 | FAILED를 단순 차단처럼 축소하는 UI 금지 | FAILED를 주황색으로 표시, BLOCKED와 같은 아이콘 사용 | V-01 |
| P-03 | ALLOWED/BLOCKED/FAILED를 합산하여 "전체 건수"로만 표시하는 것 금지 | "총 처리: 150건" (분류 없음) | V-01 |
| P-04 | orphan_count를 숨기거나 0으로 고정 표시하는 것 금지 | orphan_count 영역 자체를 제거, 또는 항상 0 표시 | V-01 |
| P-05 | production에서 debug route의 존재를 암시하는 것 금지 | "상세 정보는 debug 모드에서 확인", 비활성 버튼 표시 | V-05 |
| P-06 | evidence_id 없이 decision_code만 표시하는 것 금지 | "BLOCKED" 배지만 표시하고 추적 링크 없음 | V-03 |
| P-07 | raw 원문을 "더보기" 버튼으로 접근 가능하게 하는 것 금지 | "reasoning 전문 보기" 링크, 확장 패널 | V-04 |
| P-08 | PRE evidence만 있는 상태를 정상 완료처럼 표시하는 것 금지 | PRE만 있는 건을 "완료" 상태로 표시 | V-03 |

### 7.2 환경 경계 위반 금지

| # | 금지 조항 | 위반 예시 |
|---|-----------|-----------|
| P-09 | production에서 evidence detail(L2) 접근 경로 제공 금지 | 숨겨진 URL, 관리자 전용 링크 |
| P-10 | production에서 hash 값 표시 금지 (hash도 debug 전용) | prompt_hash를 production 응답에 포함 |
| P-11 | debug 환경에서 production 배너를 표시하여 혼동 유발 금지 | debug인데 배너 없음 (production처럼 보임) |

---

## 8. 대시보드 계층 정의

> 출처: 원본 §5

### 8.1 L0 — 운영 배너 (Emergency Banner)

용도: 전역 거버넌스 상태를 화면 최상단 1줄로 즉시 전달

| 상태 | 배너 색상 | 배너 문구 | 조건 |
|------|-----------|-----------|------|
| 정상 | 녹색 | `Governance: NORMAL` | SecurityState=NORMAL, orphan_count=0 |
| 경고 | 주황 | `Governance: RESTRICTED` | SecurityState=RESTRICTED |
| 격리 | 적색 | `Governance: QUARANTINED — sandbox only` | SecurityState=QUARANTINED |
| 잠금 | 적색 점멸 | `Governance: LOCKDOWN — human override required` | SecurityState=LOCKDOWN |
| orphan 감지 | 주황 | `Governance: NORMAL (orphan: N)` | orphan_count > 0 |

규칙:
- L0 배너는 항상 표시 (숨기기/접기 금지)
- 상태가 NORMAL이 아닌 경우 자동으로 확장 (운영자 클릭 불필요)
- production에서는 SecurityState 기반 배너만 표시 (orphan_count 미표시)

### 8.2 L1 — 상태 보드 (Status Board)

용도: 최근 거버넌스 판정의 분포와 추이를 요약 표시

| 영역 | 내용 | 표시 형태 |
|------|------|-----------|
| Decision 분포 | ALLOWED / BLOCKED / FAILED 건수 | 3칸 카드 (색상 코딩) |
| Phase 분포 | PRE-only(orphan) / PRE+POST / PRE+ERROR 건수 | 3칸 카드 |
| 최근 N건 | 시간순 evidence 목록 | 테이블 |
| orphan 경고 | orphan_count > 0이면 경고 배지 | 주황 배지 + 건수 |
| 10-check 요약 | coverage_summary | 수평 바 차트 |

규칙:
- BLOCKED와 FAILED 카드는 별도 카드로 표시 (합산 금지)
- orphan_count가 0이어도 표시 영역은 유지 (값만 0으로 표시)
- debug 환경에서만 표시 (production에서는 L0만 표시)

### 8.3 L2 — 감사 상세 (Audit Detail)

용도: 개별 evidence bundle의 상세 정보 조회 (evidence_id 클릭 시 진입)

| 영역 | 내용 |
|------|------|
| Bundle 헤더 | evidence_id, created_at, actor, action |
| Phase 타임라인 | PRE → POST 또는 PRE → ERROR 링크 |
| decision_code | ALLOWED/BLOCKED/FAILED 색상 배지 |
| reason_code | GOV-* 코드 + 운영자용 문구 |
| check_matrix | 10-check 각 항목의 status + detail |
| coverage_meta | 실행/미적용/연기/미구현 건수 |
| 링크 정보 | pre_evidence_id (역추적 링크) |
| hash 정보 | prompt_hash, reasoning_hash, traceback_hash (읽기 전용) |

규칙:
- L2는 debug 환경에서만 접근 가능
- production에서 L2로의 링크/버튼/경로 자체가 존재하지 않아야 한다
- raw 원문은 L2에서도 표시 금지 (N-01~N-07 유지)

---

## 9. 시각 검수 규칙

> 출처: 원본 §7

### 9.1 의미 분리 검수

| # | 검수 항목 | 기대 결과 |
|---|-----------|-----------|
| C-01 | BLOCKED/FAILED 시각 분리 | 색상, 아이콘, 문구가 모두 다름 |
| C-02 | ALLOWED/BLOCKED 시각 분리 | 즉시 구분 가능 (3초 이내) |
| C-03 | CheckStatus 5종 시각 분리 | 5개 모두 다른 시각 표현 |

### 9.2 추적성 검수

| # | 검수 항목 | 기대 결과 |
|---|-----------|-----------|
| C-04 | evidence_id 추적 가능 | 해당 bundle 상세(L2)로 이동 |
| C-05 | PRE→POST 링크 표시 | pre_evidence_id가 클릭 가능 링크로 표시 |
| C-06 | PRE→ERROR 링크 표시 | pre_evidence_id가 클릭 가능 링크로 표시 |
| C-07 | orphan 식별 | PRE-only 건이 별도 표시됨 |

### 9.3 비노출 검수

| # | 검수 항목 | 기대 결과 |
|---|-----------|-----------|
| C-08 | raw prompt 비노출 | prompt 원문 표시 없음 |
| C-09 | raw response 비노출 | response 원문 표시 없음 |
| C-10 | reasoning 비노출 | reasoning 원문 표시 없음 |
| C-11 | exception_message 비노출 | 메시지 원문 없음, hash만 표시 |
| C-12 | production raw 비노출 | hash 값 포함 어떤 내부 정보도 없음 |

### 9.4 환경 경계 검수

| # | 검수 항목 | 기대 결과 |
|---|-----------|-----------|
| C-13 | production L2 접근 불가 | 404 Not Found |
| C-14 | production debug 암시 없음 | debug/상세/evidence 링크 없음 |
| C-15 | debug 환경 배너 표시 | 파란색 `[DEBUG]` 배너 표시 |
| C-16 | orphan_count 표시 | orphan_count 영역 존재 (0이어도 표시) |

---

## 10. Track 4와의 연결

> 출처: 원본 §10 + Track 4 검수 문서(`docs/DASHBOARD_INSPECTION_REPORT.md`)

Track 4(L0/L1 운영 대시보드)는 본 헌법(Track 3)의 규칙을 구현한 결과물이다.

Track 4 검수 보고서(`docs/DASHBOARD_INSPECTION_REPORT.md`)에서 확인된 준수 사항:

| 헌법 금지 조항 | Track 4 준수 여부 | 증적 |
|--------------|-----------------|------|
| P-01: BLOCKED를 녹색 표시 금지 | 준수 | `--blocked-text: #f59e0b` (amber), T-D04-b |
| P-02: FAILED를 주황 표시 금지 | 준수 | `--failed-text: #ef4444` (red), T-D04-c |
| P-04: orphan_count 숨김 금지 | 준수 | L0 배너 항상 표시, T-D05-a~c |
| P-05: production debug 암시 금지 | 준수 | `{% if debug_mode %}` 조건부, T-D01-e |
| P-07: raw 원문 접근 금지 | 준수 | 원문 표시 UI 없음, T-D06-a~f |

구현 세부 사항은 Track 4 문서에 위임한다:
- `docs/DASHBOARD_GUIDE.md` — 대시보드 운영 가이드
- `docs/DASHBOARD_INSPECTION_REPORT.md` — 헌법 조항 대조 검수본
- `docs/track4_ops_checklist.md` — Track 4 종료 선언 및 운영 체크리스트

---

## Baseline 보호축 준수 확인

> 출처: 원본 §9

이 문서는 아래 GO baseline 보호축을 변경하지 않으며 준수한다.

| 보호축 | 준수 방식 |
|--------|----------|
| API "metadata" 하위 호환 유지 | 시각화는 API 계약을 변경하지 않음. 읽기 전용 표현만 |
| rejection → BLOCKED 의미 유지 | DecisionCode 시각 매핑에서 BLOCKED = 주황, ALLOWED와 명확 분리 |
| execute governance 테스트 4건 보호 | 시각화 문서는 테스트를 추가/삭제/수정하지 않음 |
| 3대 merge gate 보호 | 시각화 문서는 pytest/governance/constitution 게이트를 변경하지 않음 |
