"""
Card C-20: Real Notifier Adapter — Discord / Generic Webhook

Purpose:
  Send incident snapshot payloads to a configured webhook URL.
  Replaces the external stub sender with a real HTTP transport.

Design:
  - Uses urllib.request (stdlib) — no external dependency required
  - Timeout: 3 seconds max
  - Fail-closed: all exceptions caught, returns False on failure
  - Never raises, never mutates state
  - No hidden reasoning, no debug traces

Usage:
  from app.core.real_notifier_adapter import send_webhook
  success = send_webhook(url, payload)
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


# Max timeout for webhook HTTP request
_WEBHOOK_TIMEOUT_S = 3


def send_webhook(url: str, payload: dict[str, Any]) -> bool:
    """
    Send a JSON payload to a webhook URL via HTTP POST.

    Args:
        url: Webhook endpoint URL (Discord, Slack, generic)
        payload: JSON-serializable dict

    Returns:
        True if HTTP response was 2xx, False otherwise.

    Fail-closed: catches all exceptions, never raises.
    """
    if not url:
        return False

    try:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError:
        return False
    except Exception:
        return False


def format_discord_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Format a snapshot into a Discord-compatible webhook payload.

    Returns a dict with 'content' field (Discord simple message format).
    """
    status = snapshot.get("overall_status", "UNKNOWN")
    incident = snapshot.get("highest_incident", "NONE")
    triage = snapshot.get("triage_top", "") or ""
    generated = snapshot.get("generated_at", "")

    lines = [
        f"**K-Dexter Alert** | {status}",
        f"Incident: {incident}",
    ]
    if triage:
        lines.append(f"Action: {triage}")
    if generated:
        lines.append(f"Time: {generated[:19]}")

    return {"content": "\n".join(lines)}
