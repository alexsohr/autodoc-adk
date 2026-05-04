## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screen**: "Repo Landing Page" (screen `9fddc678066943a993e05ca756ae8980`) — use `mcp__stitch__get_screen` with projectId `17903516435494788863` and screenId `9fddc678066943a993e05ca756ae8980` to fetch the design
- **Design System**: "The Digital Curator" — tonal layering for card surfaces (no 1px borders), status badges use pill shape with functional color tokens, cards use `surface_container_lowest` on `surface_container_low` background
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`). Use Salt DS `Card` for repo cards, `GridLayout` for the card grid, `StatusIndicator` for health badges, `Button` for actions, `Input` for filter, `Dropdown` for status filter, `Dialog` for Add Repository modal, `Pagination` for page controls, and `Badge`/`Pill` for tags. Note: The status filter uses Salt DS `Dropdown` (not the shared `FilterBar` toggle pills component, which is for Jobs/Admin pages).
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch design listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **StatusBadge** — for repo status badges (Healthy, Running, Failed, Pending)
- **MetricCard** — pattern reference for card metrics display
- **ConfirmDialog** — pattern reference for Add Repository validation errors
- **SectionErrorBoundary** — wrapping the card grid for error/loading states
- **EmptyState** — when no repositories match filters
- **formatRelativeTime** — for "last generated" time display on cards

## ADDED Requirements

### Requirement: Page header with title and count
The system SHALL render a page header on the root route `/` displaying the title "Repositories" alongside a count of total repositories matching the current filters.

#### Scenario: Title and count displayed
- **WHEN** the user navigates to `/` with 17 total repositories and no filters applied
- **THEN** the page header SHALL display "Repositories" with a count indicator showing "17"

#### Scenario: Count reflects active filters
- **WHEN** the user applies a status filter of "Failed" and 3 repositories match
- **THEN** the count indicator SHALL update to show "3"

### Requirement: Filter controls
The system SHALL provide a filter input for searching repositories by name or description, and a status dropdown filter with options: All, Healthy, Running, Failed, and Pending.

#### Scenario: Name/description filter
- **WHEN** the user types "payment" into the filter input
- **THEN** the repository card grid SHALL display only repositories whose name or description contains "payment" (case-insensitive)

#### Scenario: Status dropdown filter
- **WHEN** the user selects "Failed" from the status dropdown
- **THEN** the repository card grid SHALL display only repositories whose most recent job status is "failed"

#### Scenario: Combined filters
- **WHEN** the user types "api" into the filter input AND selects "Healthy" from the status dropdown
- **THEN** the repository card grid SHALL display only repositories matching both criteria

### Requirement: Add Repository button
The system SHALL display a "+ Add Repo" button in the page header that opens the Add Repository flow.

#### Scenario: Button triggers registration flow
- **WHEN** the user clicks the "+ Add Repo" button
- **THEN** the system SHALL open the Add Repository modal dialog

### Requirement: Repository card grid
The system SHALL render repositories as a responsive card grid. Each card SHALL display: the repository name, a status badge, a description, key metrics, and tags.

#### Scenario: Healthy repository card
- **WHEN** a repository's most recent job completed successfully
- **THEN** its card SHALL display a green "Healthy" status badge, the repository description, metrics (page count, average quality score, last generation time), and tags (language, scope count, provider)

#### Scenario: Running repository card
- **WHEN** a repository has a job currently in progress
- **THEN** its card SHALL display an orange "Running" status badge, an inline progress bar showing completion percentage, and the current pipeline stage name

#### Scenario: Failed repository card
- **WHEN** a repository's most recent job failed
- **THEN** its card SHALL display a red "Failed" status badge and an inline error snippet showing the error type and message

#### Scenario: Pending repository card
- **WHEN** a repository has been registered but no job has been executed
- **THEN** its card SHALL display a purple "Pending" status badge

### Requirement: Responsive card grid layout
The system SHALL adapt the number of card columns based on viewport width to ensure usability across screen sizes.

#### Scenario: Wide viewport
- **WHEN** the viewport width is 1440px or greater
- **THEN** the card grid SHALL display 3 columns

#### Scenario: Medium viewport
- **WHEN** the viewport width is between 1024px and 1439px
- **THEN** the card grid SHALL display 2 columns

#### Scenario: Narrow viewport
- **WHEN** the viewport width is less than 1024px
- **THEN** the card grid SHALL display 1 column

### Requirement: Add Repository placeholder card
The system SHALL render a dashed-border placeholder card at the end of the repository card grid labeled "+ Add Repository" that triggers the registration flow.

#### Scenario: Placeholder card interaction
- **WHEN** the user clicks the dashed-border "+ Add Repository" card
- **THEN** the system SHALL open the Add Repository modal dialog

#### Scenario: Placeholder card position
- **WHEN** the repository card grid is rendered
- **THEN** the dashed-border placeholder card SHALL appear after all repository cards

### Requirement: Add Repository modal dialog
The system SHALL provide a modal dialog for registering a new repository. The dialog MUST collect: repository URL (required), git provider (GitHub or Bitbucket, required), target branches (comma-separated, required), and access token (optional, for private repos).

#### Scenario: Successful registration
- **WHEN** the user fills in a valid repository URL, selects a provider, enters target branches, and submits the form
- **THEN** the system SHALL create the repository via the API, close the modal, and display the new repository card in the grid with "Pending" status

#### Scenario: Validation error
- **WHEN** the user submits the form with a missing required field (e.g., empty repository URL)
- **THEN** the system SHALL display inline validation errors on the offending fields and SHALL NOT submit the form

#### Scenario: API error during registration
- **WHEN** the API returns an error during repository creation (e.g., duplicate URL)
- **THEN** the system SHALL display the error message within the modal and keep the modal open for correction

### Requirement: Pagination
The system SHALL paginate the repository card grid and display pagination controls below the grid.

#### Scenario: Pagination display
- **WHEN** there are 17 repositories and 12 are shown per page
- **THEN** the pagination area SHALL display "Showing 1-12 of 17" with page number controls

#### Scenario: Page navigation
- **WHEN** the user clicks page 2
- **THEN** the card grid SHALL display repositories 13-17 and the pagination text SHALL update to "Showing 13-17 of 17"

#### Scenario: Single page
- **WHEN** there are 4 or fewer repositories
- **THEN** the pagination controls SHALL either be hidden or displayed in a disabled state
