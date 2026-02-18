<!-- FOR AI AGENTS -->

# src/database

Async SQLAlchemy with asyncpg for PostgreSQL. pgvector for vector embeddings. Repository pattern for data access. Alembic for schema migrations. Two databases on the same PostgreSQL instance: `autodoc` (application) and `prefect` (managed by Prefect Server).

## Files

```
database/
  __init__.py
  engine.py              -> get_engine(), get_session_factory(), dispose_engine()
  models/
    __init__.py
    base.py              -> Base (DeclarativeBase), UUIDPrimaryKeyMixin, TimestampMixin
    repository.py        -> Repository model (provider, url, org, name, branch_mappings, access_token)
    job.py               -> Job model -- GOLDEN SAMPLE (status, mode, quality_report, token_usage)
    wiki_structure.py    -> WikiStructure model (keyed on repo_id + branch + scope_path + version)
    wiki_page.py         -> WikiPage model (content, quality_score, source_files, related_pages)
    page_chunk.py        -> PageChunk model (content_embedding Vector(3072), heading_path, token_count)
  repos/
    __init__.py
    repository_repo.py   -> RepositoryRepo: CRUD + cursor-based pagination for repositories
    job_repo.py          -> JobRepo: CRUD + validated status transitions + active job queries
    wiki_repo.py         -> WikiRepo: structures, pages, chunks, baseline SHA, version management
    search_repo.py       -> SearchRepo: text_search, semantic_search, hybrid_search (RRF)
  migrations/
    env.py               -> Alembic async environment config (imports all models for metadata)
    script.py.mako       -> Alembic migration template
    versions/
      001_initial_schema.py -> Initial schema: all tables, indexes, pgvector extension
```

## engine.py

Module-level singletons for async engine and session factory. Configuration comes from `get_settings()`:

- `get_engine()` -- creates/returns cached `AsyncEngine` with pool settings from env vars (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`). `echo=False` always.
- `get_session_factory()` -- creates/returns cached `async_sessionmaker[AsyncSession]` with `expire_on_commit=False`.
- `dispose_engine()` -- async cleanup, resets both singletons. Called during app shutdown.

```python
from src.database.engine import get_session_factory

factory = get_session_factory()
async with factory() as session:
    repo = WikiRepo(session)
    # ... use repo ...
```

## Models

All models inherit from `Base` (DeclarativeBase) and apply mixins.

### base.py

- `Base` -- bare `DeclarativeBase`, no extra configuration.
- `UUIDPrimaryKeyMixin` -- `id: Mapped[uuid.UUID]` with `server_default=func.gen_random_uuid()`.
- `TimestampMixin` -- `created_at` and `updated_at` as `TIMESTAMP(timezone=True)` with `server_default=func.now()`. `updated_at` has `onupdate=func.now()`.

### repository.py

`Repository(UUIDPrimaryKeyMixin, TimestampMixin, Base)` on table `repositories`.

Fields: `provider` (check: `github`, `bitbucket`), `url` (unique), `org`, `name`, `branch_mappings` (JSONB), `public_branch`, `access_token` (nullable).

### job.py -- GOLDEN SAMPLE for new models

`Job(UUIDPrimaryKeyMixin, TimestampMixin, Base)` on table `jobs`.

Fields: `repository_id` (FK to repositories, CASCADE), `status` (check: PENDING/RUNNING/COMPLETED/FAILED/CANCELLED), `mode` (check: full/incremental), `branch`, `commit_sha` (String(40), nullable), `force`, `dry_run`, `prefect_flow_run_id`, `app_commit_sha`, `quality_report` (JSONB), `token_usage` (JSONB), `config_warnings` (JSONB), `callback_url`, `error_message` (Text), `pull_request_url`.

Notable indexes:
- `ix_jobs_repository_status` on `(repository_id, status)`
- `ix_jobs_idempotency_lookup` on `(repository_id, branch, dry_run, status)`
- `uq_jobs_active_idempotency` -- partial unique index on `(repository_id, branch, dry_run)` WHERE `status IN ('PENDING', 'RUNNING')` for job idempotency

Key patterns to copy:
1. Mixin inheritance order: `UUIDPrimaryKeyMixin, TimestampMixin, Base`
2. CheckConstraints in `__table_args__` tuple
3. Indexes declared in `__table_args__`
4. ForeignKey with `ondelete="CASCADE"` for parent references

### wiki_structure.py

`WikiStructure(UUIDPrimaryKeyMixin, TimestampMixin, Base)` on table `wiki_structures`.

Fields: `repository_id` (FK CASCADE), `job_id` (FK SET NULL), `branch`, `scope_path`, `version` (Integer, >= 1), `title`, `description` (Text), `sections` (JSONB), `commit_sha`.

Unique constraint on `(repository_id, branch, scope_path, version)`. Up to 3 versions retained per scope.

### wiki_page.py

`WikiPage(UUIDPrimaryKeyMixin, TimestampMixin, Base)` on table `wiki_pages`.

Fields: `wiki_structure_id` (FK CASCADE), `page_key`, `title`, `description`, `importance` (check: high/medium/low), `page_type` (check: api/module/class/overview), `source_files` (JSONB), `related_pages` (JSONB, default `[]`), `content` (Text), `quality_score` (Float).

Has a GIN index on `to_tsvector('english', content)` for full-text search.

### page_chunk.py

`PageChunk(UUIDPrimaryKeyMixin, Base)` on table `page_chunks`. Note: uses `UUIDPrimaryKeyMixin` only (no `TimestampMixin`), has its own `created_at` column (no `updated_at`).

Fields: `wiki_page_id` (FK CASCADE), `chunk_index` (Integer, unique with wiki_page_id), `content` (Text), `content_embedding` (Vector(3072), nullable), `heading_path` (ARRAY(String)), `heading_level` (Integer, 0-6), `token_count` (Integer), `start_char`, `end_char`, `has_code` (Boolean).

The HNSW index on `content_embedding` is created via raw SQL in the migration (pgvector requires halfvec cast for 3072 dimensions): `USING hnsw ((content_embedding::halfvec(3072)) halfvec_cosine_ops)`.

### FK Cascade Chain

```
repositories
  -> jobs (CASCADE)
  -> wiki_structures (CASCADE)
       -> wiki_pages (CASCADE)
            -> page_chunks (CASCADE)
```

Deleting a repository cascades through the entire tree. Deleting a wiki_structure removes all its pages and their chunks.

## Repos (Repository Pattern)

All repo classes follow the same pattern:
1. Constructor accepts `AsyncSession`, stored as `self._session`.
2. All methods are `async`.
3. Use `sa.select()`, `session.get()`, `session.add()`, `session.flush()` -- never `commit()` (callers manage transactions).
4. Return model instances or `None`, never raw rows.

### repository_repo.py -- RepositoryRepo

Methods: `create(...)`, `get_by_id(uuid)`, `get_by_url(url)`, `list(cursor, limit)`, `update(id, **kwargs)`, `delete(id)`.

Cursor-based pagination pattern (used by all list methods):
```python
stmt = sa.select(Model).order_by(Model.created_at.desc(), Model.id.desc())
if cursor is not None:
    cursor_row = await self._session.get(Model, cursor)
    if cursor_row is not None:
        stmt = stmt.where(
            sa.or_(
                Model.created_at < cursor_row.created_at,
                sa.and_(
                    Model.created_at == cursor_row.created_at,
                    Model.id < cursor,
                ),
            )
        )
stmt = stmt.limit(limit)
```

### job_repo.py -- JobRepo

Methods: `create(...)`, `get_by_id(uuid)`, `list(repository_id, status, branch, cursor, limit)`, `update_status(job_id, status, **kwargs)`, `get_active_for_repo(repository_id, branch, dry_run)`, `get_running_jobs()`.

Status transition validation via `_VALID_TRANSITIONS` dict:
```python
_VALID_TRANSITIONS = {
    "PENDING": {"RUNNING", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED"},
    "FAILED": {"PENDING"},  # retry
}
```
`update_status()` raises `PermanentError` (from `src.errors`) on invalid transitions. Terminal states (COMPLETED, CANCELLED) have no valid transitions.

`get_active_for_repo()` finds PENDING/RUNNING jobs for idempotency checks before creating new jobs.

### wiki_repo.py -- GOLDEN SAMPLE for new repo classes

Methods:
- `create_structure(...)` -- auto-increments version, enforces 3-version retention cap (deletes oldest if >= 3)
- `create_pages(pages)` -- batch insert via `session.add_all()`
- `create_chunks(chunks)` -- batch insert via `session.add_all()`
- `get_latest_structure(repository_id, branch, scope_path)` -- highest version for a scope
- `get_page_by_key(wiki_structure_id, page_key)` -- single page lookup
- `get_structures_for_repo(repository_id, branch)` -- all structures, optionally filtered
- `get_baseline_sha(repository_id, branch)` -- `min(commit_sha)` across all structures (safe baseline for incremental updates after partial failures)
- `get_pages_for_structure(wiki_structure_id)` -- all pages for a structure, ordered by page_key
- `count_pages_for_structure(wiki_structure_id)` -- count of pages
- `duplicate_pages(source_pages, target_structure_id)` -- copies pages to a new structure for unchanged pages in incremental flow

### search_repo.py -- SearchRepo

Three search methods, all operating on the latest version of wiki_structures per scope. Each filters by `repository_id`, `branch`, and optionally `scope_path`.

Result dataclasses:
- `TextSearchResult` -- page_id, page_key, title, content, score (ts_rank), scope_path
- `SemanticSearchResult` -- adds best_chunk_content, best_chunk_heading_path
- `HybridSearchResult` -- adds best_chunk_content (nullable), best_chunk_heading_path (nullable)

**text_search**: PostgreSQL `ts_rank` + `plainto_tsquery` on the GIN-indexed `content` column of wiki_pages.

**semantic_search**: Cosine distance (`<=>` operator) on `page_chunks.content_embedding`. Uses **best-chunk-wins** aggregation: ranks chunks by similarity, takes the best chunk per page (`ROW_NUMBER() OVER (PARTITION BY wiki_page_id)` where `rn = 1`), returns page-level results.

**hybrid_search**: Reciprocal Rank Fusion combining text_search + semantic_search.
- Each method independently ranks its results.
- RRF formula: `score = 1/(k + rank_text) + 1/(k + rank_semantic)` where `k` defaults to 60.
- Absent pages (present in one result set but not the other) get penalty rank 1000.
- Uses `FULL OUTER JOIN` between semantic and text results.

All three methods use raw SQL via `sqlalchemy.text()` with a shared `_LATEST_VERSION_SUBQUERY` fragment that restricts queries to the highest version per scope.

## Migrations

Alembic is configured for async operation in `env.py`. Uses `async_engine_from_config` with `NullPool` (migrations use short-lived connections). All models are imported in `env.py` so `Base.metadata` is fully populated for autogeneration.

The URL comes from `get_settings().DATABASE_URL`.

### Creating a new migration

```bash
cd src && alembic revision --autogenerate -m "description of change"
```

### Applying migrations

```bash
cd src && alembic upgrade head
```

### 001_initial_schema.py

Creates the pgvector extension, all five tables (repositories, jobs, wiki_structures, wiki_pages, page_chunks), all indexes (including the GIN full-text index and HNSW vector index), all constraints, and all foreign keys. The HNSW index uses halfvec(3072) cast with cosine_ops, m=16, ef_construction=64.

## Golden Samples

| For | Reference | Key patterns |
|-----|-----------|--------------|
| New ORM model | `models/job.py` | Mixin order (UUIDPrimaryKeyMixin, TimestampMixin, Base), CheckConstraints in `__table_args__`, JSONB columns, FK with ondelete |
| New repo class | `repos/wiki_repo.py` | Constructor takes AsyncSession, async methods, flush() not commit(), batch insert with add_all() |
| Cursor pagination | `repos/repository_repo.py` | Two-column cursor (created_at desc, id desc) with sa.or_/sa.and_ |
| Status transitions | `repos/job_repo.py` | `_VALID_TRANSITIONS` dict, PermanentError on invalid transition |
| Vector search | `repos/search_repo.py` | pgvector `<=>` cosine distance, best-chunk-wins aggregation, RRF hybrid |
| Alembic migration | `migrations/versions/001_initial_schema.py` | Table creation, raw SQL for GIN/HNSW indexes, pgvector extension |

## Heuristics

| When | Do |
|------|----|
| Adding a new model | Create file in `models/`, use `UUIDPrimaryKeyMixin + TimestampMixin + Base` (unless there is a reason to omit TimestampMixin like PageChunk), add Alembic migration |
| Adding a DB operation | Add method to the appropriate repo class; never write raw SQL in routes or flows |
| Need bulk insert | Use `session.add_all(items)` then `await session.flush()` (see `wiki_repo.py` `create_pages`/`create_chunks`) |
| Changing schema | Create new Alembic migration: `cd src && alembic revision --autogenerate -m "description"` |
| Adding a vector column | Use `Vector(dim)` from `pgvector.sqlalchemy`, add HNSW index via raw SQL in migration |
| Need search | Use `SearchRepo` -- it handles text, semantic, and hybrid; never write search queries elsewhere |
| Adding a new FK relationship | Use `ondelete="CASCADE"` for child tables, `ondelete="SET NULL"` for optional references (like job_id on wiki_structures) |
| Need status validation | Follow `job_repo.py` pattern: define valid transitions dict, raise `PermanentError` on violations |
| Adding a new table | Follow full chain: model file, import in `migrations/env.py`, create migration, add repo class |
| Need pagination | Follow `repository_repo.py` cursor pattern with `(created_at desc, id desc)` |

## Boundaries

**Always:**
- Use async session operations (`await session.execute()`, `await session.flush()`)
- Use repository pattern for data access (route/flow code calls repo methods, never touches session directly)
- Add Alembic migration for any schema change
- Use `UUIDPrimaryKeyMixin` for new models (UUID primary keys with server-side gen_random_uuid())
- Use `TimestampMixin` for new models unless there is a specific reason not to (PageChunk only has created_at)
- Use `CASCADE DELETE` for child relationships in the FK chain
- Import new models in `migrations/env.py` so autogenerate detects them
- Use `flush()` not `commit()` in repo methods (callers manage transaction boundaries)
- Pass `AsyncSession` to repo constructors via dependency injection

**Ask first:**
- Changing existing model fields (requires migration and may affect downstream code)
- Adding new indexes (performance implications, migration required)
- Modifying search algorithms in SearchRepo (RRF parameters, ranking logic)
- Changing the version retention cap (currently 3 per scope)
- Changing status transition rules in JobRepo

**Never:**
- Use synchronous DB operations
- Write raw SQL in routes or flows (use repo methods)
- Modify existing migration files after they have been applied
- Delete migration files
- Access engine directly outside of `engine.py`
- Call `session.commit()` inside repo methods (the caller or middleware handles commits)
- Construct `Settings()` directly (use `get_settings()` for DATABASE_URL)
- Skip importing new models in `migrations/env.py` (autogenerate will miss the table)
