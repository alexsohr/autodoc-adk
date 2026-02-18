from __future__ import annotations

import asyncio
import logging
import re

import httpx

from src.errors import PermanentError, TransientError
from src.providers.base import GitProvider

logger = logging.getLogger(__name__)

_BITBUCKET_API = "https://api.bitbucket.org/2.0"


def _parse_workspace_slug(url: str) -> tuple[str, str]:
    """Extract (workspace, slug) from a Bitbucket URL.

    Supports HTTPS URLs like:
        https://bitbucket.org/workspace/repo-slug
        https://bitbucket.org/workspace/repo-slug.git
    """
    match = re.match(r"https?://bitbucket\.org/([^/]+)/([^/.]+?)(?:\.git)?/?$", url)
    if not match:
        raise PermanentError(f"Cannot parse Bitbucket workspace/slug from URL: {url}")
    return match.group(1), match.group(2)


def _auth_headers(access_token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


class BitbucketProvider(GitProvider):
    """Bitbucket Cloud implementation of the GitProvider interface."""

    # ------------------------------------------------------------------ #
    # clone_repository
    # ------------------------------------------------------------------ #
    async def clone_repository(
        self,
        url: str,
        branch: str,
        access_token: str | None,
        dest_dir: str,
    ) -> tuple[str, str]:
        workspace, slug = _parse_workspace_slug(url)

        if access_token:
            clone_url = f"https://x-token-auth:{access_token}@bitbucket.org/{workspace}/{slug}.git"
        else:
            clone_url = f"https://bitbucket.org/{workspace}/{slug}.git"

        logger.info("Cloning %s/%s (branch=%s) into %s", workspace, slug, branch, dest_dir)

        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--branch", branch, "--depth", "1", clone_url, dest_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode().strip() if stderr else "unknown error"
            # Sanitise token from error messages
            if access_token:
                err_msg = err_msg.replace(access_token, "***")
            raise TransientError(f"git clone failed (exit {proc.returncode}): {err_msg}")

        # Read HEAD SHA
        sha_proc = await asyncio.create_subprocess_exec(
            "git", "-C", dest_dir, "rev-parse", "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await sha_proc.communicate()

        if sha_proc.returncode != 0:
            err_msg = stderr.decode().strip() if stderr else "unknown error"
            raise TransientError(f"git rev-parse HEAD failed: {err_msg}")

        commit_sha = stdout.decode().strip()
        logger.info("Cloned %s/%s at %s", workspace, slug, commit_sha)
        return dest_dir, commit_sha

    # ------------------------------------------------------------------ #
    # create_pull_request
    # ------------------------------------------------------------------ #
    async def create_pull_request(
        self,
        url: str,
        branch: str,
        target_branch: str,
        title: str,
        body: str,
        access_token: str | None,
        reviewers: list[str] | None = None,
        auto_merge: bool = False,
    ) -> str:
        workspace, slug = _parse_workspace_slug(url)
        headers = _auth_headers(access_token)

        payload: dict[str, object] = {
            "title": title,
            "description": body,
            "source": {"branch": {"name": branch}},
            "destination": {"branch": {"name": target_branch}},
            "close_source_branch": auto_merge,
        }

        if reviewers:
            payload["reviewers"] = [{"username": r} for r in reviewers]

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_BITBUCKET_API}/repositories/{workspace}/{slug}/pullrequests",
                headers=headers,
                json=payload,
            )

            if resp.status_code == 409:
                # Conflict -- PR may already exist
                detail = resp.json().get("error", {}).get("message", resp.text)
                logger.warning("Bitbucket 409 creating PR: %s", detail)
                raise PermanentError(f"Bitbucket PR creation conflict (409): {detail}")

            if resp.status_code >= 500:
                raise TransientError(f"Bitbucket API server error ({resp.status_code}): {resp.text}")

            if resp.status_code >= 400:
                raise PermanentError(f"Bitbucket API client error ({resp.status_code}): {resp.text}")

            pr_data = resp.json()
            pr_url: str = pr_data["links"]["html"]["href"]
            pr_id: int = pr_data["id"]

        logger.info("Created PR #%d: %s", pr_id, pr_url)
        return pr_url

    # ------------------------------------------------------------------ #
    # close_stale_prs
    # ------------------------------------------------------------------ #
    async def close_stale_prs(
        self,
        url: str,
        branch_pattern: str,
        access_token: str | None,
    ) -> int:
        workspace, slug = _parse_workspace_slug(url)
        headers = _auth_headers(access_token)
        closed_count = 0

        async with httpx.AsyncClient(timeout=30) as client:
            next_url: str | None = (
                f"{_BITBUCKET_API}/repositories/{workspace}/{slug}/pullrequests?state=OPEN"
            )

            while next_url:
                resp = await client.get(next_url, headers=headers)

                if resp.status_code >= 400:
                    logger.warning("Failed to list PRs (status %d): %s", resp.status_code, resp.text)
                    break

                data = resp.json()
                prs = data.get("values", [])

                for pr in prs:
                    source_branch = pr.get("source", {}).get("branch", {}).get("name", "")
                    if source_branch.startswith(branch_pattern):
                        pr_id = pr["id"]
                        decline_resp = await client.post(
                            f"{_BITBUCKET_API}/repositories/{workspace}/{slug}/pullrequests/{pr_id}/decline",
                            headers=headers,
                        )
                        if decline_resp.status_code < 300:
                            closed_count += 1
                            logger.info("Declined stale PR #%d (%s)", pr_id, source_branch)
                        else:
                            logger.warning(
                                "Failed to decline PR #%d (status %d)",
                                pr_id,
                                decline_resp.status_code,
                            )

                next_url = data.get("next")

        logger.info("Declined %d stale PR(s) matching pattern %r", closed_count, branch_pattern)
        return closed_count

    # ------------------------------------------------------------------ #
    # compare_commits
    # ------------------------------------------------------------------ #
    async def compare_commits(
        self,
        url: str,
        base_sha: str,
        head_sha: str,
        access_token: str | None,
    ) -> list[str]:
        workspace, slug = _parse_workspace_slug(url)
        headers = _auth_headers(access_token)
        changed_files: list[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            next_url: str | None = (
                f"{_BITBUCKET_API}/repositories/{workspace}/{slug}/diffstat/{base_sha}..{head_sha}"
            )

            while next_url:
                resp = await client.get(next_url, headers=headers)

                if resp.status_code >= 500:
                    raise TransientError(f"Bitbucket diffstat API error ({resp.status_code}): {resp.text}")

                if resp.status_code >= 400:
                    raise PermanentError(f"Bitbucket diffstat API error ({resp.status_code}): {resp.text}")

                data = resp.json()

                for entry in data.get("values", []):
                    # Use new.path for additions/modifications, old.path for deletions
                    new_path = entry.get("new")
                    old_path = entry.get("old")
                    if new_path and new_path.get("path"):
                        changed_files.append(new_path["path"])
                    elif old_path and old_path.get("path"):
                        changed_files.append(old_path["path"])

                next_url = data.get("next")

        logger.info("Compared %s..%s: %d changed file(s)", base_sha[:8], head_sha[:8], len(changed_files))
        return changed_files
