# 성능 회귀 방지 부속 규칙 v1

Effective: 2026-05-14
Status: **ACTIVE**
Author: B (Implementer), reviewed by A (Designer)
Scope: Evidence Store read path performance standards
Related: CR-027 (hot path recovery), CR-028 (backend abstraction)

---

## 1. Purpose

CR-027에서 evidence store full-scan으로 인한 196초 타임아웃을 복구한 후,
동일 유형의 성능 회귀가 재발하지 않도록 읽기 경로 규칙을 고정한다.

---

## 2. Rules

### Rule PERF-01: Hot path에서 `list_all()` 금지

Dashboard, ops-status, ops-checks, ops-preflight, ops-aggregate, ops-playback 등
**사용자 요청에 의해 트리거되는 HTTP 엔드포인트** (hot path)에서
`list_all()`을 호출해서는 안 된다.

- `list_all()`은 전체 evidence를 메모리에 로드한다
- Evidence 건수가 증가하면 O(n) 시간/메모리 소비
- Hot path에서는 반드시 bounded query를 사용해야 한다

**허용 위치**: batch job, 월간 감사, 1회성 스크립트, 테스트

### Rule PERF-02: Evidence 조회는 bounded query 우선

Evidence store를 읽을 때는 다음 우선순위를 따른다:

1. `count()` / `count_by_actor()` — 건수만 필요할 때
2. `list_by_actor_recent(actor, limit)` — 최근 N건만 필요할 때
3. `get(bundle_id)` — 단일 건 조회
4. `count_orphan_pre()` — orphan 판정 (CR-028)
5. `list_by_actor(actor)` — 특정 actor 전체 (비-hot path만)
6. `list_all()` — 최후 수단 (비-hot path만)

Hot path에서 5번, 6번 사용 시 반드시 `[-limit:]` 슬라이싱을 동반하거나
`list_by_actor_recent`로 대체해야 한다.

### Rule PERF-03: Recent 조회는 deterministic ordering 필수

`list_by_actor_recent`의 내부 동작은 다음 계약을 따른다:

- **쿼리 정렬**: `ORDER BY created_at DESC, bundle_id DESC` (최신 우선)
- **LIMIT 적용**: `LIMIT N` 으로 bounded
- **반환 정렬**: 결과를 reverse하여 `created_at ASC` 순으로 반환 (caller 편의)
- **동점 해소**: `bundle_id DESC` tie-break 권고 (SQLite rowid 의존 금지)
- **동일 actor + limit일 때 결과 결정적**

핵심: recent 조회의 본질은 `DESC` 정렬로 최신 N건을 선택하는 것이다.
반환 순서를 ASC로 뒤집는 것은 caller 편의이며, 정렬 기준 자체는 `DESC`이다.

---

## 3. Performance Budget (Reference)

CR-027에서 수립한 기준:

| Endpoint | Cold ≤ | Warm ≤ |
|----------|--------|--------|
| ops-status | 0.5s | 0.05s |
| ops-checks | 0.5s | 0.05s |
| ops-preflight | 0.5s | 0.05s |
| ops-playback | 0.5s | 0.05s |
| ops-aggregate | 2.0s | 0.5s |

---

## 4. Backend Abstraction Rule

외부 서비스 레이어(`app/core/`, `app/api/`)는 backend의 내부 자료구조
(`_bundles`, `_conn` 등)에 직접 접근해서는 안 된다.

- 모든 evidence 읽기는 `EvidenceStore` facade 메서드를 통해야 한다
- 새로운 읽기 패턴이 필요하면 facade + backend 인터페이스에 메서드를 추가한다
- `hasattr(store, "_bundles")` 패턴은 금지 (CR-028에서 제거됨)

---

## 5. Violation Handling

위 규칙 위반 시:
- 코드 리뷰에서 차단 (C 검수 항목)
- 성능 예산 초과 시 해당 엔드포인트는 즉시 CR 대상으로 등록

---

## 6. Changelog

| Date | Change | CR |
|------|--------|----|
| 2026-05-14 | Initial version | CR-028 |
