## Why

Playwright automated testing against the deployed dashboard (localhost:3000) found 10 bugs, 4 of them blocking. The root cause for most (BUG-01, 04, 05, 06, 07) is a schema mismatch: the backend `RepositoryResponse` returns only raw database columns (`id, url, provider, org, name, branch_mappings, public_branch, created_at, updated_at`) while the frontend `Repository` TypeScript type expects enriched fields (`status, page_count, scope_count, default_branch, avg_quality_score, last_generated_at, branches, description`). The Add Repo dialog also sends fields the backend doesn't accept (`name`, `description`, `default_branch`) instead of the required ones (`branch_mappings`, `public_branch`, `provider`). Two additional bugs are UI stubs that were never implemented (notifications panel, global search results).

## What Changes

- **Enrich `RepositoryResponse`** with computed fields: `status` (derived from latest job), `page_count`, `scope_count`, `avg_quality_score`, `last_generated_at`, and alias `default_branch` → `public_branch`. This fixes BUG-01, 05, 06, 07 in one shot.
- **Align Add Repo dialog** to backend `RegisterRepositoryRequest` schema: replace `name`/`description`/`default_branch` fields with `provider` selector, `branch_mappings` input, and `public_branch`. Auto-extract repo name from URL. Surface 422 field-level errors. Fixes BUG-04 and BUG-10.
- **Investigate and fix API 404s** for scopes and jobs tabs. The frontend hooks (`useScopes` → `/documents/{id}/scopes`, `useJobs` → `/jobs?repository_id={id}`) appear correct, but the Playwright test reports 404. Likely a deployment/proxy issue or data-dependent 404. Verify routes are reachable and fix as needed. Also add error states instead of infinite skeletons. Fixes BUG-02, 03.
- **Implement notifications dropdown** with placeholder "No notifications" state. Fixes BUG-08.
- **Implement global search results dropdown** using existing `/documents/{id}/search` endpoint or a new cross-repo search. Fixes BUG-09.

## Capabilities

### New Capabilities
- `repo-list-enrichment`: Backend enrichment of repository list/detail responses with computed fields (status, counts, scores)
- `add-repo-alignment`: Align AddRepo dialog form fields to backend schema, with field-level error display and URL→name auto-populate
- `ui-stubs-completion`: Implement notifications dropdown and global search results panel

### Modified Capabilities
- `repo-workspace`: Fix Overview tab rendering of Stats and Main Branch fields (null-safe reads of enriched fields)
- `jobs-ui`: Add error state for failed API calls instead of infinite skeleton
- `docs-browser`: Verify scopes API call path and add empty-state/error handling

## Impact

- **Backend**: `src/api/schemas/repositories.py` (`RepositoryResponse`), `src/api/routes/repositories.py` (list/detail endpoints enrichment queries)
- **Frontend**: `web/src/pages/RepoListPage.tsx` (AddRepo dialog, filter logic), `web/src/pages/tabs/OverviewTab.tsx` (null-safe field reads), `web/src/pages/tabs/JobsTab.tsx` (error state), `web/src/pages/tabs/DocsTab.tsx` (error state), `web/src/components/layout/TopBar.tsx` (notifications), `web/src/components/layout/ContextSearch.tsx` (search results)
- **Types**: `web/src/types/repository.ts` may need alignment depending on enrichment approach
- **No database migrations** — all new fields are computed from existing data
- **No breaking API changes** — fields are additive on `RepositoryResponse`
