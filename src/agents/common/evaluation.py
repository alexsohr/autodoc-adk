from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvaluationResult:
    """Result from a Critic agent evaluation."""

    score: float  # Weighted average, 1.0-10.0
    passed: bool  # score >= quality_threshold
    feedback: str  # Improvement suggestions from Critic
    criteria_scores: dict[str, float] = field(default_factory=dict)  # e.g. {"accuracy": 8.0}
    criteria_weights: dict[str, float] = field(default_factory=dict)  # e.g. {"accuracy": 0.35}
