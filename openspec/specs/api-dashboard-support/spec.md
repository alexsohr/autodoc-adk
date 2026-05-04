## ADDED Requirements

### Requirement: Repository overview endpoint
The system SHALL expose a `GET /repositories/{id}/overview` endpoint that returns an aggregated overview of a repository's documentation state, including page count, quality scores, scope summaries, last job, and recent activity.

#### Scenario: Successful overview retrieval
- **WHEN** a client sends `GET /repositories/{id}/overview` with a valid repository ID
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `page_count` (int) — total number of wiki pages for this repository
  - `avg_quality_score` (float) — mean quality score across all pages
  - `scope_summaries` (list of objects) — each object containing `scope_path` (str), `page_count` (int), and `avg_quality_score` (float)
  - `last_job` (JobResponse or null) — the most recently completed or running job for this repository, using the existing JobResponse schema
  - `recent_activity` (list of objects, max 20) — each object containing `event_type` (str), `description` (str), and `timestamp` (ISO 8601 datetime), derived from job history

#### Scenario: Repository not found
- **WHEN** a client sends `GET /repositories/{id}/overview` with a non-existent repository ID
- **THEN** the response SHALL be `404 Not Found` with the existing ErrorResponse schema (`{detail: str}`)

#### Scenario: Repository with no jobs or pages
- **WHEN** a client sends `GET /repositories/{id}/overview` for a repository that has been registered but never processed
- **THEN** the response SHALL be `200 OK` with `page_count` of 0, `avg_quality_score` of null, `scope_summaries` as an empty list, `last_job` as null, and `recent_activity` as an empty list

### Requirement: Repository quality endpoint
The system SHALL expose a `GET /repositories/{id}/quality` endpoint that returns quality metrics, per-page scores, and token usage breakdowns for a repository.

#### Scenario: Successful quality retrieval
- **WHEN** a client sends `GET /repositories/{id}/quality` with a valid repository ID
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `agent_scores` (list of objects) — each object containing `name` (str, agent identifier), `current_score` (float), `previous_score` (float or null), and `trend` (list of up to 5 floats representing the last 5 job scores for that agent)
  - `page_scores` (paginated list of objects) — each object containing `page_key` (str), `title` (str), `scope` (str), `score` (float), `attempt_count` (int), and `token_cost` (int, total tokens consumed generating this page)
  - `token_breakdown` (list of objects) — each object containing `name` (str, agent identifier), `input_tokens` (int), `output_tokens` (int), and `total` (int)

#### Scenario: Page scores pagination
- **WHEN** a client sends `GET /repositories/{id}/quality` with query parameters `cursor` and `limit`
- **THEN** the `page_scores` list SHALL be paginated using the existing cursor/limit pattern, returning at most `limit` items and including a `next_cursor` field when more results are available

#### Scenario: Repository not found
- **WHEN** a client sends `GET /repositories/{id}/quality` with a non-existent repository ID
- **THEN** the response SHALL be `404 Not Found` with the existing ErrorResponse schema

### Requirement: Page quality detail endpoint
The system SHALL expose a `GET /repositories/{id}/quality/pages/{page_key}` endpoint that returns detailed critic feedback and per-criterion scores for a specific wiki page.

#### Scenario: Successful page quality retrieval
- **WHEN** a client sends `GET /repositories/{id}/quality/pages/{page_key}` with a valid repository ID and page key
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `per_criterion_scores` (object) — containing `accuracy` (float), `completeness` (float), `clarity` (float), and `structure` (float)
  - `critic_feedback` (str) — the full text of the most recent critic evaluation
  - `attempt_history` (list of objects) — each object containing `attempt` (int, 1-based attempt number), `score` (float), and `feedback` (str), ordered by attempt number ascending

#### Scenario: Page not found
- **WHEN** a client sends `GET /repositories/{id}/quality/pages/{page_key}` with a non-existent page key
- **THEN** the response SHALL be `404 Not Found` with the existing ErrorResponse schema

#### Scenario: Page with single attempt
- **WHEN** the requested page was generated successfully on the first attempt
- **THEN** the `attempt_history` list SHALL contain exactly one entry with `attempt` of 1

### Requirement: Job progress endpoint
The system SHALL expose a `GET /jobs/{id}/progress` endpoint that returns pipeline stage statuses and per-scope progress for a running or completed job.

#### Scenario: Running job progress
- **WHEN** a client sends `GET /jobs/{id}/progress` for a job that is currently running
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `stages` (list of objects) — each object containing `name` (str), `status` (enum: `completed`, `active`, `pending`), `started_at` (ISO 8601 datetime or null), `completed_at` (ISO 8601 datetime or null), and `duration_seconds` (float or null)
  - `per_scope_progress` (list of objects) — each object containing `scope_path` (str), `pages_completed` (int), and `pages_total` (int)

#### Scenario: Completed job progress
- **WHEN** a client sends `GET /jobs/{id}/progress` for a job that has completed
- **THEN** all entries in the `stages` list SHALL have `status` of `completed`, and all entries in `per_scope_progress` SHALL have `pages_completed` equal to `pages_total`

#### Scenario: Job not found
- **WHEN** a client sends `GET /jobs/{id}/progress` with a non-existent job ID
- **THEN** the response SHALL be `404 Not Found` with the existing ErrorResponse schema

#### Scenario: Stage ordering
- **WHEN** the `stages` list is returned
- **THEN** the stages SHALL be ordered by pipeline execution order (e.g., Clone, Discover, Structure, Pages, README, PR)

### Requirement: Admin health endpoint
The system SHALL expose a `GET /admin/health` endpoint that returns system health status for the API, Prefect, database, and worker pools.

#### Scenario: All systems healthy
- **WHEN** a client sends `GET /admin/health` and all subsystems are operational
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `api` (object) — containing `status` (str, `healthy`), `uptime_seconds` (float), and `avg_latency_ms` (float)
  - `prefect` (object) — containing `status` (str, `healthy`) and `work_pool_count` (int)
  - `database` (object) — containing `status` (str, `healthy`), `version` (str, e.g., `PostgreSQL 18.0`), `pgvector_enabled` (bool), and `storage_bytes` (int)
  - `workers` (object) — containing `status` (str, `healthy`), `pools` (list of objects, each containing `name` (str), `type` (str), `active` (int), `limit` (int), `queued` (int), and `status` (str)), `peak_utilization_pct` (float), and `avg_wait_seconds` (float)

#### Scenario: Degraded subsystem
- **WHEN** a client sends `GET /admin/health` and the Prefect server is unreachable
- **THEN** the response SHALL be `200 OK` with the `prefect.status` field set to `degraded` and all other healthy subsystems reporting `healthy`

#### Scenario: Database unavailable
- **WHEN** the database connection cannot be established
- **THEN** the `database.status` field SHALL be `unavailable` and the endpoint SHALL still return `200 OK` (the endpoint itself MUST NOT fail due to a downstream dependency being down)

### Requirement: Admin usage endpoint
The system SHALL expose a `GET /admin/usage` endpoint that returns token consumption, cost estimates, and job statistics for a configurable time period.

#### Scenario: Default period retrieval
- **WHEN** a client sends `GET /admin/usage` without query parameters
- **THEN** the response SHALL default to the `this_month` period and return a JSON body containing:
  - `period` (object) — containing `start` (ISO 8601 date) and `end` (ISO 8601 date)
  - `total_tokens` (int)
  - `estimated_cost_usd` (float)
  - `total_jobs` (int)
  - `repo_count` (int)
  - `top_repos_by_tokens` (list of objects) — each containing `repo_id` (UUID), `repo_name` (str), and `total_tokens` (int)
  - `usage_by_model` (list of objects) — each containing `model` (str), `input_tokens` (int), `output_tokens` (int), and `estimated_cost_usd` (float)
  - `daily_burn_rate_usd` (float)
  - `job_success_rate` (float, 0.0-1.0)
  - `recent_cost_centers` (list of objects) — each containing `transaction_id` (str), `description` (str), `token_count` (int), `status` (str, "settled" or "processing"), `amount_usd` (float), and `timestamp` (ISO 8601 datetime)

#### Scenario: Custom date range
- **WHEN** a client sends `GET /admin/usage?period=custom&start_date=2026-01-01&end_date=2026-03-31`
- **THEN** the response SHALL return usage statistics scoped to the date range 2026-01-01 through 2026-03-31 inclusive

#### Scenario: Predefined period options
- **WHEN** a client sends `GET /admin/usage` with the `period` query parameter
- **THEN** the system SHALL accept the values `this_month`, `last_30d`, `last_90d`, and `custom`; any other value SHALL result in a `422 Unprocessable Entity` response

#### Scenario: Custom period without dates
- **WHEN** a client sends `GET /admin/usage?period=custom` without `start_date` and `end_date`
- **THEN** the response SHALL be `422 Unprocessable Entity` with the existing ErrorResponse schema indicating that `start_date` and `end_date` are required when period is `custom`

### Requirement: Admin MCP status endpoint
The system SHALL expose a `GET /admin/mcp` endpoint that returns the status and usage metrics of the MCP server.

#### Scenario: MCP server running
- **WHEN** a client sends `GET /admin/mcp` and the MCP server is operational
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `endpoint_url` (str) — the URL at which the MCP server is accessible
  - `tools` (list of str) — names of registered MCP tools
  - `status` (str, `running` or `stopped`)
  - `usage` (object) — containing `total_requests` (int), `unique_agents` (int), and `success_rate` (float, 0.0 to 1.0), computed over the last 30 days
  - `auth_method` (str)
  - `last_credential_rotation` (ISO 8601 datetime or null)
  - `ip_restriction_enabled` (bool)
  - `telemetry` (object) — containing `avg_latency_ms` (float), `peak_load_rps` (float), and `memory_gb` (float)
  - `integration_snippets` (list of objects) — each containing `name` (str), `platform` (str), and `code` (str)

#### Scenario: MCP server stopped
- **WHEN** a client sends `GET /admin/mcp` and the MCP server is not running
- **THEN** the response SHALL be `200 OK` with `status` set to `stopped` and `usage` fields set to their zero values (0 for counts, 0.0 for rate)

### Requirement: Authentication identity endpoint
The system SHALL expose a `GET /auth/me` endpoint that returns the current user's identity derived from SSO headers.

#### Scenario: Authenticated user
- **WHEN** a client sends `GET /auth/me` with valid SSO headers present
- **THEN** the response SHALL be `200 OK` with a JSON body containing:
  - `username` (str)
  - `email` (str)
  - `role` (str, one of `reader`, `developer`, `admin`)

#### Scenario: Missing SSO headers
- **WHEN** a client sends `GET /auth/me` without SSO headers
- **THEN** the response SHALL be `401 Unauthorized` with the existing ErrorResponse schema

#### Scenario: Role mapping
- **WHEN** the SSO headers contain a role claim
- **THEN** the system SHALL map the claim value to one of the three supported roles (`reader`, `developer`, `admin`); unrecognized role values SHALL default to `reader`

### Requirement: Repository schedule endpoint
The system SHALL expose a `PATCH /repositories/{id}/schedule` endpoint that allows creating or updating the auto-generation schedule for a repository.

#### Scenario: Setting a schedule
- **WHEN** a client sends `PATCH /repositories/{id}/schedule` with a JSON body containing `enabled` (bool), `mode` (str, "full" or "incremental"), `frequency` (str, "daily", "weekly", or "monthly"), and `day_of_week` (int or null, 0-6 for weekly schedules)
- **THEN** the response SHALL be `200 OK` with the updated schedule object, and the system SHALL create or update the corresponding Prefect deployment schedule

#### Scenario: Disabling a schedule
- **WHEN** a client sends `PATCH /repositories/{id}/schedule` with `enabled: false`
- **THEN** the system SHALL disable the auto-generation schedule and the response SHALL reflect `enabled: false`

#### Scenario: Getting the current schedule
- **WHEN** a client sends `GET /repositories/{id}/schedule`
- **THEN** the response SHALL be `200 OK` with the current schedule configuration, or `200 OK` with `enabled: false` if no schedule exists

### Requirement: Repository config commit endpoint
The system SHALL expose a `POST /repositories/{id}/config` endpoint that creates a pull request with an updated `.autodoc.yaml` file.

#### Scenario: Committing config to repo
- **WHEN** a client sends `POST /repositories/{id}/config` with a JSON body containing `scope_path` (str) and `yaml_content` (str)
- **THEN** the system SHALL create a pull request in the source repository adding or updating the `.autodoc.yaml` file at the specified scope path, and the response SHALL be `201 Created` with `pull_request_url` (str)

#### Scenario: Invalid YAML content
- **WHEN** a client sends `POST /repositories/{id}/config` with invalid YAML content
- **THEN** the response SHALL be `422 Unprocessable Entity` with validation errors in the ErrorResponse schema

### Requirement: Consistent error responses
All new dashboard API endpoints SHALL use the existing ErrorResponse schema (`{detail: str}`) for all error responses (4xx and 5xx).

#### Scenario: Validation error format
- **WHEN** any new endpoint receives an invalid request (e.g., malformed query parameter)
- **THEN** the response SHALL use the existing ErrorResponse schema with an appropriate HTTP status code (400 or 422)

#### Scenario: Internal server error format
- **WHEN** any new endpoint encounters an unexpected internal error
- **THEN** the response SHALL return `500 Internal Server Error` with the existing ErrorResponse schema and SHALL NOT expose stack traces or internal details in the `detail` field
