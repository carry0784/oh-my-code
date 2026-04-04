"""
Parallel Agent Manager — L6
K-Dexter AOS v4

Manages parallel agent instances that execute strategies concurrently.
Each agent operates through TCL (never direct exchange access).

A (Runtime Execution) layer, B2-approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AgentStatus(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class AgentInstance:
    agent_id: str
    strategy_id: str
    exchange: str
    status: AgentStatus = AgentStatus.IDLE
    started_at: Optional[datetime] = None
    cycles_completed: int = 0


class ParallelAgentManager:
    """
    L6 Parallel Agent Manager.

    Creates, monitors, and controls parallel agent instances.
    All agent actions go through TCL.
    """

    def __init__(self, max_agents: int = 10) -> None:
        self._agents: dict[str, AgentInstance] = {}
        self._max_agents = max_agents

    def spawn(self, agent_id: str, strategy_id: str, exchange: str) -> Optional[AgentInstance]:
        if len(self._agents) >= self._max_agents:
            return None
        agent = AgentInstance(
            agent_id=agent_id,
            strategy_id=strategy_id,
            exchange=exchange,
        )
        self._agents[agent_id] = agent
        return agent

    def start(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None or agent.status not in (AgentStatus.IDLE, AgentStatus.PAUSED):
            return False
        agent.status = AgentStatus.RUNNING
        agent.started_at = datetime.now(timezone.utc)
        return True

    def pause(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None or agent.status != AgentStatus.RUNNING:
            return False
        agent.status = AgentStatus.PAUSED
        return True

    def stop(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None or agent.status in (AgentStatus.STOPPED,):
            return False
        agent.status = AgentStatus.STOPPED
        return True

    def record_cycle(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None or agent.status != AgentStatus.RUNNING:
            return False
        agent.cycles_completed += 1
        return True

    def get(self, agent_id: str) -> Optional[AgentInstance]:
        return self._agents.get(agent_id)

    def list_running(self) -> list[AgentInstance]:
        return [a for a in self._agents.values() if a.status == AgentStatus.RUNNING]

    def list_all(self) -> list[AgentInstance]:
        return list(self._agents.values())

    def active_count(self) -> int:
        return sum(1 for a in self._agents.values() if a.status == AgentStatus.RUNNING)
