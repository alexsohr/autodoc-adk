<!-- FOR AI AGENTS -->

# API Package (`src/api/`)

FastAPI REST API layer for AutoDoc ADK. Serves endpoints for repository management, job management, document browsing/search, webhook ingestion, and health checks. Uses dependency injection for DB access and cursor-based pagination on all list endpoints.

## Package Structure

```
api/
├── __init__.py
├── app.py                -> create_app() factory, lifespan context manager, exception handlers
├── dependencies.py       -> FastAPI Depends: get_db_session, get_repository_repo, get_job_repo, get_wiki_repo, get_search_repo
├── schemas/
│   ├── __init__.py
│   ├── common.py         -> ErrorResponse, PaginatedResponse base models
│   ├── repositories.py   -> RegisterRepositoryRequest, UpdateRepositoryRequest, RepositoryResponse, PaginatedRepositoryResponse
│   ├── jobs.py           -> CreateJobRequest, JobResponse, PaginatedJobResponse, QualityReport, TokenUsage, JobStatus/JobMode enums, WikiStructureResponse, TaskState, LogEntry
│   └── documents.py      -> ScopeInfo, ScopesResponse, WikiPageSummary, WikiSection, WikiPageResponse, PaginatedWikiResponse, SearchResult, SearchResponse
└── routes/
    ├── __init__.py
    ├── health.py          -> GET /health with dependency checks (DB, Prefect, OTel)
    ├── repositories.py    -> CRUD for /repositories (golden sample for new routes)
    ├── jobs.py            -> /jobs CRUD + /jobs/{id}/cancel, /jobs/{id}/retry, /jobs/{id}/structure, /jobs/{id}/tasks, /jobs/{id}/logs
    ├── documents.py       -> /documents/{repo_id}/scopes, /search, /pages/{page_key}, /{repo_id} (wiki sections)
    └── webhooks.py        -> POST /webhooks/push (GitHub/Bitbucket payload normalization)
```

## Golden Samples

| When creating        | Reference file             | Key patterns demonstrated                                          |
|----------------------|----------------------------|--------------------------------------------------------------------|
| New route module     | `routes/repositories.py`   | APIRouter setup, Depends injection, cursor pagination, error codes |
| Request/response schema | `schemas/jobs.py`       | Pydantic v2 models, StrEnum, nested schemas, ConfigDict(from_attributes=True) |
| New dependency       | `dependencies.py`          | AsyncGenerator pattern, session commit/rollback, repo instantiation |

## Endpoints Reference

### Health
- `GET /health` -- Returns DB, Prefect, OTel status. Overall: healthy/degraded/unhealthy.

### Repositories (`routes/repositories.py`)
- `POST /repositories` -- Register repo. 201 on success, 409 on duplicate URL.
- `GET /repositories` -- List with cursor pagination (?cursor=UUID&limit=N).
- `GET /repositories/{id}` -- Get single repo.
- `PATCH /repositories/{id}` -- Partial update (branch_mappings, public_branch, access_token).
- `DELETE /repositories/{id}` -- Delete with cascading. 204 on success.

### Jobs (`routes/jobs.py`)
- `POST /jobs` -- Create doc generation job. Auto-detects full vs incremental mode. Idempotent: returns 200 with existing PENDING/RUNNING job if one exists for same (repo, branch, dry_run). Submits Prefect flow via BackgroundTasks.
- `GET /jobs` -- List with filters (?repository_id, ?status, ?branch) and cursor pagination.
- `GET /jobs/{id}` -- Get single job.
- `GET /jobs/{id}/structure` -- Get wiki structure for the job's repo/branch.
- `GET /jobs/{id}/tasks` -- Get Prefect task run states.
- `GET /jobs/{id}/logs` -- Get Prefect flow run logs.
- `POST /jobs/{id}/cancel` -- Cancel PENDING/RUNNING job. 409 for terminal states.
- `POST /jobs/{id}/retry` -- Retry FAILED job. Resets to PENDING, re-submits flow. 409 for non-FAILED.

### Documents (`routes/documents.py`)
- `GET /documents/{repo_id}/scopes` -- List documentation scopes. ?branch= defaults to public_branch.
- `GET /documents/{repo_id}/search` -- Search wiki pages. ?query=, ?search_type=(text|semantic|hybrid), ?branch=, ?scope=, ?limit=.
- `GET /documents/{repo_id}/pages/{page_key}` -- Get full page content. ?branch=, ?scope=.
- `GET /documents/{repo_id}` -- Get wiki structure sections with cursor pagination. ?branch=, ?scope=, ?cursor=, ?limit=.

### Webhooks (`routes/webhooks.py`)
- `POST /webhooks/push` -- Receives GitHub/Bitbucket push events. Returns 202 with job_id, 204 if skipped (unregistered repo or unconfigured branch), 400 for bad payloads.

## Architecture Patterns

### Dependency Injection Chain
```
Route handler
  -> Depends(get_*_repo)        # e.g. get_job_repo, get_repository_repo
    -> Depends(get_db_session)  # AsyncGenerator: yields session, commits on success, rollback on error
      -> get_session_factory()  # from src.database.engine
```

Routes never access the database directly. All DB operations go through repository classes (RepositoryRepo, JobRepo, WikiRepo, SearchRepo) injected via `dependencies.py`.

### Cursor-Based Pagination
All list endpoints use cursor + limit parameters (never offset). The cursor is typically a UUID (the `id` of the last item). Pattern from `routes/repositories.py`:
```python
rows = await repo.list(cursor=cursor, limit=limit)
next_cursor = str(rows[-1].id) if len(rows) == limit else None
```

### Job Submission
`create_job()` in `routes/jobs.py` is the main entry point. Flow:
1. Look up repository, validate branch against branch_mappings
2. Idempotency check: return existing active job if one matches (repo, branch, dry_run)
3. Auto-determine mode: `full` if no existing wiki structure or `force=True`, otherwise `incremental`
4. Create job record in DB with PENDING status
5. Submit Prefect flow via `BackgroundTasks.add_task(_submit_flow, ...)`

Webhooks follow the same pattern but detect mode from payload headers (GitHub: `X-GitHub-Event`, Bitbucket: `X-Event-Key`).

### Exception Handling
`app.py` registers global exception handlers that map domain errors to HTTP status codes:
- `TransientError` -> 503
- `PermanentError` -> 400
- `QualityError` -> 422

Route-level errors use `HTTPException` directly with appropriate status codes.

### Application Lifecycle
`app.py` defines a `lifespan` async context manager that:
- On startup: runs `reconcile_stale_jobs()` to sync RUNNING jobs against Prefect flow states
- On shutdown: calls `dispose_engine()` to close DB connection pool

## Code Conventions

- All route handlers are `async def`
- Pydantic v2 models for all request/response schemas; use `ConfigDict(from_attributes=True)` for ORM mapping
- Schema enums use `enum.StrEnum` (e.g., `JobStatus`, `JobMode`)
- Schemas are defined in `schemas/` files, never inline in routes
- Routers use `APIRouter(tags=[...])` for OpenAPI grouping; `documents.py` also uses `prefix="/documents"`
- Error responses use `HTTPException` with detail strings compatible with `ErrorResponse` schema
- Webhook parsers (`parse_github_push`, `parse_bitbucket_push`) are standalone functions that raise `ValueError` on bad payloads
- Logging uses `logging.getLogger(__name__)`

## Heuristics

| When you need to...                     | Do this                                                                  |
|-----------------------------------------|--------------------------------------------------------------------------|
| Add a new endpoint                      | Create route in `routes/`, add schemas in `schemas/`, register router in `app.py` via `app.include_router()` |
| Add DB access to a route                | Add dependency function in `dependencies.py`, inject via `Depends()`     |
| Add a list endpoint                     | Use cursor-based pagination (follow `routes/repositories.py`)            |
| Return an error                         | Use `HTTPException` with appropriate status code (404, 409, 422, etc.)   |
| Add a new webhook provider              | Add `parse_<provider>_push()` function in `webhooks.py`, add header detection in `receive_webhook()` |
| Add a new schema                        | Add to the appropriate file under `schemas/`                             |
| Map a DB model to a response            | Use `ResponseModel.model_validate(db_row)` with `ConfigDict(from_attributes=True)` |
| Submit a long-running operation         | Use `BackgroundTasks.add_task()` (see job creation pattern)              |

## Boundaries

**Always:**
- Use Pydantic schemas for request/response validation
- Use dependency injection for DB access (through repo classes)
- Use cursor-based pagination for list endpoints
- Return proper HTTP status codes (201 for create, 204 for delete, 404 for not found, 409 for conflict)
- Register new routers in `app.py` via `app.include_router()`

**Ask first:**
- Changing existing API response schemas (breaking change for clients)
- Adding new route modules (affects `app.py` router registration)
- Modifying webhook payload handling (affects provider integrations)
- Changing the dependency injection chain

**Never:**
- Access DB directly in route handlers (always go through injected repo classes)
- Use offset-based pagination
- Return raw SQLAlchemy models in responses (always map to Pydantic schemas)
- Add authentication/authorization logic in this layer (deferred to reverse proxy/API gateway)
- Define schemas inline in route files
