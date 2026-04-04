"""
Card C-28: Channel Policy — Escalation matrix for multi-channel routing.

Purpose:
  Map severity tiers and policy actions to specific notification channels.
  Replaces the hardcoded channel lists in alert_router with an explicit,
  configurable escalation matrix.

Design:
  routing  = classify severity (C-14)
  policy   = decide send/suppress/escalate (C-21)
  channel_policy = map to specific channels (C-28)
  sender   = deliver (C-15/C-20/C-27)

  - Deterministic: same tier + action → same channels
  - Configurable: matrix can be replaced at init
  - Read-only: no state mutation
  - Fail-closed: unknown tier/action → safe default

Matrix:
  ┌─────────────┬────────┬──────────┬──────────┬──────┬───────┐
  │ Tier/Action  │console │ snapshot │ external │ file │ slack │
  ├─────────────┼────────┼──────────┼──────────┼──────┼───────┤
  │ critical     │   ✓    │    ✓     │    ✓     │  ✓   │   ✓   │
  │ high         │   ✓    │    ✓     │    ✓     │  ✓   │       │
  │ low          │        │    ✓     │          │  ✓   │       │
  │ escalate     │   ✓    │    ✓     │    ✓     │  ✓   │   ✓   │
  │ resolve      │   ✓    │    ✓     │          │  ✓   │       │
  │ clear        │        │          │          │      │       │
  └─────────────┴────────┴──────────┴──────────┴──────┴───────┘
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Default escalation matrix
# ---------------------------------------------------------------------------

_DEFAULT_MATRIX: dict[str, list[str]] = {
    "critical":  ["console", "snapshot", "external", "file", "slack"],
    "high":      ["console", "snapshot", "external", "file"],
    "low":       ["snapshot", "file"],
    "escalate":  ["console", "snapshot", "external", "file", "slack"],
    "resolve":   ["console", "snapshot", "file"],
    "clear":     [],
}

# Fallback for unknown tiers/actions
_FALLBACK_CHANNELS = ["snapshot"]


# ---------------------------------------------------------------------------
# Channel Policy
# ---------------------------------------------------------------------------

class ChannelPolicy:
    """
    Escalation matrix that maps severity tier + policy action to channels.

    Usage:
        policy = ChannelPolicy()
        channels = policy.resolve_channels("critical", "send")
        channels = policy.resolve_channels("low", "escalate")
    """

    def __init__(self, matrix: dict[str, list[str]] | None = None) -> None:
        self._matrix = dict(matrix) if matrix else dict(_DEFAULT_MATRIX)

    def resolve_channels(
        self,
        severity_tier: str,
        policy_action: str = "send",
    ) -> list[str]:
        """
        Determine which channels to use based on severity tier and policy action.

        Priority:
          1. If policy_action is "escalate" → use escalate row
          2. If policy_action is "resolve" → use resolve row
          3. If policy_action is "suppress" → empty
          4. Otherwise → use severity_tier row

        Returns list of channel names. Fail-closed: unknown → fallback.
        """
        try:
            if policy_action == "suppress":
                return []

            if policy_action == "escalate":
                return list(self._matrix.get("escalate", _FALLBACK_CHANNELS))

            if policy_action == "resolve":
                return list(self._matrix.get("resolve", _FALLBACK_CHANNELS))

            return list(self._matrix.get(severity_tier, _FALLBACK_CHANNELS))
        except Exception:
            return list(_FALLBACK_CHANNELS)

    def get_matrix(self) -> dict[str, list[str]]:
        """Return a copy of the current matrix."""
        return {k: list(v) for k, v in self._matrix.items()}

    def update_tier(self, tier: str, channels: list[str]) -> None:
        """Update channels for a specific tier. For runtime reconfiguration."""
        self._matrix[tier] = list(channels)
