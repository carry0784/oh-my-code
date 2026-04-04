"""
PaperTradingBridge — CR-044 Phase 7
Paper trading execution bridge.

Simulates paper trading by recording hypothetical fills and computing
live match scores against backtest results. This fills the placeholder
in FitnessFunction._live_match_score().

dry_run=True by default. Pure computation — no actual exchange I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.services.performance_metrics import PerformanceReport, PerformanceCalculator, TradeRecord

logger = get_logger(__name__)


@dataclass
class PaperTradingConfig:
    min_paper_trades: int = 20
    min_paper_duration_hours: int = 168  # 1 week
    max_paper_drawdown_pct: float = 25.0
    live_match_threshold: float = 0.6
    dry_run: bool = True


@dataclass
class PaperSession:
    session_id: str = ""
    genome_id: str = ""
    trades: list[TradeRecord] = field(default_factory=list)
    started_at: str = ""
    is_active: bool = True


@dataclass
class PaperTradingResult:
    genome_id: str = ""
    paper_performance: PerformanceReport | None = None
    backtest_performance: PerformanceReport | None = None
    live_match_score: float = 0.5
    trade_count: int = 0
    is_ready_for_promotion: bool = False


class PaperTradingBridge:
    """Manages paper trading sessions and computes live match scores."""

    def __init__(self, config: PaperTradingConfig | None = None):
        self.config = config or PaperTradingConfig()
        self.sessions: dict[str, PaperSession] = {}
        self._next_id = 0

    def start_session(self, genome_id: str) -> str:
        self._next_id += 1
        session_id = f"paper_{self._next_id}"
        self.sessions[session_id] = PaperSession(
            session_id=session_id,
            genome_id=genome_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("paper_session_started", session_id=session_id, genome_id=genome_id)
        return session_id

    def record_trade(self, session_id: str, trade: TradeRecord) -> bool:
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return False
        session.trades.append(trade)
        return True

    def close_session(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.is_active = False

    def evaluate_session(
        self,
        session_id: str,
        backtest_perf: PerformanceReport,
    ) -> PaperTradingResult:
        session = self.sessions.get(session_id)
        if not session:
            return PaperTradingResult()

        result = PaperTradingResult(genome_id=session.genome_id)
        result.trade_count = len(session.trades)

        # Calculate paper performance
        if session.trades:
            calc = PerformanceCalculator()
            result.paper_performance = calc.calculate(session.trades, initial_capital=10000.0)
        else:
            result.paper_performance = PerformanceReport()

        result.backtest_performance = backtest_perf

        # Compute live match score
        result.live_match_score = self.compute_live_match(backtest_perf, result.paper_performance)

        # Check promotion readiness
        result.is_ready_for_promotion = (
            result.trade_count >= self.config.min_paper_trades
            and result.live_match_score >= self.config.live_match_threshold
            and result.paper_performance.max_drawdown_pct <= self.config.max_paper_drawdown_pct
        )

        logger.info(
            "paper_session_evaluated",
            session_id=session_id,
            match_score=round(result.live_match_score, 4),
            ready=result.is_ready_for_promotion,
        )
        return result

    def compute_live_match(
        self,
        backtest: PerformanceReport,
        paper: PerformanceReport,
    ) -> float:
        if paper.total_trades < 5:
            return 0.5

        # Direction match (60%)
        direction = (
            1.0
            if (
                (backtest.total_return_pct > 0 and paper.total_return_pct > 0)
                or (backtest.total_return_pct <= 0 and paper.total_return_pct <= 0)
            )
            else 0.0
        )

        # Win rate similarity (40%)
        wr_diff = abs(backtest.win_rate - paper.win_rate)
        wr_sim = max(0, 1.0 - wr_diff * 2)

        return direction * 0.6 + wr_sim * 0.4
