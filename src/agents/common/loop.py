from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.agents.common.evaluation import EvaluationResult

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class QualityLoopConfig:
    """Configuration for the quality-gated loop."""

    quality_threshold: float  # e.g. 7.0
    max_attempts: int  # e.g. 3
    criterion_floors: dict[str, float] = field(default_factory=dict)  # e.g. {"accuracy": 5.0}


def _check_below_floor(
    evaluation: EvaluationResult,
    criterion_floors: dict[str, float],
) -> bool:
    """Return True if any criterion score falls below its configured floor."""
    for criterion, floor in criterion_floors.items():
        score = evaluation.criteria_scores.get(criterion)
        if score is not None and score < floor:
            return True
    return False


def _extract_token_usage(event: Any) -> TokenUsage:
    """Extract token usage from a single ADK event's usageMetadata."""
    usage = TokenUsage()
    if event.usageMetadata is not None:
        meta = event.usageMetadata
        usage.input_tokens = meta.promptTokenCount or 0
        usage.output_tokens = meta.candidatesTokenCount or 0
        usage.total_tokens = meta.totalTokenCount or 0
        usage.calls = 1
    return usage


async def _run_agent(
    runner: Runner,
    *,
    user_id: str,
    session_id: str,
    message_text: str,
    agent_name: str,
) -> tuple[str, TokenUsage]:
    """Run an agent via its runner and collect the text response + token usage.

    Args:
        runner: The ADK Runner wrapping the agent.
        user_id: User identifier for the session.
        session_id: Session identifier.
        message_text: The user message to send.
        agent_name: Expected author name for response filtering.

    Returns:
        Tuple of (response_text, token_usage).
    """
    content = types.Content(
        role="user",
        parts=[types.Part(text=message_text)],
    )
    response_parts: list[str] = []
    token_usage = TokenUsage()

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Accumulate token usage from every event that carries metadata
        event_usage = _extract_token_usage(event)
        token_usage.add(event_usage)

        # Collect text parts authored by the target agent
        if event.author == agent_name and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)

    return "".join(response_parts), token_usage


async def run_quality_loop(
    *,
    generator: LlmAgent,
    critic: LlmAgent,
    config: QualityLoopConfig,
    session_service: DatabaseSessionService,
    session_id: str,
    user_id: str,
    app_name: str,
    initial_message: str,
    parse_output: Callable[[str], T],
    parse_evaluation: Callable[[str], EvaluationResult],
) -> AgentResult[T]:
    """Run a quality-gated Generator + Critic loop.

    For each attempt the Generator produces output which is then evaluated by
    the Critic.  The loop terminates early when the quality gate is satisfied
    (overall score >= threshold **and** no per-criterion floor violation).  If
    the gate is never satisfied the best-scoring attempt is returned.

    On Critic LLM failure the attempt auto-passes with a score equal to the
    quality threshold and a warning is logged (no pipeline crash).

    Args:
        generator: The ADK LlmAgent that produces content.
        critic: The ADK LlmAgent that evaluates the content.
        config: Quality gate parameters (threshold, max attempts, criterion floors).
        session_service: ADK DatabaseSessionService for session persistence.
        session_id: Base session identifier (suffixed per attempt).
        user_id: User identifier for the session.
        app_name: ADK application name.
        initial_message: The prompt / context sent to the generator on the first
            attempt.  On subsequent attempts the critic's feedback is appended.
        parse_output: Callable that converts the generator's raw text response
            into the desired output type ``T``.
        parse_evaluation: Callable that converts the critic's raw text response
            into an :class:`EvaluationResult`.

    Returns:
        An :class:`AgentResult[T]` containing the best output, scores, and
        evaluation history.
    """
    best_output: T | None = None
    best_score: float = 0.0
    best_below_floor: bool = False
    evaluation_history: list[EvaluationResult] = []
    token_usage = TokenUsage()
    attempt = 0

    generator_runner = Runner(
        agent=generator,
        app_name=app_name,
        session_service=session_service,
    )
    critic_runner = Runner(
        agent=critic,
        app_name=app_name,
        session_service=session_service,
    )

    feedback: str | None = None

    for attempt in range(1, config.max_attempts + 1):
        # -- Build generator prompt -------------------------------------------
        if attempt == 1:
            gen_prompt = initial_message
        else:
            gen_prompt = f"{initial_message}\n\nPrevious attempt feedback (attempt {attempt - 1}):\n{feedback}"

        # Each attempt uses a unique session so history does not leak between
        # attempts (the generator should respond to the full prompt each time).
        gen_session_id = f"{session_id}-gen-{attempt}-{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=gen_session_id,
        )

        # -- Run generator -----------------------------------------------------
        gen_text, gen_usage = await _run_agent(
            generator_runner,
            user_id=user_id,
            session_id=gen_session_id,
            message_text=gen_prompt,
            agent_name=generator.name,
        )
        token_usage.add(gen_usage)

        # -- Parse generator output --------------------------------------------
        try:
            parsed_output = parse_output(gen_text)
        except Exception:
            logger.warning(
                "Failed to parse generator output on attempt %d, skipping",
                attempt,
                exc_info=True,
            )
            continue

        # -- Run critic --------------------------------------------------------
        critic_session_id = f"{session_id}-critic-{attempt}-{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=critic_session_id,
        )

        try:
            critic_text, critic_usage = await _run_agent(
                critic_runner,
                user_id=user_id,
                session_id=critic_session_id,
                message_text=gen_text,
                agent_name=critic.name,
            )
            token_usage.add(critic_usage)

            evaluation = parse_evaluation(critic_text)
        except Exception:
            # Critic failure auto-passes with threshold score
            logger.warning(
                "Critic failed on attempt %d; auto-passing with threshold score %.1f",
                attempt,
                config.quality_threshold,
                exc_info=True,
            )
            evaluation = EvaluationResult(
                score=config.quality_threshold,
                passed=True,
                feedback="Critic evaluation failed; auto-passed.",
            )

        evaluation_history.append(evaluation)
        feedback = evaluation.feedback

        # -- Check criterion floors -------------------------------------------
        below_floor = _check_below_floor(evaluation, config.criterion_floors)

        # -- Track best attempt ------------------------------------------------
        if evaluation.score > best_score:
            best_score = evaluation.score
            best_output = parsed_output
            best_below_floor = below_floor

        # -- Check quality gate ------------------------------------------------
        passed = evaluation.score >= config.quality_threshold and not below_floor
        if passed:
            logger.info(
                "Quality gate passed on attempt %d with score %.2f",
                attempt,
                evaluation.score,
            )
            break
        else:
            logger.info(
                "Quality gate not passed on attempt %d (score=%.2f, below_floor=%s)",
                attempt,
                evaluation.score,
                below_floor,
            )

    return AgentResult(
        output=best_output,  # type: ignore[arg-type]
        attempts=attempt,
        final_score=best_score,
        passed_quality_gate=best_score >= config.quality_threshold and not best_below_floor,
        below_minimum_floor=best_below_floor,
        evaluation_history=evaluation_history,
        token_usage=token_usage,
    )
