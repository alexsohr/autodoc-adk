## Context

The dashboard frontend was built against a `Repository` TypeScript type that assumes an enriched response shape (status, page_count, scope_count, default_branch, avg_quality_score, etc.), but the backend `RepositoryResponse` schema (`src/api/schemas/repositories.py`) only returns raw database columns. The Add Repo dialog was designed for a simplified create flow (URL + name) but the backend `RegisterRepositoryRequest` requires `provider`, `branch_mappings`, and `public_branch`. Two UI features (notifications, global search) are wired to buttons/inputs but have no backing implementation.

Existing infrastructure that's relevant:
- `GET /repositories/{id}/overview` already computes `page_count`, `avg_quality_score`, `scope_summaries`, `last_job` — but only for a single repo, not the list view.
- `GET /documents/{id}/scopes` exists at the correct path; the frontend `useScopes` hook calls it correctly.
- `GET /jobs` with `repository_id` query param exists; the frontend `useJobs` hook calls it correctly.
- `GET /documents/{id}/search` exists for per-repo search.

## Goals / Non-Goals

**Goals:**
- Fix all 10 bugs from the Playwright report so every feature works end-to-end
- Keep changes additive (no breaking API changes, no migrations)
- Maintain type safety between backend schemas and frontend types

**Non-Goals:**
- Cross-repository global search (BUG-09 fix will search within pinned/all repos using existing per-repo search)
- Real-time notification system (BUG-08 fix will add a placeholder dropdown)
- Redesigning the Add Repo flow beyond what the backend schema requires

## Decisions

### D1: Enrich RepositoryResponse at the schema level

**Decision**: Add computed fields directly to `RepositoryResponse` and compute them in the list/detail route handlers, rather than creating a separate dashboard-specific endpoint.

**Rationale**: The frontend `Repository` type is used everywhere (list, cards, workspace header, overview tab). Having a single enriched response avoids maintaining two parallel response shapes. The `RepositoryOverviewResponse` already computes most of these values for the detail view — we'll extract the computation logic into a shared helper.

**Alternative considered**: Creating a `GET /dashboard/repositories` endpoint that returns enriched data. Rejected because it duplicates the existing `/repositories` endpoint and forces the frontend to know which endpoint to call in which context.

**Fields to add to `RepositoryResponse`:**
| Field | Type | Computation |
|-------|------|-------------|
| `status` | `str` | Derived from latest job: `RUNNING`→running, `FAILED`→failed, `COMPLETED`→healthy, no jobs→pending |
| `page_count` | `int` | `COUNT(*)` from wiki_pages for this repo's latest structures |
| `scope_count` | `int` | `COUNT(DISTINCT scope_path)` from wiki_structures for this repo |
| `avg_quality_score` | `float \| None` | Average of page quality scores, or None if no pages |
| `last_generated_at` | `datetime \| None` | `updated_at` of the latest completed job |
| `default_branch` | `str` | Alias for existing `public_branch` |

**Performance note**: The enrichment helper will make per-repo async queries (N+1 pattern). With cursor-based pagination capped at 20 repos and all queries hitting the same local PostgreSQL instance, this is acceptable (~100 async queries, well under 200ms). Batch methods or raw SQL subqueries are deferred unless profiling shows a bottleneck.

### D2: Align Add Repo dialog to RegisterRepositoryRequest

**Decision**: Redesign the dialog to show all fields upfront: `url`, `provider` (auto-detected from URL), `branch_mappings` (key-value editor, default: `{"main": "main"}`), `public_branch` (dropdown of mapping keys), and optional `access_token`. No hidden/advanced sections — all fields always visible.

**Removed fields**: `name` and `description` are removed from the form. The backend derives `org`/`name` from the URL. `description` has no backend column and is out of scope.

**Flow:**
1. User enters URL → provider auto-detected (github.com → github, bitbucket.org → bitbucket), repo name displayed as confirmation
2. Branch mappings editor shown with default `main → main`, user can add/remove rows
3. Public branch dropdown populated from branch mapping keys
4. Optional access token field for private repos
5. 422 errors displayed with field-level detail from Pydantic's `ValidationError` response body

### D3: Fix Jobs tab case mismatch and Docs tab empty state (investigation complete)

**Investigation result**: Both API routes work correctly (200 through backend, Vite proxy, and nginx). The Playwright report URLs were inaccurate — the tester misreported the paths.

**BUG-02 (Docs tab)**: Not an API bug. The scopes endpoint returns `{"scopes": []}` for repos with no generated documentation. The UI shows "No documentation tree available" which is functionally correct but could be more helpful. Fix: improve the empty state message to guide users toward running a generation job.

**BUG-03 (Jobs tab)**: Real bug, but **not a 404**. Root cause is a **case mismatch** between frontend and backend:
- `JobsTab.STATUS_FILTERS` uses lowercase values (`"running"`, `"failed"`, etc.)
- Backend `JobStatus` StrEnum uses uppercase (`"RUNNING"`, `"FAILED"`, etc.)
- Filter **counts** compare `j.status === f.value` → `"FAILED" === "failed"` → always false → all counts show (0)
- Filter **API calls** send lowercase status → backend returns 422 (enum validation) → TanStack Query errors → skeleton persists (no error handling)

**Fix**: Use uppercase values in `STATUS_FILTERS` to match the `Job.status` type and the backend `JobStatus` enum. Also add error state handling for `isError`.

### D4: Notifications — placeholder dropdown

**Decision**: Add a minimal Popover-based dropdown triggered by the bell icon. Show "No new notifications" placeholder. This unblocks the UI without building a full notification system.

### D5: Global search — cross-repo search using existing search endpoint

**Decision**: The ContextSearch component will:
1. Show a results dropdown when the user types (debounced 300ms)
2. Search across all repositories using `GET /documents/{id}/search` called in parallel for each repo (or the first 5 repos)
3. Display grouped results (repo → pages) in a dropdown overlay
4. Navigate to the matching page on click

**Scope**: Queries the first 5 repositories from the list (no dependency on pinning). If fewer than 5 exist, queries all of them.

**Alternative considered**: A new backend endpoint `GET /search?q=...` that searches across all repos. Better for performance but requires a new route. For now, the parallel-query approach works with the 5-repo cap.

## Risks / Trade-offs

- **[Performance] Enriched list query uses N+1** → Accepted tradeoff. Max 20 repos × ~5 async queries each against local PostgreSQL. Well under 200ms. Defer batch optimization unless profiling shows a bottleneck.
- **[Scope] Global search with parallel per-repo queries doesn't scale** → Capped at 5 repos. Acceptable for current scale. Document as future optimization to add a cross-repo search endpoint.
- **[Data] Status derived from latest job may be stale** → Acceptable — dashboard already uses polling (TanStack Query `refetchInterval`). Could add WebSocket push later.
- **[UX] Add Repo dialog shows all fields** → All fields visible (no advanced toggle). Sensible defaults (auto-detect provider, pre-filled branch mapping `main→main`) reduce friction while keeping the form honest.
