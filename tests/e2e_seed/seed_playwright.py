"""Idempotent fixture seeder for the Playwright E2E suite.

Inserts canonical fixture rows tagged ``seed_tag='playwright'`` into the
``repositories`` table (plus seeded jobs for the digital-clock repo) and
emits a JSON manifest of inserted IDs/names that the Playwright suite
consumes via ``web/tests/e2e/helpers/seed-data.ts``.

Idempotency: each run begins by deleting all rows with
``seed_tag='playwright'`` so running the script twice does not change the
final row count.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from src.database.engine import get_session_factory

SEED_TAG = "playwright"

# Repo root = parents[2] of this file: tests/e2e_seed/seed_playwright.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = _REPO_ROOT / "web" / "tests" / "e2e" / ".seed-data.json"

_REPOS: tuple[dict[str, str], ...] = (
    {
        "slug": "digitalClock",
        "org": "Kalebu",
        "name": "Digital-clock-in-Python",
        "provider": "github",
    },
    {
        "slug": "debugRepo",
        "org": "test",
        "name": "debug-repo",
        "provider": "github",
    },
    {
        "slug": "dbg2",
        "org": "test",
        "name": "dbg2",
        "provider": "github",
    },
    {
        "slug": "healthy",
        "org": "fixtures",
        "name": "healthy-repo",
        "provider": "github",
    },
    {
        "slug": "running",
        "org": "fixtures",
        "name": "running-repo",
        "provider": "github",
    },
    {
        "slug": "failed",
        "org": "fixtures",
        "name": "failed-repo",
        "provider": "github",
    },
    {
        "slug": "pending",
        "org": "fixtures",
        "name": "pending-repo",
        "provider": "github",
    },
)


async def seed_playwright(manifest_path: Path | None = None) -> dict[str, Any]:
    """Seed Playwright fixtures and write the manifest.

    Args:
        manifest_path: Optional override for the JSON manifest path. When
            omitted, defaults to ``web/tests/e2e/.seed-data.json`` relative
            to the repo root.

    Returns:
        The manifest dict that was written to disk.
    """
    target_path = manifest_path if manifest_path is not None else DEFAULT_MANIFEST
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fixture_urls = [
        f"https://github.com/{spec['org']}/{spec['name']}" for spec in _REPOS
    ]

    factory = get_session_factory()
    async with factory() as session:
        # Idempotency: clear prior playwright-tagged rows. Foreign-key
        # cascades remove dependent jobs / wiki rows.
        await session.execute(
            text("DELETE FROM repositories WHERE seed_tag = :tag"),
            {"tag": SEED_TAG},
        )
        # Also drop any untagged rows occupying our fixture URLs (UNIQUE
        # constraint would otherwise reject the insert).
        await session.execute(
            text("DELETE FROM repositories WHERE url = ANY(:urls)"),
            {"urls": fixture_urls},
        )

        repo_manifest: dict[str, dict[str, str]] = {}
        repo_ids_by_slug: dict[str, str] = {}

        for spec in _REPOS:
            repo_id = str(uuid.uuid4())
            org = spec["org"]
            name = spec["name"]
            url = f"https://github.com/{org}/{name}"
            await session.execute(
                text(
                    """
                    INSERT INTO repositories
                        (id, provider, url, org, name, branch_mappings,
                         public_branch, seed_tag)
                    VALUES
                        (:id, :provider, :url, :org, :name,
                         '{}'::jsonb, :public_branch, :seed_tag)
                    """
                ),
                {
                    "id": repo_id,
                    "provider": spec["provider"],
                    "url": url,
                    "org": org,
                    "name": name,
                    "public_branch": "main",
                    "seed_tag": SEED_TAG,
                },
            )
            repo_manifest[spec["slug"]] = {
                "id": repo_id,
                "name": name,
                "fullName": f"{org}/{name}",
                "provider": spec["provider"],
            }
            repo_ids_by_slug[spec["slug"]] = repo_id

        # Seed jobs only for digitalClock: 1 COMPLETED + 13 FAILED + 6 CANCELLED.
        digital_clock_id = repo_ids_by_slug["digitalClock"]
        completed_job_id = str(uuid.uuid4())

        async def _insert_job(
            job_id: str, status: str, token_usage: str | None = None
        ) -> None:
            await session.execute(
                text(
                    """
                    INSERT INTO jobs
                        (id, repository_id, status, mode, branch, token_usage)
                    VALUES
                        (:id, :repo_id, :status, :mode, :branch,
                         CAST(:token_usage AS jsonb))
                    """
                ),
                {
                    "id": job_id,
                    "repo_id": digital_clock_id,
                    "status": status,
                    "mode": "full",
                    "branch": "main",
                    "token_usage": token_usage,
                },
            )

        # The single COMPLETED job carries token_usage so the admin Usage page
        # exercises non-zero totals (cost, top-repos, total tokens). Other jobs
        # leave token_usage NULL so they don't pad the aggregates. Token counts
        # are sized so the rendered estimated cost rounds to a non-$0.00 value
        # given the route's rates ($0.15/M input, $0.60/M output).
        await _insert_job(
            completed_job_id,
            "COMPLETED",
            token_usage=(
                '{"total_input_tokens": 150000, '
                '"total_output_tokens": 50000, '
                '"total_tokens": 200000}'
            ),
        )
        for _ in range(13):
            await _insert_job(str(uuid.uuid4()), "FAILED")
        for _ in range(6):
            await _insert_job(str(uuid.uuid4()), "CANCELLED")

        await session.commit()

    manifest: dict[str, Any] = {
        "repos": repo_manifest,
        "jobs": {"completedJobId": completed_job_id},
    }

    target_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _main() -> int:
    try:
        asyncio.run(seed_playwright())
    except Exception as exc:  # noqa: BLE001 - top-level CLI guard
        print(f"seed_playwright failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
