## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screens**:
  - "Repo Jobs Tab" (screen `be6929a954e54d9a8d75b8a3ac729eee`) — job list layout, completed/failed rows, pagination
  - "Repo Jobs Tab" (screen `0fecf70fefc246089e088aade8a0071d`) — running job expanded view, pipeline visualization, per-scope progress
- **Design System**: "The Digital Curator" — running jobs use primary blue border accent, pipeline stages use functional color tokens (green completed, blue active, gray pending), failed jobs use `error_container` background for error messages
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`). Use Salt DS `ToggleButtonGroup` for status filter pills, `Card` for running job cards, `Button` for trigger/cancel/retry actions, `Badge`/`StatusIndicator` for status badges, `LinearProgress` for progress bars, Salt DS data grid for completed job rows, and `Pagination` for page controls.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch designs listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **StatusBadge** — for all job status badges (RUNNING, COMPLETED, FAILED, PENDING, CANCELLED)
- **PipelineVisualization** — for pipeline stage display in running and expanded job views
- **FilterBar** — for status filter pills with counts
- **DataTable** — for completed/failed/cancelled job rows with expandable detail
- **ConfirmDialog** — for cancel job confirmation
- **ScoreBadge** — for average quality score display (scale: quality)
- **SectionErrorBoundary** — wrapping the job list and job detail sections
- **formatRelativeTime**, **formatDuration**, **formatTokens** — from shared formatting utilities

## ADDED Requirements

### Requirement: Jobs tab header with status filter pills
The system SHALL render a "Job History" title at the top of the Jobs tab. Below the title, the system SHALL display status filter pills: "All" (selected by default), "Running", "Completed", and "Failed". Each pill SHALL display the count of jobs matching that status.

#### Scenario: Default filter selection
- **WHEN** the user navigates to `/repos/{id}/jobs`
- **THEN** the "All" filter pill SHALL be visually selected and all jobs SHALL be displayed regardless of status

#### Scenario: Filtering by status
- **WHEN** the user clicks the "Running" filter pill
- **THEN** only jobs with status "running" SHALL be displayed, and the "Running" pill SHALL become visually selected

#### Scenario: Filter pill counts
- **WHEN** the repository has 2 running, 40 completed, and 5 failed jobs
- **THEN** the filter pills SHALL display "All (47)", "Running (2)", "Completed (40)", "Failed (5)"

### Requirement: Job trigger buttons with role-based visibility
The system SHALL display two trigger buttons in the Jobs tab header: "Run Full Generation" (primary style) and "Incremental Update" (secondary style). Each button SHALL include a dry run toggle. These buttons SHALL only be visible to users with Developer or Admin roles.

#### Scenario: Trigger buttons visible for Developer role
- **WHEN** the current user has the Developer role
- **THEN** the "Run Full Generation" and "Incremental Update" buttons SHALL be visible in the Jobs tab header

#### Scenario: Trigger buttons visible for Admin role
- **WHEN** the current user has the Admin role
- **THEN** the "Run Full Generation" and "Incremental Update" buttons SHALL be visible in the Jobs tab header

#### Scenario: Trigger buttons hidden for Reader role
- **WHEN** the current user has the Reader role
- **THEN** the "Run Full Generation" and "Incremental Update" buttons SHALL NOT be rendered

#### Scenario: Triggering a full generation
- **WHEN** a Developer clicks the "Run Full Generation" button with the dry run toggle off
- **THEN** the system SHALL invoke the full generation flow for the repository and a new running job SHALL appear in the job list

#### Scenario: Dry run toggle
- **WHEN** a user enables the dry run toggle and clicks "Run Full Generation"
- **THEN** the system SHALL invoke the full generation flow in dry run mode

### Requirement: Running job expanded display
Running jobs SHALL be displayed in an expanded card format with a blue left border. The card SHALL show the status badge, generation mode, branch, commit SHA, elapsed time, a pipeline visualization, per-scope progress bars within the Pages stage, and a cancel button.

#### Scenario: Running job card layout
- **WHEN** a job with status "running" is rendered in the job list
- **THEN** the card SHALL be expanded with a blue left border, displaying the "Running" status badge, mode (full/incremental), branch name, short commit SHA, and elapsed time since the job started

#### Scenario: Pipeline visualization stages
- **WHEN** a running job has completed the Clone and Discover stages, is currently executing Structure, and has Pages, README, and PR pending
- **THEN** the pipeline visualization SHALL show Clone and Discover with green background, checkmark icon, and duration; Structure with blue background and animated indicator; and Pages, README, and PR with gray background

#### Scenario: Per-scope progress bars in Pages stage
- **WHEN** the running job is in the Pages stage with 3 scopes where scope "backend" is 80% complete, "frontend" is 40% complete, and "shared" has not started
- **THEN** the pipeline visualization SHALL display individual progress bars for each scope within the Pages stage, showing their respective completion percentages

#### Scenario: Cancel button for running job
- **WHEN** a running job card is rendered and the current user has Developer or Admin role
- **THEN** a red "Cancel" button SHALL be displayed on the card

#### Scenario: Cancelling a running job
- **WHEN** a Developer clicks the "Cancel" button on a running job
- **THEN** the system SHALL request cancellation of the job and the job card SHALL transition to the cancelled state

### Requirement: Completed job collapsed display
Completed jobs SHALL be displayed as collapsed single-row entries showing the status badge, generation mode, branch, commit SHA, page count, average quality score, total tokens used, duration, relative time, and a PR link (if available). Clicking the row SHALL expand it to show full pipeline detail.

#### Scenario: Completed job row content
- **WHEN** a completed job generated 24 pages with average quality 8.7, used 150,000 tokens, ran for 12 minutes, completed 2 hours ago, and created PR #42
- **THEN** the row SHALL display a green "Completed" badge, the mode, branch, commit, "24 pages", "8.7 avg", "150k", "12m", "2h ago", and a clickable "PR #42" link

#### Scenario: Expanding a completed job
- **WHEN** the user clicks on a completed job row
- **THEN** the row SHALL expand to reveal the full pipeline visualization with stage durations and details

#### Scenario: PR link navigation
- **WHEN** the user clicks the "PR #42" link on a completed job row
- **THEN** the system SHALL open the pull request URL in a new browser tab

### Requirement: Failed job display with error detail
Failed jobs SHALL be displayed in the same collapsed single-row format as completed jobs, with the addition of an inline error box displayed in red monospace text showing the error type and detail message. A "Retry" action link SHALL be available.

#### Scenario: Failed job error display
- **WHEN** a failed job with error type "PermanentError" and detail "Repository not found" is rendered
- **THEN** the row SHALL display a red "Failed" status badge, and below the row an inline error box SHALL display "PermanentError: Repository not found" in red monospace font

#### Scenario: Retry action on failed job
- **WHEN** the user clicks the "Retry" link on a failed job and the user has Developer or Admin role
- **THEN** the system SHALL trigger a new job with the same parameters as the failed job

#### Scenario: Retry hidden for Reader role
- **WHEN** the current user has the Reader role
- **THEN** the "Retry" action link SHALL NOT be displayed on failed jobs

### Requirement: Cancelled job dimmed display
Cancelled jobs SHALL be displayed as a dimmed row with reduced opacity. The row SHALL show the "Cancelled" status badge, generation mode, branch, the stage at which the job was cancelled, and relative time.

#### Scenario: Cancelled job row appearance
- **WHEN** a cancelled job that was stopped during the "Pages" stage 30 minutes ago is rendered
- **THEN** the row SHALL be displayed with reduced opacity, showing a "Cancelled" status badge, the mode, branch, "Cancelled at: Pages", and "30m ago"

### Requirement: Job detail view
The system SHALL provide a dedicated job detail view at `/repos/{id}/jobs/{job_id}` displaying the full pipeline visualization, a logs viewer, and task state information.

#### Scenario: Navigating to job detail
- **WHEN** the user navigates to `/repos/{id}/jobs/{job_id}`
- **THEN** the system SHALL render the full pipeline visualization for that job, a scrollable logs viewer populated from `GET /jobs/{job_id}/logs`, and a list of task states with their statuses and durations

#### Scenario: Logs viewer content
- **WHEN** the job detail view loads and the API returns log entries from `GET /jobs/{job_id}/logs`
- **THEN** the logs viewer SHALL display the log entries in chronological order in a scrollable, monospace-formatted panel

#### Scenario: Deep-linkable job detail URL
- **WHEN** a user navigates directly to `/repos/42/jobs/abc-123` via the browser URL bar
- **THEN** the system SHALL render the job detail view for job "abc-123" in repository 42

### Requirement: Jobs list pagination
The system SHALL paginate the jobs list and display a pagination indicator showing the current range and total count.

#### Scenario: Pagination indicator displayed
- **WHEN** the jobs list contains 47 jobs and the first page of 5 is displayed
- **THEN** a pagination indicator SHALL display "Showing 1-5 of 47 jobs"

#### Scenario: Navigating to next page
- **WHEN** the user clicks the next page control
- **THEN** the jobs list SHALL display the next 5 jobs and the pagination indicator SHALL update to "Showing 6-10 of 47 jobs"

#### Scenario: Last page with fewer items
- **WHEN** the user navigates to the last page and only 2 jobs remain
- **THEN** the pagination indicator SHALL display "Showing 46-47 of 47 jobs" and the next page control SHALL be disabled
