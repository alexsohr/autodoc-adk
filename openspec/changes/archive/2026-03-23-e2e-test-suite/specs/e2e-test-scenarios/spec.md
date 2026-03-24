## ADDED Requirements

<!-- ═══════════════════════════════════════════════════════════════
     TIER 1: MUST-HAVE (~25 scenarios)
     Core happy paths + error paths for flows tested manually today
     ═══════════════════════════════════════════════════════════════ -->

### Requirement: Full generation happy path
The system SHALL test the complete lifecycle from repository registration through job completion, verifying that all database records are created correctly and documents are retrievable via the API. [TIER 1]

#### Scenario: Repository registration through document retrieval
- **WHEN** `POST /repositories` registers a fixture repo, then `POST /jobs` triggers full generation, and the flow completes
- **THEN** `GET /jobs/{id}` returns status COMPLETED with a non-null `quality_report`, `GET /documents/{repo_id}` returns all three wiki pages, and each page's content contains the expected `page_key`

#### Scenario: Structure matches canned output
- **WHEN** full generation completes
- **THEN** `GET /jobs/{id}/structure` returns a wiki structure with 2 sections and 3 pages matching the StructureExtractor stub output

#### Scenario: Job fields populated correctly
- **WHEN** full generation completes
- **THEN** `GET /jobs/{id}` returns mode="full", commit_sha is set, pull_request_url is set, token_usage is non-null, and quality_report contains overall_score, page_scores, and structure_score

### Requirement: Dry run mode
The system SHALL test that `dry_run=true` produces structure only, with no pages generated, no README distilled, and no PR created. [TIER 1]

#### Scenario: Dry run produces structure only
- **WHEN** `POST /jobs` is called with `dry_run=true` and the flow completes
- **THEN** `StructureExtractor.run()` is called exactly once, `PageGenerator.run()` is never called, `ReadmeDistiller.run()` is never called, `create_autodoc_pr()` is never called, and `GET /documents/{repo_id}` returns zero pages

### Requirement: Quality gate failure
The system SHALL test that a below-floor quality score causes the job to fail with appropriate error information. [TIER 1]

#### Scenario: Below-floor structure score fails the job
- **WHEN** the StructureExtractor stub returns `score=3.0` with `below_minimum_floor=True` and `POST /jobs` triggers generation
- **THEN** `GET /jobs/{id}` returns status FAILED, the error information references quality or floor violation, and no WikiPages exist for the job

### Requirement: Incremental update — affected pages only
The system SHALL test that only affected pages are regenerated when source files change, and unchanged pages are preserved from the previous version. [TIER 1]

#### Scenario: Only changed pages regenerated
- **WHEN** a full generation has completed, then `POST /jobs` triggers an incremental update with `compare_commits` returning `["src/core.py"]` as the only changed file
- **THEN** `PageGenerator.run()` is called only for pages whose `source_files` include `src/core.py`, and the job completes with mode "incremental" and status COMPLETED

#### Scenario: Unchanged pages preserved
- **WHEN** an incremental update completes
- **THEN** pages not affected by the change retain their content from the previous version

### Requirement: Incremental — no changes detected
The system SHALL test that when no files have changed between commits, the incremental flow short-circuits to COMPLETED without processing any scopes. [TIER 1]

#### Scenario: No changes short-circuits
- **WHEN** `compare_commits` returns an empty list of changed files
- **THEN** the job completes with status COMPLETED, quality_report contains `no_changes=true`, and no agents are invoked

### Requirement: Incremental — structural change triggers re-extraction
The system SHALL test that when structural files (e.g., `__init__.py`, `.autodoc.yaml`) change, the structure is re-extracted before regenerating pages. [TIER 1]

#### Scenario: Structural change re-extracts structure
- **WHEN** `compare_commits` returns `["src/__init__.py"]` (a structural indicator)
- **THEN** `StructureExtractor.run()` is called for the affected scope, and pages referencing changed files are regenerated

### Requirement: Incremental — no baseline SHA
The system SHALL test that attempting incremental update without a prior full generation fails with a clear error. [TIER 1]

#### Scenario: No baseline fails permanently
- **WHEN** `POST /jobs` triggers incremental mode but no prior structure exists for the repo+branch
- **THEN** the job transitions to FAILED with an error message indicating no baseline SHA

### Requirement: Job idempotency
The system SHALL test that submitting a duplicate job with the same parameters returns the existing active job. [TIER 1]

#### Scenario: Duplicate job returns existing
- **WHEN** `POST /jobs` is called twice with identical `repository_id`, `branch`, and `dry_run` while the first job is still active
- **THEN** the second response returns status 200 (not 201) with the same job ID as the first

### Requirement: Error propagation — transient and permanent
The system SHALL test that transient errors trigger retries and permanent errors fail the job immediately. [TIER 1]

#### Scenario: Transient error triggers retry
- **WHEN** `clone_repository` raises `TransientError` on the first call and succeeds on the second
- **THEN** the flow retries and the job eventually completes with status COMPLETED

#### Scenario: Permanent error fails immediately
- **WHEN** `clone_repository` raises `PermanentError("repo not found")`
- **THEN** the job transitions directly to FAILED and the error message contains "repo not found"

#### Scenario: QualityError from structure extraction
- **WHEN** the structure extraction task raises `QualityError`
- **THEN** the job transitions to FAILED with a quality-related error message and no pages are created

### Requirement: Repository registration and validation
The system SHALL test repository registration with valid and invalid inputs. [TIER 1]

#### Scenario: Register valid GitHub repository
- **WHEN** `POST /repositories` is called with a valid GitHub URL, provider="github", branch_mappings, and public_branch
- **THEN** the response is 201 with correct id, url, org, name, provider, and branch_mappings

#### Scenario: Register duplicate URL
- **WHEN** `POST /repositories` is called with a URL that is already registered
- **THEN** the response is 409 conflict

#### Scenario: Register with URL/provider mismatch
- **WHEN** `POST /repositories` is called with url="https://github.com/org/repo" but provider="bitbucket"
- **THEN** the response is 422 validation error

#### Scenario: Register with public_branch not in branch_mappings
- **WHEN** `POST /repositories` is called with public_branch="staging" but branch_mappings only contains "main"
- **THEN** the response is 422 validation error

### Requirement: Repository deletion cascade
The system SHALL test that deleting a repository cleans up all associated data across all related tables. [TIER 1]

#### Scenario: Cascade delete removes all associated records
- **WHEN** full generation has populated all tables for a repository, then `DELETE /repositories/{id}` is called
- **THEN** all jobs, wiki_structures, wiki_pages, and page_chunks associated with that repository are deleted from the database

### Requirement: Search correctness
The system SHALL test that text search, semantic search, and hybrid search all return expected results over generated content with deterministic embeddings. [TIER 1]

#### Scenario: Text search finds pages by keyword
- **WHEN** full generation completes and `GET /documents/{repo_id}/search?query=core&search_type=text` is called with a keyword present in canned page content
- **THEN** the response contains pages whose content includes that keyword

#### Scenario: Semantic search returns related pages
- **WHEN** full generation completes and `GET /documents/{repo_id}/search?query=core&search_type=semantic` is called
- **THEN** the response contains pages with non-zero relevance scores ordered by similarity

#### Scenario: Hybrid search uses RRF ranking
- **WHEN** full generation completes and `GET /documents/{repo_id}/search?query=core&search_type=hybrid` is called
- **THEN** the response contains results ranked by Reciprocal Rank Fusion combining text and semantic scores

### Requirement: Mode auto-detection
The system SHALL test that the job mode is correctly auto-detected based on existing state. [TIER 1]

#### Scenario: Auto-detect full mode when no prior structure
- **WHEN** `POST /jobs` is called for a repo+branch with no existing wiki structure and `force=false`
- **THEN** the job is created with mode="full"

#### Scenario: Auto-detect incremental mode when structure exists
- **WHEN** `POST /jobs` is called for a repo+branch that has an existing wiki structure and `force=false`
- **THEN** the job is created with mode="incremental"

#### Scenario: Force overrides to full mode
- **WHEN** `POST /jobs` is called with `force=true` for a repo+branch with existing structure
- **THEN** the job is created with mode="full" regardless of existing structure

### Requirement: Job creation validation
The system SHALL test job creation input validation. [TIER 1]

#### Scenario: Repository not found
- **WHEN** `POST /jobs` is called with a non-existent repository_id
- **THEN** the response is 404

#### Scenario: Branch not in branch_mappings
- **WHEN** `POST /jobs` is called with a branch not in the repository's branch_mappings
- **THEN** the response is 422

<!-- ═══════════════════════════════════════════════════════════════
     TIER 2: IMPORTANT (~30 scenarios)
     Webhooks, job lifecycle edges, incremental subtleties
     ═══════════════════════════════════════════════════════════════ -->

### Requirement: Webhook — GitHub push
The system SHALL test that GitHub push webhooks trigger incremental jobs for registered repos. [TIER 2]

#### Scenario: GitHub push triggers job
- **WHEN** `POST /webhooks/push` receives a valid GitHub push payload with `X-GitHub-Event: push` header for a registered repo and configured branch
- **THEN** the response is 202 with a job_id

#### Scenario: GitHub push for unregistered repo
- **WHEN** `POST /webhooks/push` receives a GitHub push payload for a repo URL not in the database
- **THEN** the response is 204 (silent skip)

#### Scenario: GitHub push for unconfigured branch
- **WHEN** `POST /webhooks/push` receives a GitHub push payload for a registered repo but a branch not in branch_mappings
- **THEN** the response is 204 (silent skip)

### Requirement: Webhook — Bitbucket push
The system SHALL test that Bitbucket push webhooks trigger incremental jobs for registered repos. [TIER 2]

#### Scenario: Bitbucket push triggers job
- **WHEN** `POST /webhooks/push` receives a valid Bitbucket push payload with `X-Event-Key: repo:push` header for a registered repo and configured branch
- **THEN** the response is 202 with a job_id

### Requirement: Webhook — error handling
The system SHALL test webhook error paths. [TIER 2]

#### Scenario: Unknown provider
- **WHEN** `POST /webhooks/push` receives a payload with no recognized event header
- **THEN** the response is 400

#### Scenario: Malformed JSON
- **WHEN** `POST /webhooks/push` receives invalid JSON
- **THEN** the response is 400

#### Scenario: Webhook idempotency
- **WHEN** `POST /webhooks/push` receives a push payload while an active job already exists for that repo+branch
- **THEN** the response is 202 with the existing job_id

### Requirement: Job cancel
The system SHALL test job cancellation for various job states. [TIER 2]

#### Scenario: Cancel PENDING job
- **WHEN** `POST /jobs/{id}/cancel` is called for a PENDING job
- **THEN** the job transitions to CANCELLED

#### Scenario: Cancel RUNNING job
- **WHEN** `POST /jobs/{id}/cancel` is called for a RUNNING job
- **THEN** the job transitions to CANCELLED

#### Scenario: Cancel COMPLETED job
- **WHEN** `POST /jobs/{id}/cancel` is called for a COMPLETED job
- **THEN** the response is 409 (invalid transition)

#### Scenario: Cancel already CANCELLED job
- **WHEN** `POST /jobs/{id}/cancel` is called for an already CANCELLED job
- **THEN** the response is 409 (invalid transition)

### Requirement: Job retry
The system SHALL test job retry behavior. [TIER 2]

#### Scenario: Retry FAILED job
- **WHEN** `POST /jobs/{id}/retry` is called for a FAILED job
- **THEN** the job resets to PENDING, error_message is cleared, mode is re-determined, and a new flow is submitted

#### Scenario: Retry non-FAILED job
- **WHEN** `POST /jobs/{id}/retry` is called for a COMPLETED job
- **THEN** the response is 409

#### Scenario: Retry non-existent job
- **WHEN** `POST /jobs/{id}/retry` is called with a non-existent UUID
- **THEN** the response is 404

### Requirement: Repository update
The system SHALL test repository update operations. [TIER 2]

#### Scenario: Update branch_mappings
- **WHEN** `PATCH /repositories/{id}` is called with new branch_mappings
- **THEN** the response is 200 with updated mappings

#### Scenario: Update access_token only
- **WHEN** `PATCH /repositories/{id}` is called with only access_token
- **THEN** the response is 200 with the token updated

#### Scenario: Update public_branch to invalid value
- **WHEN** `PATCH /repositories/{id}` sets public_branch to a branch not in branch_mappings
- **THEN** the response is 422

#### Scenario: Update with no fields
- **WHEN** `PATCH /repositories/{id}` is called with an empty body
- **THEN** the response is 422 "No fields to update"

#### Scenario: Update non-existent repository
- **WHEN** `PATCH /repositories/{id}` is called with a non-existent UUID
- **THEN** the response is 404

### Requirement: Callback delivery
The system SHALL test that completion callbacks are delivered correctly. [TIER 2]

#### Scenario: Callback on successful completion
- **WHEN** `POST /jobs` is called with a `callback_url` and the job completes successfully
- **THEN** `deliver_callback()` is invoked with the callback_url and a payload containing job_id, status=COMPLETED, quality_report, and pull_request_url

#### Scenario: Callback on failure
- **WHEN** `POST /jobs` is called with a `callback_url` and the job fails
- **THEN** `deliver_callback()` is invoked with status=FAILED and error_message in the payload

### Requirement: Stale PR cleanup
The system SHALL test that existing autodoc PRs are closed before creating a new one. [TIER 2]

#### Scenario: Stale PRs closed before new PR
- **WHEN** full generation runs and `close_stale_autodoc_prs` is stubbed
- **THEN** `close_stale_autodoc_prs()` is called before `create_autodoc_pr()`

### Requirement: No .autodoc.yaml defaults to root scope
The system SHALL test that a repository without `.autodoc.yaml` is processed with default configuration at scope_path=".". [TIER 2]

#### Scenario: Default config for repo without .autodoc.yaml
- **WHEN** the fixture repo has no `.autodoc.yaml` file and `POST /jobs` triggers full generation
- **THEN** the flow processes the repository with scope_path="." and default configuration values

### Requirement: Monorepo with multiple scopes
The system SHALL test that a repository with multiple `.autodoc.yaml` files processes each scope independently. [TIER 2]

#### Scenario: Multiple scopes processed in parallel
- **WHEN** the fixture repo has `.autodoc.yaml` at root and `packages/api/.autodoc.yaml`, and `POST /jobs` triggers full generation
- **THEN** both scopes are processed, each with their own WikiStructure and WikiPages

#### Scenario: Scope overlap auto-exclusion
- **WHEN** a parent scope at "." has a child scope at "packages/api/"
- **THEN** the parent scope auto-excludes the "packages/api/" directory from its file tree

### Requirement: Partial scope failure
The system SHALL test behavior when some scopes succeed and others fail. [TIER 2]

#### Scenario: Partial failure marks job as FAILED with partial results
- **WHEN** a monorepo has 2 scopes, scope A succeeds but scope B's StructureExtractor raises PermanentError
- **THEN** the job is marked FAILED, but scope A's pages are accessible in the database

#### Scenario: All scopes fail
- **WHEN** all scopes raise PermanentError during processing
- **THEN** the job is marked FAILED with a clear error message

### Requirement: Incremental dry run
The system SHALL test dry_run=true in incremental mode. [TIER 2]

#### Scenario: Incremental dry run skips PR
- **WHEN** `POST /jobs` triggers an incremental update with `dry_run=true`
- **THEN** changed pages are regenerated but no PR is created

<!-- ═══════════════════════════════════════════════════════════════
     TIER 3: NICE-TO-HAVE (~31 scenarios)
     Pagination, health checks, validation corners, documents
     ═══════════════════════════════════════════════════════════════ -->

### Requirement: Repository list pagination
The system SHALL test cursor-based pagination on the repository list endpoint. [TIER 3]

#### Scenario: First page with next_cursor
- **WHEN** `GET /repositories?limit=2` is called with 5 repositories in the database
- **THEN** the response contains 2 items and a non-null `next_cursor`

#### Scenario: Last page
- **WHEN** `GET /repositories?cursor={last_cursor}&limit=2` is called and only 1 repository remains
- **THEN** the response contains 1 item and `next_cursor` is null

#### Scenario: Empty results
- **WHEN** `GET /repositories` is called with no repositories in the database
- **THEN** the response contains items=[] and next_cursor=null

### Requirement: Repository get
The system SHALL test retrieving a single repository. [TIER 3]

#### Scenario: Get existing repository
- **WHEN** `GET /repositories/{id}` is called for an existing repository
- **THEN** the response is 200 with all repository fields

#### Scenario: Get non-existent repository
- **WHEN** `GET /repositories/{id}` is called with a non-existent UUID
- **THEN** the response is 404

### Requirement: Delete non-existent repository
The system SHALL test deleting a repository that does not exist. [TIER 3]

#### Scenario: Delete non-existent
- **WHEN** `DELETE /repositories/{id}` is called with a non-existent UUID
- **THEN** the response is 404

### Requirement: Job list with filters
The system SHALL test the job listing endpoint with various filter combinations. [TIER 3]

#### Scenario: Filter by repository_id
- **WHEN** `GET /jobs?repository_id={id}` is called
- **THEN** only jobs for that repository are returned

#### Scenario: Filter by status
- **WHEN** `GET /jobs?status=COMPLETED` is called
- **THEN** only completed jobs are returned

#### Scenario: Filter by branch
- **WHEN** `GET /jobs?branch=main` is called
- **THEN** only jobs for the main branch are returned

#### Scenario: Combined filters
- **WHEN** `GET /jobs?repository_id={id}&status=FAILED` is called
- **THEN** only failed jobs for that specific repository are returned

#### Scenario: Empty results
- **WHEN** `GET /jobs?status=CANCELLED` is called and no cancelled jobs exist
- **THEN** the response contains items=[] and next_cursor=null

### Requirement: Job get
The system SHALL test retrieving individual job details. [TIER 3]

#### Scenario: Get completed job has quality report
- **WHEN** `GET /jobs/{id}` is called for a COMPLETED job
- **THEN** the response includes quality_report and token_usage

#### Scenario: Get failed job has error message
- **WHEN** `GET /jobs/{id}` is called for a FAILED job
- **THEN** the response includes error_message

#### Scenario: Get non-existent job
- **WHEN** `GET /jobs/{id}` is called with a non-existent UUID
- **THEN** the response is 404

### Requirement: Job tasks and logs
The system SHALL test the task state and log retrieval endpoints. [TIER 3]

#### Scenario: Get tasks for job without flow run
- **WHEN** `GET /jobs/{id}/tasks` is called for a job with no prefect_flow_run_id
- **THEN** the response is an empty list

#### Scenario: Get logs for job without flow run
- **WHEN** `GET /jobs/{id}/logs` is called for a job with no prefect_flow_run_id
- **THEN** the response is an empty list

### Requirement: Document scopes listing
The system SHALL test the scopes listing endpoint. [TIER 3]

#### Scenario: List scopes after generation
- **WHEN** full generation completes and `GET /documents/{repo_id}/scopes` is called
- **THEN** the response contains at least one scope with scope_path, title, and page_count > 0

#### Scenario: List scopes with no structures
- **WHEN** `GET /documents/{repo_id}/scopes` is called for a repo with no wiki structures
- **THEN** the response contains an empty scopes list

### Requirement: Document page retrieval
The system SHALL test individual page retrieval. [TIER 3]

#### Scenario: Get specific page by key
- **WHEN** `GET /documents/{repo_id}/pages/{page_key}` is called for an existing page
- **THEN** the response includes page_key, title, content, source_files, and quality_score

#### Scenario: Get page not found
- **WHEN** `GET /documents/{repo_id}/pages/nonexistent` is called
- **THEN** the response is 404

### Requirement: Full wiki retrieval
The system SHALL test the full wiki endpoint. [TIER 3]

#### Scenario: Get full wiki
- **WHEN** `GET /documents/{repo_id}/wiki` is called after generation
- **THEN** the response includes title, sections with embedded pages, scope_path, branch, and commit_sha

#### Scenario: Get wiki with no structure
- **WHEN** `GET /documents/{repo_id}/wiki` is called for a repo with no wiki structure
- **THEN** the response is 404

### Requirement: Paginated wiki sections
The system SHALL test the paginated wiki endpoint. [TIER 3]

#### Scenario: Paginate wiki sections
- **WHEN** `GET /documents/{repo_id}?limit=1` is called after generation
- **THEN** the response contains 1 section and a non-null next_cursor

### Requirement: Search with scope filter
The system SHALL test search filtered by scope path. [TIER 3]

#### Scenario: Search within specific scope
- **WHEN** `GET /documents/{repo_id}/search?query=core&scope=packages/api` is called
- **THEN** only results from the "packages/api" scope are returned

#### Scenario: Search with no results
- **WHEN** `GET /documents/{repo_id}/search?query=zzzznonexistent` is called
- **THEN** the response contains an empty results list

### Requirement: Health check
The system SHALL test the health check endpoint with various dependency states. [TIER 3]

#### Scenario: All healthy
- **WHEN** `GET /health` is called with all dependencies available
- **THEN** the response is 200 with status="healthy"

#### Scenario: Database degraded
- **WHEN** `GET /health` is called with the database unreachable
- **THEN** the response is 200 with status="degraded" or status="unhealthy"

### Requirement: Repo size limits
The system SHALL test that repositories exceeding configured limits are rejected. [TIER 3]

#### Scenario: Too many files
- **WHEN** the fixture repo's file tree exceeds `MAX_TOTAL_FILES`
- **THEN** the flow raises PermanentError and the job is marked FAILED

### Requirement: Flow submission failure
The system SHALL test behavior when flow submission itself fails. [TIER 3]

#### Scenario: Flow submission error
- **WHEN** `POST /jobs` is called but the internal flow submission raises an exception
- **THEN** the job is created with status FAILED and error_message describes the submission failure

### Requirement: Test suite performance
The complete E2E test suite SHALL execute in under 3 minutes including database startup and migration. [TIER 1]

#### Scenario: Suite completes within time budget
- **WHEN** the full E2E test suite runs from testcontainers startup through all test scenarios to completion
- **THEN** the total elapsed time is under 180 seconds

### Requirement: Zero external API calls
The E2E test suite SHALL make zero calls to external APIs (LLM providers, Git hosting, embedding services) during execution. [TIER 1]

#### Scenario: No network calls to external services
- **WHEN** the E2E test suite runs to completion
- **THEN** no HTTP requests are made to LLM provider APIs, Git hosting APIs, or embedding service APIs
