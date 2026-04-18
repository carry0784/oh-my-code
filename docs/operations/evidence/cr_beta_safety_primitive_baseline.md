# CR-β — T2 SAFETY primitive baseline evidence

| Field | Value |
|---|---|
| recorded_at (UTC) | 2026-04-18T11:44:26Z (Foundation Batch 공통 기준 시각) |
| base | CR-γ0 (T0 INFRASTRUCTURE seed) + CR-γ (T3 OBSERVATION channel baseline) |
| batch_mode | 배치 자율 검증 (Tier Firewall v2, Foundation Batch 연쇄) |
| judgment | **GO_MERGE_READY_AS_CHANNEL_BASELINE** (safety primitive baseline only, wiring 분리) |
| L1 권위 언어 | 불변 (22Z canonical sha256 `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3`, 144,482 bytes) |
| live 활성화 | 금지 유지 — T1 LIVE consumer (`live_order_executor`, `order_router`) 전원 untracked |

## 1. Scope

Foundation Batch 세 번째 단계. T0 INFRASTRUCTURE seed 위에 다중 레벨 kill
state manager(`kill_switch`)와 emergency halt protocol(`emergency_stop`)을
safety primitive baseline으로 repo 추적 상태에 고정한다.

| # | Module | 역할 |
|--:|---|---|
| 1 | `app/services/kill_switch.py` | Redis-backed multi-level kill switch (`NONE`/`SOFT`/`HARD`/`MANUAL` × `global`/`binance`/`bitget` scope) |
| 2 | `app/services/emergency_stop.py` | Pure-computation emergency halt protocol (manual · drawdown_breach · system_error · governance_violation triggers) |
| 3 | `tests/test_kill_switch.py` | kill_switch unit tests (T0 + T2 import only) |

참고: `tests/test_emergency_stop.py`는 **현재 존재하지 않는다**. emergency_stop 테스트는
별도 후속 CR에서 추가한다 (본 CR 범위 외).

## 2. Target files + integrity

| Path | Lines | sha256 |
|---|---:|---|
| `app/services/kill_switch.py` | 269 | `04e87f1e8989c2b55a803b8e46ae9e519a2f03d752e9052dd678f177271b5e9c` |
| `app/services/emergency_stop.py` | 393 | `ee9d30eaeaa5907cc73a215b7180b32f05577f0ea9a5652f16ada85cbad79015` |
| `tests/test_kill_switch.py` | 231 | `5990eb59f4a8f3be442351f48d0b2ab611af448e1f590f706882f12780b310f8` |

## 3. Public API snapshot

### `kill_switch.py`

- 타입 별칭: `KillLevel = Literal["NONE", "SOFT", "HARD", "MANUAL"]`, `KillScope = Literal["global", "binance", "bitget"]`
- 상수: `LEVEL_RANK`, `STATE_KEY_TEMPLATE`, `HISTORY_KEY`, `HISTORY_MAX_LEN`
- 클래스 `KillSwitch`
  - lifecycle: `connect()`, `close()`
  - state queries: `get_state(scope)`, `current_level(scope)`, `is_entry_allowed(venue)`, `is_force_close_required(venue)`, `snapshot()`
  - mutations: `trigger(level, scope, reason, by)`, `release(scope, by)`
  - internal: `_append_history(payload)`
  - publish: T0 event_bus 로 `KillEvent` asdict publish (non-fatal, bus None 허용)
- 클래스 `AutoKillTriggers`
  - 상수: `DAILY_LOSS_SOFT_PCT = -0.02`, `DAILY_LOSS_HARD_PCT = -0.05`, `VENUE_API_FAIL_SEC = 180` (Autonomy Charter A3·A4)
  - `decide_level(daily_pnl_pct) -> KillLevel` (pure, no I/O)

### `emergency_stop.py`

- Thresholds: `_THRESHOLD_PORTFOLIO_DD = 10.0%`, `_THRESHOLD_SYMBOL_DD = 30.0%`, `_THRESHOLD_CONSECUTIVE_LOSSES = 15`, `_THRESHOLD_ERROR_COUNT = 5`, `_ERROR_WINDOW_SECONDS = 3600`
- 데이터클래스 `EmergencyStopEvent`
- 클래스 `EmergencyStop`
  - `trigger(reason, affected_symbols, actor, trigger)` — HALTED flag set, 심볼별 cancellation flag, ledger 기록 시도, CRITICAL 로그
  - `resume(event_id, actor, reason)` — 해당 event만 활성 해제, 남은 active 0일 때 halted 해제
  - `is_halted()`, `get_active_stops()`, `get_history()`
  - `check_auto_triggers(portfolio_metrics)` — 4 thresholds 순차 확인
  - internal: `_count_recent_errors(error_timestamps)`
- Pure computation: no exchange API, no I/O, no external state 저장 (메모리 상 리스트만)

## 4. Dependency graph

| Module | Runtime imports | 판정 |
|---|---|---|
| `kill_switch.py` | `app.core.config.settings`, `app.core.logging`, **T0** `app.services.event_bus` (`EventBus`, `KillEvent`, `TOPIC_KILL_GLOBAL`, `kill_topic`), `redis.asyncio` | T2 순수 — T0 only |
| `emergency_stop.py` | `app.core.logging`, pre-tracked `app.services.symbol_universe` | T2 순수 — pre-tracked only |
| (emergency_stop TYPE_CHECKING only) | `app.services.governance_as_code.GovernanceAsCode`, `app.services.human_override_ledger.HumanOverrideLedger` | **런타임 import 아님** — `from __future__ import annotations` 적용, 타입 힌트는 lazy-evaluated 문자열로 평가. 실제 모듈 `governance_as_code`, `human_override_ledger`는 untracked지만 본 CR landing 후에도 런타임 영향 없음 |
| `tests/test_kill_switch.py` | T0 `event_bus`, T2 `kill_switch` only | T2 순수 |

→ **외부로 T1 LIVE 경로를 import하는 모듈 없음**. Tier Firewall v2 CLEAN.

## 5. L1 권위 언어 vs kill/halt 언어 구분

22Z canonical (FROZEN) 언어와 kill/halt primitive 언어는 **서로 다른 레이어**의 어휘이며 중첩하지 않는다:

| 계층 | 어휘 집합 |
|---|---|
| L1 22Z judgment (FROZEN) | `receipt_layer`, `engine_layer`, `system_layer_summary`, `system_layer_detail`, `fail_closed_active` (list of `fail_closed_rule_N`), `pass_status`, `c1/c2/c3/c4`, `pass_blocked_reason`, `confusion_incident_count`, `consecutive_all_true_windows`, T1~T4 reopen trigger codes |
| L2 kill_switch (본 CR) | `KillLevel` = `NONE`/`SOFT`/`HARD`/`MANUAL`, `KillScope` = `global`/`binance`/`bitget`, Redis state key `kill:{scope}`, `KillEvent` payload |
| L2 emergency_stop (본 CR) | `_halted`, trigger 종류 `manual`/`drawdown_breach`/`system_error`/`governance_violation`, `EmergencyStopEvent` |

주의할 유사어:
- 22Z의 `fail_closed`는 **judgment 실패 후의 상위 판정 블록** (adjudication 체계 내부).
- kill_switch의 `HARD`/`MANUAL`은 **주문 실행 경로를 실행 레벨에서 강제 금지**하는 safety primitive.
  → 의미론 계층이 다르므로 **L1 충돌 없음**. `EXECUTION_NOT_AUTHORIZED`에 해당하는 compound flag는 여전히 22Z canonical에서만 정의된다.

## 6. Runtime smoke (bqje9m466.output 재인용 + kill_switch 관련)

| Line | Event |
|---:|---|
| 10 | `event_bus_connected` (T0 landed) |
| **11** | **`kill_switch_connected`** — 본 CR-β 대상 `kill_switch.py`가 실제로 main.py lifespan에 의해 import/wired되어 Redis에 connect 완료 |
| 12–14 | observation projection/telegram/event_bus_listening — CR-γ 대상 |
| 23–28 | `/observation/*`, `/dashboard` 모두 `200 OK` |

→ 현재 working tree의 `kill_switch.py`는 운영 프로세스에 이미 로드되어 Redis와 연결됨. `emergency_stop.py`는 lifespan에서 별도 wiring 없이 독립 모듈로 존재 (테스트 · 향후 auto-trigger loop 준비 단계).

## 7. HALT 4 조건 재체크

| Halt 조건 | 판정 | 근거 |
|---|---|---|
| 1. Rollback unit 미정의 | ✅ CLEAN | 3 파일(2 모듈 + 1 test) 원자 revert 가능. CR-γ0 선행 landing으로 T0 의존성 충족. T1 LIVE consumer 전원 untracked라 revert 시 runtime 단절 없음 |
| 2. Receipt chain 분열 | ✅ CLEAN | 본 문서가 파일 sha256 / public ABI / 의존성 그래프 / L1 구분표 / smoke 증거 / canonical sha256 모두 포함 |
| 3. Live-safety 충돌 | ✅ CLEAN | kill_switch publish는 T3 telegram_notifier (CR-γ에서 이미 landed)로 흘러가지만, T1 주문 차단 경로는 `live_order_executor`/`order_router` untracked 상태로 미기동. emergency_stop은 순수 계산 + 메모리 flag, exchange API 접촉 없음 |
| 4. L1 충돌 | ✅ CLEAN | 22Z canonical / gate semantics / EXECUTION_NOT_AUTHORIZED 미접촉. kill/halt 언어는 별도 실행 레이어 (§5 참조) |

## 8. 분리 유지 항목 (본 CR scope **외**)

| 변경 대상 | 분리 사유 | 후속 CR |
|---|---|---|
| `app/main.py` (M) | lifespan `kill_switch_connected` wiring은 tracked `app/main.py` modified 변경에서 수행 중 | **wiring CR** |
| `tests/test_emergency_stop.py` (부재) | 본 CR 시점에 파일 없음 | emergency_stop 테스트 추가 CR |
| `app/services/governance_as_code.py` (??) | emergency_stop TYPE_CHECKING 참조 | 별도 Tier (T7 governance) CR |
| `app/services/human_override_ledger.py` (??) | emergency_stop TYPE_CHECKING 참조 | 별도 Tier (T7 governance) CR |
| 외부화 (remote push / PR 공개) | Foundation Batch 완결 후 1회 판단 | **externalization boundary** (T2 landing 직후) |

## 9. Governance 제약 준수표

| 제약 | 준수 방법 |
|---|---|
| L1 core 불변 | 22Z canonical / exit_dashboard_checklist 미접촉 |
| PPF C1–C11 | PPF 모듈 미접촉 |
| Track 4 READ-ONLY | 본 CR는 dashboard route 추가 없음 |
| CR-046 prod_lock=True | 주문 생성 API 미접촉. kill_switch trigger는 Redis state만 write, 주문 강제 청산은 T1 consumer 책임 영역 |
| CR-048 shadow-only | shadow_manifest 우회 없음 |
| live/safety 활성화 금지 | T1 LIVE consumer untracked 상태 보존 — kill 판정이 실제 주문 금지로 이어지는 경로는 아직 wiring 미완 |

## 10. Judgment

**GO_MERGE_READY_AS_CHANNEL_BASELINE** — T2 SAFETY primitive baseline.
safety 판정 엔진(`kill_switch`, `emergency_stop`)이 repo 추적 상태로 고정되며,
실제 주문 금지/강제 청산의 "발화 경로" 는 후속 wiring CR (`app/main.py` modified 및
T1 LIVE consumer CR-α) 의 책임으로 의도적 분리된다.

### Foundation Batch 연쇄 상태 (본 CR 시점)

```
* CR-β   (HEAD cr-new/beta-t2-safety-baseline)       ← 본 문서
* CR-γ   56d71d1→dada18e                             T3 channel baseline (GO_MERGE_READY_AS_CHANNEL_BASELINE)
* CR-γ0  56d71d1                                     T0 infrastructure seed (GO_MERGE_READY)
* 6aaf824 (cr-new/p3-structural-resolved-declaration-evidence)  분기원
```

→ Foundation Batch (T0 → T3 → T2) 내부 기준선 고정 완료.
다음 단계는 externalization 판단 (remote push / PR 공개) — local landing과 별도 경계.
CR-α (T1 LIVE) 진입은 externalization 이후 검토 대상.
