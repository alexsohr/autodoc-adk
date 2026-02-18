from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.config.settings import get_settings
from src.database.repos.job_repo import JobRepo

logger = logging.getLogger(__name__)


@task(name="aggregate_job_metrics")
async def aggregate_job_metrics(
    *,
    job_id: uuid.UUID,
    structure_result: AgentResult | None,
    page_results: list[AgentResult],
    readme_result: AgentResult | None,
    job_repo: JobRepo,
) -> dict:
    """Collect token usage and quality scores from all agent results.

    Builds ``quality_report`` and ``token_usage`` JSONB objects, updates
    the job record.

    Returns the quality_report dict.
    """
    settings = get_settings()

    # Build token usage
    total_usage = TokenUsage()
    by_agent: dict[str, dict] = {}

    if structure_result:
        total_usage.add(structure_result.token_usage)
        by_agent["structure_extractor"] = {
            "input_tokens": structure_result.token_usage.input_tokens,
            "output_tokens": structure_result.token_usage.output_tokens,
            "total_tokens": structure_result.token_usage.total_tokens,
            "calls": structure_result.token_usage.calls,
        }

    page_total = TokenUsage()
    page_scores: list[dict] = []
    pages_below_floor = 0

    for pr in page_results:
        page_total.add(pr.token_usage)
        total_usage.add(pr.token_usage)
        if pr.output is not None:
            page_scores.append(
                {
                    "page_key": pr.output.page_key,
                    "score": pr.final_score,
                    "passed": pr.passed_quality_gate,
                    "attempts": pr.attempts,
                    "below_minimum_floor": pr.below_minimum_floor,
                }
            )
            if pr.below_minimum_floor:
                pages_below_floor += 1

    by_agent["page_generator"] = {
        "input_tokens": page_total.input_tokens,
        "output_tokens": page_total.output_tokens,
        "total_tokens": page_total.total_tokens,
        "calls": page_total.calls,
    }

    if readme_result:
        total_usage.add(readme_result.token_usage)
        by_agent["readme_distiller"] = {
            "input_tokens": readme_result.token_usage.input_tokens,
            "output_tokens": readme_result.token_usage.output_tokens,
            "total_tokens": readme_result.token_usage.total_tokens,
            "calls": readme_result.token_usage.calls,
        }

    # Compute overall score (average across all results)
    all_scores: list[float] = []
    if structure_result:
        all_scores.append(structure_result.final_score)
    all_scores.extend(pr.final_score for pr in page_results)
    if readme_result:
        all_scores.append(readme_result.final_score)

    overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    quality_report: dict = {
        "overall_score": round(overall_score, 2),
        "quality_threshold": settings.QUALITY_THRESHOLD,
        "passed": overall_score >= settings.QUALITY_THRESHOLD
        and pages_below_floor == 0,
        "total_pages": len(page_results),
        "pages_below_floor": pages_below_floor,
        "page_scores": page_scores,
        "structure_score": {
            "score": structure_result.final_score,
            "passed": structure_result.passed_quality_gate,
            "attempts": structure_result.attempts,
        }
        if structure_result
        else None,
        "readme_score": {
            "score": readme_result.final_score,
            "passed": readme_result.passed_quality_gate,
            "attempts": readme_result.attempts,
        }
        if readme_result
        else None,
    }

    token_usage_report: dict = {
        "total_input_tokens": total_usage.input_tokens,
        "total_output_tokens": total_usage.output_tokens,
        "total_tokens": total_usage.total_tokens,
        "by_agent": by_agent,
    }

    # Update job record (set JSONB fields without status transition)
    job = await job_repo.get_by_id(job_id)
    if job is not None:
        job.quality_report = quality_report
        job.token_usage = token_usage_report

    logger.info(
        "Aggregated metrics: overall=%.2f, pages=%d, tokens=%d",
        overall_score,
        len(page_results),
        total_usage.total_tokens,
    )

    return quality_report
