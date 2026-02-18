<!-- FOR AI AGENTS -->

# providers/ -- Git Hosting Provider Abstraction

Small package providing a unified interface for git hosting provider operations (clone, PR, diff).

## Key Files

```
providers/
  __init__.py      -> Exports: GitProvider, get_provider
  base.py          -> GitProvider ABC + get_provider(provider) factory
  github.py        -> GitHubProvider implementation (GOLDEN SAMPLE for new providers)
  bitbucket.py     -> BitbucketProvider implementation
```

## GitProvider Interface (base.py)

All methods are async. All accept `access_token: str | None` for authentication.

| Method | Signature | Returns |
|--------|-----------|---------|
| `clone_repository` | `(url, branch, access_token, dest_dir)` | `tuple[str, str]` -- (repo_path, commit_sha) |
| `create_pull_request` | `(url, branch, target_branch, title, body, access_token, reviewers=None, auto_merge=False)` | `str` -- PR URL |
| `close_stale_prs` | `(url, branch_pattern, access_token)` | `int` -- count of PRs closed |
| `compare_commits` | `(url, base_sha, head_sha, access_token)` | `list[str]` -- changed file paths |

## Factory

`get_provider(provider: str) -> GitProvider` in `base.py`. Accepts `"github"` or `"bitbucket"`. Raises `PermanentError` for unsupported providers. Uses deferred imports to avoid circular dependencies.

## Golden Samples

| For | Reference | Key patterns |
|-----|-----------|--------------|
| New provider implementation | `github.py` | Subclass `GitProvider`, implement all 4 abstract methods, use `httpx.AsyncClient`, module-level URL parser + auth header helpers |

## Internal Patterns

- **URL parsing**: Each provider has a module-level `_parse_*()` helper (`_parse_owner_repo` for GitHub, `_parse_workspace_slug` for Bitbucket) that extracts identifiers from HTTPS URLs via regex. Raises `PermanentError` on invalid URL.
- **Auth headers**: Each provider has a module-level `_auth_headers(access_token)` that builds provider-specific HTTP headers. Bearer token if provided, base headers always included.
- **Error classification**: HTTP 5xx raises `TransientError` (retryable by Prefect). HTTP 4xx raises `PermanentError` (fail fast). Both imported from `src.errors`.
- **Clone via subprocess**: Uses `asyncio.create_subprocess_exec` with `git clone --branch <branch> --depth 1`. Token injected into clone URL, sanitized from error messages.
- **SHA retrieval**: After clone, runs `git rev-parse HEAD` via subprocess to get commit SHA.
- **Stale PR cleanup**: Paginates through open PRs, closes/declines those whose source branch starts with `branch_pattern`.
- **Compare via API**: Uses provider's compare/diffstat REST API (not git diff). Returns list of changed file paths.
- **GitHub extras**: `create_pull_request` supports `reviewers` (POST to requested_reviewers endpoint) and `auto_merge` (GraphQL mutation `enablePullRequestAutoMerge` with SQUASH method).
- **Bitbucket pagination**: Uses `next` URL from response JSON for cursor-based pagination (diffstat and PR listing).
- **Logging**: Each provider module uses `logging.getLogger(__name__)`.

## Heuristics

| When | Do |
|------|-----|
| Adding a new provider (e.g., GitLab) | Create `gitlab.py`, subclass `GitProvider`, implement all 4 abstract methods following `github.py` patterns, add `_parse_*()` and `_auth_headers()` helpers, register in `get_provider()` factory in `base.py` |
| Need to clone a repo | Call `provider.clone_repository()` -- returns `(dest_dir, commit_sha)` |
| Need changed files between commits | Call `provider.compare_commits()` -- uses hosting API, not git diff |
| Creating a documentation PR | Call `provider.close_stale_prs()` first, then `provider.create_pull_request()` |
| Handling API errors | Check error type: `TransientError` = retry, `PermanentError` = abort |

## Boundaries

**Always:**
- Subclass `GitProvider` for new providers
- Use `httpx.AsyncClient` for HTTP API calls (async)
- Return `(repo_path, commit_sha)` tuple from `clone_repository`
- Classify errors as `TransientError` (5xx/network) or `PermanentError` (4xx/parse)
- Sanitize access tokens from error messages
- Register new providers in `get_provider()` factory in `base.py`
- Use deferred imports in `get_provider()` to avoid circular dependencies

**Ask first:**
- Adding a new provider (GitLab, etc.)
- Changing PR branch naming convention (`autodoc/{repo_name}-{branch}-{job_id_short}-{YYYY-MM-DD}`)
- Modifying `compare_commits` response format
- Changing clone depth or strategy

**Never:**
- Use git CLI for diff (use hosting provider's compare API)
- Hardcode access tokens
- Skip stale PR cleanup before creating a new PR
- Log or expose access tokens in error messages
