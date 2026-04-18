# CR-γ0 — T0 INFRASTRUCTURE baseline evidence

| Field | Value |
|---|---|
| recorded_at (UTC) | 2026-04-18T11:44:26Z |
| base_head | 6aaf82497e212d22b0329695023f46dce80bdb60 (`feat(card-b7): TimescaleDB 24-symbol data pipeline`) |
| batch_mode | 배치 자율 검증 (Tier Firewall v2) |
| judgment | **GO_MERGE_READY** (T0 INFRASTRUCTURE seed) |
| L1 권위 언어 | 불변 |
| 22Z canonical sha256 | `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3` (144,482 bytes) |
| live/safety 활성화 | 금지 유지 (본 CR scope 외) |

## 1. Scope

Redis pub/sub wrapper(`EventBus`)와 24-심볼 canonical-to-venue mapping(`symbol_registry`)을
T0 INFRASTRUCTURE Tier로 분리·커밋한다. 두 모듈은 T1 LIVE / T2 SAFETY / T3 OBSERVATION /
T4 PAPER 등 다중 Tier가 동시에 의존하는 **공용 인프라**이므로 Governance Tier Firewall v2의
T0 규정("2개 이상 Tier가 직접 import하는 공용 인프라 모듈은 T0 INFRASTRUCTURE Tier로 분리")에
정확히 해당한다.

## 2. Target files + integrity

| Path | Lines | sha256 |
|---|---:|---|
| `app/services/event_bus.py` | 329 | `e07fb27bcc0322bba12237f5fe2bc2e33ffecd1a2cc7a25ded293a2efb606a2f` |
| `app/services/symbol_registry.py` | 223 | `a7d0a7cccbf4bd5139e37690199d6c22dcc552c915b6f22d5b89ca7ba273f354` |
| `tests/test_event_bus.py` | 271 | `fa85d76d4b18557fccc24fe3201b40d0fa4a26ad268f49f9e52e47385eccf4f7` |
| `tests/test_symbol_registry.py` | 171 | `545d484a216abc9af7e61d42e28d4894c672088d0a2d6ff8b083b3aa54bbedad` |

## 3. Public API snapshot

### `event_bus.py`

- 13 topic 상수: `TOPIC_TICK_BINANCE`, `TOPIC_TICK_BITGET`, `TOPIC_DIVERGENCE`, `TOPIC_SPIKE_TEMPLATE`, `TOPIC_KILL_GLOBAL`, `TOPIC_KILL_TEMPLATE`, `TOPIC_TOP3`, `TOPIC_SIGNAL`, `TOPIC_ORDER`, `TOPIC_POSITION_CLOSE`, `TOPIC_OBSERVATION`, `PATTERN_ALL_TICKS`, `PATTERN_ALL_KILLS`
- 3 helper: `tick_topic(venue)`, `kill_topic(venue)`, `spike_topic(venue)`
- 5 dataclass: `KillEvent`, `DivergenceEvent`, `SpikeEvent`, `SignalEvent`, `ObservationEvent` (22Z judgment 필드 운반 컨테이너 — 생산자 아님)
- 1 클래스: `EventBus`
  - async methods: `connect`, `close`, `publish(topic, payload)`, `subscribe(topics, handler)`, `psubscribe(pattern, handler)`, `start_listening()`, `_listener_loop`

### `symbol_registry.py`

- 타입 별칭: `Venue = Literal["binance", "bitget"]`, `SUPPORTED_VENUES: tuple`
- 3 frozen dataclass: `VenueSymbol`, `SymbolEntry`, `SymbolRegistry`
- 1 함수: `build_default_registry()` (`_load_probe_map()` 내부 헬퍼, fallback `_TIERS` 24 symbols)
- 모듈 싱글턴: `REGISTRY = build_default_registry()`

### External dependencies (import graph)

- stdlib only + `redis.asyncio` + `app.core.config.settings` + `app.core.logging`
- No cycles, no T1/T2/T3/T4 import.
- `data/backtest_results/symbol_registry_probe.json`: `.gitignore` 매치(`git check-ignore` exit 0). 부재 시 `_TIERS` fallback이 24 symbols를 공급하므로 런타임 무영향.

## 4. Consumer map (참고 — 본 CR scope 아님)

| Tier | 미추적 consumer 파일 | 활성 상태 |
|---|---|---|
| T1 LIVE | `app/services/live_order_executor.py`, `app/services/order_router.py` | untracked (현 커밋에 없음) |
| T2 SAFETY | `app/services/kill_switch.py` | untracked |
| T3 OBSERVATION | `observation_alert.py`, `observation_dashboard_projection.py`, `telegram_notifier.py`, `ws_event_bridge.py`, `ws_market_stream.py`, `ingestion_health.py` | untracked (CR-γ narrower 대상) |

→ 본 CR-γ0 머지 후에도 T1/T2/T3 런타임 경로는 여전히 off, 단지 `app/main.py`가 이미 T0 + T3 observation 일부를 attach 중(아래 §5).

## 5. Runtime smoke (bqje9m466.output 인용)

| Line | Event |
|---:|---|
| 3 | `Starting trading system` (env=production, log_mode=FILE_PERSISTED) |
| 10 | `event_bus_connected` (redis_url=redis://localhost:6379/0) |
| 11 | `kill_switch_connected` |
| 12 | `observation_projection_attached` (feed_maxlen=20) |
| 13 | `telegram_notifier_attached` (chat_id_masked=6013***) |
| 14 | `event_bus_listening_started` |
| 23–27 | `/observation/{status,stats,gate,events,window-progress}` 전부 `200 OK` |

→ 현재 working tree 상의 `event_bus.py` + `symbol_registry.py`가 운영 uvicorn 프로세스에 정상 로드되어 Redis pub/sub + 24-symbol mapping이 실제로 동작 중.

## 6. HALT 4 조건 재체크

| Halt 조건 | 판정 | 근거 |
|---|---|---|
| 1. Rollback unit 미정의 | ✅ CLEAN | 2 신규 파일 + 2 테스트만 추가. atomic revert 가능. 현 consumer(T1/T2/T3) 전원 untracked이라 runtime path 비활성 |
| 2. Receipt chain 분열 | ✅ CLEAN | 본 문서가 파일 sha256 / public ABI / consumer map / smoke log / canonical sha256 모두 포함 |
| 3. Live-safety 충돌 | ✅ CLEAN | pub/sub + static mapping만. Order 제출 / Kill 강제 경로는 T1/T2 consumer 파일에 있고 그 파일들은 현 커밋에 포함되지 않음 |
| 4. L1 충돌 (22Z canonical / gate semantics / EXECUTION_NOT_AUTHORIZED) | ✅ CLEAN | canonical JSON 미접촉, gate semantics 재정의 없음, EXECUTION_NOT_AUTHORIZED 변경 없음. `ObservationEvent` dataclass는 22Z 언어의 **운반 컨테이너**로만 기능 |

## 7. Governance 제약 준수표

| 제약 | 준수 방법 |
|---|---|
| L1 core 불변 | 22Z canonical JSON / exit_dashboard_checklist 미접촉 |
| PPF C1–C11 | PPF 모듈 미접촉 |
| Track 4 READ-ONLY | 본 CR는 dashboard route 추가 아님 (pub/sub 인프라만) |
| CR-046 prod_lock=True | 주문·Kill 경로 미접촉 |
| CR-048 shadow-only | shadow_manifest 미접촉 |

## 8. Judgment

**GO_MERGE_READY** — T0 INFRASTRUCTURE seed baseline. 단일 커밋으로 원자 landing 가능.
후행 CR-γ narrower (T3 OBSERVATION)가 본 CR 위에 자동 연쇄 진행된다 (Tier Firewall v2 §후행 baseline 자동 연쇄 규정).
