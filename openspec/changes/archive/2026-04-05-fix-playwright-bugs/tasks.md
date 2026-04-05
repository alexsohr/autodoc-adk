## 1. Backend: Enrich RepositoryResponse (BUG-01, 05, 06, 07)

- [x] 1.1 Add computed fields to `RepositoryResponse` in `src/api/schemas/repositories.py`: `status` (str, default "pending"), `page_count` (int, default 0), `scope_count` (int, default 0), `avg_quality_score` (float | None), `last_generated_at` (datetime | None), `default_branch` (str)
- [x] 1.2 Create helper function `enrich_repository_response()` in `src/api/routes/repositories.py` that queries latest job status, page/scope counts, quality scores, and last generation time for a given repository row. Map job status: RUNNING→running, FAILED→failed, COMPLETED→healthy, no jobs→pending. Set `default_branch` = `public_branch`.
- [x] 1.3 Update `list_repositories()` endpoint to call the enrichment helper for each repository in the paginated result. N+1 async queries are acceptable at this scale (max 20 repos, local PostgreSQL).
- [x] 1.4 Update `get_repository()` detail endpoint to call the enrichment helper.
- [x] 1.5 Verify enriched fields appear in `GET /repositories` and `GET /repositories/{id}` responses with curl or test.

## 2. Frontend: Fix Repository Type and Filter (BUG-01)

- [x] 2.1 Verify `web/src/types/repository.ts` `Repository` interface matches the enriched `RepositoryResponse` (status, page_count, scope_count, avg_quality_score, default_branch, last_generated_at). Adjust if needed — ensure `branches` field is either removed or made optional since the backend doesn't return it.
- [x] 2.2 Verify STATUS_FILTERS values in `RepoListPage.tsx` match the lowercase status strings from the enriched backend ("healthy", "running", "failed", "pending"). Confirm the filter count logic works with the new data.

## 3. Frontend: Fix Overview Tab (BUG-05, 06, 07)

- [x] 3.1 Fix the Stats rendering in `OverviewTab.tsx` RepoInfoPanel: use null-safe access with fallback to `0` for `page_count` and `scope_count` (e.g., `repo.page_count ?? 0`). Never render `"undefined"`.
- [x] 3.2 Fix the Main Branch field in `OverviewTab.tsx` RepoInfoPanel: read from `repo.default_branch` (which is now populated from backend's `public_branch` alias).
- [x] 3.3 Fix the workspace header status badge in `RepoWorkspace.tsx`: ensure it reads `repo.status` from the enriched repository data (same as list view). Verify StatusBadge config map includes "pending".

## 4. Frontend: Align Add Repo Dialog (BUG-04, 10)

- [x] 4.1 Redesign AddRepoDialog in `RepoListPage.tsx`: remove `name`/`description` fields. Show all fields upfront (no advanced toggle): `url`, `provider` (auto-detected from URL, shown as read-only badge), `branch_mappings` (key-value editor with add/remove rows, default: `{"main": "main"}`), `public_branch` (dropdown of branch_mappings keys), and optional `access_token`.
- [x] 4.2 Add URL onChange handler that: (a) auto-detects provider from hostname (github.com→github, bitbucket.org→bitbucket), (b) extracts repo name slug from URL for display confirmation, (c) strips `.git` suffix.
- [x] 4.3 Update `useCreateRepository` mutation payload to send `{url, provider, branch_mappings, public_branch, access_token}` matching `RegisterRepositoryRequest`.
- [x] 4.4 Add field-level 422 error display: parse Pydantic validation error body `{detail: [{loc, msg, type}]}` and map `loc` fields to form field error messages.

## 5. Fix Jobs Tab Case Mismatch and Add Error States (BUG-02, 03)

Investigation complete — API routes work correctly. Playwright report URLs were inaccurate.
- BUG-02: Scopes endpoint returns empty `{"scopes": []}` for repos with no docs. Not a 404. Fix is better empty state.
- BUG-03: Case mismatch — `STATUS_FILTERS` uses lowercase but `Job.status` and backend `JobStatus` enum use uppercase. Causes (0) counts and 422 on filter click.

- [x] 5.1 In `JobsTab.tsx`: change `STATUS_FILTERS` values to uppercase (`"RUNNING"`, `"COMPLETED"`, `"FAILED"`, `"CANCELLED"`, `"PENDING"`) to match the `Job.status` type and backend `JobStatus` enum. Update filter count comparison and API filter params accordingly.
- [x] 5.2 In `JobsTab.tsx`: add error state handling — when `useJobs` returns `isError`, replace skeleton with an error message ("Failed to load jobs") and a "Retry" button that calls `refetch()`.
- [x] 5.3 In `DocsTab.tsx`: improve empty state — when `useScopes` returns an empty array, show "No documentation scopes found. Run a documentation generation job to create scopes." instead of "No documentation tree available."
- [x] 5.4 In `DocsTab.tsx`: add error state handling — when `useScopes` returns `isError`, show "Failed to load documentation scopes" with a "Retry" button.

## 6. Frontend: Notifications Dropdown (BUG-08)

- [x] 6.1 Add state and Popover/dropdown to TopBar notifications button: onClick toggles a dropdown panel. Display "No new notifications" placeholder. Close on outside click or Escape.

## 7. Frontend: Global Search Results (BUG-09)

- [x] 7.1 Extend `ContextSearch.tsx` with search state, debounced input handler (300ms), and results dropdown overlay.
- [x] 7.2 On input change, fetch search results by calling `GET /documents/{repoId}/search?q={query}` for each repository (use `useRepositories` to get repo list, then parallel search calls). Cap at first 5 repos for performance.
- [x] 7.3 Render grouped results (repo name → matching pages) in the dropdown. Each result item navigates to `/repos/{repoId}/docs?page={pageKey}` on click. Show "No results found" for empty results. Close dropdown on Escape or blur.

## 8. Verification

- [x] 8.1 Run `uv run ruff check src/ tests/` and `cd web && npx tsc --noEmit` to verify no lint or type errors.
- [x] 8.2 Run `uv run pytest tests/unit/` to verify no regressions.
- [x] 8.3 Run `cd web && npm test` to verify no frontend test regressions.
- [x] 8.4 Manual smoke test: start dev stack, verify each of the 10 bugs is fixed against the Playwright report checklist.
