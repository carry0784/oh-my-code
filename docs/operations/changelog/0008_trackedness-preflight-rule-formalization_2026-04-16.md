# 0008 — Trackedness Preflight rule 공식 문서화

**Date**: 2026-04-16
**Author**: claude-code (autonomous)
**Gate classification**: autonomous (4/4 gates 미저촉)
**Scope**: docs (operating rules)
**Framework**: v2 (`changelog/0006`)
**transition_class**: LOCAL_ONLY

## What

신규 파일 생성: `docs/operations/trackedness_preflight_rule.md` v1.0

### 포함된 내용

1. **Purpose** (§0): premise failure 예방
2. **Scope** (§1): 변경 설계 / PR / local reflection 이전 체크리스트
3. **Preflight 3 checks** (§2):
   - `git ls-files --error-unmatch <path>`
   - `git check-ignore -v <path>`
   - artifact category 분류
4. **Artifact 3-범주 분기** (§3):
   - tracked repo artifact → PR 기반 change control
   - gitignored runtime artifact → local reflection + tracked evidence receipt
   - external runtime artifact → 별도 operational procedure
5. **Log fields** (§4): receipt / changelog 에 포함 필수
6. **Prohibitions** (§5): 범주 혼합 PR / gitignore 편집 우회 / external 강제 편입 / preflight 생략 금지
7. **Enforcement** (§6): claude-code / operator / CI 검증 방식
8. **적용 예시** (§7): 3 범주 각각 사례
9. **Version / Revision 정책** (§8)
10. **Cross-References** (§9)

## Why

- `cr_new_change3_local_reflection_2026-04-14.md` §7 에 규칙 원문이 묻혀 있어 검색·인용 불편
- `cr_new_p3_new_window_launch_2026-04-14.md` 의 NOT DONE 목록 항목: "Trackedness Preflight rule 공식 운영 규칙 등재 docs PR"
- `beg_residual_reassessment_2026-04-16.md` §3.3 에서 G = NEEDS_ACTION autonomous 판정
- 사용자 analysis response 2026-04-16 — 승인 ③ "G autonomous 집행: 예", 권장: 신규 문서 `docs/operations/trackedness_preflight_rule.md` (operating_constitution 편입 지양)

## 승인 권고 준수 사항

사용자 권고 사항 이행:

| 권고 | 준수 여부 |
|---|---|
| 신규 문서로 생성 (operating_constitution 편입 아님) | ✅ `docs/operations/trackedness_preflight_rule.md` 신설 |
| 목적 / 입력 / 판정 조건 / 금지영역 / 로그 필드 명시 | ✅ §0~§5 전부 포함 |
| 기존 operating_constitution 은 건드리지 않음 | ✅ 본 작업에서 편집 없음 |
| 반경 작게 유지 | ✅ 새 단일 파일, 기존 sealed 본문 0 터치 |

## Evidence

- 규칙 원문 source: `docs/operations/evidence/cr_new_change3_local_reflection_2026-04-14.md` §7.1, §7.2
- NOT DONE 목록 출처: `docs/operations/evidence/cr_new_p3_new_window_launch_2026-04-14.md` NOT DONE
- 재판정 출처: `docs/operations/evidence/beg_residual_reassessment_2026-04-16.md` §3.3
- 실사례 ref: `docs/operations/evidence/cr046_sol_stageb_post_seal_reset_2026-04-16.md` §2 (gitignored runtime artifact 분류, 본 rule 적용)

## Reversibility

- 신규 파일 단독 추가
- `git rm docs/operations/trackedness_preflight_rule.md` 1 개 명령으로 원복
- 기존 파일 미편집 → revert blast radius 최소

## 4-Gate (v2) 미저촉 검증

| Gate | 저촉 |
|---|---|
| G1 파괴적 삭제 | ✗ (신규 추가만) |
| G2 실배포 / 실거래 | ✗ (rule 문서) |
| G3 비가역 변경 | ✗ (단일 파일 revert 가능) |
| G4 원격 공개 | ✗ (local commit, push 별도 승인) |

## Cross-effects 점검

- `operating_constitution.md` — 편집 없음
- `receipt_naming_convention.md` — 편집 없음
- 기존 sealed 본문 — 편집 없음
- ops_state.json — 편집 없음
- 코드 / 테스트 / 설정 — 편집 없음

## Follow-up

- G 항목 종결 (B/E/G 재판정표 §4.2 완료)
- 다음 작업: push 승인 요청 (G4 게이트, 조건 "E/G 완료 후" 충족)
- 향후 CI 검증 자동화 (trackedness_preflight_rule.md §6.3) 는 별도 CR
