## MODIFIED Requirements

### Requirement: Overview tab metric cards display repository statistics
The Overview tab metric cards (Doc Pages, Scopes, Avg Quality, Last Generated) SHALL render values from the enriched repository response. When a value is `null` or `undefined`, the card SHALL display `0` for counts and `"—"` for optional fields. The system SHALL NOT render the literal string `"undefined"`.

#### Scenario: Repository with documentation statistics
- **WHEN** the overview tab loads for a repository with `page_count: 15`, `scope_count: 3`, `avg_quality_score: 0.82`
- **THEN** the metric cards SHALL display `"15"`, `"3"`, `"0.82"` respectively

#### Scenario: Repository with no documentation
- **WHEN** the overview tab loads for a repository with `page_count: 0`, `scope_count: 0`, `avg_quality_score: null`
- **THEN** the metric cards SHALL display `"0"`, `"0"`, `"—"` respectively — never `"undefined"`

### Requirement: Repository Info panel displays Main Branch
The "Main Branch" row in the Repository Info panel SHALL display the value from the `default_branch` field (aliased from `public_branch` in the enriched response).

#### Scenario: Main Branch populated
- **WHEN** the overview tab loads for a repository with `default_branch: "main"`
- **THEN** the "Main Branch" row SHALL display `"main"`

### Requirement: Workspace header status badge reflects enriched status
The status badge in the workspace header SHALL use the `status` field from the enriched repository response, matching the same value shown on the repository list card.

#### Scenario: Repository with pending status
- **WHEN** the workspace header loads for a repository with `status: "pending"`
- **THEN** the status badge SHALL display `"Pending"` — not `"Unknown"`
