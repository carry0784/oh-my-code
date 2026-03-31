"""
K-Dexter Pipeline Blockage Summary Service

Read-only observation service that aggregates blockage data across all tiers
and computes factual blockage rate/distribution/density metrics.

NEVER writes to any Ledger. NEVER deletes or transitions proposals.
Output is factual observation — no future estimation or auto-judgment.
All output is factual observation only.

Data source:
  TierSummary from the 4-tier board builder (blocked_count, total, guard_reason_top).
  Only blocked proposals are counted.

Safety:
  - Read-only: no write operations
  - Simulation-only: no cleanup executed
  - No future estimation or scoring
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from app.schemas.blockage_summary_schema import (
    BlockageSummarySchema,
    TierBlockage,
    ReasonAggregation,
    BlockageDensitySignal,
    BlockageSafety,
)
from app.schemas.four_tier_board_schema import TierSummary

if TYPE_CHECKING:
    pass


# Concentration threshold — >66% of blocks in a single tier
_CONCENTRATION_THRESHOLD = 2 / 3

# High blockage rate threshold — >50% of proposals blocked
_HIGH_BLOCKAGE_THRESHOLD = 0.5

# Description templates (OC-08 pattern-based)
_TEMPLATE_NONE = "No blocked proposals."
_TEMPLATE_BASIC = "{total} blocked proposal(s) across {tier_count} tier(s)."
_TEMPLATE_CONCENTRATED = (
    "{total} blocked proposal(s). "
    "Concentrated in {tier} tier ({count}/{total}, {ratio})."
)
_TEMPLATE_HIGH_RATE = (
    "{total} blocked proposal(s). "
    "{tier} tier has high blockage rate ({rate} of proposals)."
)
_TEMPLATE_BOTH = (
    "{total} blocked proposal(s). "
    "Concentrated in {conc_tier} tier ({conc_count}/{total}, {conc_ratio}). "
    "{rate_tier} tier has high blockage rate ({rate})."
)


def build_blockage_summary(
    agent_tier: TierSummary,
    execution_tier: TierSummary,
    submit_tier: TierSummary,
) -> BlockageSummarySchema:
    """
    Build pipeline blockage summary from tier summaries.

    Read-only: only reads from pre-built TierSummary instances.
    Never writes, deletes, or transitions any proposal.

    Returns BlockageSummarySchema with rate, distribution, and density.
    """
    tiers = [
        ("Agent", agent_tier),
        ("Execution", execution_tier),
        ("Submit", submit_tier),
    ]

    # -- Per-tier blockage ------------------------------------------------ #
    by_tier = []
    total_blocked = 0
    total_proposals = 0

    for name, tier in tiers:
        blocked = tier.blocked_count if tier.connected else 0
        total = tier.total if tier.connected else 0
        rate = (blocked / total) if total > 0 else 0.0

        by_tier.append(TierBlockage(
            tier_name=name,
            blocked_count=blocked,
            total_count=total,
            blockage_rate=round(rate, 3),
        ))
        total_blocked += blocked
        total_proposals += total

    overall_rate = (total_blocked / total_proposals) if total_proposals > 0 else 0.0

    # -- Top reasons (aggregated across tiers) ---------------------------- #
    reason_counter = Counter()
    for _, tier in tiers:
        if not tier.connected:
            continue
        for reason_str in tier.guard_reason_top:
            parts = reason_str.rsplit(": ", 1)
            if len(parts) == 2:
                try:
                    reason_counter[parts[0]] += int(parts[1])
                except ValueError:
                    reason_counter[reason_str] += 1
            else:
                reason_counter[reason_str] += 1

    top_reasons = [
        ReasonAggregation(reason=name, count=count)
        for name, count in reason_counter.most_common(10)
    ]

    # -- Density signal --------------------------------------------------- #
    tier_blocks = {name: tier.blocked_count for name, tier in tiers if tier.connected}
    tier_rates = {
        name: (tier.blocked_count / tier.total if tier.total > 0 else 0.0)
        for name, tier in tiers if tier.connected
    }
    density = _build_density_signal(total_blocked, tier_blocks, tier_rates)

    return BlockageSummarySchema(
        total_blocked=total_blocked,
        total_proposals=total_proposals,
        overall_blockage_rate=round(overall_rate, 3),
        by_tier=by_tier,
        top_reasons=top_reasons,
        density=density,
        safety=BlockageSafety(),
    )


def _build_density_signal(
    total_blocked: int,
    tier_blocks: dict[str, int],
    tier_rates: dict[str, float],
) -> BlockageDensitySignal:
    """
    Build descriptive blockage density signal.

    NOT prescriptive. Describes observable patterns only.
    """
    if total_blocked == 0:
        return BlockageDensitySignal(description=_TEMPLATE_NONE)

    # Concentration check
    dominant_tier = max(tier_blocks, key=tier_blocks.get) if tier_blocks else ""
    dominant_count = tier_blocks.get(dominant_tier, 0)
    dominant_ratio = dominant_count / total_blocked if total_blocked > 0 else 0.0
    is_concentrated = dominant_ratio > _CONCENTRATION_THRESHOLD

    # High blockage rate check
    high_tier = max(tier_rates, key=tier_rates.get) if tier_rates else ""
    high_rate = tier_rates.get(high_tier, 0.0)
    has_high_blockage = high_rate > _HIGH_BLOCKAGE_THRESHOLD

    # Count tiers with blocks
    active_tiers = sum(1 for v in tier_blocks.values() if v > 0)

    # Build description from templates
    if is_concentrated and has_high_blockage:
        description = _TEMPLATE_BOTH.format(
            total=total_blocked,
            conc_tier=dominant_tier,
            conc_count=dominant_count,
            conc_ratio=f"{dominant_ratio:.0%}",
            rate_tier=high_tier,
            rate=f"{high_rate:.0%}",
        )
    elif is_concentrated:
        description = _TEMPLATE_CONCENTRATED.format(
            total=total_blocked,
            tier=dominant_tier,
            count=dominant_count,
            ratio=f"{dominant_ratio:.0%}",
        )
    elif has_high_blockage:
        description = _TEMPLATE_HIGH_RATE.format(
            total=total_blocked,
            tier=high_tier,
            rate=f"{high_rate:.0%}",
        )
    else:
        description = _TEMPLATE_BASIC.format(
            total=total_blocked,
            tier_count=active_tiers,
        )

    return BlockageDensitySignal(
        is_concentrated=is_concentrated,
        dominant_tier=dominant_tier,
        dominant_ratio=round(dominant_ratio, 3),
        has_high_blockage=has_high_blockage,
        high_blockage_tier=high_tier if has_high_blockage else "",
        description=description,
    )
