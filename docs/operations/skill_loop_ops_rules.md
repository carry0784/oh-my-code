# K-Dexter Skill Loop -- 운영 규칙 봉인본

> 상태: SEALED (2026-03-30)
> 변경 시: GovernanceGate 사전 승인 필수

---

## 1. 상태 판정 기준

### Risk Score 체계

| 항목 | 점수 | 비고 |
|------|------|------|
| test_failed | 1점/건 | 테스트 실패 |
| test_error | 2점/건 | 테스트 에러 |
| import_error | 3점/건 | import 실패 |
| validation_fail | 2점/건 | 시스템 검증 실패 |
| governance_violation | 5점/건 | 거버넌스 위반 |
| governance_warning | 2점/건 | 거버넌스 경고 |
| constitution_fail | 5점/건 | 헌법 정합성 실패 |
| live_path_touch | 3점/건 | 실거래 경로 접촉 |

### Recurrence 가중치

| 분류 | 배수 | 기준 |
|------|------|------|
| FIRST | x1.0 | 최초 발생 |
| REPEAT | x1.5 | 2회 이상 |
| PATTERN | x2.0 | 3회 이상 또는 7일 내 2회 |

### Grade 판정

| Grade | Risk Score | 의미 | 운영 대응 |
|-------|-----------|------|-----------|
| GREEN | 0-2 | 정상 | 모니터링 유지 |
| YELLOW | 3-7 | 경고 | 제한적 자동수정 허용 |
| RED | 8+ | 위험 | 수동 검토 전환 |
| BLOCK | N/A | 차단 | 즉시 중단, override 금지 |

---

## 2. BLOCK 우선 규칙

1. **BLOCK은 점수와 무관하게 최우선 판정이다**
2. governance-checker가 BLOCK을 반환하면 모든 자동수정 즉시 중단
3. BLOCK 상태에서는 어떤 자동 조치도 허용되지 않는다
4. BLOCK 해소는 반드시 사람이 원인을 수정한 후에만 가능하다
5. BLOCK override는 금지된다

---

## 3. AutoFix Policy Engine

### 정책 테이블

| 실패 유형 | FIRST | REPEAT | PATTERN |
|-----------|-------|--------|---------|
| F-IMPORT | ALLOW | ALLOW | MANUAL |
| F-TEST | ALLOW | ALLOW | MANUAL |
| F-LINT | ALLOW | ALLOW | ALLOW |
| F-CONFIG | ALLOW | MANUAL | DENY |
| F-MIGRATION | MANUAL | DENY | DENY |
| F-ENDPOINT | ALLOW | MANUAL | DENY |
| F-GOVERNANCE | DENY | DENY | DENY |
| F-WORKER | ALLOW | MANUAL | DENY |

### 판정 의미

- **ALLOW**: 자동수정 허용
- **MANUAL**: 수정안 제시만, 사람 승인 필요
- **DENY**: 자동수정 금지, 수동 검토 전환

### Pattern 승격 규칙

- PATTERN 3건+: G-MON 경고 승격 (WARN)
- PATTERN 5건+: AutoFix 영구 금지 (BAN)

---

## 4. 운영 루프 규칙

1. AutoFix Loop는 최대 3회 반복 (무한루프 방지)
2. 1회당 수정 대상 최대 3파일 (최소 침습)
3. 전체 DENY이면 즉시 루프 종료
4. BLOCK 감지 시 exit code 2로 종료
5. 매 실행마다 data/failure_patterns.json에 기록

---

## 5. 정기 검증

### 4상태 검증 (scenario-all)

- **주기**: 주 1회 + release 전
- **방법**: `python scripts/inject_failure.py --mode scenario-all`
- **기준**: 4/4 ALL PASS 필수
- **실패 시**: 운영 중단, 원인 분석 후 재검증

### 상태별 검증 항목

| 상태 | 검증 내용 | 기대 결과 |
|------|-----------|-----------|
| GREEN | 실패 0건 | grade=GREEN, risk=0 |
| YELLOW | test+import 실패 | grade=YELLOW, risk=3-7 |
| RED | 복합 실패 | grade=YELLOW/RED, risk=5+ |
| BLOCK | 보호 파일 수정 | judgment=BLOCK, exit=1 |

---

## 6. 금지 사항

1. RED 상태에서 자동수정 강제 실행 금지
2. BLOCK override 금지
3. governance_check.py 규칙 임의 완화 금지
4. risk score threshold 임의 조정 금지
5. PATTERN 기록 삭제 금지
6. grade_history.json 조작 금지

---

## 7. 파일 목록

| 파일 | 역할 | 수정 권한 |
|------|------|-----------|
| scripts/autofix_loop.py | 자기치유 루프 | 거버넌스 승인 필요 |
| scripts/evaluate_results.py | 결과 평가 | 거버넌스 승인 필요 |
| scripts/governance_check.py | 거버넌스 검증 | BLOCK 보호 |
| scripts/validate_system.py | 시스템 검증 | 일반 |
| scripts/run_tests.py | 테스트 실행 | 일반 |
| scripts/inject_failure.py | 장애 주입 (검증용) | 일반 |
| data/grade_history.json | 시계열 기록 | 자동 생성 |
| data/failure_patterns.json | 실패 패턴 | 자동 생성 |
| data/4state_verification.json | 4상태 검증 | 자동 생성 |

---

## 변경 이력

| 날짜 | 변경 | 승인 |
|------|------|------|
| 2026-03-30 | 초판 봉인 | K-Dexter 운영 |
