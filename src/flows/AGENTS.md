<!-- FOR AI AGENTS -->

# flows/ -- Prefect 3 Flows and Tasks

This package contains Prefect 3 flows and tasks for documentation generation orchestration. Three Prefect flows orchestrate the documentation pipeline. Orchestrator flows (full_generation, incremental_update) fan out scope processing to parallel K8s jobs. Tasks are atomic units within flows. Three work pools prevent deadlock: `orchestrator-pool`, `k8s-pool`, `local-dev`.

## Package Structure

```
flows/
├── __init__.py                 -> Exports: full_generation_flow, incremental_update_flow, scope_processing_flow
├── full_generation.py          -> full_generation_flow(repository_id) — orchestrator for full doc gen
├── incremental_update.py       -> incremental_update_flow(repository_id, force, dry_run) — incremental updates
├── scope_processing.py         -> scope_processing_flow(repo_id, scope_config, commit_sha, dry_run) — worker per scope
└── tasks/
    ├── __init__.py
    ├── clone.py                -> clone_repository(repository, branch) → (repo_path, commit_sha)
    ├── discover.py             -> discover_autodoc_configs(repo_path) → list of config paths
    ├── scan.py                 -> scan_file_tree(repo_path, config) with include/exclude patterns
    ├── structure.py            -> extract_structure() — runs StructureExtractor agent
    ├── pages.py                -> generate_pages() — runs PageGenerator for all pages (GOLDEN SAMPLE)
    ├── readme.py               -> distill_readme() — runs ReadmeDistiller agent
    ├── embeddings.py           -> generate_embeddings_task() — chunks + embeds all pages
    ├── pr.py                   -> close_stale_autodoc_prs(), create_autodoc_pr() with ScopeReadme
    ├── sessions.py             -> archive_sessions() to S3, delete_sessions() from DB
    ├── cleanup.py              -> cleanup_workspace(), cleanup_orphan_workspaces() (scheduled)
    ├── metrics.py              -> aggregate_job_metrics() — quality + token aggregation
    ├── callback.py             -> deliver_callback() — webhook notification with 3x exponential backoff
    └── reconcile.py            -> reconcile_stale_jobs() — syncs RUNNING jobs vs Prefect states
```

## Golden Samples

| For | Reference | Key patterns |
|-----|-----------|--------------|
| Orchestrator flow | `full_generation.py` | `@flow` decorator, task composition, scope fan-out via `run_deployment()`, error handling |
| Worker flow | `scope_processing.py` | `@flow` for scope worker, agent orchestration, DB persistence, parallel embeddings and readme |
| Prefect task | `tasks/pages.py` | `@task` decorator, atomic operations, `AgentResult` handling |
| Scheduled task | `tasks/cleanup.py` | `cleanup_orphan_workspaces()` with schedule configuration |

## Architecture

### Three Work Pools

| Pool | Type | Limit | Purpose |
|------|------|-------|---------|
| `orchestrator-pool` | kubernetes | 10 | Parent flows (full_generation, incremental_update) |
| `k8s-pool` | kubernetes | 50 | Scope worker flows (scope_processing) |
| `local-dev` | process | -- | Local development (all flows run in-process) |

Orchestrator and worker flows run on separate pools to prevent deadlock. An orchestrator flow waits for worker flows to complete; if both shared a pool, the orchestrator could consume all slots and leave no room for workers.

### Flow Hierarchy

- **Orchestrator flows** (`full_generation_flow`, `incremental_update_flow`): Run on `orchestrator-pool`. Discover scopes, apply overlap exclusions, fan out scope workers via `run_deployment()` (prod) or direct invocation (dev).
- **Scope worker flow** (`scope_processing_flow`): Runs on `k8s-pool` as an independent K8s job per scope. Executes the agent pipeline: scan, extract structure, generate pages, embed, distill readme.
- **Task atomicity**: Each `@task` is one atomic unit of work. Cross-task consistency is maintained via flow-level retry, not task-level transactions.

### Deployment Selection

`AUTODOC_FLOW_DEPLOYMENT_PREFIX` env var (`dev` or `prod`) selects the deployment target. In dev mode, scope processing runs in-process on `local-dev` pool. In prod, it launches K8s jobs on `k8s-pool` via `run_deployment()`.

## Flow Pipeline

Full generation pipeline, step by step:

1. `clone_repository` -> `(repo_path, commit_sha)`
2. `discover_autodoc_configs` -> list of `.autodoc.yaml` paths
3. `apply_scope_overlap_exclusions` -> parent scopes auto-exclude child scope directories
4. Fan out: `scope_processing_flow` per scope (via `run_deployment` in prod, direct in dev)
5. Per scope: `scan_file_tree` -> `extract_structure` -> `generate_pages` -> [`generate_embeddings` || `distill_readme`]
6. `create_autodoc_pr` with all scope READMEs
7. `aggregate_job_metrics` -> update job `quality_report`
8. `archive_sessions` -> `delete_sessions` -> `cleanup_workspace`
9. `deliver_callback` if `callback_url` was provided

### Incremental Flow Differences

The incremental update flow (`incremental_update_flow`) differs from full generation:

- Uses provider compare API (not `git diff`) to determine changed files since last run
- Detects structural changes (new modules/directories) that require re-extraction
- Identifies specific pages needing regeneration based on changed source files
- Baseline SHA = `min(commit_sha)` across all scopes (safe baseline after partial failures)
- Supports `dry_run=True` for previewing changes without DB writes or PR creation

## Session Lifecycle

ADK agent sessions follow a strict lifecycle within every flow run:

1. `DatabaseSessionService` persists sessions to PostgreSQL during agent execution
2. After flow completion (success or failure), `archive_sessions` uploads session data to S3
3. `delete_sessions` removes session records from PostgreSQL
4. This prevents unbounded session table growth while preserving data for debugging

## Error Handling

Three error types drive flow behavior (defined in `src/errors.py`):

| Error | Behavior | Use when |
|-------|----------|----------|
| `TransientError` | Prefect retries the task automatically | Network failures, rate limits, temporary DB issues |
| `PermanentError` | Task fails immediately, no retry | Invalid input, missing config, unrecoverable state |
| `QualityError` | Handled by the agent quality loop, not Prefect | Agent output below quality threshold |

Orchestrator flows catch exceptions from scope workers and mark the job as `FAILED` with a detailed error report. Partial results (pages from successful scopes) remain accessible via the API.

## Callback Delivery

When a job has a `callback_url`, `deliver_callback` sends a POST request with job status after flow completion (success or failure). Retry policy: 3 attempts with exponential backoff (`2s`, `4s`, `8s`) on transient failures.

## Heuristics

| When | Do |
|------|-----|
| Adding a new task | Create in `tasks/`, use `@task` decorator, keep atomic (one logical operation) |
| Task needs DB access | Accept session parameter, do not create your own session |
| Task is retryable | Raise `TransientError` -- Prefect retries automatically |
| Task should fail fast | Raise `PermanentError` |
| Adding to the pipeline | Add task call in `scope_processing_flow` or the appropriate orchestrator flow |
| Need parallel tasks | Use `asyncio.gather()` within the flow (see `scope_processing_flow` for embeddings parallel with readme) |
| Adding a scheduled task | Follow `cleanup.py` pattern, add deployment in Prefect configuration |
| Debugging a flow | Check Prefect UI -- it is the primary ops dashboard |
| Need to track metrics | Accumulate in `AgentResult.token_usage`, aggregate via `aggregate_job_metrics()` |
| Modifying fan-out | Scope fan-out uses `run_deployment()` in prod, direct call in dev; respect pool separation |

## Boundaries

**Always:**
- Use `@task` decorator for atomic units of work
- Use `@flow` decorator for orchestration
- Keep tasks atomic -- one logical operation per task
- Handle `TransientError` vs `PermanentError` correctly
- Archive and cleanup sessions after flow completion
- Deliver callback if `callback_url` is set on the job
- Use `get_settings()` for configuration (never read env vars directly)
- Use `get_model()` for LLM instances in agent tasks

**Ask first:**
- Changing flow structure or task ordering
- Adding new flows
- Modifying Prefect deployment configuration
- Changing work pool assignments
- Altering the scope fan-out mechanism

**Never:**
- Create long-running tasks (break into smaller atomic tasks instead)
- Skip session cleanup after flow runs
- Use synchronous operations in flows or tasks (everything is async)
- Access Prefect internals directly (use Prefect's public API)
- Skip error handling in orchestrator flows
- Run orchestrator and worker flows on the same work pool (deadlock risk)
