"""Webhook receiver for Git provider push events (T076, T077)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.routes.jobs import _submit_flow
from src.config.settings import get_settings
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class WebhookAcceptedResponse(BaseModel):
    job_id: UUID


# ---------------------------------------------------------------------------
# T077: Provider-specific payload parsers
# ---------------------------------------------------------------------------


def parse_github_push(payload: dict) -> tuple[str, str, str]:
    """Extract (repo_url, branch, commit_sha) from a GitHub push event payload.

    Raises ``ValueError`` on missing or invalid fields.
    """
    try:
        repo_url: str = payload["repository"]["clone_url"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Missing repository.clone_url in GitHub payload") from exc

    ref: str | None = payload.get("ref")
    if not ref or not ref.startswith("refs/heads/"):
        raise ValueError(
            f"Invalid or missing ref in GitHub payload (expected refs/heads/*): {ref!r}"
        )
    branch = ref.removeprefix("refs/heads/")

    commit_sha: str | None = payload.get("after")
    if not commit_sha:
        raise ValueError("Missing 'after' commit SHA in GitHub payload")

    return repo_url, branch, commit_sha


def parse_bitbucket_push(payload: dict) -> tuple[str, str, str]:
    """Extract (repo_url, branch, commit_sha) from a Bitbucket push event payload.

    Raises ``ValueError`` on missing or invalid fields.
    """
    try:
        repo_url: str = payload["repository"]["links"]["html"]["href"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Missing repository.links.html.href in Bitbucket payload"
        ) from exc

    try:
        changes = payload["push"]["changes"]
        change = changes[0]
        branch: str = change["new"]["name"]
        commit_sha: str = change["new"]["target"]["hash"]
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(
            "Missing or invalid push.changes in Bitbucket payload"
        ) from exc

    return repo_url, branch, commit_sha


# ---------------------------------------------------------------------------
# T076: POST /webhooks/push
# ---------------------------------------------------------------------------


@router.post(
    "/webhooks/push",
    response_model=None,
    responses={
        202: {"model": WebhookAcceptedResponse},
        204: {"description": "Webhook skipped"},
        400: {"description": "Invalid payload"},
    },
    status_code=202,
)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    repository_repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> Response | JSONResponse:
    """Receive push webhooks from GitHub or Bitbucket.

    Detects provider from request headers, normalises the payload to extract
    repository URL, branch, and commit SHA, then triggers a documentation
    generation job if the repository is registered and the branch is configured.

    Returns 202 when a job is triggered, 204 when skipped, 400 for bad payloads.
    """
    payload = await request.json()

    # 1. Detect provider and parse payload
    github_event = request.headers.get("X-GitHub-Event")
    bitbucket_event = request.headers.get("X-Event-Key")

    try:
        if github_event:
            if github_event != "push":
                return Response(status_code=204)
            repo_url, branch, commit_sha = parse_github_push(payload)
        elif bitbucket_event:
            if bitbucket_event != "repo:push":
                return Response(status_code=204)
            repo_url, branch, commit_sha = parse_bitbucket_push(payload)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unable to detect Git provider from request headers",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 2. Look up repository
    repo = await repository_repo.get_by_url(repo_url)
    if repo is None:
        logger.debug("Webhook skipped: repository not registered (%s)", repo_url)
        return Response(status_code=204)

    # 3. Check if branch is configured
    if branch not in repo.branch_mappings:
        logger.debug(
            "Webhook skipped: branch %s not in branch_mappings for %s",
            branch,
            repo_url,
        )
        return Response(status_code=204)

    # 4. Idempotency check
    existing = await job_repo.get_active_for_repo(
        repository_id=repo.id,
        branch=branch,
        dry_run=False,
    )
    if existing is not None:
        logger.info(
            "Webhook: returning existing active job %s for %s/%s",
            existing.id,
            repo_url,
            branch,
        )
        return JSONResponse(
            status_code=202,
            content=WebhookAcceptedResponse(job_id=existing.id).model_dump(mode="json"),
        )

    # 5. Determine mode
    structure = await wiki_repo.get_latest_structure(
        repository_id=repo.id,
        branch=branch,
    )
    mode = "full" if structure is None else "incremental"

    # 6. Create job
    settings = get_settings()
    job = await job_repo.create(
        repository_id=repo.id,
        status="PENDING",
        mode=mode,
        branch=branch,
        force=False,
        dry_run=False,
        app_commit_sha=settings.APP_COMMIT_SHA,
    )

    # 7. Submit flow
    background_tasks.add_task(
        _submit_flow,
        mode=mode,
        repository_id=repo.id,
        job_id=job.id,
        branch=branch,
        dry_run=False,
    )

    logger.info(
        "Webhook: created %s job %s for %s branch=%s sha=%s",
        mode,
        job.id,
        repo_url,
        branch,
        commit_sha,
    )

    return JSONResponse(
        status_code=202,
        content=WebhookAcceptedResponse(job_id=job.id).model_dump(mode="json"),
    )
