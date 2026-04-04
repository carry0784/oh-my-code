# CR-048A SEALED PASS — Async Resource Lifecycle

**봉인일**: 2026-04-03
**판정**: SEALED PASS
**승인자**: A

---

## 1. 원인

Celery solo worker (sync context) → `ExchangeFactory.create("binance")` →
`BinanceExchange.__init__()` → `BaseExchange.create_session()` →
`aiohttp.TCPConnector(resolver=ThreadedResolver())` →
`asyncio.get_running_loop()` → **RuntimeError: no running event loop**

영향 범위: `collect_market_state`, `sync_all_positions` (동일 진입점)

## 2. 수정 구조

**Config Singleton + Per-Run Runtime Client 분리**

| 원칙 | 적용 |
|------|------|
| `__init__`은 pure sync (config/credentials만) | 5개 어댑터 전체 적용 |
| async 자원은 `connect()` context manager 내부에서 생성 | `_open()` / `_close()` hook |
| 실행 종료 시 명시적 async close | session reference 직접 보관 + 이중 close |
| GC 의존 정리 금지 | `_close()`에서 `await session.close()` 직접 호출 |
| `.client` property guard | connect() 밖 접근 시 RuntimeError |

## 3. 수정 파일 (12개)

| 분류 | 파일 | 변경 |
|------|------|------|
| Exchange 계층 (5) | `exchanges/base.py` | `connect()` async context manager + `_open()`/`_close()` hook |
| | `exchanges/binance.py` | config-only init, session reference 직접 보관, 이중 close |
| | `exchanges/bitget.py` | 동일 패턴 (미래 방어) |
| | `exchanges/upbit.py` | 동일 패턴 (미래 방어) |
| | `exchanges/kis.py` | httpx.AsyncClient를 `_open()`으로 이동 |
| | `exchanges/kiwoom.py` | 동일 |
| Task lifecycle (4) | `workers/tasks/data_collection_tasks.py` | `async with exchange.connect():` |
| | `workers/tasks/market_tasks.py` | 동일 |
| | `workers/tasks/order_tasks.py` | 동일 |
| | `workers/tasks/sol_paper_tasks.py` | 동일 |
| Test (1) | `tests/test_universe_runner.py` | Part 18: 22 tests (6 classes) |
| Docs (1) | `docs/testing/cr048_test_baseline.md` | 598 → 620, CR-048A seal |

## 4. 테스트 결과

| 범위 | 결과 |
|------|------|
| CR-048 baseline 9 files | **620 passed** (598 + 22 new) |
| Full suite (pre-existing C15 제외) | 1240 passed |

### 22 new tests (Part 18)

| Class | Tests | 검증 |
|-------|-------|------|
| TestExchangeConfigOnlyInit | 5 | 5개 어댑터 sync 안전 |
| TestExchangeClientPropertyGuard | 3 | connect() 밖 접근 RuntimeError |
| TestExchangeConnectLifecycle | 3 | 생성/정리/cross-loop |
| TestExchangeFactorySyncSafe | 1 | Factory.create() sync 안전 |
| TestTaskConnectPattern | 4 | 4개 task 파일 connect() 사용 |
| TestAsyncResourceLifecyclePolicy | 6 | init 내 async 자원 금지 + 규약 존재 |

## 5. 런타임 검증 결과

| 지표 | 수정 전 | 수정 후 |
|------|:-------:|:-------:|
| `no running event loop` | 5회+/관찰기간 | **0회** |
| `Unclosed client session` | N/A (크래시) | **0건** |
| `Unclosed connector` | N/A (크래시) | **0건** |
| `sync_all_positions` succeeded | task만 succeeded, 내부 no-op | **4회 연속 succeeded** |
| `collect_market_state` exchange API | 크래시 | **SOL/USDT 79.02 정상 수신** |
| 기존 task 회귀 | - | `check_pending_orders` 정상, `record_asset_snapshot` 정상 |

## 6. 범위 밖 이슈 이관표

| 이슈 | 이관 대상 | 상태 |
|------|-----------|------|
| `market_states` 테이블 미존재 | CR-038 (DB migration) | 미적용 |
| Binance testnet futures deprecation | 별도 운영 이슈 | 미해결 |
| `PENDING enum mismatch` | CR-048B | 분리 유지 |

## 7. 헌법 대조

| 조항 | 준수 |
|------|------|
| LLM 본선 제외 | O |
| dry_run=True 유지 | O |
| 금지 경로 차단 | O |
| 실전 전략 직접 수정 금지 | O |
| 항상 롤백 가능 | O |
| CR-048B 분리 유지 | O |

## 8. 규약 승격 권고

본 CR에서 확립된 원칙을 **Async Resource Lifecycle Constitution**으로 승격:

- sync constructor에서 async 자원 생성 금지
- singleton에는 config만, live transport 저장 금지
- `asyncio.run()` 경계 안에서 생성한 것은 그 경계 안에서 닫기
- exchange/HTTP client/DB engine에 동일 철학 적용

---

**CR-048A: SEALED PASS / 종료**
