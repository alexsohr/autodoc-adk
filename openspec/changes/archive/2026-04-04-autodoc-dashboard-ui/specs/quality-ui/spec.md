# Quality Tab Specification

**Route:** `/repos/{id}/quality`
**Visibility:** Developer, Admin
**Change:** autodoc-dashboard-ui

## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screen**: "Repo Quality Tab" (screen `45683976412041889f2f916b3a3eba76`) — use `mcp__stitch__get_screen` with projectId `17903516435494788863` and screenId `45683976412041889f2f916b3a3eba76` to fetch the design
- **Design System**: "The Digital Curator" — agent score cards use tonal layering, quality scores use functional color tokens (green ≥8.0, orange 7.0-7.9, red <7.0), sparklines/trend charts use `primary` blue, token usage bars use proportional fills
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`). Use Salt DS `Card` for agent score cards, Salt DS data grid for the per-page quality table, `Badge` for score indicators, `LinearProgress` for criterion progress bars, `Dropdown` for filters, `Pagination` for table pagination, and `StackLayout`/`GridLayout` for arrangement.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch design listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **MetricCard** — for agent score cards (current score, delta, trend)
- **ScoreBadge** — for all quality score displays (scale: quality)
- **DataTable** — for the per-page quality table with sorting and pagination
- **SectionErrorBoundary** — wrapping each section independently
- **EmptyState** — when no quality data exists yet
- **formatTokens** — for token cost display in table and breakdown

**Status:** Draft
**Date:** 2026-04-04

---

## ADDED Requirements

### Requirement: Agent Score Cards

The Quality tab SHALL display three Agent Score Cards in a horizontal three-column layout, one for each AI agent: Structure Extractor, Page Generator, and README Distiller.

Each card SHALL present the agent's current quality score prominently (large font), a delta indicator showing the change from the previous run (displayed as an up arrow or down arrow with color coding), and a trend sparkline visualizing scores across the last five runs.

#### Scenario: Score cards render for a completed run

WHEN a user navigates to `/repos/{id}/quality` for a repository with at least one completed generation run
THEN the system SHALL display three Agent Score Cards, one per agent, each showing the current score from the most recent run.

#### Scenario: Delta indicator reflects score change direction

WHEN the current run score for an agent differs from the previous run score
THEN the card SHALL display a delta value with an upward arrow (colored green) if the score increased, or a downward arrow (colored red) if the score decreased.

#### Scenario: Delta indicator when no previous run exists

WHEN a repository has only one completed run
THEN the delta indicator SHALL be omitted or displayed as a neutral dash, indicating no comparison is available.

#### Scenario: Trend sparkline displays last five runs

WHEN at least two completed runs exist for the repository
THEN each Agent Score Card SHALL render a sparkline chart reflecting up to the last five run scores for that agent.

---

### Requirement: Per-Page Quality Table

The Quality tab SHALL include a Per-Page Quality Table displaying quality metrics for every generated wiki page.

The table SHALL support filtering by run (latest run selected by default, with an option to view all runs) and by scope (when the repository has multiple `.autodoc.yaml` scopes).

The table columns SHALL be: page name (linked to the corresponding page in the Docs tab), scope, score (displayed as a color-coded badge), attempt count (highlighted when greater than one), and token cost.

The table SHALL be sortable by any column and paginated.

#### Scenario: Table displays pages for the latest run

WHEN a user views the Quality tab without changing filters
THEN the Per-Page Quality Table SHALL display all pages from the most recent completed run, sorted by page name ascending by default.

#### Scenario: Score badge uses correct color coding

WHEN a page has a quality score of 8.0 or higher
THEN the score badge SHALL be green.

WHEN a page has a quality score between 7.0 and 7.9 inclusive
THEN the score badge SHALL be orange.

WHEN a page has a quality score below 7.0
THEN the score badge SHALL be red.

#### Scenario: Attempt count is highlighted for multi-attempt pages

WHEN a page required more than one generation attempt (i.e., the critic loop ran multiple times)
THEN the attempt count cell SHALL be visually highlighted to draw attention.

#### Scenario: Page name links to the Docs tab

WHEN a user clicks a page name in the table
THEN the system SHALL navigate to the corresponding page within the Docs tab of the same repository workspace.

#### Scenario: Filter by scope

WHEN a repository contains multiple scopes and the user selects a specific scope from the scope filter
THEN the table SHALL display only pages belonging to that scope.

#### Scenario: Pagination

WHEN the number of pages exceeds the page size (default 25 rows)
THEN the table SHALL display pagination controls allowing navigation between pages of results.

---

### Requirement: Critic Feedback Panel

The Quality tab SHALL provide a Critic Feedback Panel that expands when a user selects a page row in the Per-Page Quality Table.

The panel SHALL display per-criterion scores with horizontal progress bars for: accuracy, completeness, clarity, and structure.

The panel SHALL display the critic's textual feedback rendered in italic quoted style.

When the page required multiple generation attempts, the panel SHALL display an attempt history showing the score progression across attempts.

#### Scenario: Panel expands on page selection

WHEN a user clicks or selects a row in the Per-Page Quality Table
THEN the Critic Feedback Panel SHALL expand below or beside the selected row, displaying detailed critic evaluation data for that page.

#### Scenario: Per-criterion scores render as progress bars

WHEN the Critic Feedback Panel is open for a page
THEN the panel SHALL display progress bars for accuracy, completeness, clarity, and structure, each filled proportionally to the criterion score and color-coded using the standard thresholds (green >= 8.0, orange 7.0-7.9, red < 7.0).

#### Scenario: Critic feedback text is displayed

WHEN the Critic Feedback Panel is open for a page that has critic feedback text
THEN the feedback text SHALL be rendered in an italic, quoted block style.

#### Scenario: Attempt history displayed for multi-attempt pages

WHEN the selected page has more than one generation attempt
THEN the panel SHALL display an attempt history section listing each attempt's overall score, enabling the user to review how quality improved across iterations.

---

### Requirement: Token Usage Breakdown

The Quality tab SHALL include a Token Usage Breakdown section displaying token consumption for the selected run.

The section SHALL show per-agent token usage with proportional horizontal bars (one bar per agent) and a run total.

#### Scenario: Token usage bars reflect proportional consumption

WHEN a user views the Token Usage Breakdown for a completed run
THEN the system SHALL display one horizontal bar per agent (Structure Extractor, Page Generator, README Distiller) sized proportionally to each agent's token consumption relative to the run total.

#### Scenario: Run total is displayed

WHEN the Token Usage Breakdown is visible
THEN the section SHALL display the total token count for the entire run as a summary figure.

---

### Requirement: Color Coding Standard

All score displays across the Quality tab SHALL use the `ScoreBadge` shared component (scale: quality) which implements the consistent color-coding scheme: green for score >= 8.0, orange for score >= 7.0 and < 8.0, red for score < 7.0. Individual components on the Quality tab SHALL NOT implement their own color logic.

#### Scenario: Consistent color coding via ScoreBadge
- **WHEN** any quality score is rendered on the Quality tab
- **THEN** it MUST use the `ScoreBadge` component from `shared-components/spec.md` to ensure consistent thresholds across Agent Score Cards, Per-Page Quality Table, and Critic Feedback Panel
