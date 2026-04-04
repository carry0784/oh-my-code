# Notification Layer Final Seal

**Card**: C-42 (Notification Layer Seal)
**Type**: Institutional Seal
**Date**: 2026-03-25
**Baseline at seal**: 1631 passed, 0 failed

---

## 1. Purpose

The notification layer exists to **observe system state, generate operational snapshots, route alerts, and deliver notifications** to operators and external channels.

- Notification exists to inform operators of system conditions.
- Notification is subordinate to governance and engine layers.
- Notification is **not** a trading engine.
- Notification is **not** a decision-making system.
- Notification is **read-only with respect to engine state**.
- Notification consumes state; it never produces trading decisions.

---

## 2. System Scope

### Modules

| Module | File | Card | Role |
|--------|------|------|------|
| Alert Router | `alert_router.py` | C-14 | Route snapshots to channel candidates |
| Alert Policy | `alert_policy.py` | C-21 | Escalation/suppression decisions |
| Channel Policy | `channel_policy.py` | C-28 | Severity-to-channel matrix |
| Notification Sender | `notification_sender.py` | C-15 | Channel dispatch registry |
| Real Notifier Adapter | `real_notifier_adapter.py` | C-20 | Discord/Webhook transport |
| Multi-Notifier Adapters | `notifier_adapters.py` | C-27 | File/Slack transport |
| Notification Flow | `notification_flow.py` | C-22 | Flow orchestration |
| Flow Log | `notification_flow_log.py` | C-23 | Flow execution log |
| Receipt Store | `notification_receipt_store.py` | C-16 | Delivery receipt storage |
| Receipt File Backend | `notification_receipt_file_backend.py` | C-18 | JSONL persistence |
| Flow Retry Bridge | `flow_retry_bridge.py` | C-34 | Enqueue failures to retry |

### Explicit Non-Scope

- Trading signal generation or evaluation
- Engine state mutation
- Order placement or modification
- Position management
- Database schema ownership (beyond receipts)
- Autonomous decision-making

---

## 3. Allowed Responsibilities

1. Observe system state via dashboard v2 payload
2. Build incident snapshots from observed state
3. Route snapshots to appropriate channels
4. Apply alert policy (escalation/suppression/resolve)
5. Apply channel policy (severity-to-channel mapping)
6. Dispatch to registered channel senders
7. Record delivery receipts
8. Persist receipts to file backend
9. Log flow execution outcomes
10. Bridge failed deliveries to retry layer (enqueue only)

---

## 4. Forbidden Responsibilities

1. Mutate engine state, trust state, work state, or governance state
2. Generate trading signals or modify existing signals
3. Place, cancel, or modify orders
4. Own retry execution (delegated to retry layer)
5. Run background daemons or schedulers
6. Self-register startup hooks
7. Bypass alert policy or channel policy
8. Expose raw prompts, chain of thought, or internal reasoning
9. Make autonomous trading decisions based on notification outcomes

---

## 5. Flow Constitution

```
observe → snapshot → route → policy → channel_policy → send → receipt → persist → bridge_to_retry
```

Each step is fail-closed. Step failure does not block subsequent steps.

---

## 6. Invariants

1. Notification layer is read-only with respect to engine/governance state
2. All channel sends go through sender registry
3. All policy decisions go through alert_policy + channel_policy
4. Receipt is always recorded regardless of delivery outcome
5. Flow log captures every execution pass
6. Bridge only enqueues; never executes retries
7. No import or startup side effects
8. Fail-closed at every step

---

## 7. Amendment Rule

Changes to the notification layer require an explicit constitutional card with full review.

---

*Sealed by Card C-42.*
