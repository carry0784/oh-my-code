# Foundation Batch (T0 → T3 → T2) — integrated report

| Field | Value |
|---|---|
| recorded_at (UTC) | 2026-04-18T11:44:26Z |
| batch_mode | 배치 자율 검증 (Tier Firewall v2, Foundation Batch 연쇄 완료) |
| composition | T0 INFRASTRUCTURE (`cr-γ0`) → T3 OBSERVATION (`cr-γ`) → T2 SAFETY (`cr-β`) |
| aggregate | 20 files changed, +5,654 insertions (0 deletions) |
| judgment | **FOUNDATION_BATCH_LOCAL_LANDING_COMPLETE** |
| externalization | **PENDING** (별도 경계, 본 보고 §7 참조) |
| CR-α (T1 LIVE) | **GATED** — externalization 판단 이후 재검토 |
| L1 권위 언어 | 불변 (22Z canonical sha256 `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3`, 144,482 bytes — Foundation Batch 전·후 3회 확인 일치) |

## 1. Foundation Batch 정의

본 보고에서 Foundation Batch란 **T1 LIVE 진입 전에 원자적으로 고정되어야 하는
3개 Tier baseline 묶음** 을 의미한다.

| Tier | 역할 | 본 Batch 내 commit |
|---|---|---|
| T0 INFRASTRUCTURE | 다중 Tier 공용 인프라 (Redis pub/sub + canonical-to-venue mapping) | `cr-γ0` = 56d71d1 |
| T3 OBSERVATION | 관측·알림·WebSocket·health 채널 (22Z 언어 consume-only) | `cr-γ` = dada18e |
| T2 SAFETY | kill switch / emergency halt safety primitive | `cr-β` = 409d77a |

L2 배치 규칙 (본 Batch로 운용 확정):
- **동일 큰틀 배치 안에서 선행 Tier가 CLEAN이면 후행 Tier baseline 배치는 자동 연쇄 수행한다** (micro-approval 금지).
- **local landing은 내부 기준선 고정이며, remote push / PR 공개는 외부화 경계로 별도 판단한다**.
- Foundation Batch는 T1 LIVE를 **포함하지 않는다**. T1 consumer 파일 (`live_order_executor`, `order_router`) 은 본 Batch 전 구간에서 untracked 상태를 보존한다.

## 2. Commit 체인 (HEAD 기준)

```
* 409d77a (HEAD cr-new/beta-t2-safety-baseline)               CR-β   T2 SAFETY primitive        +1,041 lines, 4 files
* dada18e (cr-new/gamma-t3-observation-channel-baseline)      CR-γ   T3 OBSERVATION channel     +3,520 lines, 11 files
* 56d71d1 (cr-new/gamma0-t0-infrastructure-baseline)          CR-γ0  T0 INFRASTRUCTURE seed     +1,093 lines, 5 files
* 6aaf824 (cr-new/p3-structural-resolved-declaration-evidence, origin ahead 1)  feat(card-b7): TimescaleDB 24-symbol data pipeline (분기원)
```

→ Foundation Batch 총합: **20 files changed, +5,654 insertions(+)**. 각 CR은 원자 revert 단위로 독립.

## 3. 구성 receipt 링크

| CR | Receipt | Tier | Judgment |
|---|---|---|---|
| CR-γ0 | `docs/operations/evidence/cr_gamma0_infrastructure_baseline.md` | T0 | `GO_MERGE_READY` |
| CR-γ | `docs/operations/evidence/cr_gamma_observation_channel_baseline.md` | T3 | `GO_MERGE_READY_AS_CHANNEL_BASELINE` |
| CR-β | `docs/operations/evidence/cr_beta_safety_primitive_baseline.md` | T2 | `GO_MERGE_READY_AS_CHANNEL_BASELINE` |

3-state 판정 언어 분포:
- `GO_MERGE_READY` × 1 (CR-γ0) — 모듈·테스트·receipt·wiring 모두 동일 CR 안에 포함 가능한 원자 Tier.
- `GO_MERGE_READY_AS_CHANNEL_BASELINE` × 2 (CR-γ, CR-β) — 모듈·테스트·receipt는 머지 가능, wiring은 의도적 별도 CR.

## 4. Tier Firewall v2 결과 (aggregate dependency graph)

```
T0 INFRASTRUCTURE (cr-γ0)
├── event_bus.py       ← redis.asyncio + app.core.*
└── symbol_registry.py ← app.core.* (+ optional probe JSON with _TIERS fallback)

T3 OBSERVATION (cr-γ)  [depends on T0]
├── observation_alert.py                    ← T0.event_bus
├── observation_dashboard_projection.py     ← T0.event_bus
├── telegram_notifier.py                    ← T0.event_bus
├── ws_event_bridge.py                      ← T0.event_bus, T3.ws_market_stream
├── ws_market_stream.py                     ← T0.symbol_registry
└── ingestion_health.py                     ← pre-tracked symbol_universe, lazy hyper_history_manager

T2 SAFETY (cr-β)  [depends on T0 only]
├── kill_switch.py       ← T0.event_bus + redis.asyncio
└── emergency_stop.py    ← pre-tracked symbol_universe
                          (TYPE_CHECKING only: governance_as_code, human_override_ledger
                           — untracked but runtime-safe via `from __future__ import annotations`)
```

Tier Firewall v2 판정:
- **T0 → T2 / T3 수직 의존 CLEAN** (T2·T3는 공용 T0만 import).
- **T2 ↔ T3 횡적 의존 없음** (safety와 observation 분리 유지).
- **T1 LIVE 경로 import 0건** (live_order_executor / order_router untracked 상태 보존).
- **T4~T7 import 0건** (Foundation Batch scope 외 tier 미접촉).

## 5. L1 권위 언어 불변 증명

22Z canonical sha256은 Foundation Batch 전 3회 확인되었으며 전부 동일하다:

| 확인 시점 | sha256 | size |
|---|---|---|
| CR-γ0 receipt 작성 시 | `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3` | 144,482 bytes |
| CR-γ receipt 작성 시 | `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3` | 144,482 bytes |
| CR-β commit 직후 | `4b3763a39d9a98e797794dd45cb42f4fdbabb5408991338aaad7c76eb4ecc8e3` | 144,482 bytes |

→ **22Z canonical JSON 미접촉 확정**. L1 권위 언어(22Z canonical + gate semantics +
EXECUTION_NOT_AUTHORIZED)는 Foundation Batch 전 구간에서 불변.

L2 어휘 확장은 다음 세 영역에서 발생했으며 L1과 **어휘 중첩 없음**:

| L2 영역 | 확장 어휘 | 충돌 여부 |
|---|---|---|
| T3 OBSERVATION | `ObservationEventType` (12종), severity (ALERT/WARN/INFO), `authority_note` 필드 | L1 consume-only, 새 state 도입 0 |
| T2 SAFETY kill_switch | `KillLevel` (NONE/SOFT/HARD/MANUAL) × `KillScope` (global/binance/bitget), `KillEvent` | L1 judgment 어휘와 의미 레이어 다름 |
| T2 SAFETY emergency_stop | `_halted`, trigger 코드 (manual/drawdown_breach/system_error/governance_violation) | L1 judgment 어휘와 의미 레이어 다름 |

## 6. HALT 4 조건 aggregate 재체크

| # | Halt 조건 | CR-γ0 | CR-γ | CR-β | aggregate |
|--:|---|:-:|:-:|:-:|:-:|
| 1 | Rollback unit 미정의 | ✅ | ✅ | ✅ | ✅ CLEAN (3개 CR 각각 원자 revert 가능, 역순 revert 시 T1/T4 영향 없음 — T1/T4 consumer 전원 untracked) |
| 2 | Receipt chain 분열 | ✅ | ✅ | ✅ | ✅ CLEAN (3개 개별 receipt + 본 통합 receipt, canonical sha256 3회 일치) |
| 3 | Live-safety 충돌 | ✅ | ✅ | ✅ | ✅ CLEAN (T1 consumer 전원 untracked. kill_switch publish → telegram_notifier 경로만 live, 실제 주문 금지 wiring은 후속 CR-α 책임) |
| 4 | L1 충돌 | ✅ | ✅ | ✅ | ✅ CLEAN (§5 증명) |

→ Foundation Batch **4대 halt 조건 전체 CLEAN**. 자율 검증 배치 종료 요건 충족.

## 7. Externalization boundary (본 보고와 분리된 별도 경계)

Foundation Batch는 **local landing 내부 기준선 고정만 포함한다**. 다음 사항은
본 보고가 판정하지 **않으며**, 독립 경계로 별도 검토한다:

| 항목 | 본 보고에서 판정 여부 | 비고 |
|---|:-:|---|
| 3개 local branch 존재 (`cr-new/gamma0…`, `cr-new/gamma-t3…`, `cr-new/beta-t2…`) | ✅ 확인 | 모두 remote 미등록 (local only) |
| `git push` 실행 | ❌ 미판정 | 외부화 경계 판단 대상 |
| GitHub PR 생성 | ❌ 미판정 | 외부화 경계 판단 대상 |
| PR reviewer / CI 워크플로우 트리거 | ❌ 미판정 | 외부화 경계 판단 대상 |
| wiring CR (app/main.py / observation_dashboard route / ops.py modified) | ❌ 미판정 | 별도 wiring CR 경계 |

Externalization 판단 요인 (참고용, 결론 아님):
- 3개 CR 전부 HALT 4 CLEAN + L1 불변 → 외부화 기술 전제 조건 충족.
- 3개 CR 모두 T1 LIVE 경로 미접촉 → prod_lock=True 정신 부합.
- Remote push 시 origin 이 GitHub public repo (carry0784/oh-my-code) 이며 3 branch 새로 공개됨.
- wiring CR 순서 결정이 필요: (a) push 전 wiring 완성 후 단일 PR / (b) baseline PR 3개 먼저 공개하고 wiring은 후속 PR.

**결론: 외부화 판단은 본 Foundation Batch 통합 보고를 근거로 사용자/운영자 측이
명시적으로 내려야 하는 별도 경계이다. Claude Code는 본 시점까지의 모든 판정을
local landing 범위로 한정하며, `git push` / `gh pr create` 로 자동 진행하지 않는다.**

## 8. CR-α (T1 LIVE) gating 선언

본 Foundation Batch 종료 시점 이후에도 **CR-α (T1 LIVE consumer 도입) 으로
자동 진행하지 않는다**. CR-α 진입 조건:

1. Foundation Batch 외부화 판단 완료 (본 보고 §7).
2. wiring CR 전략 결정 (base Tier가 remote에서 안정화된 후 consumer CR 추가 여부).
3. T1 LIVE 모듈 (`live_order_executor`, `order_router`) 의 safety boundary 재검증 — 특히:
   - KillSwitch.is_entry_allowed / is_force_close_required 콜 경로
   - EmergencyStop 트리거와 주문 취소 경로 연결 방식
   - 22Z EXECUTION_NOT_AUTHORIZED 와 kill/halt 어휘의 compound flag 설계
4. CR-046 prod_lock=True 지속 준수 확인 (paper rollout 범위 밖 live 금지).

## 9. Governance 제약 aggregate

| 제약 | Foundation Batch 전체 준수 |
|---|---|
| L1 core 불변 | ✅ 22Z canonical / exit_dashboard_checklist 미접촉 |
| PPF C1–C11 | ✅ PPF 모듈 (strategies/ppf/*) 전 Batch에서 미접촉 |
| Track 4 READ-ONLY | ✅ dashboard route 등록 없음 (HTTP 라우트 추가는 wiring CR로 분리) |
| CR-046 prod_lock=True | ✅ 주문 생성 API 미접촉 |
| CR-048 shadow-only | ✅ shadow_manifest 우회 없음 |
| live/safety 활성화 금지 | ✅ T1 consumer untracked 유지 |

## 10. 종결

- **Foundation Batch (T0 → T3 → T2) local landing 완료.** 3개 branch, 20 files, +5,654 lines, HALT 4 CLEAN, L1 불변.
- **외부화 (remote push / PR) 는 별도 경계** 로 이월 — 본 보고는 외부화를 실행하지 않는다.
- **CR-α (T1 LIVE) 는 gated** — 외부화 판단 + wiring 전략 + safety boundary 재검증 완료 전 진입 금지.

본 통합 보고는 Foundation Batch 내부 기준선 고정의 최종 receipt로 기능하며,
이후 모든 외부화 / wiring / T1 진입 CR은 본 receipt를 근거로 인용할 수 있다.
