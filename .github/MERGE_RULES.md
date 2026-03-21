# OPS-GATE-003: PR Merge 강제 검문 규칙

> 본 문서는 운영 통제 규칙이며, 헌법(docs/aos-constitution/) 의미를 변경하지 않는다.
> OPS-BASELINE(2026-03-21), OPS-GATE-001(PR 사전 점검), OPS-GATE-002(PR 템플릿)에 이어
> 병합 직전 최종 검문 단계를 정의한다.

---

## 1. Merge Blocker 조건

아래 조건 중 **1개라도 해당**하면 merge를 금지한다.

| ID | 조건 | 판정 기준 |
|----|------|-----------|
| MB-01 | 목적·diff 범위 불일치 | PR 사전 점검의 "목적 1문장"이 실제 diff와 대응하지 않음 |
| MB-02 | 변경 유형 혼합 | baseline/dedup/refactor/feature/fix/docs/ops 중 2개 이상 혼합 |
| MB-03 | 예상 파일·실제 diff 불일치 | 사전 점검의 "예상 변경 파일"과 실제 diff 파일 목록이 불일치 |
| MB-04 | verify 미통과 | `python scripts/verify_constitution.py` 미실행 또는 PASS 아님 (헌법 변경 PR 한정) |
| MB-05 | changelog 누락 | 헌법 문서 변경 시 changelog에 해당 항목이 없음 |
| MB-06 | 의미 변경 선언 누락 | "의미 변경 없음/있음" 선언이 PR 본문에 없음 |
| MB-07 | base branch 부적합 | 운영본 변경인데 base가 master가 아님, 또는 목적에 맞지 않는 base 사용 |

## 2. Merge Approve 조건

아래 조건을 **모두 충족**해야 merge를 승인한다.

| ID | 조건 | 확인 방법 |
|----|------|-----------|
| MA-01 | diff 범위 일치 | "목적 1문장"과 실제 diff가 1:1 대응 |
| MA-02 | verify PASS | `verify_constitution.py` PASS (헌법 변경 PR) 또는 해당 없음 확인 |
| MA-03 | changelog 준수 | APPEND_ONLY 규칙 유지, 변경 유형 코드 기입 |
| MA-04 | Reviewer Focus 존재 | PR 본문에 리뷰 집중 영역이 명시됨 |
| MA-05 | 사전 점검 기입 완료 | PR 템플릿 8항목 전체 기입 |
| MA-06 | 변경 파일 허용 오차 | 실제 diff 파일이 예상 목록 대비 +2개 이내 |
| MA-07 | Merge 직전 게이트 기입 | PR 하단 "Merge 직전 게이트" 3항목(예상/실제 diff, verify, merge 가능 여부) 전체 기입, merge 가능 여부 = `가능`. 목적·변경 유형은 상단 사전 점검을 참조하며 재기입 불요. |

> **MA-07 위반 시**: "Merge 직전 게이트"가 미기입이거나 merge 가능 여부가 `불가`인 PR은 MB-01과 동일하게 merge를 금지한다.

## 3. PR Close / Reopen 규칙

### 3.1 Close 사유

| 사유 | 조치 |
|------|------|
| 범위 초과 | close 후 목적별 브랜치로 분리 재제출 |
| 목적 혼합 | close 후 변경 유형 단위로 분리 재제출 |
| base branch 오류 | close 후 올바른 base로 재생성 |

### 3.2 Close 코멘트 형식

```
## Close 사유: [범위 초과 / 목적 혼합 / base 오류]

- 위반 Blocker: MB-xx
- 실제 diff: N파일, +X/-Y
- 예상 diff: M파일
- 재구성 계획: [분리 방식 기술]
```

### 3.3 Reopen 금지

close된 PR은 reopen하지 않는다. 원인 해소 후 새 PR로 재제출한다.

## 4. Exception 규칙

### 4.1 예외 허용 조건

| 유형 | 허용 조건 |
|------|-----------|
| hotfix | 운영 장애·보안 취약점 등 긴급 수정 |
| emergency patch | verify 스크립트 자체 오류로 PASS 불가 시 |

### 4.2 예외 시 필수 요건

| 요건 | 내용 |
|------|------|
| reason code | `HOTFIX-yyyy-mm-dd-nn` 또는 `EMERGENCY-yyyy-mm-dd-nn` |
| 추가 승인 | PR 본문에 예외 사유 명시, 리뷰어 1인 이상 명시적 승인 |
| 사후 검증 | 병합 후 24시간 이내 verify PASS 확인 및 changelog 보완 |
| 후속 PR | 예외 사항을 정규화하는 후속 PR을 72시간 이내 제출 |

## 5. Post-Merge 규칙

### 5.1 브랜치 정리

| 대상 | 기준 |
|------|------|
| 원격 head branch | merge 완료 후 즉시 삭제 |
| 로컬 head branch | merge 확인 후 삭제 |
| base branch | 삭제 금지 (main, master는 영구 유지) |

### 5.2 changelog 기록

- 헌법 문서 변경: 변경 유형 코드와 함께 필수 기록
- ops 문서 변경: OPS-GATE-xxx 코드로 기록
- src/tests 변경: changelog 기록 불요 (헌법 범위 밖)

### 5.3 최종 verify

- merge 후 base branch에서 `verify_constitution.py` 재실행
- PASS 확인 후 운영 기준선 갱신 여부 판단

### 5.4 운영 기준선 갱신 조건

- 헌법 문서 구조 변경 시: changelog에 OPS-BASELINE 갱신 기록
- ops 규칙 추가 시: changelog에 OPS-GATE-xxx 기록 (기준선 갱신 불요)
- src/tests 변경 시: 기준선 갱신 불요
