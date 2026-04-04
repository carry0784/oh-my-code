# RI-2A-2b Activation Manifest

**Purpose**: 실제 enable 전에만 사용하는 단일 체크리스트.
**Authority**: A + 구현자 공동
**Rule**: 모든 항목이 기준을 충족해야 beat uncomment / DRY_SCHEDULE False 전환 가능.

---

## Activation Checklist

| # | 항목 | 현재 상태 | 기준 | 전환 승인 |
|---|------|:---------:|------|-----------|
| 1 | beat_entry_commented | **true** | → false 전환 시 A 승인 | A |
| 2 | dry_schedule_true | **true** | → false 전환 시 A 승인 | A |
| 3 | dispatch_active | **false** | beat uncomment 후 true | A |
| 4 | purge_active | **false** | 별도 A 승인 후 true | A |
| 5 | rollback_verified | **true** | 구현 완료 후 true | 구현자 |
| 6 | idempotency_verified | **true** | 테스트 PASS 후 true | 구현자 |
| 7 | observability_verified | **true** | 10필드 구현 확인 후 true | 구현자 |
| 8 | dry_24h_clean | **false** | dry-schedule 24H 무오류 후 true | 구현자 + A |
| 9 | consecutive_failures_zero | **true** | 연속 실패 0 확인 후 true | 구현자 |
| 10 | schema_introduced | **true** | is_archived 컬럼 추가됨 | — |
| 11 | schema_operationally_active | **false** | retention purge 미구현 | A |

---

## Manifest Update Rules

| 규칙 | 설명 |
|------|------|
| false→true 전환 | 증거 기반 (테스트 결과, 로그 분석) |
| true→false 복귀 | 장애 발생 시 즉시 |
| 전체 true 달성 | beat uncomment + DRY_SCHEDULE False 전환 GO 요청 가능 |
| 갱신 기록 | 날짜, 변경 항목, 근거를 아래 Log에 추가 |

---

## Update Log

| 날짜 | 항목 | 변경 | 근거 |
|------|------|------|------|
| 2026-04-04 | 초기 생성 | 전체 초기값 설정 | RI-2A-2b 구현 착수 |
| 2026-04-04 | rollback_verified / idempotency_verified / observability_verified / consecutive_failures_zero | false → true | 구현·테스트 완료 (completion_evidence §1 18/18, §3 Activation Block Table) |
| 2026-04-04 | RI-2A-2b SEALED | Baseline v2.5 (5456/5456 PASS) 확정 | A 판정 ACCEPT · SEALED (completion_evidence §A 판정) |

---

```
RI-2A-2b Activation Manifest v1.1
Status: SEALED phase — Activation BLOCKED
Baseline: v2.5 (5456/5456 PASS)
Beat enable: NOT ALLOWED (별도 A 승인 필요)
DRY_SCHEDULE False: NOT ALLOWED (별도 A 승인 필요)
Purge active: NOT ALLOWED (별도 A 승인 필요)
```
