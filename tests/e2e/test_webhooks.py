from __future__ import annotations

import contextlib
import os
from unittest.mock import AsyncMock, patch

import pytest

from tests.e2e.stubs import (
    make_bitbucket_push_payload,
    make_callback_stub,
    make_clone_stub,
    make_github_push_payload,
    make_pr_stub,
    make_structure_stub,
)

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo")

_REPO_COUNTER = 100  # Start high to avoid collision with test_job_lifecycle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_repo(
    client,
    *,
    url: str | None = None,
    provider: str = "github",
    branch_mappings: dict[str, str] | None = None,
) -> dict:
    """Register a repository and return the JSON response body.

    Each call uses a unique URL suffix by default so that tests within the
    same DB transaction do not collide on the unique URL constraint.
    """
    global _REPO_COUNTER
    _REPO_COUNTER += 1

    if url is None:
        url = f"https://github.com/test-org/webhook-project-{_REPO_COUNTER}"

    if branch_mappings is None:
        branch_mappings = {"main": "production"}

    resp = await client.post(
        "/repositories",
        json={
            "url": url,
            "provider": provider,
            "branch_mappings": branch_mappings,
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _flow_patches(
    *,
    clone_side_effect=None,
    scope_result=None,
):
    """Return a list of ``patch`` context managers for all external flow calls.

    Mirrors the pattern from test_job_lifecycle.py to stub out clone, scope
    processing, PR tasks, metrics, callback, and cleanup.
    """
    from dataclasses import asdict

    from src.flows.schemas import (
        PageTaskResult,
        ReadmeTaskResult,
        ScopeProcessingResult,
        StructureTaskResult,
        TokenUsageResult,
    )
    from src.services.config_loader import AutodocConfig

    if clone_side_effect is None:
        clone_side_effect = make_clone_stub(fixture_path=FIXTURE_PATH)

    if scope_result is None:
        stub = make_structure_stub(score=8.2, below_floor=False)
        agent_result = stub.return_value
        spec = agent_result.output
        sections_json = [asdict(s) for s in spec.sections]

        structure_result = StructureTaskResult(
            final_score=8.2,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=1500, output_tokens=800, total_tokens=2300, calls=2),
            output_title=spec.title,
            output_description=spec.description,
            sections_json=sections_json,
        )

        page_results = [
            PageTaskResult(
                page_key="core-module",
                final_score=8.0,
                passed_quality_gate=True,
                below_minimum_floor=False,
                attempts=1,
                token_usage=TokenUsageResult(input_tokens=1200, output_tokens=600, total_tokens=1800, calls=2),
            ),
        ]

        readme_result = ReadmeTaskResult(
            final_score=7.5,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            content="# Webhook Project Docs\n\nGenerated.\n",
            token_usage=TokenUsageResult(input_tokens=1000, output_tokens=500, total_tokens=1500, calls=2),
        )

        scope_result = ScopeProcessingResult(
            structure_result=structure_result,
            page_results=page_results,
            readme_result=readme_result,
            wiki_structure_id=None,
            embedding_count=0,
        )

    scope_mock = AsyncMock(return_value=scope_result)
    close_stale_mock, create_pr_mock = make_pr_stub()
    callback_mock = make_callback_stub()
    default_config = AutodocConfig(scope_path=".")

    return [
        # Clone — at orchestrator import sites
        patch("src.flows.full_generation.clone_repository", side_effect=clone_side_effect),
        patch("src.flows.incremental_update.clone_repository", side_effect=clone_side_effect),
        # Scope processing — replaces entire sub-flow
        patch("src.flows.full_generation.scope_processing_flow", scope_mock),
        # Discover — return a single default config
        patch(
            "src.flows.full_generation.discover_autodoc_configs",
            new_callable=AsyncMock,
            return_value=[default_config],
        ),
        patch(
            "src.flows.incremental_update.discover_autodoc_configs",
            new_callable=AsyncMock,
            return_value=[default_config],
        ),
        # PR
        patch("src.flows.full_generation.close_stale_autodoc_prs", close_stale_mock),
        patch("src.flows.full_generation.create_autodoc_pr", create_pr_mock),
        patch("src.flows.incremental_update.close_stale_autodoc_prs", close_stale_mock),
        patch("src.flows.incremental_update.create_autodoc_pr", create_pr_mock),
        # Metrics
        patch("src.flows.full_generation.aggregate_job_metrics", new_callable=AsyncMock, return_value={}),
        patch("src.flows.incremental_update.aggregate_job_metrics", new_callable=AsyncMock, return_value={}),
        # Callback
        patch("src.flows.full_generation.deliver_callback", callback_mock),
        patch("src.flows.incremental_update.deliver_callback", callback_mock),
        # Cleanup
        patch("src.flows.full_generation.cleanup_workspace", new_callable=AsyncMock),
        patch("src.flows.incremental_update.cleanup_workspace", new_callable=AsyncMock),
    ]


# ---------------------------------------------------------------------------
# 5.2  GitHub push triggers job
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestWebhooks:
    """Webhook endpoint E2E tests (POST /webhooks/push)."""

    async def test_github_push_triggers_job(self, client, db_session, prefect_harness):
        """5.2 — A GitHub push event for a registered repo creates a job (202)."""
        repo_url = "https://github.com/test/webhook-repo-github"
        await _register_repo(client, url=repo_url)

        payload, headers = make_github_push_payload(repo_url, "main", "abc123")

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post("/webhooks/push", json=payload, headers=headers)

        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert "job_id" in data
        assert data["job_id"] is not None

    async def test_bitbucket_push_triggers_job(self, client, db_session, prefect_harness):
        """5.3 — A Bitbucket push event for a registered repo creates a job (202)."""
        repo_url = "https://bitbucket.org/test/webhook-repo-bitbucket"
        await _register_repo(client, url=repo_url, provider="bitbucket")

        payload, headers = make_bitbucket_push_payload(repo_url, "main", "def456")

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post("/webhooks/push", json=payload, headers=headers)

        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert "job_id" in data
        assert data["job_id"] is not None

    async def test_unregistered_repo_returns_204(self, client, db_session):
        """5.4 — Push from an unregistered repo is silently skipped (204)."""
        payload, headers = make_github_push_payload("https://github.com/unknown/not-registered", "main", "aaa111")

        resp = await client.post("/webhooks/push", json=payload, headers=headers)

        assert resp.status_code == 204

    async def test_unconfigured_branch_returns_204(self, client, db_session):
        """5.5 — Push on a branch not in branch_mappings is skipped (204)."""
        repo_url = "https://github.com/test/webhook-repo-branch-skip"
        await _register_repo(
            client,
            url=repo_url,
            branch_mappings={"main": "Main"},
        )

        # Push to "develop" which is NOT in branch_mappings
        payload, headers = make_github_push_payload(repo_url, "develop", "bbb222")

        resp = await client.post("/webhooks/push", json=payload, headers=headers)

        assert resp.status_code == 204

    async def test_unknown_provider_returns_400(self, client, db_session):
        """5.6 — No recognized provider header returns 400."""
        resp = await client.post(
            "/webhooks/push",
            json={"some": "payload"},
            # No X-GitHub-Event or X-Event-Key header
        )

        assert resp.status_code == 400
        assert "provider" in resp.json()["detail"].lower() or "header" in resp.json()["detail"].lower()

    async def test_malformed_json_returns_error(self, client, db_session):
        """5.7 — Invalid JSON body raises an error (handler does not accept it)."""
        import json

        with pytest.raises((json.JSONDecodeError, Exception)):
            await client.post(
                "/webhooks/push",
                content=b"not json",
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "push",
                },
            )

    async def test_webhook_idempotency(self, client, db_session, prefect_harness):
        """5.8 — Webhook returns existing active job instead of creating a duplicate."""
        repo_url = "https://github.com/test/webhook-repo-idempotent"
        repo = await _register_repo(client, url=repo_url)
        repo_id = repo["id"]

        # Create an active job via POST /jobs with _submit_flow patched to
        # no-op so the job stays in PENDING state.
        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            resp1 = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp1.status_code == 201, resp1.text
            original_job_id = resp1.json()["id"]

        # Now POST webhook — should find the existing PENDING job and return it.
        payload, headers = make_github_push_payload(repo_url, "main", "ccc333")

        resp2 = await client.post("/webhooks/push", json=payload, headers=headers)

        assert resp2.status_code == 202, resp2.text
        data = resp2.json()
        assert data["job_id"] == original_job_id, (
            f"Expected idempotent return of existing job {original_job_id}, got {data['job_id']}"
        )
