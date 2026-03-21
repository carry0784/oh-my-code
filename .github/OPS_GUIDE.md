# 운영 게이트 참조 가이드

> 기준선: OPS-GATE-001~006 (2026-03-21 봉인)
> 본 문서는 운영 통제 체계의 참조 안내이며, 헌법 의미를 변경하지 않는다.
>
> **비정의 원칙**: 본 문서는 규칙을 정의하지 않는다. 모든 정의의 원본은
> MERGE_RULES.md(Blocker/Approve 조건)와 pull_request_template.md(기입 양식)이다.
> 본 문서와 정의 원본이 충돌할 경우 정의 원본이 무조건 우선하며,
> 본 문서의 해당 부분은 오류로 간주하고 즉시 정정한다.

---

## 1. 운영 게이트 기준선

아래 게이트가 현재 유효한 운영 통제 기준선이다.

| Gate | 정의 | SSOT 문서 |
|------|------|-----------|
| OPS-BASELINE | 운영 기준선 확정 (main=RC1, master=RC1+DEDUP) | changelog.md |
| OPS-GATE-001 | PR 사전 점검 8항목 | pull_request_template.md §사전 점검 |
| OPS-GATE-002 | PR 템플릿 상단 Merge 차단 문구 | pull_request_template.md §WARNING |
| OPS-GATE-003 | Merge Blocker/Approve/Close/Exception/Post-Merge 규칙 | MERGE_RULES.md |
| OPS-GATE-004 | 리허설 검증 (용어 통일 "merge 금지") | changelog.md (기록만) |
| OPS-GATE-005 | Merge 직전 게이트 5줄→3줄 최적화 | pull_request_template.md §Merge 직전 게이트 |

### SSOT 우선순위

| 순위 | 문서 | 역할 |
|------|------|------|
| 1 | MERGE_RULES.md | Blocker/Approve 조건의 정의 원본 |
| 2 | pull_request_template.md | 운영자 기입 인터페이스 (MERGE_RULES의 실행 양식) |
| 3 | OPS_GUIDE.md (본 문서) | 참조 안내 (정의 권한 없음) |
| 4 | changelog.md | 변경 이력 기록 (APPEND_ONLY) |

충돌 시 상위 순위 문서가 우선한다.

## 2. 참조 관계

```
MERGE_RULES.md (정의 원본)
  ├── MB-01~MB-07  Merge Blocker 조건
  ├── MA-01~MA-07  Merge Approve 조건
  ├── §3 Close/Reopen 규칙
  ├── §4 Exception 규칙
  └── §5 Post-Merge 규칙

pull_request_template.md (기입 양식)
  ├── §WARNING       ← MERGE_RULES MB-01,MB-02 요약
  ├── §사전 점검      ← MERGE_RULES MA-05 이행
  ├── §Summary~Focus ← PR 본문 구조
  └── §Merge 직전 게이트 ← MERGE_RULES MA-07 이행

OPS_GUIDE.md (본 문서, 참조 안내)
  └── 위 두 문서의 사용 순서·참조 관계 안내

changelog.md (이력 기록)
  └── OPS-GATE-xxx 변경 기록
```

## 3. 운영자 절차표

| 단계 | 시점 | 따를 문서 | 핵심 행동 |
|------|------|-----------|-----------|
| 1 | 브랜치 생성 전 | OPS_GUIDE §1 | 변경 유형 판별, 단일 목적 확인 |
| 2 | PR 작성 시 | pull_request_template.md | 사전 점검 8항목 기입 |
| 3 | 구현 완료 후 | MERGE_RULES §1 | MB-01~MB-07 자가 점검 |
| 4 | verify 시 | verify_constitution.py | PASS 확인 (헌법 변경 PR) |
| 5 | PR 제출 시 | pull_request_template.md | Summary~Reviewer Focus 작성 |
| 6 | Merge 직전 | pull_request_template.md 하단 | 게이트 3항목 기입 |
| 7 | Merge 판정 | MERGE_RULES §2 | MA-01~MA-07 전체 충족 확인 |
| 8 | Merge 후 | MERGE_RULES §5 | 브랜치 삭제, verify 재확인 |

## 4. 중복/모호 참조 검사 결과

| 검사 항목 | 결과 |
|-----------|------|
| "merge 금지" 용어 통일 | 통일 완료 (OPS-GATE-004) |
| template WARNING vs MERGE_RULES MB | template은 MB-01,MB-02의 요약 — 정의 원본은 MERGE_RULES |
| template 게이트 vs MERGE_RULES MA-07 | template은 MA-07의 기입 양식 — 정의 원본은 MERGE_RULES |
| "분리 재구성" vs "분리 재제출" | template=요약("재구성"), MERGE_RULES=상세("재제출") — 의미 동일, 역할 분리로 허용 |

모호하거나 상충하는 참조 없음.

## 5. Reference Drift Guard

### 5.1 원칙

본 문서(OPS_GUIDE.md)는 정의 원본의 내용을 **복제하지 않고 참조만 유지**한다.
조건 번호(MB-xx, MA-xx), 게이트 번호(OPS-GATE-xxx), 절차 단계 수 등
정의 원본에서 변경될 수 있는 값을 직접 열거할 때는 반드시 출처를 명시한다.

### 5.2 정의 문서 변경 시 갱신 규칙

| 변경 대상 | OPS_GUIDE 갱신 필요 여부 | 조건 |
|-----------|-------------------------|------|
| MERGE_RULES.md MB/MA 조건 추가·삭제 | 예 | §2 참조 관계도의 조건 범위가 달라질 때 |
| MERGE_RULES.md 기존 조건 문구 수정 | 아니오 | 본 문서는 조건 내용을 복제하지 않으므로 |
| pull_request_template.md 섹션 추가·삭제 | 예 | §2 참조 관계도의 섹션 목록이 달라질 때 |
| pull_request_template.md 문구 수정 | 아니오 | 본 문서는 문구를 복제하지 않으므로 |
| changelog.md 항목 추가 | 아니오 | APPEND_ONLY 기록이며 본 문서와 무관 |

### 5.3 Drift 의심 시 조치

1. PR 리뷰에서 OPS_GUIDE.md와 정의 원본 간 불일치가 발견되면 Reviewer가 지적한다.
2. 해당 PR에서 즉시 정정하거나, 정정 범위가 PR 목적을 초과하면 별도 ops PR로 분리한다.
3. Drift가 있는 상태에서는 OPS_GUIDE.md보다 정의 원본(MERGE_RULES.md, template)을 따른다.
