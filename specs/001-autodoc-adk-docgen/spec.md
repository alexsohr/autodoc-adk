# Feature Specification: AutoDoc ADK Documentation Generator

**Feature Branch**: `001-autodoc-adk-docgen`
**Created**: 2026-02-15
**Status**: Draft
**Input**: User description: "AutoDoc ADK documentation generator — full system as described in the v2 structure design document"

## User Scenarios & Testing

### User Story 1 - Full Documentation Generation (Priority: P1)

A developer registers a repository (specifying the branches to document and the target branches for PRs) and triggers documentation generation. The system determines whether this is a first-time (full) or incremental run based on whether a previous commit SHA is stored for that repository in autodoc. For a first-time run, the system clones the repository, analyzes its structure, generates comprehensive wiki-style documentation pages, distills a README, and opens a pull request with the README targeting the configured PR branch.

**Why this priority**: This is the core value proposition — turning a codebase into structured documentation automatically. Without this, nothing else works.

**Independent Test**: Can be fully tested by registering a sample repository via the API (with documented branches and PR target branch), triggering a generation job, and verifying that a PR is created targeting the configured branch with a README and that wiki pages are stored and searchable.

**Acceptance Scenarios**:

1. **Given** a registered public repository with no previous commit SHA stored in autodoc, **When** a user triggers `POST /jobs`, **Then** the system determines this is a full generation, creates a job (PENDING), clones the repository, extracts documentation structure, generates wiki pages with quality evaluation, distills a README, stores wiki pages in PostgreSQL, and creates a pull request containing the README targeting the configured PR branch.
2. **Given** a registered private repository with an access token, **When** a user triggers generation, **Then** the system authenticates the clone and PR creation using the stored access token.
3. **Given** a job is in progress, **When** a user queries `GET /jobs/{id}`, **Then** the response includes the current status, and upon completion includes `quality_report`, `token_usage`, and `pull_request_url`.
4. **Given** a repository with no `.autodoc.yaml`, **When** full generation is triggered, **Then** sensible defaults are applied (all files included, junior-developer audience, tutorial tone, comprehensive detail).
5. **Given** a repository with existing documentation and no code changes since the last run, **When** a user triggers `POST /jobs` with `force: true`, **Then** the system performs a full documentation generation regardless of whether changes exist.
6. **Given** a repository with existing documentation and no code changes since the last run, **When** a user triggers `POST /jobs` without the `force` flag, **Then** the job completes immediately with `status: no_changes` and no regeneration is performed.

---

### User Story 2 - Incremental Documentation Update (Priority: P1)

A developer pushes code changes and triggers a documentation job. Because the repository already has a previous commit SHA stored in autodoc (from a prior full generation), the system automatically determines this is an incremental update. It detects changed files via the provider's compare API, regenerates only affected pages, merges with unchanged pages, and creates an updated PR targeting the configured PR branch.

**Why this priority**: Incremental updates are essential for ongoing maintenance — full regeneration is expensive and slow. This makes the system practical for continuous use.

**Independent Test**: Can be tested by first running a full generation (so a commit SHA is stored), then modifying source files in the repository, and triggering a new job. The system automatically selects incremental mode. Verify that only affected pages are regenerated and the PR contains the updated README.

**Acceptance Scenarios**:

1. **Given** a repository with existing documentation and a stored `commit_sha` in autodoc, **When** `POST /jobs` is triggered, **Then** the system automatically determines this is an incremental update, diffs changed files via the provider API, clones only if changes exist, regenerates only affected pages, and creates a PR targeting the configured PR branch.
2. **Given** no files have changed since the last documentation run, **When** a job is triggered without the `force` flag, **Then** the job completes immediately with `status: no_changes` and no clone is performed.
3. **Given** structural changes are detected (new modules or deleted directories), **When** an incremental job runs, **Then** the structure is re-extracted before regenerating affected pages.
4. **Given** no files have changed since the last documentation run, **When** a job is triggered with `force: true`, **Then** the system performs a full regeneration regardless, overriding the incremental logic.

---

### User Story 3 - Quality-Gated Generation with Generator & Critic Pattern (Priority: P1)

Each generating agent (StructureExtractor, PageGenerator, ReadmeDistiller) uses a Generator & Critic loop where a separate Critic sub-agent (potentially a different LLM model) evaluates output against a weighted rubric and provides feedback for retry.

**Why this priority**: Quality gating is fundamental to producing useful documentation. Without it, the system generates unreliable content.

**Independent Test**: Can be tested by configuring low quality thresholds, triggering generation, and verifying that agents retry with Critic feedback, track best attempts, and respect per-criterion minimum scores.

**Acceptance Scenarios**:

1. **Given** a Generator produces output below the quality threshold, **When** the Critic evaluates it, **Then** the loop retries with the Critic's feedback up to `max_attempts`, tracking the best result.
2. **Given** a best attempt after all retries is below `MINIMUM_SCORE_FLOOR`, **When** the agent loop completes, **Then** the result is flagged as `below_minimum_floor` in the `AgentResult`.
3. **Given** a per-criterion floor is configured (e.g., accuracy >= 5.0), **When** one criterion falls below its floor even though the weighted average passes, **Then** the result is flagged as below minimum floor.
4. **Given** the Critic LLM call fails (rate limit, timeout), **When** the failure is caught, **Then** the attempt is auto-passed with a warning and the pipeline continues.

---

### User Story 4 - Repository Configuration via .autodoc.yaml (Priority: P2)

A developer places a `.autodoc.yaml` file in their repository to customize documentation style, include/exclude patterns, README preferences, and PR settings.

**Why this priority**: Configuration customization allows teams to tailor documentation to their needs. It builds on the core generation capability.

**Independent Test**: Can be tested by creating a repository with a `.autodoc.yaml` specifying custom include/exclude patterns, style preferences, and README settings, then verifying the generated documentation respects all configured options.

**Acceptance Scenarios**:

1. **Given** a repository with a `.autodoc.yaml` specifying `include: ["src/"]` and `exclude: ["*.test.*"]`, **When** documentation is generated, **Then** only files under `src/` (excluding test files) are documented.
2. **Given** a `.autodoc.yaml` with `style.audience: "senior-developer"` and `style.tone: "reference"`, **When** pages are generated, **Then** the documentation style reflects these preferences.
3. **Given** a `.autodoc.yaml` with `custom_instructions` containing domain-specific terminology, **When** documentation is generated, **Then** the custom instructions are injected into agent prompts.
4. **Given** a `.autodoc.yaml` with unknown keys, **When** the config is loaded, **Then** warnings are emitted and stored in the job record.
5. **Given** a `.autodoc.yaml` with invalid values, **When** the config is loaded, **Then** the job fails with a descriptive validation error.

---

### User Story 5 - Monorepo Support (Priority: P2)

A developer working on a monorepo places `.autodoc.yaml` files in multiple sub-projects. The system discovers all scopes, processes them in parallel, and produces separate wiki structures and READMEs per scope in a single PR.

**Why this priority**: Monorepo support extends the system to enterprise-scale repositories. It depends on the core generation and configuration stories.

**Independent Test**: Can be tested by creating a repository with `.autodoc.yaml` files in root and two sub-directories, triggering generation, and verifying separate wiki structures exist per scope and a single PR contains all scope READMEs.

**Acceptance Scenarios**:

1. **Given** a monorepo with `.autodoc.yaml` at root and `packages/auth/`, **When** full generation is triggered, **Then** two scopes are processed in parallel, each with its own wiki structure and pages.
2. **Given** overlapping scopes (root and sub-directory), **When** scopes are discovered, **Then** the parent scope auto-excludes the child scope's directory.
3. **Given** an incremental update where only one scope has changed files, **When** the incremental job runs, **Then** only the affected scope's pages are regenerated.

---

### User Story 6 - Documentation Search (Priority: P2)

A developer or external agent searches across generated wiki documentation using text, semantic, or hybrid search.

**Why this priority**: Search enables consumption of the generated documentation and is the primary way users interact with wiki content after generation.

**Independent Test**: Can be tested by generating documentation for a repository, then performing text, semantic, and hybrid searches via the API and verifying relevant results are returned.

**Acceptance Scenarios**:

1. **Given** a repository with generated wiki pages, **When** a user queries `GET /documents/{repo_id}/search?query=authentication&search_type=text`, **Then** relevant pages are returned ranked by text relevance.
2. **Given** generated wiki pages with embeddings, **When** a semantic search is performed, **Then** results are ranked by cosine similarity of content embeddings.
3. **Given** a hybrid search request, **When** the search executes, **Then** results are combined using Reciprocal Rank Fusion (RRF) with k=60.
4. **Given** a search with `scope` parameter specified, **When** the search executes, **Then** results are filtered to only that scope's pages.

---

### User Story 7 - Job Management (Priority: P2)

A user manages documentation jobs: viewing status, cancelling running jobs, retrying failed jobs, and receiving webhook callbacks on completion.

**Why this priority**: Job management provides operational control over the system. Users need visibility and control over long-running documentation generation processes.

**Independent Test**: Can be tested by triggering a job, checking its status, cancelling it, retrying a failed job, and verifying webhook callbacks are delivered.

**Acceptance Scenarios**:

1. **Given** a running job, **When** `POST /jobs/{id}/cancel` is called, **Then** the job is cancelled via Prefect's native cancellation and status is updated to CANCELLED.
2. **Given** a failed job, **When** `POST /jobs/{id}/retry` is called, **Then** the flow resumes from the last successful Prefect task.
3. **Given** a job with `callback_url` configured, **When** the job completes or fails, **Then** a webhook notification is POSTed to the callback URL with job details.
4. **Given** duplicate `POST /jobs` requests for the same `(repository_id, branch, dry_run)`, **When** an active job exists, **Then** the existing job is returned instead of creating a duplicate.

---

### User Story 8 - Webhook-Driven Documentation Updates (Priority: P3)

A Git provider sends a push webhook to the system. The webhook handler determines whether to trigger a full or incremental documentation run based on whether a previous commit SHA is stored for that repository in autodoc. If a commit SHA exists, it triggers an incremental update; if no commit SHA exists (first-time documentation), it triggers a full generation.

**Why this priority**: Webhooks automate the documentation update pipeline, removing manual trigger steps. This is an enhancement over the manual API trigger.

**Independent Test**: Can be tested by sending a simulated GitHub push webhook payload to `POST /webhooks/push` — first for a repository with no stored commit SHA (verify full generation), then after documentation exists (verify incremental generation).

**Acceptance Scenarios**:

1. **Given** a registered repository with a stored commit SHA and webhook configured, **When** a GitHub push event is received at `POST /webhooks/push`, **Then** the system detects the provider from headers, extracts the repo URL and branch, determines this is an incremental update (commit SHA exists), and triggers an incremental job.
2. **Given** a registered repository with no stored commit SHA, **When** a push webhook is received, **Then** the system determines this is a first-time generation and triggers a full documentation job.
3. **Given** the pushed branch is not in the repository's configured documentation branches, **When** the webhook is received, **Then** the event is skipped.
4. **Given** an unregistered repository URL in the webhook payload, **When** the webhook is processed, **Then** the event is skipped (auto-registration is not performed for webhooks — repositories must be pre-registered with their branch configuration).
5. **Given** rapid successive pushes to the same branch, **When** multiple webhooks arrive, **Then** job idempotency prevents duplicate jobs.

---

### User Story 9 - MCP Server for External Agents (Priority: P3)

External AI agents consume the autodoc system as an MCP server with two focused tools: discovering registered repositories and querying their generated documentation.

**Why this priority**: MCP integration extends the system's reach to other AI agents but depends on all core functionality being in place first. The MCP surface is intentionally minimal — documentation generation is triggered via the REST API or webhooks, not through MCP.

**Independent Test**: Can be tested by connecting an MCP client to the autodoc MCP server and invoking `find_repository` to discover a registered repository, then using `query_documents` with the discovered repository to search its documentation.

**Acceptance Scenarios**:

1. **Given** an external agent, **When** it calls the `find_repository` MCP tool with a search term (name, URL, or partial match), **Then** matching registered repositories are returned with their IDs, names, providers, and documented branches.
2. **Given** a repository ID obtained from `find_repository`, **When** an agent calls `query_documents` with the repository ID and a natural language query, **Then** relevant documentation pages are returned ranked by relevance.

---

### Edge Cases

- What happens when a repository exceeds `MAX_REPO_SIZE` or `MAX_TOTAL_FILES`? The scan_file_tree task fails with a `PermanentError` and the job is marked FAILED.
- What happens when a page generation fails but others succeed? Already-committed pages persist as partial results; the job is marked FAILED with a detailed quality report. Retry resumes from the last successful task.
- What happens when the embedding model configuration changes between runs? Existing embeddings become invalid. A full re-generation is required for all repositories.
- What happens when multiple scopes have overlapping files? Parent scopes auto-exclude child scope directories.
- What happens when an orphaned temp directory exists from a crashed worker? A scheduled cleanup task removes `autodoc_*` temp dirs older than 1 hour.
- What happens when the Prefect server is unreachable during job creation? The health check reports `unhealthy` status; job creation fails gracefully.
- What happens when pruning removes >90% of files in scan_file_tree? A warning is emitted but processing continues.

## Out of Scope (v1)

- **UI dashboard** — no web interface for browsing documentation; consumption is via API, MCP, and PRs
- **Multi-language documentation** — output is English only
- **PDF export** — no document format conversion
- **Self-hosted Git providers** — no Gitea, Gogs, or other self-hosted Git support; only GitHub, GitLab, Bitbucket
- **User accounts and RBAC** — no application-level authentication or role-based access control; auth is deferred to infrastructure
- **Token encryption** — access tokens stored as plaintext; encryption deferred to a future version

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow users to register repositories (GitHub, GitLab, Bitbucket) with optional access tokens (stored as plaintext in v1) via a REST API. During registration, users MUST specify a 1:1 mapping of documentation branches to PR target branches and designate exactly one branch as the **public branch** whose wiki is used for all search queries.
- **FR-002**: System MUST support full documentation generation — clone, scan/prune file tree, extract structure, generate pages with quality evaluation, distill README, create PR targeting the configured PR branch.
- **FR-003**: System MUST support incremental documentation updates — detect changes via provider compare API, regenerate only affected pages, merge with unchanged pages, create PR targeting the configured PR branch.
- **FR-003a**: System MUST automatically determine whether a job is full or incremental based on whether a previous commit SHA is stored for the repository in autodoc. If no commit SHA exists, the system performs full generation; if a commit SHA exists, it performs incremental update.
- **FR-003b**: System MUST support a `force` flag on the `POST /jobs` API that triggers full documentation generation regardless of whether changes exist or a previous commit SHA is stored.
- **FR-004**: System MUST implement a Generator & Critic loop pattern where each generating agent (StructureExtractor, PageGenerator, ReadmeDistiller) pairs a Generator sub-agent with a separate Critic sub-agent for independent quality evaluation against weighted rubrics.
- **FR-005**: System MUST support configurable Critic models separate from Generator models to avoid self-reinforcing evaluation bias.
- **FR-006**: System MUST produce two output formats: a structured wiki (sections + pages in PostgreSQL) and a distilled README pushed via pull request.
- **FR-007**: System MUST support per-scope `.autodoc.yaml` configuration for customizing include/exclude patterns, documentation style, custom instructions, README preferences, and PR settings.
- **FR-008**: System MUST support monorepo documentation via auto-discovery of multiple `.autodoc.yaml` files, processing each scope in parallel with independent wiki structures and READMEs.
- **FR-009**: System MUST provide text search (PostgreSQL tsvector), semantic search (pgvector), and hybrid search (Reciprocal Rank Fusion) across wiki pages via API and MCP (`query_documents` tool). Search queries MUST default to the repository's designated public branch.
- **FR-010**: System MUST create pull requests containing generated READMEs, targeting the PR branch configured during repository registration, with configurable reviewers and auto-merge settings.
- **FR-011**: System MUST expose exactly two MCP tools for external agents: `find_repository` (discover registered repositories by name, URL, or partial match) and `query_documents` (search documentation for a repository discovered via `find_repository`).
- **FR-012**: System MUST support job management: status tracking, cancellation (Prefect native), retry from last successful task, and webhook callbacks on completion/failure.
- **FR-013**: System MUST enforce job idempotency — duplicate requests for the same `(repository_id, branch, dry_run)` return the existing active job.
- **FR-014**: System MUST receive Git provider push/merge webhooks and automatically determine whether to trigger full or incremental documentation generation based on whether a previous commit SHA is stored for the repository. Webhooks MUST only trigger jobs for branches in the repository's configured documentation branches.
- **FR-015**: System MUST persist ADK agent sessions to PostgreSQL via DatabaseSessionService, enabling Critic feedback to be fed back to the Generator through conversation history across retry attempts.
- **FR-016**: System MUST archive ADK sessions to S3 after each flow run and delete them from PostgreSQL.
- **FR-017**: System MUST track the best attempt (highest score) across retries, with configurable overall minimum score floor and per-criterion minimum scores.
- **FR-018**: System MUST aggregate token usage and quality metrics from all AgentResults at the end of each job.
- **FR-019**: System MUST support dry-run mode for both full and incremental flows, extracting structure without generating content.
- **FR-020**: System MUST enforce repository size limits (MAX_TOTAL_FILES, MAX_FILE_SIZE, MAX_REPO_SIZE) during file tree scanning.
- **FR-021**: System MUST retain up to 3 wiki structure versions per `(repository_id, branch, scope_path)`, deleting the oldest when a 4th is created.
- **FR-022**: System MUST close stale autodoc PRs before creating new ones for the same branch.
- **FR-023**: System MUST reconcile stale RUNNING jobs against Prefect flow states on startup.
- **FR-024**: System MUST support scope overlap auto-exclusion where parent scopes automatically exclude child scope directories with their own `.autodoc.yaml`.
- **FR-025**: System MUST support updating and deleting repositories with cascading deletes of associated documentation, jobs, and wiki structures.
- **FR-026**: System MUST enforce a 1-hour hard timeout on all job types (full and incremental). When a pod reaches the timeout, it MUST update the job status to FAILED (with a timeout reason) before the pod is terminated.
- **FR-027**: System MUST enforce a configurable global concurrency limit on simultaneous running jobs (e.g., `MAX_CONCURRENT_JOBS`). Jobs exceeding the limit remain in PENDING status until a slot is available. Managed via Prefect's native concurrency limits.

### Key Entities

- **Repository**: A registered Git repository (GitHub/GitLab/Bitbucket) with URL, provider, optional access token (plaintext in v1), a 1:1 mapping of documentation branches to PR target branches (e.g., `{main: main, develop: develop}`), and a designated **public branch** — the single branch whose wiki is returned by all search queries. Multiple branches can trigger documentation generation, but only the public branch's documentation is searchable. Uniquely identified by URL.
- **Job**: A documentation generation task tied to a repository and branch. Tracks status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED), resolved mode (full/incremental — determined automatically based on whether a previous commit SHA exists), force flag, quality report, token usage, and PR URL.
- **WikiStructure**: A versioned documentation structure for a specific `(repository_id, branch, scope_path)`. Contains sections hierarchy and page specifications. Up to 3 versions retained per scope.
- **WikiPage**: A single generated documentation page belonging to a WikiStructure. Contains markdown content, content embedding (pgvector), quality score, source file references, and code references. Cascade-deleted when its WikiStructure is removed.
- **AutodocConfig**: Per-scope configuration from `.autodoc.yaml` defining include/exclude patterns, style preferences, custom instructions, README settings, and PR preferences.
- **AgentResult**: Wrapper for agent output carrying evaluation history, attempt count, final score, quality gate status, and token usage.
- **EvaluationResult**: Critic output with weighted score, pass/fail status, per-criterion scores, and improvement feedback.

## Clarifications

### Session 2026-02-15

- Q: What are the target time limits for full and incremental documentation generation? → A: 1-hour hard timeout for all job types. Pod updates job status to FAILED before terminating on timeout.
- Q: What is the mapping model between documented branches and PR target branches? → A: 1:1 mapping — each documented branch has a paired PR target branch. Multiple branches can trigger generation (e.g., develop and main). Only one branch per repository is designated as the "public" branch; all documentation searches query through that branch's wiki.
- Q: Should the system limit how many jobs can run concurrently? → A: Global concurrency limit only (e.g., max N concurrent jobs system-wide). No per-repo limit.
- Q: What level of token protection is expected for repository access tokens? → A: No encryption in v1. Tokens stored as plaintext; repositories are trusted. Encryption deferred to a future version.
- Q: Which capabilities are explicitly not in scope for v1? → A: All out of scope: UI dashboard, multi-language docs, PDF export, self-hosted Git (Gitea/etc), user accounts/RBAC.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can register a repository and receive generated documentation (wiki pages + README PR) from a single API call. All jobs (full and incremental) have a 1-hour hard timeout enforced at the pod level.
- **SC-002**: Incremental documentation updates regenerate only affected pages, completing faster than full generation for small changesets (fewer than 10% of files changed), within the same 1-hour timeout.
- **SC-003**: Quality-gated generation produces documentation where the average quality score across all pages exceeds the configured threshold in at least 90% of jobs.
- **SC-004**: Documentation search returns relevant results for natural language queries, with hybrid search outperforming text-only or semantic-only search in result relevance.
- **SC-005**: Monorepo support correctly discovers and independently processes multiple documentation scopes, with no cross-scope contamination in generated content.
- **SC-006**: The system handles repositories across all three supported providers (GitHub, GitLab, Bitbucket) for cloning, diff detection, and PR creation.
- **SC-007**: Job management operations (cancel, retry, status check) complete within 2 seconds of the API call.
- **SC-008**: Webhook-driven incremental updates trigger within 5 seconds of receiving a push event.
- **SC-009**: The system maintains at most 3 documentation versions per scope without manual intervention.
- **SC-010**: Partial failures preserve already-generated pages and provide detailed quality reports identifying which pages failed and why.

## Assumptions

- Google ADK's `DatabaseSessionService` supports PostgreSQL for session persistence.
- Google ADK's built-in OpenTelemetry integration provides automatic tracing of agent execution, LLM calls, and tool usage.
- Prefect 3 supports the work pool, deployment, and concurrency limit patterns described (process pool for dev, Kubernetes pool for prod).
- Git providers (GitHub, GitLab, Bitbucket) expose compare APIs that return changed file lists between two commits.
- S3 (or compatible object storage) is available for archiving ADK sessions.
- API authentication is handled at the infrastructure layer (reverse proxy/API gateway) and is not part of the application.
- Rate limiting is handled at the infrastructure layer (NGINX/cloud load balancer).
- Webhook signature verification (HMAC) is deferred to implementation based on deployment context.
