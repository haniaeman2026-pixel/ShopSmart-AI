"""
Base Agent Module
Provides common abstractions, logging, and execution tracing for all specialized agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import time


@dataclass
class AgentTrace:
    """Represents the execution trace and reasoning output of a single agent."""
    agent_name: str
    role: str
    responsibility: str
    started_at: str
    execution_time_ms: float
    status: str  # "success", "warning", "error"
    decision_summary: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "role": self.role,
            "responsibility": self.responsibility,
            "started_at": self.started_at,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "status": self.status,
            "decision_summary": self.decision_summary,
            "details": self.details,
        }


class BaseAgent(ABC):
    """Abstract Base Class for all agents in the FAQ Assistant pipeline."""

    def __init__(self, name: str, role: str, responsibility: str):
        self.name = name
        self.role = role
        self.responsibility = responsibility

    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """Execute the primary task of the agent."""
        pass

    def create_trace(
        self,
        start_time: float,
        status: str,
        decision_summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AgentTrace:
        """Build an execution trace for auditing and transparency."""
        execution_time_ms = (time.perf_counter() - start_time) * 1000.0
        return AgentTrace(
            agent_name=self.name,
            role=self.role,
            responsibility=self.responsibility,
            started_at=datetime.now().isoformat(),
            execution_time_ms=execution_time_ms,
            status=status,
            decision_summary=decision_summary,
            details=details or {},
        )
