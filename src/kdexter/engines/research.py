"""
Research Engine -- L23 K-Dexter AOS

Purpose: conduct topic research and return structured findings.
M-18: research_complete flag must be True before PLANNING state can proceed.

Governance: B2 (governance_layer_map.md -- L23)
Mandatory: M-18 (research_complete required at PLANNING)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #


@dataclass
class ResearchResult:
    """Result of a research operation."""

    topic: str
    findings: list[str]  # ordered list of finding strings
    confidence: float  # 0.0 ~ 1.0
    research_complete: bool  # M-18: must be True to pass PLANNING gate
    researched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------ #
# L23 Research Engine
# ------------------------------------------------------------------ #


class ResearchEngine:
    """
    L23 Research Engine.

    Conducts research on a given topic and returns a ResearchResult.
    The research_complete field satisfies M-18: PLANNING state will not
    proceed unless research_complete is True.

    Stub behaviour: always returns research_complete=True with an empty
    findings list. Replace conduct() body with real retrieval logic when
    the backing knowledge source is available.

    Usage:
        engine = ResearchEngine()
        result = engine.conduct("incident root cause patterns")
        assert result.research_complete  # M-18 satisfied
    """

    def __init__(self) -> None:
        self._last_result: Optional[ResearchResult] = None

    @property
    def last_result(self) -> Optional[ResearchResult]:
        return self._last_result

    def conduct(self, topic: str) -> ResearchResult:
        """
        Conduct research on the given topic.

        M-18: returned result always sets research_complete=True in this stub.
        Confidence is set to 0.0 when no real findings are produced.

        Args:
            topic: subject to research

        Returns:
            ResearchResult with research_complete=True
        """
        result = ResearchResult(
            topic=topic,
            findings=[],
            confidence=0.0,
            research_complete=True,
        )
        self._last_result = result
        return result
