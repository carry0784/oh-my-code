# CR-048 운영 검증 보고 — 헌법 조항 대조 검수본 (최종)

**검증일**: 2026-04-02
**검증 환경**: Windows 11, Celery 5.6.2, PostgreSQL 16, Redis 7
**본 검증은 worker/beat 동시 가동 상태에서 수행되었음**

---

## 1. 해석 및 요약

### 2단 판정

| 범위 | 판정 | 근거 |
|------|------|------|
| **CR-048 범위** | **PASS** | solo pool 전환, tz fix, per-call engine — cycle runner 2회 연속 succeeded, receipt 7건 저장, crash 0 |
| **운영 자동관찰 루프 전체** | **CONDITIONAL PASS** | record_asset_snapshot E2E 미확인, 기존 async task 잔존 이슈, 관찰 시간 6.5분으로 장기 안정성 미입증 |

---

## 2. 증명된 것 / 아직 증명 못 한 것

| 증명됨 | 미증명 |
|--------|--------|
| pool=solo 반영 (startup banner 원문) | record_asset_snapshot E2E 실행 |
| SpawnPool crash 제거 (0건) | 24-72h 장기 안정성 |
| run_strategy_cycle 연속 succeeded (2회) | 누적 backlog 추이 |
| check_pending_orders 연속 succeeded (8회+) | 재기동 후 반복 일관성 |
| receipt DB 저장 (7건, snapshot 전부 보존) | 메모리/핸들 누수 |
| dry_run=false 위반 0 | 주기 태스크 간 간섭 패턴 |
| asyncpg timezone mismatch 해소 | 기존 async task event loop 이슈 |
| event loop mismatch (per-call engine) 해소 | expire_signals enum 불일치 |

---

## 3. 미충족 조항

| 조항 | 상태 | 영향 |
|------|------|------|
| record_asset_snapshot E2E | 미실행 | 핵심 3종 중 1종 미확인 |
| sync_all_positions event loop | 잔존 (task 수신 및 종료는 확인되었으나, 내부 event loop warning이 남아 기능적 완전 성공으로 판정하지 않음) | CR-048 scope 밖, 운영 전체엔 영향 |
| collect_market_state event loop | 잔존 (retry 반복, 기능 미수행) | CR-048 scope 밖, 운영 전체엔 영향 |
| expire_signals enum mismatch | 잔존 (raised) | CR-048 scope 밖, DB 정합성 영향 |
| 24-72h 관찰 | 미완료 | 안정 운영 확정 불가 |

---

## 4. 후속 CR 분리

| CR | 대상 | 우선순위 |
|---|---|---|
| CR-048 본체 | cycle runner observation loop | **PASS (완료)** |
| CR-048A (신규) | async task event loop 잔존 이슈 (sync_all_positions, collect_market_state) | 높음 |
| CR-048B (신규) | signal enum mismatch (expire_signals) | 중간 |

---

## 5. 운영 확정 승급 조건

| 단계 | 승급 조건 | 현재 상태 |
|------|-----------|----------|
| Patch Applied | 코드 반영 + 테스트 통과 | 598 tests green |
| Runtime Recovered | crash 0 + 핵심 task E2E 확인 | 부분충족 (2/3 종 확인, `record_asset_snapshot` 미확인) |
| Stable Observation | 24-72h backlog/receipt 안정 | 미시작 |
| Production-worthy | 잔존 async/event-loop 이슈 정리 | CR-048A/B 필요 |

---

## 6. Startup Banner 증빙 원문

```
 -------------- celery@HOME v5.6.2 (recovery)
--- ***** -----
-- ******* ---- Windows-11-10.0.26200-SP0 2026-04-02 21:11:04
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> app:         trading_workers:0x2215c57ecf0
- ** ---------- .> transport:   redis://localhost:6379/1
- ** ---------- .> results:     redis://localhost:6379/2
- *** --- * --- .> concurrency: 1 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----
```

---

## 7. 핵심 Task 로그 체인

### check_pending_orders (8회+ succeeded)

```
[21:16:44] received → succeeded in 0.016s
[21:16:46] received → succeeded in 0.026s
```

### run_strategy_cycle (2회 연속 succeeded)

```
[21:21:42] US_STOCK received → succeeded in 0.056s
  result: skip_reason_code=market_closed, guard_snapshot 포함
[21:26:08] KR_STOCK received → succeeded in 0.046s
  result: skip_reason_code=market_closed, guard_snapshot 포함
```

### sync_all_positions (task 수신/종료 확인, 기능적 완전 성공은 미판정)

```
[21:21:14] received → succeeded in 0.002s
  WARNING: Position sync failed error='no running event loop'
```

> task framework 레벨 종료는 정상이나, 내부 핵심 동작은 event loop 부재로 no-op 성격. 기능적 완전 성공으로 판정하지 않음.

### record_asset_snapshot

> 검증 시간 범위(6.5분) 내 beat dispatch 미관찰. E2E 미확인.

---

## 8. Receipt DB 증빙

```sql
Total receipts: 7
  market_closed: 4   -- KR_STOCK/US_STOCK (outside hours)
  none: 2            -- CRYPTO (24/7, normal cycle)
  safe_mode_active: 1
dry_run=false violations: 0
guard_snapshot_json present: 7/7
```

---

## 9. 상태 전이표

| 이전 상태 | 조건 | 다음 상태 |
|-----------|------|-----------|
| Patch Applied | startup banner + crash 0 + receipt 저장 확인 | Runtime Recovered (부분충족) |
| Runtime Recovered (부분충족) | `record_asset_snapshot` E2E 확인 | Runtime Recovered (충족) |
| Runtime Recovered (충족) | 24-72h backlog/receipt 안정 | Stable Observation |
| Stable Observation | CR-048A/B 해소 | Production-worthy |

**현재 위치: Patch Applied → Runtime Recovered (부분충족)**

---

## 10. 수정 파일 (이번 배치 전체)

| File | Change |
|------|--------|
| `workers/celery_app.py` | solo/prefork 분기 + beat uncomment |
| `workers/tasks/cycle_runner_tasks.py` | asyncio.run + per-call engine + receipt persistence |
| `app/models/cycle_receipt.py` | DateTime(timezone=True) |
| `alembic/versions/016_cycle_receipt_tz_fix.py` | TIMESTAMPTZ 마이그레이션 |
| `tests/test_universe_runner.py` | Part 15-17 (187 tests in file) |
| `docs/testing/cr048_test_baseline.md` | 598 tests, 6B-ops seal |

---

## 11. 미해결 리스크

- Solo concurrency 1: 30s/60s 주기 태스크 병목 가능
- 기존 async task: event loop 부재로 graceful degradation만 됨
- Holiday calendar 부재: 불필요한 market_closed receipt 축적
- 관찰 기간 부족: 6.5분 단기 검증만 완료

---

## 12. 다음 단계 권고

1. **24-72h 안정 관찰 계속** (본 검증은 worker/beat 동시 가동 상태에서 수행되었음)
2. 관찰 중 record_asset_snapshot succeeded 확인 → Runtime Recovered 충족 승급
3. CR-048A (async event loop) 별도 분류 착수
4. 관찰 종료 후 → Stable Observation 승급 판정
5. 이후 → Phase 6C minimal RuleBasedRiskOverlay
