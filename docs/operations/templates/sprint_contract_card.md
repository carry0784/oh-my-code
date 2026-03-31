# Sprint Contract Card — [CARD-ID]

> **작성자**: Claude Code A
> **날짜**: YYYY-MM-DD
> **등급**: Level A / B / C
> **상태**: DRAFT / ACTIVE / COMPLETE / CANCELLED

---

## 0. 연결

| Field | Value |
|-------|-------|
| 상위 문서 | DOC-L2-HARNESS (Claude Code A/B/C Harness Constitution) |
| 관련 봉인 | (해당 봉인 문서 ID, 없으면 N/A) |
| 선행 작업 | (선행 Sprint Contract Card ID, 없으면 N/A) |

---

## 1. 작업명

> (한 문장으로 정의)

---

## 2. 목표

> (달성 조건 1~3줄. "무엇이 완료인가"를 명확히 서술)

---

## 3. 범위

| # | 대상 파일/모듈 | 변경 유형 | 보호 여부 |
|---|--------------|----------|----------|
| 1 | | NEW / MODIFY / DELETE | YES / NO |
| 2 | | | |

---

## 4. 비범위 (변경 금지)

| # | 대상 | 이유 |
|---|------|------|
| 1 | | |
| 2 | | |

> **규칙**: 비범위 파일을 수정하면 Claude Code C가 자동 BLOCK 판정한다.

---

## 5. 완료 기준

- [ ] 기준 1: (구체적 조건)
- [ ] 기준 2: (구체적 조건)
- [ ] 회귀 테스트 0 failures (전체 스위트)
- [ ] 봉인 위반 0 (해당 봉인 문서 대조)
- [ ] 문서/코드 일치 (변경에 따른 문서 갱신 완료)

---

## 6. 금지 조항

| # | 금지 | 이유 |
|---|------|------|
| 1 | | |
| 2 | | |

> **규칙**: 금지 조항 위반은 테스트 PASS 여부와 무관하게 BLOCK 사유가 된다.

---

## 7. 테스트 기준

| 축(axis) | 최소 테스트 수 | 검증 대상 |
|----------|--------------|----------|
| | | |

| 회귀 검증 | 대상 |
|----------|------|
| Control Total | (현재 기준 수) |
| Full Suite | PASS 필수 (기존 실패 제외) |

---

## 8. 출력 형식

Claude Code B가 제출해야 할 산출물:

| # | 산출물 | 형식 |
|---|--------|------|
| 1 | 변경 보고서 | DOC-L2-HARNESS §4.3 형식 |
| 2 | | |

---

## 9. Claude Code C 검수 중점

Claude Code C가 특히 확인해야 할 사항:

| # | 중점 검수 항목 | 이유 |
|---|--------------|------|
| 1 | | |
| 2 | | |

---

## 10. 등급별 특기 사항

### Level A 전용
- Claude Code C 간단 검수 (평가표 생략 가능, 판정만 필수)

### Level B 전용
- Claude Code C 정식 검수 (평가표 필수)

### Level C 전용
- Claude Code C 강검수 (평가표 필수, 봉인 대조 필수)
- 재작업 루프 최대 3회
- 인간 최종 승인 필수

---

> Template version: 1.0 (2026-03-30)
> Source: DOC-L2-HARNESS (claude-code-harness-constitution.md)
