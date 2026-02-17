from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from src.agents.common.evaluation import EvaluationResult

T = TypeVar("T")


@dataclass
class TokenUsage:
    """Token usage tracking for an agent run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, other: TokenUsage) -> None:
        """Accumulate another TokenUsage into this one."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        self.calls += other.calls


@dataclass
class AgentResult(Generic[T]):
    """Wrapper for all agent outputs with quality metadata."""

    output: T
    attempts: int
    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    evaluation_history: list[EvaluationResult] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
