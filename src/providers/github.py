from __future__ import annotations

import asyncio
import logging
import re

import httpx

from src.errors import PermanentError, TransientError
from src.providers.base import GitProvider

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_GITHUB_GRAPHQL = "https://api.github.com/graphql"


def _parse_owner_repo(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Supports HTTPS URLs like:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
    """
    match = re.match(r"https?://github\.com/([^/]+)/([^/.]+?)(?:\.git)?/?$", url)
    if not match:
        raise PermanentError(f"Cannot parse GitHub owner/repo from URL: {url}")
    return match.group(1), match.group(2)


def _auth_headers(access_token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


class GitHubProvider(GitProvider):
    """GitHub implementation of the GitProvider interface."""

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
        owner, repo = _parse_owner_repo(url)

        if access_token:
            clone_url = f"https://{access_token}@github.com/{owner}/{repo}.git"
        else:
            clone_url = f"https://github.com/{owner}/{repo}.git"

        logger.info("Cloning %s/%s (branch=%s) into %s", owner, repo, branch, dest_dir)

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
        logger.info("Cloned %s/%s at %s", owner, repo, commit_sha)
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
        owner, repo = _parse_owner_repo(url)
        headers = _auth_headers(access_token)

        payload: dict[str, object] = {
            "head": branch,
            "base": target_branch,
            "title": title,
            "body": body,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=headers,
                json=payload,
            )

            if resp.status_code == 422:
                # Might be "A pull request already exists" -- not necessarily fatal
                detail = resp.json().get("message", "")
                logger.warning("GitHub 422 creating PR: %s", detail)
                raise PermanentError(f"GitHub PR creation conflict (422): {detail}")

            if resp.status_code >= 500:
                raise TransientError(f"GitHub API server error ({resp.status_code}): {resp.text}")

            if resp.status_code >= 400:
                raise PermanentError(f"GitHub API client error ({resp.status_code}): {resp.text}")

            pr_data = resp.json()
            pr_url: str = pr_data["html_url"]
            pr_number: int = pr_data["number"]
            node_id: str = pr_data["node_id"]

            logger.info("Created PR #%d: %s", pr_number, pr_url)

            # Request reviewers if provided
            if reviewers:
                review_resp = await client.post(
                    f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers",
                    headers=headers,
                    json={"reviewers": reviewers},
                )
                if review_resp.status_code >= 400:
                    logger.warning(
                        "Failed to request reviewers (status %d): %s",
                        review_resp.status_code,
                        review_resp.text,
                    )

            # Enable auto-merge via GraphQL if requested
            if auto_merge:
                await self._enable_auto_merge(client, headers, node_id)

        return pr_url

    async def _enable_auto_merge(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        pr_node_id: str,
    ) -> None:
        """Enable auto-merge on a PR using the GitHub GraphQL API."""
        mutation = """
        mutation EnableAutoMerge($pullRequestId: ID!) {
            enablePullRequestAutoMerge(input: {pullRequestId: $pullRequestId, mergeMethod: SQUASH}) {
                pullRequest { number }
            }
        }
        """
        graphql_headers = {**headers, "Content-Type": "application/json"}

        resp = await client.post(
            _GITHUB_GRAPHQL,
            headers=graphql_headers,
            json={"query": mutation, "variables": {"pullRequestId": pr_node_id}},
        )

        if resp.status_code >= 400:
            logger.warning("Failed to enable auto-merge (status %d): %s", resp.status_code, resp.text)
        else:
            data = resp.json()
            if "errors" in data:
                logger.warning("GraphQL errors enabling auto-merge: %s", data["errors"])
            else:
                logger.info("Auto-merge enabled for PR node %s", pr_node_id)

    # ------------------------------------------------------------------ #
    # close_stale_prs
    # ------------------------------------------------------------------ #
    async def close_stale_prs(
        self,
        url: str,
        branch_pattern: str,
        access_token: str | None,
    ) -> int:
        owner, repo = _parse_owner_repo(url)
        headers = _auth_headers(access_token)
        closed_count = 0

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while True:
                resp = await client.get(
                    f"{_GITHUB_API}/repos/{owner}/{repo}/pulls",
                    headers=headers,
                    params={"state": "open", "per_page": 100, "page": page},
                )

                if resp.status_code >= 400:
                    logger.warning("Failed to list PRs (status %d): %s", resp.status_code, resp.text)
                    break

                prs = resp.json()
                if not prs:
                    break

                for pr in prs:
                    head_ref = pr.get("head", {}).get("ref", "")
                    if head_ref.startswith(branch_pattern):
                        close_resp = await client.patch(
                            f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{pr['number']}",
                            headers=headers,
                            json={"state": "closed"},
                        )
                        if close_resp.status_code < 300:
                            closed_count += 1
                            logger.info("Closed stale PR #%d (%s)", pr["number"], head_ref)
                        else:
                            logger.warning(
                                "Failed to close PR #%d (status %d)",
                                pr["number"],
                                close_resp.status_code,
                            )

                page += 1

        logger.info("Closed %d stale PR(s) matching pattern %r", closed_count, branch_pattern)
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
        owner, repo = _parse_owner_repo(url)
        headers = _auth_headers(access_token)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_GITHUB_API}/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}",
                headers=headers,
            )

            if resp.status_code >= 500:
                raise TransientError(f"GitHub compare API error ({resp.status_code}): {resp.text}")

            if resp.status_code >= 400:
                raise PermanentError(f"GitHub compare API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            files: list[str] = [f["filename"] for f in data.get("files", [])]

        logger.info("Compared %s...%s: %d changed file(s)", base_sha[:8], head_sha[:8], len(files))
        return files
