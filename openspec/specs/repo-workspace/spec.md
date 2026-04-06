## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screens**:
  - "Repo Overview Tab" (screen `f5c340e4a7c04e5783b4b8d40e42cace`) — overview layout, metric cards, latest job card, scope table, activity timeline
  - "Repo Chat Tab" (screen `248d5fd554cd4cc893f43035fc0e933a`) — chat placeholder layout
- **Design System**: "The Digital Curator" — metric cards use tonal layering, pipeline visualization uses functional color tokens (success green, warning orange, error red), activity timeline uses color-coded entries
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`). Use Salt DS `Tabs`/`Tab`/`TabPanel` for the tab bar, `Card` for metric cards and job cards, `StackLayout`/`GridLayout` for arrangement, `StatusIndicator` for badges, `Button` for trigger actions, and Salt DS data grid or `Table` components for the scope breakdown table.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch designs listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **MetricCard** — for the 4 overview metric cards (Doc Pages, Avg Quality, Scopes, Last Generated)
- **StatusBadge** — for job status and scope status displays
- **ScoreBadge** — for average quality score (scale: quality)
- **PipelineVisualization** — for the latest job card pipeline display
- **DataTable** — for the scope breakdown table
- **SectionErrorBoundary** — wrapping each overview section independently
- **EmptyState** — for empty activity timeline
- **formatRelativeTime**, **formatDuration** — from shared formatting utilities

## ADDED Requirements

### Requirement: Tabbed workspace container
The system SHALL render a tabbed container for a single repository at the route `/repos/{id}/*`. The tab bar SHALL contain the following tabs in order: Overview, Docs, Search, Chat, Jobs, Quality, and Settings.

#### Scenario: Tab bar rendered
- **WHEN** the user navigates to any route under `/repos/{id}/`
- **THEN** the workspace SHALL render a horizontal tab bar with all applicable tabs for the user's role

#### Scenario: Default tab
- **WHEN** the user navigates to `/repos/{id}` without a tab sub-route
- **THEN** the Overview tab SHALL be selected and its content rendered by default

### Requirement: Tab-to-route mapping
Each tab SHALL correspond to a dedicated sub-route under `/repos/{id}/`. The system SHALL synchronize the active tab with the URL path.

#### Scenario: Tab navigation updates URL
- **WHEN** the user clicks the "Jobs" tab
- **THEN** the URL SHALL update to `/repos/{id}/jobs` and the Jobs tab content SHALL render

#### Scenario: Direct URL selects tab
- **WHEN** the user navigates directly to `/repos/{id}/search`
- **THEN** the Search tab SHALL be selected and its content rendered

#### Scenario: Tab routes
- **WHEN** the workspace is rendered
- **THEN** the tab-to-route mapping SHALL be: Overview = `/repos/{id}`, Docs = `/repos/{id}/docs`, Search = `/repos/{id}/search`, Chat = `/repos/{id}/chat`, Jobs = `/repos/{id}/jobs`, Quality = `/repos/{id}/quality`, Settings = `/repos/{id}/settings`

### Requirement: Role-based tab visibility for Settings
The Settings tab SHALL be visible only to users with the Developer or Admin role.

#### Scenario: Settings visible to Developer
- **WHEN** the current user has the Developer role
- **THEN** the Settings tab SHALL be present in the tab bar

#### Scenario: Settings visible to Admin
- **WHEN** the current user has the Admin role
- **THEN** the Settings tab SHALL be present in the tab bar

#### Scenario: Settings hidden from Reader
- **WHEN** the current user has the Reader role
- **THEN** the Settings tab SHALL NOT be present in the tab bar

#### Scenario: Direct URL access denied for Reader
- **WHEN** a user with the Reader role navigates directly to `/repos/{id}/settings`
- **THEN** the system SHALL redirect to `/repos/{id}` or display an access-denied message

### Requirement: Role-based tab visibility for Quality
The Quality tab SHALL be visible only to users with the Developer or Admin role.

#### Scenario: Quality visible to Developer
- **WHEN** the current user has the Developer role
- **THEN** the Quality tab SHALL be present in the tab bar

#### Scenario: Quality visible to Admin
- **WHEN** the current user has the Admin role
- **THEN** the Quality tab SHALL be present in the tab bar

#### Scenario: Quality hidden from Reader
- **WHEN** the current user has the Reader role
- **THEN** the Quality tab SHALL NOT be present in the tab bar

### Requirement: Role-based permissions for Jobs tab
The Jobs tab SHALL be visible to all roles. However, only users with the Developer or Admin role SHALL be able to trigger or cancel jobs.

#### Scenario: Reader can view jobs
- **WHEN** the current user has the Reader role and navigates to the Jobs tab
- **THEN** the system SHALL display the job list and job details in read-only mode

#### Scenario: Reader cannot trigger jobs
- **WHEN** the current user has the Reader role and views the Jobs tab
- **THEN** the "Trigger Job" and "Cancel Job" buttons SHALL be disabled or hidden

#### Scenario: Developer can trigger jobs
- **WHEN** the current user has the Developer role and views the Jobs tab
- **THEN** the "Trigger Job" and "Cancel Job" buttons SHALL be enabled and functional

### Requirement: Chat tab placeholder
The Chat tab SHALL be rendered as a placeholder for a future feature. It MUST be present in the tab bar but SHALL display a "Coming Soon" state when selected.

#### Scenario: Chat tab placeholder content
- **WHEN** the user selects the Chat tab
- **THEN** the system SHALL render a placeholder view indicating that the Chat feature is coming soon, and SHALL NOT render an empty or broken page

### Requirement: Overview tab metric cards display repository statistics
The Overview tab metric cards (Doc Pages, Scopes, Avg Quality, Last Generated) SHALL render values from the enriched repository response. When a value is `null` or `undefined`, the card SHALL display `0` for counts and `"—"` for optional fields. The system SHALL NOT render the literal string `"undefined"`.

#### Scenario: Repository with documentation statistics
- **WHEN** the overview tab loads for a repository with `page_count: 15`, `scope_count: 3`, `avg_quality_score: 0.82`
- **THEN** the metric cards SHALL display `"15"`, `"3"`, `"0.82"` respectively

#### Scenario: Repository with no documentation
- **WHEN** the overview tab loads for a repository with `page_count: 0`, `scope_count: 0`, `avg_quality_score: null`
- **THEN** the metric cards SHALL display `"0"`, `"0"`, `"—"` respectively — never `"undefined"`

### Requirement: Overview tab latest job card
The Overview tab SHALL display a Latest Job Card showing the most recent job's pipeline visualization and trigger buttons for initiating new jobs.

#### Scenario: Latest job with pipeline stages
- **WHEN** the most recent job for the repository has completed
- **THEN** the Latest Job Card SHALL display a pipeline visualization showing each stage (Clone, Discover, Structure, Pages, README, PR) with pass/fail indicators and duration

#### Scenario: Trigger full generation
- **WHEN** a user with Developer or Admin role clicks "Trigger Full Generation" on the Latest Job Card
- **THEN** the system SHALL submit a new full generation job via the API and update the card to show the running job

#### Scenario: Trigger incremental update
- **WHEN** a user with Developer or Admin role clicks "Trigger Incremental Update" on the Latest Job Card
- **THEN** the system SHALL submit a new incremental update job via the API

### Requirement: Overview tab scope breakdown table
The Overview tab SHALL display a Scope Breakdown Table listing each scope in the repository with its scope path, page count, average quality score (using ScoreBadge), and status (using StatusBadge).

#### Scenario: Scope table rendered
- **WHEN** the repository has 3 scopes (e.g., `/`, `/packages/core`, `/packages/ui`)
- **THEN** the Scope Breakdown Table SHALL display 3 rows, each with the scope path, page count, average quality score (using ScoreBadge), and status (using StatusBadge)

#### Scenario: Scope table sorting
- **WHEN** the user clicks a column header in the Scope Breakdown Table
- **THEN** the table SHALL sort rows by that column in ascending order, and clicking again SHALL reverse to descending order

### Requirement: Overview tab repo info panel
The Overview tab SHALL display a Repo Info panel showing the repository's URL, git provider, configured branches, creation date, and tags.

#### Scenario: Repo info displayed
- **WHEN** the user views the Overview tab
- **THEN** the Repo Info panel SHALL display the repository URL (as a clickable link), provider name (GitHub/Bitbucket), configured branches, registration date, and tags

#### Scenario: Edit config shortcut
- **WHEN** the Repo Info panel is displayed and the user has Developer or Admin role
- **THEN** the panel SHALL include an "Edit Repo Config" link that navigates to the Settings tab

### Requirement: Overview tab recent activity timeline
The Overview tab SHALL display a Recent Activity Timeline showing the latest events for the repository (job completions, failures, configuration changes).

#### Scenario: Activity timeline rendered
- **WHEN** the repository has recent job events
- **THEN** the Recent Activity Timeline SHALL display events in reverse chronological order, each with a timestamp, event type icon, and description (e.g., "Full generation completed - 45 pages, avg quality 8.2")

#### Scenario: Empty activity timeline
- **WHEN** the repository has no prior events (newly registered)
- **THEN** the Recent Activity Timeline SHALL display a message such as "No activity yet"

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
