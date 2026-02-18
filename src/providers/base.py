from __future__ import annotations

from abc import ABC, abstractmethod


class GitProvider(ABC):
    """Abstract interface for git hosting provider operations."""

    @abstractmethod
    async def clone_repository(
        self,
        url: str,
        branch: str,
        access_token: str | None,
        dest_dir: str,
    ) -> tuple[str, str]:
        """Clone repo to dest_dir. Returns (repo_path, commit_sha)."""

    @abstractmethod
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
        """Create a PR and return the PR URL."""

    @abstractmethod
    async def close_stale_prs(
        self,
        url: str,
        branch_pattern: str,
        access_token: str | None,
    ) -> int:
        """Close open PRs matching branch_pattern. Returns count closed."""

    @abstractmethod
    async def compare_commits(
        self,
        url: str,
        base_sha: str,
        head_sha: str,
        access_token: str | None,
    ) -> list[str]:
        """Return list of changed file paths between two SHAs."""


def get_provider(provider: str) -> GitProvider:
    """Factory function that returns the appropriate GitProvider implementation.

    Imports are deferred to avoid circular imports.
    """
    if provider == "github":
        from src.providers.github import GitHubProvider

        return GitHubProvider()
    if provider == "bitbucket":
        from src.providers.bitbucket import BitbucketProvider

        return BitbucketProvider()

    from src.errors import PermanentError

    raise PermanentError(f"Unsupported git provider: {provider!r}")
