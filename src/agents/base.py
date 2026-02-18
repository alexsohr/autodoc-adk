from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from src.agents.common.agent_result import AgentResult

T = TypeVar("T")


class BaseAgent(ABC, Generic[T]):
    """Abstract base class for all documentation agents."""

    @abstractmethod
    async def run(
        self,
        input_data: Any,
        session_service: Any,
        session_id: str,
    ) -> AgentResult[T]:
        """Execute the agent and return a quality-gated result.

        Args:
            input_data: Agent-specific input (file list, page spec, etc.)
            session_service: ADK DatabaseSessionService instance.
            session_id: Session ID for conversation history.
        """
