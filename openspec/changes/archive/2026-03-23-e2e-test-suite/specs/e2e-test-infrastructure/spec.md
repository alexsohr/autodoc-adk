## ADDED Requirements

### Requirement: Test database via testcontainers
The system SHALL use `testcontainers-python` (`testcontainers[postgres]`) to programmatically start a PostgreSQL 18 + pgvector container from a session-scoped pytest fixture. Alembic migrations SHALL run automatically against the container before any test executes. The container SHALL be reused across all tests in a single pytest session and automatically cleaned up when the session ends.

#### Scenario: Database container starts and migrations run
- **WHEN** the E2E test session starts
- **THEN** a PostgreSQL 18 + pgvector container is running via testcontainers and all Alembic migrations have been applied

#### Scenario: Container reuse across tests
- **WHEN** multiple E2E test functions execute in sequence
- **THEN** all tests use the same database container without restarting it

#### Scenario: Automatic cleanup
- **WHEN** the E2E test session ends
- **THEN** the testcontainers PostgreSQL container is stopped and removed automatically

### Requirement: Transaction-based test isolation
Each test function SHALL run inside a database SAVEPOINT that rolls back after the test completes. This SHALL apply to both FastAPI dependency-injected sessions and flow task sessions created via `get_session_factory()`.

#### Scenario: Test sees clean database state
- **WHEN** test A inserts a Repository record and completes
- **THEN** test B (running after test A) does not see the Repository record

#### Scenario: Flow task sessions use test transaction
- **WHEN** a flow task calls `get_session_factory()` to create a new session during an E2E test
- **THEN** that session operates within the test's SAVEPOINT and its writes are visible to the test's assertions

### Requirement: FastAPI test client with real application wiring
The test suite SHALL create the FastAPI app via `create_app()` and provide an `httpx.AsyncClient` connected via `ASGITransport`. The `get_db_session` dependency SHALL be overridden to yield the test transaction session.

#### Scenario: API requests hit real route handlers
- **WHEN** the test client sends `POST /repositories` with a valid payload
- **THEN** the request is handled by the real `create_repository` route handler (not a mock)

#### Scenario: Database dependency override
- **WHEN** a route handler calls `get_db_session` during an E2E test
- **THEN** it receives the test transaction session, not a production database session

### Requirement: In-process Prefect flow execution
The test suite SHALL activate `prefect_test_harness()` and ensure `AUTODOC_FLOW_DEPLOYMENT_PREFIX=dev` so that flow submission via `_submit_flow` runs the flow coroutine in-process. Flow execution SHALL complete before test assertions run.

#### Scenario: Flow runs synchronously from test perspective
- **WHEN** `POST /jobs` triggers a flow via `_submit_flow`
- **THEN** the flow executes in-process and completes before the test proceeds to assertions

#### Scenario: No external Prefect infrastructure required
- **WHEN** E2E tests run
- **THEN** no Prefect server, Redis, or worker process is required

### Requirement: Makefile targets for E2E tests
The deployment Makefile SHALL include targets: `test-e2e` (run E2E tests with testcontainers managing the DB), `test-all` (run unit + integration + E2E), and `test-e2e-clean` (prune any orphaned test containers).

#### Scenario: Run E2E tests via make
- **WHEN** a developer runs `make test-e2e`
- **THEN** testcontainers starts a PostgreSQL container, migrations run, E2E tests execute, container is cleaned up, and results are reported

#### Scenario: Run all test suites
- **WHEN** a developer runs `make test-all`
- **THEN** unit, integration, and E2E tests all execute in sequence

### Requirement: Webhook payload factories
The system SHALL provide `make_github_push_payload(repo_url, branch, commit_sha)` and `make_bitbucket_push_payload(repo_url, branch, commit_sha)` factories that generate valid webhook payloads with correct headers for provider detection.

#### Scenario: GitHub payload factory
- **WHEN** `make_github_push_payload("https://github.com/org/repo", "main", "abc123")` is called
- **THEN** it returns a tuple of (payload_dict, headers_dict) where headers include `X-GitHub-Event: push`

#### Scenario: Bitbucket payload factory
- **WHEN** `make_bitbucket_push_payload("https://bitbucket.org/org/repo", "main", "abc123")` is called
- **THEN** it returns a tuple of (payload_dict, headers_dict) where headers include `X-Event-Key: repo:push`

### Requirement: Callback capture fixture
The system SHALL provide a fixture that patches `deliver_callback()` and captures all callback invocations (URL, payload) for assertion in tests.

#### Scenario: Callback captured after job completion
- **WHEN** a job with `callback_url` completes and deliver_callback is patched
- **THEN** the fixture captures the callback payload including job_id, status, and quality_report
