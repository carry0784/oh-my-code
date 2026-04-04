"""
CorrelationAnalyzer — CR-043 Phase 6
Pairwise strategy return correlation and diversification analysis.

Computes correlation matrices from equity curves or return series,
identifies strategy clusters, and calculates diversification ratios.

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CorrelationMatrix:
    """Result of correlation analysis."""

    genome_ids: list[str] = field(default_factory=list)
    matrix: np.ndarray = field(default_factory=lambda: np.array([]))
    avg_correlation: float = 0.0
    max_pairwise: float = 0.0
    diversification_ratio: float = 1.0


class CorrelationAnalyzer:
    """Analyzes correlation between strategy return series."""

    def compute_from_returns(
        self,
        returns: dict[str, list[float]],
    ) -> CorrelationMatrix:
        """
        Compute correlation matrix from return series.

        Args:
            returns: genome_id -> list of period returns
        """
        if len(returns) < 2:
            ids = list(returns.keys())
            return CorrelationMatrix(
                genome_ids=ids,
                matrix=np.eye(len(ids)),
                avg_correlation=0.0 if len(ids) < 2 else 1.0,
                max_pairwise=0.0 if len(ids) < 2 else 1.0,
                diversification_ratio=1.0,
            )

        ids = list(returns.keys())
        n = len(ids)

        # Align lengths
        min_len = min(len(returns[gid]) for gid in ids)
        if min_len < 3:
            return CorrelationMatrix(
                genome_ids=ids,
                matrix=np.eye(n),
                avg_correlation=0.0,
                diversification_ratio=1.0,
            )

        data = np.array([returns[gid][:min_len] for gid in ids])

        # Compute correlation matrix
        corr = np.corrcoef(data)
        # Handle NaN (constant series)
        corr = np.nan_to_num(corr, nan=0.0)

        # Stats
        upper_tri = corr[np.triu_indices(n, k=1)]
        avg_corr = float(np.mean(upper_tri)) if len(upper_tri) > 0 else 0.0
        max_pair = float(np.max(upper_tri)) if len(upper_tri) > 0 else 0.0

        # Diversification ratio: weighted avg vol / portfolio vol
        # Using equal weights for simplicity
        weights = np.ones(n) / n
        vols = np.std(data, axis=1)
        weighted_avg_vol = float(np.dot(weights, vols))
        portfolio_returns = data.T @ weights
        portfolio_vol = float(np.std(portfolio_returns))
        div_ratio = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1.0

        result = CorrelationMatrix(
            genome_ids=ids,
            matrix=corr,
            avg_correlation=avg_corr,
            max_pairwise=max_pair,
            diversification_ratio=div_ratio,
        )

        logger.info(
            "correlation_computed",
            n_strategies=n,
            avg_corr=round(avg_corr, 4),
            div_ratio=round(div_ratio, 4),
        )
        return result

    def compute_from_equity(
        self,
        equity_curves: dict[str, list[float]],
    ) -> CorrelationMatrix:
        """Compute correlation from equity curves by converting to returns."""
        returns = {}
        for gid, curve in equity_curves.items():
            if len(curve) < 2:
                returns[gid] = []
            else:
                rets = []
                for i in range(1, len(curve)):
                    if curve[i - 1] != 0:
                        rets.append((curve[i] - curve[i - 1]) / curve[i - 1])
                    else:
                        rets.append(0.0)
                returns[gid] = rets
        return self.compute_from_returns(returns)

    def identify_clusters(
        self,
        matrix: CorrelationMatrix,
        threshold: float = 0.7,
    ) -> list[list[str]]:
        """
        Identify clusters of highly correlated strategies.
        Simple threshold-based clustering.
        """
        n = len(matrix.genome_ids)
        visited = set()
        clusters = []

        for i in range(n):
            if i in visited:
                continue
            cluster = [matrix.genome_ids[i]]
            visited.add(i)
            for j in range(i + 1, n):
                if j not in visited and matrix.matrix[i, j] >= threshold:
                    cluster.append(matrix.genome_ids[j])
                    visited.add(j)
            clusters.append(cluster)

        logger.info("clusters_identified", count=len(clusters))
        return clusters
