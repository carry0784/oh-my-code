"""
Card C-27: Multi-Notifier Adapters — File, Slack, and extensible channel support.

Purpose:
  Provide additional notification channel adapters beyond the C-20 webhook.
  Each adapter follows the same contract: (snapshot, routing) -> ChannelResult.

Design:
  - File adapter: append incident summary to a local JSONL file
  - Slack adapter: stub for future Slack webhook integration
  - All adapters are fail-closed: never raise, return ChannelResult
  - No hidden reasoning, no debug traces
  - Transport logic isolated per adapter
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.notification_sender import ChannelResult


# ---------------------------------------------------------------------------
# File Notifier — append incident summary to local JSONL file
# ---------------------------------------------------------------------------

def send_file(snapshot: dict[str, Any], routing: dict[str, Any]) -> ChannelResult:
    """
    Append a compact incident summary to a notification log file.
    File path from config. Fail-closed: returns False on any error.
    """
    try:
        from app.core.config import settings
        file_path = getattr(settings, "notifier_file_path", "")
    except Exception:
        file_path = ""

    if not file_path:
        return ChannelResult(
            channel="file",
            delivered=False,
            detail="file notifier not configured",
        )

    try:
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "status": snapshot.get("overall_status", "UNKNOWN"),
            "incident": snapshot.get("highest_incident", "NONE"),
            "severity": routing.get("severity_tier", "unknown"),
            "channels": routing.get("channels", []),
        }
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return ChannelResult(
            channel="file",
            delivered=True,
            detail=f"appended to {file_path}",
        )
    except Exception as e:
        return ChannelResult(
            channel="file",
            delivered=False,
            detail=f"file write error: {str(e)[:80]}",
        )


# ---------------------------------------------------------------------------
# Slack Notifier — stub for future Slack webhook integration
# ---------------------------------------------------------------------------

def send_slack(snapshot: dict[str, Any], routing: dict[str, Any]) -> ChannelResult:
    """
    Send incident summary to Slack webhook.
    Stub: actual Slack integration deferred to future card.
    """
    try:
        from app.core.config import settings
        slack_url = getattr(settings, "notifier_slack_url", "")
    except Exception:
        slack_url = ""

    if not slack_url:
        return ChannelResult(
            channel="slack",
            delivered=False,
            detail="slack notifier not configured (stub)",
        )

    try:
        from app.core.real_notifier_adapter import send_webhook
        status = snapshot.get("overall_status", "UNKNOWN")
        incident = snapshot.get("highest_incident", "NONE")
        payload = {"text": f"[K-Dexter] {status} | Incident: {incident}"}
        success = send_webhook(slack_url, payload)
        return ChannelResult(
            channel="slack",
            delivered=success,
            detail="slack sent" if success else "slack delivery failed",
        )
    except Exception as e:
        return ChannelResult(
            channel="slack",
            delivered=False,
            detail=f"slack error: {str(e)[:80]}",
        )
