## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screens**: Shared components appear across ALL Stitch screens. Reference multiple screens to ensure visual consistency.
- **Design System**: "The Digital Curator" (Architectural Intelligence Framework) — the custom Salt DS theme file SHALL implement all design tokens from the Stitch design system: color palette, typography scale (Inter), surface hierarchy (tonal layering, no 1px borders), glassmorphism for floating elements, ambient shadows (tinted, never pure black), and the signature CTA gradient.
- **Component Library**: All shared components SHALL wrap or compose `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`). Shared components provide domain-specific semantics on top of generic Salt DS primitives.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch designs.

## ADDED Requirements

### Requirement: Custom Salt DS theme
The system SHALL provide a custom Salt DS theme CSS file (`web/src/theme/autodoc-theme.css`) that maps the Stitch design system tokens to Salt DS CSS custom properties. The `SaltProvider` in `main.tsx` SHALL load this theme. All components SHALL inherit styling from this theme — no hardcoded color values in component code.

#### Scenario: Theme color tokens
- **WHEN** the custom theme is loaded
- **THEN** it SHALL define CSS custom properties mapping: primary (`#264dd9`), success (`#2e7d32`), warning (`#e65100`), error (`#c62828`), and all surface hierarchy tokens (`surface`, `surface_container_low`, `surface_container_lowest`, etc.) from the Stitch design system

#### Scenario: No-line rule enforcement
- **WHEN** any component renders a section boundary
- **THEN** it SHALL use background color shifts (tonal layering) between surface tiers, NOT 1px solid borders

#### Scenario: Glassmorphism for floating elements
- **WHEN** a floating element is rendered (modal, search overlay, dropdown menu)
- **THEN** it SHALL apply `surface_container_lowest` at 85% opacity with a `20px` backdrop-blur

#### Scenario: Primary CTA gradient
- **WHEN** a primary action button is rendered
- **THEN** it SHALL apply a subtle linear gradient from `primary` (#264dd9) to `primary_container` (#4568f3) at 135 degrees, not a flat color

#### Scenario: Light mode only
- **WHEN** the `SaltProvider` is configured
- **THEN** it SHALL set `mode="light"`. Dark mode is explicitly out of scope for v1.

### Requirement: StatusBadge component
The system SHALL provide a reusable `StatusBadge` component that renders a color-coded pill badge for entity status. This component SHALL be used everywhere a status is displayed (repo cards, job rows, admin tables, overview tab).

#### Scenario: Repository status rendering
- **WHEN** `StatusBadge` receives a repository status
- **THEN** it SHALL render: "Healthy" with success color (green), "Running" with warning color (orange), "Failed" with error color (red), "Pending" with secondary color (purple) — each as a pill-shaped badge using Salt DS `Pill` or `Badge`

#### Scenario: Job status rendering
- **WHEN** `StatusBadge` receives a job status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- **THEN** it SHALL render the status with the corresponding color: COMPLETED → green, RUNNING → orange, FAILED → red, PENDING → purple, CANCELLED → gray (neutral)

### Requirement: ScoreBadge component
The system SHALL provide a reusable `ScoreBadge` component that renders a color-coded score badge. The component SHALL accept a `scale` prop: `quality` (0-10 range) or `relevance` (0-1 range). This component SHALL be used in the quality tab, docs browser metadata, search results, overview tab, and job rows.

#### Scenario: Quality scale color coding (0-10)
- **WHEN** `ScoreBadge` receives a score with `scale="quality"`
- **THEN** it SHALL render: green background for score ≥ 8.0, orange background for score 7.0–7.9, red background for score < 7.0

#### Scenario: Quality scale display format
- **WHEN** `ScoreBadge` receives a score with `scale="quality"`
- **THEN** it SHALL display the score formatted as `X.Y/10` (one decimal place) using the shared `formatScore` utility

#### Scenario: Relevance scale color coding (0-1)
- **WHEN** `ScoreBadge` receives a score with `scale="relevance"`
- **THEN** it SHALL render: green background for score ≥ 0.8, orange background for score 0.6–0.79, gray background for score < 0.6

#### Scenario: Relevance scale display format
- **WHEN** `ScoreBadge` receives a score with `scale="relevance"`
- **THEN** it SHALL display the score formatted as `0.XX` (two decimal places)

### Requirement: MetricCard component
The system SHALL provide a reusable `MetricCard` component that displays a labeled value with optional delta. This component SHALL be used in the overview tab (4 cards), admin health page (4 cards), and admin usage page (3 cards).

#### Scenario: Metric with positive delta
- **WHEN** `MetricCard` receives a value and a positive delta
- **THEN** it SHALL render the value prominently (large text), the label below it, and the delta with an upward arrow (↑) in green

#### Scenario: Metric with negative delta
- **WHEN** `MetricCard` receives a value and a negative delta
- **THEN** it SHALL render the delta with a downward arrow (↓) in red

#### Scenario: Metric without delta
- **WHEN** `MetricCard` receives a value but no delta
- **THEN** it SHALL render the value and label without a delta indicator

### Requirement: PipelineVisualization component
The system SHALL provide a reusable `PipelineVisualization` component that renders the job pipeline stages (Clone → Discover → Structure → Pages → README → PR). This component SHALL be used in the overview tab (latest job card) and jobs tab (running and expanded job views).

#### Scenario: Completed stage rendering
- **WHEN** a pipeline stage has status "completed"
- **THEN** it SHALL render with a green background, a ✓ checkmark, and the stage duration

#### Scenario: Active stage rendering
- **WHEN** a pipeline stage has status "active"
- **THEN** it SHALL render with a blue (primary) background and a pulse/progress animation

#### Scenario: Pending stage rendering
- **WHEN** a pipeline stage has status "pending"
- **THEN** it SHALL render with a gray (neutral) background and a "pending" label

### Requirement: DataTable component
The system SHALL provide a reusable `DataTable` component built on Salt DS data grid that provides consistent table styling, sortable columns, and pagination. This component SHALL be used in jobs tab, quality tab, admin jobs page, admin health page (work pools), and settings tab (branches, webhook deliveries).

#### Scenario: Sortable columns
- **WHEN** `DataTable` receives a column configuration with `sortable: true`
- **THEN** clicking the column header SHALL toggle sort direction (ascending → descending → none) and re-sort the data

#### Scenario: Integrated pagination
- **WHEN** `DataTable` receives paginated data
- **THEN** it SHALL render a "Showing X–Y of Z" indicator and page controls below the table, using Salt DS `Pagination`

#### Scenario: Row expansion
- **WHEN** `DataTable` is configured with expandable rows
- **THEN** clicking a row SHALL expand it to show additional detail content below the row

### Requirement: FilterBar component
The system SHALL provide a reusable `FilterBar` component that renders a horizontal bar of filter controls. This component SHALL be used on the landing page (text filter + status dropdown), jobs tab (status pills), admin jobs page (status pills + search), and search tab (mode pills + scope dropdown).

#### Scenario: Filter pill rendering
- **WHEN** `FilterBar` receives filter options with counts
- **THEN** it SHALL render each option as a selectable pill using Salt DS `ToggleButtonGroup`, with the count displayed in the pill label (e.g., "Running (3)")

#### Scenario: Filter change callback
- **WHEN** the user selects a different filter
- **THEN** `FilterBar` SHALL call the provided `onChange` callback with the new filter value, allowing the parent component to refetch or re-filter data

### Requirement: ConfirmDialog component
The system SHALL provide a reusable `ConfirmDialog` component for destructive actions. This component SHALL be used in settings tab (danger zone), jobs tab (cancel confirmation), and repo deletion.

#### Scenario: Destructive action confirmation
- **WHEN** `ConfirmDialog` is opened for a destructive action
- **THEN** it SHALL display the action title, a warning message, and two buttons: "Cancel" (secondary) and the confirm action (error/red color), using Salt DS `Dialog`

#### Scenario: Confirmation prevents accidental execution
- **WHEN** `ConfirmDialog` is shown
- **THEN** the confirm button SHALL be disabled for 2 seconds to prevent accidental double-clicks

### Requirement: SectionErrorBoundary component
The system SHALL provide a reusable `SectionErrorBoundary` component that wraps individual page sections and catches errors independently. This component SHALL be used around every data-fetching section so that one failed API call does not take down the entire page.

#### Scenario: Section-level API failure
- **WHEN** a section's API call returns an error (4xx or 5xx)
- **THEN** only that section SHALL display an error panel with the error message and a "Retry" button; all other sections on the page SHALL continue to function normally

#### Scenario: Section retry
- **WHEN** the user clicks "Retry" in an error panel
- **THEN** the section SHALL re-execute its data fetch and transition back to the loading state

#### Scenario: Section loading state
- **WHEN** a section's data is being fetched
- **THEN** the section SHALL display a Salt DS `Skeleton` placeholder that mimics the shape of the expected content (not a generic spinner)

### Requirement: EmptyState component
The system SHALL provide a reusable `EmptyState` component for views with no data. This component SHALL be used when: a repo has no jobs, a search returns no results, a repo has no docs, the quality tab has no scores, etc.

#### Scenario: Empty state with CTA
- **WHEN** `EmptyState` receives a message and an action
- **THEN** it SHALL render an icon, a descriptive message, and a primary action button (e.g., "No jobs yet" + "Run First Generation" button)

#### Scenario: Empty state without CTA
- **WHEN** `EmptyState` receives only a message
- **THEN** it SHALL render an icon and the descriptive message without an action button

### Requirement: Shared formatting utilities
The system SHALL provide a shared formatting utility module (`web/src/utils/formatters.ts`) that all components use for consistent data display. Components SHALL NOT format values inline — they SHALL import and use these utilities.

#### Scenario: Relative time formatting
- **WHEN** `formatRelativeTime` receives a timestamp
- **THEN** it SHALL return a human-readable relative string (e.g., "2h ago", "3 days ago", "just now")

#### Scenario: Score formatting
- **WHEN** `formatScore` receives a numeric score
- **THEN** it SHALL return the score formatted as "X.Y/10" with exactly one decimal place

#### Scenario: Token count formatting
- **WHEN** `formatTokens` receives a token count
- **THEN** it SHALL return a comma-separated number (e.g., 3450 → "3,450") or abbreviated form for large values (e.g., 1200000 → "1.2M")

#### Scenario: Duration formatting
- **WHEN** `formatDuration` receives a duration in seconds
- **THEN** it SHALL return a human-readable duration (e.g., 125 → "2m 5s", 3661 → "1h 1m")

### Requirement: Persistent UI state via LocalStorage
The system SHALL persist user-specific UI state in the browser's LocalStorage. This state SHALL survive page refreshes and browser restarts but is explicitly per-browser (not synced across devices).

#### Scenario: Sidebar pinned repos
- **WHEN** the user pins a repository to the sidebar
- **THEN** the system SHALL store the pinned repo IDs in LocalStorage under a namespaced key (e.g., `autodoc:pinned-repos`)
- **WHEN** the app loads
- **THEN** it SHALL read pinned repo IDs from LocalStorage and render them in the sidebar

#### Scenario: Sidebar collapse state
- **WHEN** the user collapses or expands the sidebar
- **THEN** the system SHALL persist the collapsed/expanded state in LocalStorage
- **WHEN** the app loads
- **THEN** it SHALL restore the sidebar to its previously saved state

#### Scenario: LocalStorage unavailable
- **WHEN** LocalStorage is unavailable (private browsing, storage full)
- **THEN** the system SHALL fall back to in-memory state without errors — UI functions normally but state is lost on refresh

### Requirement: Storybook component catalog
The system SHALL include a Storybook configuration that catalogs all shared components with interactive examples. Storybook SHALL be accessible via `npm run storybook` in the `web/` directory.

#### Scenario: Shared component stories
- **WHEN** a developer runs Storybook
- **THEN** it SHALL display stories for every shared component (StatusBadge, ScoreBadge, MetricCard, PipelineVisualization, DataTable, FilterBar, ConfirmDialog, SectionErrorBoundary, EmptyState) showing all variants and states

#### Scenario: Theme integration
- **WHEN** Storybook renders components
- **THEN** it SHALL load the custom Salt DS theme so components appear exactly as they will in the application
