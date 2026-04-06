## ADDED Requirements

### Requirement: Repository response includes derived status
The `RepositoryResponse` schema SHALL include a `status` field computed from the repository's latest job. The status mapping SHALL be: job status `RUNNING` → `"running"`, `FAILED` → `"failed"`, `COMPLETED` → `"healthy"`, no jobs → `"pending"`.

#### Scenario: Repository with completed job shows healthy status
- **WHEN** a repository's most recent job has status `COMPLETED`
- **THEN** the repository response `status` field SHALL be `"healthy"`

#### Scenario: Repository with no jobs shows pending status
- **WHEN** a repository has no associated jobs
- **THEN** the repository response `status` field SHALL be `"pending"`

#### Scenario: Repository with running job shows running status
- **WHEN** a repository's most recent job has status `RUNNING`
- **THEN** the repository response `status` field SHALL be `"running"`

#### Scenario: Repository with failed job shows failed status
- **WHEN** a repository's most recent job has status `FAILED`
- **THEN** the repository response `status` field SHALL be `"failed"`

### Requirement: Repository response includes page and scope counts
The `RepositoryResponse` schema SHALL include `page_count` (int) and `scope_count` (int) fields computed from the repository's wiki structures and pages.

#### Scenario: Repository with documentation pages
- **WHEN** a repository has 15 wiki pages across 3 scopes
- **THEN** the response SHALL include `page_count: 15` and `scope_count: 3`

#### Scenario: Repository with no documentation
- **WHEN** a repository has no wiki structures
- **THEN** the response SHALL include `page_count: 0` and `scope_count: 0`

### Requirement: Repository response includes quality score
The `RepositoryResponse` schema SHALL include an `avg_quality_score` field (float or null) representing the average quality score across all pages.

#### Scenario: Repository with scored pages
- **WHEN** a repository has pages with quality scores [0.8, 0.9, 0.7]
- **THEN** the response SHALL include `avg_quality_score: 0.8`

#### Scenario: Repository with no scored pages
- **WHEN** a repository has no pages or no quality scores
- **THEN** the response SHALL include `avg_quality_score: null`

### Requirement: Repository response includes last generation timestamp
The `RepositoryResponse` schema SHALL include a `last_generated_at` field (datetime or null) from the most recent completed job's `updated_at`.

#### Scenario: Repository with completed jobs
- **WHEN** a repository's latest completed job finished at `2026-04-01T10:00:00Z`
- **THEN** the response SHALL include `last_generated_at: "2026-04-01T10:00:00Z"`

#### Scenario: Repository with no completed jobs
- **WHEN** a repository has no completed jobs
- **THEN** the response SHALL include `last_generated_at: null`

### Requirement: Repository response includes default_branch alias
The `RepositoryResponse` schema SHALL include a `default_branch` field that mirrors the existing `public_branch` value.

#### Scenario: Repository with public_branch set to main
- **WHEN** a repository has `public_branch: "main"`
- **THEN** the response SHALL include both `public_branch: "main"` and `default_branch: "main"`

### Requirement: Pending status filter works on repository list
The frontend status filter SHALL correctly count and filter repositories by their derived status values.

#### Scenario: Filtering by Pending status
- **WHEN** 3 repositories have no jobs (status = pending) and user clicks the "Pending" filter
- **THEN** the filter tab SHALL show count `(3)` and display only those 3 repository cards
