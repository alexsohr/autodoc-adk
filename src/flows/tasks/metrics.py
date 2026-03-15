from __future__ import annotations

import logging
import uuid

from prefect import task

from src.config.settings import get_settings
from src.flows.schemas import PageTaskResult, ReadmeTaskResult, StructureTaskResult

logger = logging.getLogger(__name__)


@task(name="aggregate_job_metrics")
async def aggregate_job_metrics(
    *,
    job_id: uuid.UUID,
    structure_result: StructureTaskResult | None,
    page_results: list[PageTaskResult],
    readme_result: ReadmeTaskResult | None,
) -> dict:
    """Collect token usage and quality scores from all agent results.

    Builds ``quality_report`` and ``token_usage`` JSONB objects, updates
    the job record via its own DB session.

    Returns the quality_report dict.
    """
    settings = get_settings()

    # Build token usage with simple integer tracking
    total_input = 0
    total_output = 0
    total_tokens = 0
    total_calls = 0
    by_agent: dict[str, dict] = {}

    if structure_result:
        tu = structure_result.token_usage
        total_input += tu.input_tokens
        total_output += tu.output_tokens
        total_tokens += tu.total_tokens
        total_calls += tu.calls
        by_agent["structure_extractor"] = tu.model_dump()

    page_input = 0
    page_output = 0
    page_tokens = 0
    page_calls = 0
    page_scores: list[dict] = []
    pages_below_floor = 0

    for pr in page_results:
        page_input += pr.token_usage.input_tokens
        page_output += pr.token_usage.output_tokens
        page_tokens += pr.token_usage.total_tokens
        page_calls += pr.token_usage.calls
        page_scores.append(
            {
                "page_key": pr.page_key,
                "score": pr.final_score,
                "passed": pr.passed_quality_gate,
                "attempts": pr.attempts,
                "below_minimum_floor": pr.below_minimum_floor,
            }
        )
        if pr.below_minimum_floor:
            pages_below_floor += 1

    total_input += page_input
    total_output += page_output
    total_tokens += page_tokens
    total_calls += page_calls
    by_agent["page_generator"] = {
        "input_tokens": page_input,
        "output_tokens": page_output,
        "total_tokens": page_tokens,
        "calls": page_calls,
    }

    if readme_result:
        tu = readme_result.token_usage
        total_input += tu.input_tokens
        total_output += tu.output_tokens
        total_tokens += tu.total_tokens
        total_calls += tu.calls
        by_agent["readme_distiller"] = tu.model_dump()

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
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "by_agent": by_agent,
    }

    # Update job record via own DB session
    from src.database.engine import get_session_factory
    from src.database.repos.job_repo import JobRepo

    session_factory = get_session_factory()
    async with session_factory() as session:
        job_repo = JobRepo(session)
        job = await job_repo.get_by_id(job_id)
        if job is not None:
            job.quality_report = quality_report
            job.token_usage = token_usage_report
            await session.flush()
        await session.commit()

    logger.info(
        "Aggregated metrics: overall=%.2f, pages=%d, tokens=%d",
        overall_score,
        len(page_results),
        total_tokens,
    )

    return quality_report
