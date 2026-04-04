"""
Card C-14: Alert Router — Lightweight routing decision for incident snapshots.

Purpose:
  Determine which alert channels a snapshot should be routed to based on
  incident severity. This module makes ROUTING DECISIONS ONLY — it does NOT
  send notifications. Actual delivery is deferred to future notifier cards.

Design:
  - Read-only: no state mutation, no side effects
  - Fail-closed: unknown states route to ["snapshot"] (safe default)
  - Deterministic: same input always produces same routing decision
  - No hidden reasoning, no debug traces

Routing rules:
  LOCKDOWN / QUARANTINED → ["console", "snapshot", "external"]
  LOOP_EXCEEDED / CONSTITUTIONAL_VIOLATION → ["console", "snapshot", "external"]
  WORK_FAILED / WORK_BLOCKED / LOOP_CRITICAL → ["console", "snapshot"]
  DOCTRINE_VIOLATION / degraded → ["snapshot"]
  HEALTHY (no incidents) → []
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Severity tiers for routing decisions
# ---------------------------------------------------------------------------

_CRITICAL_INCIDENTS = frozenset(
    {
        "LOCKDOWN",
        "QUARANTINED",
        "LOOP_EXCEEDED",
    }
)

_HIGH_INCIDENTS = frozenset(
    {
        "WORK_FAILED",
        "WORK_BLOCKED",
        "LOOP_CRITICAL",
    }
)

# Routes per severity tier
_ROUTE_CRITICAL = ["console", "snapshot", "external"]
_ROUTE_HIGH = ["console", "snapshot"]
_ROUTE_LOW = ["snapshot"]
_ROUTE_CLEAR = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def route_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Determine alert routing for an incident snapshot.

    Args:
        snapshot: Output of _build_incident_snapshot() (C-13)

    Returns:
        {
            "channels": ["console", "snapshot", "external"],
            "severity_tier": "critical" | "high" | "low" | "clear",
            "reason": str,
        }

    Read-only: no state mutation, no side effects, no notification sent.
    """
    highest = snapshot.get("highest_incident", "NONE")
    active = snapshot.get("active_incidents", [])
    degraded = snapshot.get("degraded_reasons", [])

    # Check for critical incidents
    for inc in active:
        # Normalize: DOCTRINE_VIOLATION_xN → check prefix
        base = inc.split("_x")[0] if "_x" in inc else inc
        if base in _CRITICAL_INCIDENTS:
            return {
                "channels": list(_ROUTE_CRITICAL),
                "severity_tier": "critical",
                "reason": "critical incident: " + inc,
            }
        # CONSTITUTIONAL doctrine violation
        if "CONSTITUTIONAL" in inc.upper():
            return {
                "channels": list(_ROUTE_CRITICAL),
                "severity_tier": "critical",
                "reason": "constitutional violation: " + inc,
            }

    # Check for high incidents
    for inc in active:
        base = inc.split("_x")[0] if "_x" in inc else inc
        if base in _HIGH_INCIDENTS:
            return {
                "channels": list(_ROUTE_HIGH),
                "severity_tier": "high",
                "reason": "high-severity incident: " + inc,
            }

    # Check for low-severity (doctrine violations, degraded sources)
    if len(active) > 0:
        return {
            "channels": list(_ROUTE_LOW),
            "severity_tier": "low",
            "reason": "active incident: " + active[0],
        }

    if len(degraded) > 0:
        return {
            "channels": list(_ROUTE_LOW),
            "severity_tier": "low",
            "reason": "degraded sources: " + str(len(degraded)),
        }

    # All clear
    return {
        "channels": list(_ROUTE_CLEAR),
        "severity_tier": "clear",
        "reason": "no active incidents",
    }
