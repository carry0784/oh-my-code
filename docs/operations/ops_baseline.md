# Operations Baseline

## S-01 Stabilization Baseline

Status: FULL GO
Approved: 2026-03-25
Receipt: `docs/operations/s01_full_go_receipt.md`

### Resolved Conditions

- B-01 consumed persistence
- B-02 hourly observability
- B-03 dispatch window guard
- B-04 Tab 3 render integrity

### Baseline Effect

- consumed activation/hash 이력은 `evidence_store` 기반으로 재시작 이후에도 유지된다.
- dispatch window는 기록만이 아니라 만료 시 실제 거부된다.
- hourly check의 일부 unknown 항목은 `ops-status.integrity_panel` 기반으로 보강된다.
- Tab 3는 구조 무결성 검증이 완료되었다.

### Hold Condition

이 FULL GO 기준선은 아래 조건이 유지될 때 유효하다.

- `evidence_store` 활성
- dispatch window 만료 거부 로직 유지
- hourly enrichment 정상
- Tab 3 fetch/render 구조 무결성 유지

---

## S-02 Operational Automation Baseline

Status: DONE
Date: 2026-03-25
Receipt: `docs/operations/s02_receipt.md`

- daily/hourly read-only 운영 점검이 Celery beat에 등록됨
- ops 전용 테스트 18건 추가 (총 261 passed)
- preflight는 자동화 제외 (운영 통제 유지)
