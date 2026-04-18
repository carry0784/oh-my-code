# CR-γ — T3 OBSERVATION channel baseline evidence

| Field | Value |
|---|---|
| recorded_at (UTC) | 2026-04-18T11:44:26Z |
| base | CR-γ0 (T0 INFRASTRUCTURE seed) |
| batch_mode | 배치 자율 검증 (Tier Firewall v2) |
| judgment | **GO_MERGE_READY_AS_CHANNEL_BASELINE** |
| L1 권위 언어 | 불변 |
| 22Z canonical sha256 | `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3` (144,482 bytes) |
| wiring 상태 | **별도 wiring CR 필요** — 본 CR는 module / test / receipt baseline까지만. `app/main.py`, `app/api/routes/observation_dashboard.py`, `app/api/routes/ops.py` wiring은 후속 CR에서 landing |
| live/safety 활성화 | 금지 유지 |

## 1. Scope

T3 OBSERVATION channel의 6개 모듈을 repo 추적 상태로 고정한다.
각 모듈은 T0 INFRASTRUCTURE seed(`event_bus`, `symbol_registry`)에만 의존하며
Tier Firewall v2상 단일 Tier 내부 배치로 원자적이다.

| # | Module | 역할 |
|--:|---|---|
| 1 | `observation_alert.py` | Review 21 관측 이벤트 emitter (dedup TTL + severity 자동 매핑) |
| 2 | `observation_dashboard_projection.py` | Review 22 대시보드 read-only 투영 (4 카드 섹션) |
| 3 | `telegram_notifier.py` | Signal/Kill/Divergence/Spike/Observation 외부 전송 (rate limit + priority queue) |
| 4 | `ws_event_bridge.py` | Tick → EventBus throttled republish + divergence/spike 탐지 |
| 5 | `ws_market_stream.py` | Binance/Bitget 공개 WebSocket 통합 스트림 |
| 6 | `ingestion_health.py` | 24-심볼 5-hypertable health + OHLCV gap 탐지 (read-only SQL) |

## 2. Target files + integrity

| Path | Lines | sha256 |
|---|---:|---|
| `app/services/observation_alert.py` | 282 | `1ee1d238ad993dbaa5190c213443110f04172ed3de9fe44d4b887b616aa83c96` |
| `app/services/observation_dashboard_projection.py` | 322 | `bcf9c345a9d1d4acd5c174d0402ffe58876e37fa83b761af6d056deadc569cf3` |
| `app/services/telegram_notifier.py` | 341 | `2709927d8198823ff6d3df1bc78692a867c43031de1a251c4907c00f550baf74` |
| `app/services/ws_event_bridge.py` | 160 | `99ed5eb4483f06620fd23c0e2b60616843d00a058269ba75c45ab4ddc6def7aa` |
| `app/services/ws_market_stream.py` | 385 | `0a258fbe15b2bccedd6a911ddd33b4a6d4e477828df7f4831b5595f379ba9c88` |
| `app/services/ingestion_health.py` | 538 | `ed95e7ed427d1f0912471c3d3fbb4ae6a75692841f0175f6c2bdfb593f80635e` |
| `tests/test_observation_alert.py` | 407 | `fb56cacc367678b3cc2c806f2b94fdd529fd96f245289d50b7f6fbba2e15f9ea` |
| `tests/test_observation_dashboard_projection.py` | 486 | `52c73d407a1ba1ce153195984895cc67d698f27c7f37738c4f820f2679b42e31` |
| `tests/test_telegram_notifier.py` | 211 | `f8e3b9f8c54bf50790e32cc5e90cce10cbeda5e2ff20ed44dffcc2545519ebc4` |
| `tests/test_ws_market_stream.py` | 269 | `53e770798d5f04a6d35791ec2ee154e06d2adcb562731f7c38c22da1bc6e8b72` |

## 3. Dependency graph

| Module | Internal imports | Tier 판정 |
|---|---|---|
| `observation_alert.py` | `app.core.logging`, **T0** `app.services.event_bus` | T3 순수 |
| `observation_dashboard_projection.py` | `app.core.logging`, **T0** `app.services.event_bus` | T3 순수 |
| `telegram_notifier.py` | `app.core.config`, `app.core.logging`, **T0** `app.services.event_bus` | T3 순수 |
| `ws_event_bridge.py` | `app.core.logging`, **T0** `app.services.event_bus`, **T3** `app.services.ws_market_stream` | T3 내부 |
| `ws_market_stream.py` | `app.core.logging`, **T0** `app.services.symbol_registry` | T3 순수 |
| `ingestion_health.py` | `app.core.logging`, pre-tracked `app.services.symbol_universe`, lazy pre-tracked `app.services.hyper_history_manager` | T3 순수 (pre-tracked deps only) |

→ 외부로 **T1 LIVE, T2 SAFETY 경로를 import하는 모듈 없음**. Tier Firewall v2 CLEAN.

## 4. 22Z 언어 사용 패턴 (L1 준수 확인)

- 모든 모듈은 Review 21/22에서 이미 정의된 22Z judgment 용어만을 **소비(consume)** 한다.
- 새 state vocabulary 도입 없음. c1/c2/c3/c4, fail_closed_rule_N, INSUFFICIENT_EVIDENCE, PASS_BLOCKED 등은
  `data/evidence/system_state_20260418T220000Z.json`에 이미 정의된 canonical 언어.
- `ObservationDashboardProjection`의 모든 read-only getter는 `authority_note` 문자열을 부착하여
  투영이 judgment authority가 아님을 명시한다.
- `telegram_notifier._format_observation`은 `parse_mode=None` 강제로 22Z 필드명의 underscore를
  원형 그대로 전송 (Markdown 파서 오인 방지).
- `observation_alert.emit()` 실패는 로깅만 하고 절대 propagate 하지 않는다 (L270 `repr(exc)[:200]`).

→ **L1 권위 언어(22Z canonical + gate semantics + EXECUTION_NOT_AUTHORIZED) 불변**.

## 5. Runtime smoke (bqje9m466.output 재인용)

- `observation_dashboard_projection.py`와 `telegram_notifier.py`는 이미 운영 프로세스에 attach되어 있음
  (이는 `app/main.py` modified tracked 변경에서 이루어지며 별도 wiring CR 대상).
- `/observation/{status,stats,gate,events,window-progress}` 5개 엔드포인트 모두 `200 OK`.
- 관측된 wiring events: `observation_projection_attached` (feed_maxlen=20), `telegram_notifier_attached` (chat_id_masked=6013***), `event_bus_listening_started`.

## 6. HALT 4 조건 재체크

| Halt 조건 | 판정 | 근거 |
|---|---|---|
| 1. Rollback unit 미정의 | ✅ CLEAN | 6 모듈 + 4 테스트 + 1 receipt로 원자 revert. CR-γ0 선행 landing 전제 하에 T0 의존성도 롤백 단위 정합 |
| 2. Receipt chain 분열 | ✅ CLEAN | 파일 sha256·public ABI·의존성 그래프·smoke 증거·L1 불변 확인 |
| 3. Live-safety 충돌 | ✅ CLEAN | T3 self-contained. `ws_event_bridge`가 spike/divergence를 publish하지만, 현 시점 consumer인 T2 `kill_switch`가 untracked라 실제 kill path wiring 없음. `ingestion_health`는 read-only SQL 전용 |
| 4. L1 충돌 | ✅ CLEAN | 22Z judgment 언어 **consume-only**, 새 state 도입 없음, authority note 부착 강제 |

## 7. 분리 유지 항목 (본 CR scope **외**)

| 변경 대상 | 분리 사유 | 후속 CR |
|---|---|---|
| `app/main.py` (M) | lifespan wiring 변경 — 서비스 활성화 단계 | wiring CR |
| `app/api/routes/observation_dashboard.py` (??) | 대시보드 HTTP 라우트 등록 | wiring CR |
| `app/api/routes/ops.py` (M) | ops endpoints 확장 | wiring CR |
| `docs/operations/exit_dashboard_checklist_v1.md` (prior patch) | Lane 분리 주의 주석 | 독립 receipt (이미 적용) |

## 8. Governance 제약 준수표

| 제약 | 준수 방법 |
|---|---|
| L1 core 불변 | 22Z canonical / exit_dashboard_checklist 수정 없음 |
| PPF C1–C11 | PPF 모듈 미접촉 |
| Track 4 READ-ONLY | 본 CR는 서비스 모듈만; HTTP 등록은 wiring CR로 분리 |
| CR-046 prod_lock=True | 주문·Kill 경로 미접촉 |
| CR-048 shadow-only | shadow_manifest 우회 없음 |

## 9. Judgment

**GO_MERGE_READY_AS_CHANNEL_BASELINE** — T3 OBSERVATION channel 모듈·테스트·receipt baseline.
wiring CR landing 전에는 `/observation/*` 엔드포인트 활성화는 `app/main.py` modified tracked 변경에 의존한다.
본 CR는 모듈 baseline을 repo 추적 상태로 **고정**하는 데 목적이 있으며, 서비스 최종 활성화는 별도 wiring CR에서 완결된다.

### 상태 언어 정밀화 (L2 새 규약)

| 상태 | 의미 |
|---|---|
| `GO_MERGE_READY` | 모듈·테스트·receipt + wiring까지 동일 CR 안에 포함 — 머지 즉시 서비스 최종 활성화 |
| `GO_MERGE_READY_AS_CHANNEL_BASELINE` | 모듈·테스트·receipt는 머지 가능, wiring은 의도적 별도 CR |
| `GO_MERGE_READY_PENDING_WIRING_CR` | 위와 동일하되 wiring CR이 이미 draft 단계로 identified된 경우 |

본 CR는 두 번째 상태에 해당한다.
