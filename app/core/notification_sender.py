"""
Card C-15: Notification Sender Bridge

Purpose:
  Execute notification delivery for routed incident snapshots.
  Consumes routing decisions from C-14 alert_router and dispatches
  to channel-specific senders.

Design:
  - Each channel has a sender function: send_to_<channel>(payload) -> SendResult
  - Senders are abstracted behind a registry for easy mocking/extension
  - Fail-closed: sender failure returns a receipt with error, never raises
  - No state mutation, no hidden reasoning
  - Transport-specific logic is isolated in sender functions, not in routes
  - Actual external calls (Discord/Slack/webhook) are stubs in this card —
    real implementations are deferred to future adapter cards

Sender contract:
  Input:  snapshot dict (from C-13) + routing dict (from C-14)
  Output: NotificationReceipt with per-channel results
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ChannelResult:
    """Result of a single channel send attempt."""

    channel: str
    delivered: bool
    detail: str = ""


@dataclass
class NotificationReceipt:
    """Aggregate receipt for all channel send attempts."""

    attempted_at: str = ""
    severity_tier: str = ""
    channels_attempted: int = 0
    channels_delivered: int = 0
    results: list[ChannelResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Channel sender registry
# ---------------------------------------------------------------------------

# Sender function type: (snapshot, routing) -> ChannelResult
SenderFn = Callable[[dict[str, Any], dict[str, Any]], ChannelResult]

_SENDER_REGISTRY: dict[str, SenderFn] = {}


def register_sender(channel: str, fn: SenderFn) -> None:
    """Register a sender function for a channel."""
    _SENDER_REGISTRY[channel] = fn


def get_sender(channel: str) -> SenderFn | None:
    """Get the registered sender for a channel."""
    return _SENDER_REGISTRY.get(channel)


# ---------------------------------------------------------------------------
# Built-in senders (stubs — real implementations in future cards)
# ---------------------------------------------------------------------------


def _send_console(snapshot: dict, routing: dict) -> ChannelResult:
    """Console sender — logs to stdout. Always succeeds."""
    highest = snapshot.get("highest_incident", "NONE")
    status = snapshot.get("overall_status", "UNKNOWN")
    return ChannelResult(
        channel="console",
        delivered=True,
        detail=f"[ALERT] {status} | {highest}",
    )


def _send_snapshot(snapshot: dict, routing: dict) -> ChannelResult:
    """Snapshot sender — prepares export payload. Always succeeds."""
    version = snapshot.get("snapshot_version", "unknown")
    generated = snapshot.get("generated_at", "unknown")
    return ChannelResult(
        channel="snapshot",
        delivered=True,
        detail=f"snapshot:{version} @ {generated}",
    )


def _send_external(snapshot: dict, routing: dict) -> ChannelResult:
    """
    External sender — uses real webhook adapter if configured (C-20).
    Falls back to stub if webhook URL not set.
    """
    try:
        from app.core.config import settings

        webhook_url = getattr(settings, "notifier_webhook_url", "")
    except Exception:
        webhook_url = ""

    if not webhook_url:
        return ChannelResult(
            channel="external",
            delivered=False,
            detail="external notifier not configured (stub)",
        )

    try:
        from app.core.real_notifier_adapter import send_webhook, format_discord_payload

        payload = format_discord_payload(snapshot)
        success = send_webhook(webhook_url, payload)
        return ChannelResult(
            channel="external",
            delivered=success,
            detail="webhook sent" if success else "webhook delivery failed",
        )
    except Exception as e:
        return ChannelResult(
            channel="external",
            delivered=False,
            detail=f"adapter error: {str(e)[:80]}",
        )


# Register built-in senders
register_sender("console", _send_console)
register_sender("snapshot", _send_snapshot)
register_sender("external", _send_external)

# C-27: Register multi-notifier adapters
try:
    from app.core.notifier_adapters import send_file, send_slack

    register_sender("file", send_file)
    register_sender("slack", send_slack)
except Exception:
    pass  # fail-closed: adapters unavailable is non-fatal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_notifications(snapshot: dict[str, Any], routing: dict[str, Any]) -> NotificationReceipt:
    """
    Dispatch notifications to all channels specified in routing.

    Args:
        snapshot: Output of _build_incident_snapshot() (C-13)
        routing:  Output of route_snapshot() (C-14)

    Returns:
        NotificationReceipt with per-channel results.

    Fail-closed: individual sender failures are captured in results,
    never propagated as exceptions.
    """
    now = datetime.now(timezone.utc)
    channels = routing.get("channels", [])
    severity_tier = routing.get("severity_tier", "unknown")

    receipt = NotificationReceipt(
        attempted_at=now.isoformat(),
        severity_tier=severity_tier,
        channels_attempted=len(channels),
    )

    for channel in channels:
        sender = get_sender(channel)
        if sender is None:
            receipt.results.append(
                ChannelResult(
                    channel=channel,
                    delivered=False,
                    detail=f"no sender registered for channel: {channel}",
                )
            )
            continue

        try:
            result = sender(snapshot, routing)
            receipt.results.append(result)
            if result.delivered:
                receipt.channels_delivered += 1
        except Exception as e:
            receipt.results.append(
                ChannelResult(
                    channel=channel,
                    delivered=False,
                    detail=f"sender error: {str(e)[:100]}",
                )
            )

    return receipt
