# Change Re-entry Checklist

**작성일**: 2026-04-03
**상태**: STANDBY (Baseline Hold 해제 시 사용)
**승인자**: A

---

## 1. 목적

Baseline Hold 해제 후 신규 변경(CR)을 착수할 때,
기준선을 훼손하지 않으면서 안전하게 개발을 재개하기 위한 체크리스트.

---

## 2. 착수 전 필수 조건

아래 **전부** 충족 시에만 변경 착수 가능:

| # | 조건 | 확인 |
|---|------|------|
| 1 | **A가 Baseline Hold 해제 승인** | [ ] |
| 2 | **변경 범위(CR)가 명시적으로 정의됨** | [ ] |
| 3 | **영향 받는 기준선 항목이 사전 식별됨** | [ ] |
| 4 | **현재 기준선 6항목 재측정 → 전부 일치 확인** | [ ] |
| 5 | **회귀 테스트 전체 PASS 확인** | [ ] |

---

## 3. 변경 범위 명시 양식

새 CR 착수 시 반드시 아래를 기재:

```
CR-XXX: [제목]
- 변경 대상 파일: [목록]
- 영향 받는 기준선 항목: [operational_mode / exchange_mode / disabled_beat_tasks / blocked_api_count / 해당 없음]
- 영향 받는 규칙: [BL-EXMODE01 / BL-OPS-RESTART01 / 해당 없음]
- 금지 사항 위반 여부: [없음 / 있으면 사유]
- 롤백 방법: [git revert / 설정 복원 / 기타]
```

---

## 4. 변경 중 재검증 체크리스트

변경 작업 중 아래를 주기적으로 확인:

| # | 체크 | 기대값 |
|---|------|--------|
| 1 | `operational_mode` | 변경 범위에 포함되지 않으면 `BASELINE_HOLD` 유지 |
| 2 | `exchange_mode` | A 승인 없이 `DATA_ONLY` 외 값 금지 |
| 3 | `blocked_api_count` | 변경 범위에 포함되지 않으면 `5` 유지 |
| 4 | `disabled_beat_tasks` | 변경 범위에 포함되지 않으면 `3` 유지 |
| 5 | 금지 task 3개 | beat schedule 미등록 유지 |
| 6 | 회귀 테스트 | 기존 테스트 PASS 유지 |

---

## 5. 변경 완료 후 봉인 절차

| 단계 | 행동 | 승인 |
|------|------|------|
| 1 | 변경 내용 증거 문서 작성 | 작업자 |
| 2 | 회귀 테스트 전체 PASS 확인 | 작업자 |
| 3 | 기준선 6항목 재측정 | 작업자 |
| 4 | 기준선 값 갱신 (변경된 경우) | A 승인 |
| 5 | `ops_state.json` 갱신 (변경된 경우) | A만 편집 |
| 6 | CR 봉인 판정 | A |
| 7 | Baseline Hold 재진입 (필요 시) | A |

---

## 6. 롤백 조건

아래 중 하나라도 발생하면 **즉시 롤백**:

| 조건 | 조치 |
|------|------|
| 변경 범위 밖 기준선 항목이 깨짐 | git revert + 기준선 재측정 |
| 금지 task가 재등장 | beat schedule 확인 + 원복 |
| private API 호출 흔적 발생 | 변경 취소 + 원인 조사 |
| 회귀 테스트 FAIL (기존 테스트) | 변경 취소 + 수정 후 재시도 |
| A가 중단 지시 | 즉시 중단 + 현재 상태 보고 |

---

## 7. 금지 사항 (변경 중에도 유효)

- DATA_ONLY 계약 훼손 금지
- SEALED PASS 범위 재개방 금지
- ETH 운영 경로 금지 (CR-046)
- Phase 3 구현 금지 (A 승인 전)
- `ops_state.json` 무단 편집 금지 (A만 편집)

---

## 8. 관련 문서

| 문서 | 위치 |
|------|------|
| Baseline Hold Runbook | `docs/operations/baseline_hold_runbook.md` |
| ops_state.json | 프로젝트 루트 |
| BL-EXMODE01 | `docs/architecture/bl_exmode01.md` |
| BL-OPS-RESTART01 | `docs/architecture/bl_ops_restart01.md` |
| TEST-ORDERDEP-001 | `docs/operations/evidence/test_orderdep_001.md` |

---

**Change Re-entry Checklist 작성 완료.**
