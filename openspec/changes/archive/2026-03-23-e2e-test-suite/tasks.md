## 1. Test Infrastructure (testcontainers + fixtures)

- [x] 1.1 Add `testcontainers[postgres]` to dev dependencies in `pyproject.toml`
- [x] 1.2 Create `tests/e2e/__init__.py` and `tests/e2e/conftest.py` with session-scoped testcontainers PostgreSQL+pgvector fixture (start container, run Alembic migrations once)
- [x] 1.3 Add function-scoped SAVEPOINT fixture for test isolation (begin nested transaction, yield session, rollback after test)
- [x] 1.4 Add FastAPI test client fixture: `create_app()`, override `get_db_session` with test session, yield `httpx.AsyncClient` with `ASGITransport`
- [x] 1.5 Add Prefect test harness fixture: activate `prefect_test_harness()`, set `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev`, patch `get_engine()`/`get_session_factory()` for flow tasks
- [x] 1.6 Add pytest marker `e2e` and register in `pyproject.toml`
- [x] 1.7 Add Makefile targets: `test-e2e`, `test-all`, `test-e2e-clean`

## 2. Test Fixture Repositories

- [x] 2.1 Create `tests/e2e/fixtures/sample-repo/` with `.autodoc.yaml`, `src/__init__.py`, `src/core.py`, `src/utils.py`, `README.md`, `pyproject.toml`
- [x] 2.2 Create `tests/e2e/fixtures/sample-repo-v2/` with modified `src/core.py` and new `src/new_module.py` for incremental update tests
- [x] 2.3 Create `tests/e2e/fixtures/sample-monorepo/` with root `.autodoc.yaml` and `packages/api/.autodoc.yaml` for monorepo tests
- [x] 2.4 Create `tests/e2e/fixtures/sample-repo-no-config/` without `.autodoc.yaml` for default config tests

## 3. Agent & Provider Stubs

- [x] 3.1 Create `tests/e2e/stubs.py` with `make_structure_stub(score=8.2, below_floor=False)` — returns `AgentResult[WikiStructureSpec]` with 2 sections, 3 pages
- [x] 3.2 Add `make_page_stub()` — returns `AgentResult[GeneratedPage]` with page_key-derived Markdown content, handles multiple calls via side_effect
- [x] 3.3 Add `make_readme_stub()` — returns `AgentResult[ReadmeOutput]` with Markdown referencing structure title and page titles
- [x] 3.4 Add `make_clone_stub(fixture_path)` — copies fixture repo to temp dir, returns `(path, "abc123fake")`, supports error injection (TransientError/PermanentError)
- [x] 3.5 Add `make_embedding_stub()` — returns deterministic hash-based vectors (SHA-256 seeded), same text always produces same vector
- [x] 3.6 Add `make_pr_stub()` — patches `create_autodoc_pr()` to return fake URL, patches `close_stale_autodoc_prs()` as no-op returning 0
- [x] 3.7 Add `make_compare_commits_stub(changed_files)` — returns configurable list of changed file paths for incremental tests
- [x] 3.8 Add `make_callback_stub()` — patches `deliver_callback()` as no-op, captures invocation args for assertion
- [x] 3.9 Add `make_github_push_payload(repo_url, branch, sha)` and `make_bitbucket_push_payload(repo_url, branch, sha)` — webhook payload factories
- [x] 3.10 Add conftest fixture that activates all default stubs (patch agent subclasses, clone, embeddings, PR, callback)

## 4. TIER 1: Core Flow Tests (~25 scenarios)

- [x] 4.1 Create `tests/e2e/test_full_generation.py` — `TestFullGeneration` class
- [x] 4.2 Test: happy path — POST /repositories → POST /jobs → assert COMPLETED, verify structure (2 sections, 3 pages), verify all pages retrievable, verify job fields (quality_report, token_usage, pull_request_url, commit_sha)
- [x] 4.3 Test: dry run — POST /jobs with dry_run=true → structure exists, no pages, no PR call
- [x] 4.4 Test: quality gate failure — structure stub with score=3.0, below_floor=True → FAILED, no pages
- [x] 4.5 Create `tests/e2e/test_incremental.py` — `TestIncrementalUpdate` class
- [x] 4.6 Test: affected pages only — full generation → incremental with compare_commits=["src/core.py"] → only affected pages regenerated, unchanged preserved
- [x] 4.7 Test: no changes short-circuit — compare_commits=[] → COMPLETED with no_changes=true, no agents invoked
- [x] 4.8 Test: structural change — compare_commits=["src/__init__.py"] → StructureExtractor called, affected pages regenerated
- [x] 4.9 Test: no baseline SHA — incremental mode with no prior structure → FAILED
- [x] 4.10 Create `tests/e2e/test_job_lifecycle.py` — `TestJobLifecycle` class
- [x] 4.11 Test: job idempotency — duplicate POST /jobs → same job ID, status 200
- [x] 4.12 Test: transient error retry — clone raises TransientError once → retries → COMPLETED
- [x] 4.13 Test: permanent error — clone raises PermanentError → FAILED with preserved message
- [x] 4.14 Test: QualityError from structure → FAILED with quality message
- [x] 4.15 Create `tests/e2e/test_repository_crud.py` — `TestRepositoryCRUD` class
- [x] 4.16 Test: register valid GitHub repo → 201
- [x] 4.17 Test: register duplicate URL → 409
- [x] 4.18 Test: register with URL/provider mismatch → 422
- [x] 4.19 Test: register with public_branch not in branch_mappings → 422
- [x] 4.20 Test: cascade delete — full generation → DELETE /repositories/{id} → all related records gone
- [x] 4.21 Create `tests/e2e/test_search.py` — `TestSearch` class
- [x] 4.22 Test: text search → pages containing keyword returned
- [x] 4.23 Test: semantic search → pages with non-zero relevance scores
- [x] 4.24 Test: hybrid search → RRF-ranked results
- [x] 4.25 Test: mode auto-detection — no structure → full; existing structure → incremental; force=true → full
- [x] 4.26 Test: job creation validation — repo not found → 404; branch not in mappings → 422

## 5. TIER 2: Webhooks, Lifecycle Edges, Advanced Flows (~30 scenarios)

- [x] 5.1 Create `tests/e2e/test_webhooks.py` — `TestWebhooks` class
- [x] 5.2 Test: GitHub push → 202 with job_id
- [x] 5.3 Test: Bitbucket push → 202 with job_id
- [x] 5.4 Test: unregistered repo → 204 skip
- [x] 5.5 Test: unconfigured branch → 204 skip
- [x] 5.6 Test: unknown provider (no event header) → 400
- [x] 5.7 Test: malformed JSON → error
- [x] 5.8 Test: webhook idempotency (active job exists) → 202 with existing job_id
- [x] 5.9 Add cancel tests to `test_job_lifecycle.py`
- [x] 5.10 Test: cancel PENDING → CANCELLED
- [x] 5.11 Test: cancel RUNNING → CANCELLED
- [x] 5.12 Test: cancel COMPLETED → 409
- [x] 5.13 Test: cancel CANCELLED → 409
- [x] 5.14 Add retry tests to `test_job_lifecycle.py`
- [x] 5.15 Test: retry FAILED → resets to PENDING, re-submits
- [x] 5.16 Test: retry non-FAILED → 409
- [x] 5.17 Test: retry non-existent → 404
- [x] 5.18 Add update tests to `test_repository_crud.py`
- [x] 5.19 Test: update branch_mappings → 200
- [x] 5.20 Test: update access_token only → 200
- [x] 5.21 Test: update public_branch to invalid → 422
- [x] 5.22 Test: update with no fields → 422
- [x] 5.23 Test: update non-existent → 404
- [x] 5.24 Add callback tests to `test_job_lifecycle.py`
- [x] 5.25 Test: callback on successful completion (captured payload has status=COMPLETED, quality_report)
- [x] 5.26 Test: callback on failure (captured payload has status=FAILED, error_message)
- [x] 5.27 Test: stale PR cleanup — close_stale_autodoc_prs called before create_autodoc_pr
- [x] 5.28 Create `tests/e2e/test_advanced_flows.py` — `TestAdvancedFlows` class
- [x] 5.29 Test: no .autodoc.yaml defaults to root scope (scope_path=".")
- [x] 5.30 Test: monorepo with multiple scopes — both processed, separate structures and pages
- [ ] 5.31 Test: scope overlap auto-exclusion — parent excludes child dirs
- [x] 5.32 Test: partial scope failure — one scope fails, other's pages accessible
- [x] 5.33 Test: all scopes fail → FAILED
- [x] 5.34 Test: incremental dry run — pages regenerated but no PR

## 6. TIER 3: Pagination, Documents, Health, Edges (~31 scenarios)

- [x] 6.1 Add pagination tests to `test_repository_crud.py`
- [x] 6.2 Test: first page with next_cursor
- [x] 6.3 Test: last page (next_cursor=null)
- [x] 6.4 Test: empty results
- [x] 6.5 Test: get existing repo → 200
- [x] 6.6 Test: get non-existent repo → 404
- [x] 6.7 Test: delete non-existent → 404
- [x] 6.8 Add job listing/detail tests to `test_job_lifecycle.py`
- [x] 6.9 Test: filter by repository_id
- [x] 6.10 Test: filter by status
- [x] 6.11 Test: filter by branch
- [x] 6.12 Test: combined filters
- [x] 6.13 Test: empty job results
- [x] 6.14 Test: get completed job has quality_report + token_usage
- [x] 6.15 Test: get failed job has error_message
- [x] 6.16 Test: get non-existent job → 404
- [x] 6.17 Test: get tasks without flow_run_id → empty list
- [x] 6.18 Test: get logs without flow_run_id → empty list
- [x] 6.19 Create `tests/e2e/test_documents.py` — `TestDocuments` class
- [x] 6.20 Test: list scopes after generation → page_count > 0
- [x] 6.21 Test: list scopes with no structures → empty
- [x] 6.22 Test: get specific page by key → content, source_files, quality_score
- [x] 6.23 Test: get page not found → 404
- [x] 6.24 Test: get full wiki → sections with embedded pages
- [x] 6.25 Test: get wiki no structure → 404
- [x] 6.26 Test: paginate wiki sections → next_cursor
- [ ] 6.27 Test: search with scope filter
- [x] 6.28 Test: search with no results → empty
- [x] 6.29 Create `tests/e2e/test_health.py` — `TestHealth` class
- [x] 6.30 Test: all healthy → status="healthy"
- [x] 6.31 Test: DB degraded → status="degraded"/"unhealthy"
- [ ] 6.32 Test: repo size limits exceeded → PermanentError → FAILED (skipped — requires internal flow task testing)
- [x] 6.33 Test: flow submission failure → job created but FAILED

## 7. CI Integration

- [x] 7.1 Verify all Tier 1 tests pass with `make test-e2e` and total runtime is under 3 minutes
- [x] 7.2 Add CI pipeline stage for E2E tests (parallel with unit/integration)
- [x] 7.3 Verify Tier 2 tests pass
- [x] 7.4 Verify Tier 3 tests pass
- [x] 7.5 Verify full suite stays under 3-minute budget
