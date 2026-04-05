## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screens**: The global shell (sidebar, top bar, search bar) is visible in all Stitch screens. Reference any screen for shell layout — e.g., "Repo Landing Page" (screen `9fddc678066943a993e05ca756ae8980`), "Repo Overview Tab" (screen `f5c340e4a7c04e5783b4b8d40e42cace`)
- **Design System**: "The Digital Curator" (Architectural Intelligence Framework) — see Stitch project design system for color tokens, typography (Inter), surface hierarchy ("no-line" rule, tonal layering), glassmorphism for floating elements, and dark sidebar (`inverse_surface: #2f2f40`)
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`). Use Salt DS `BorderLayout`/`BorderItem` for the three-zone shell, `NavigationItem` for sidebar items, `SearchInput` for the search bar, `Badge` for status indicators, `Button` for actions, and `StackLayout`/`FlexLayout` for internal arrangement. Only create custom components when Salt DS does not provide the needed functionality.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch designs listed above.

## ADDED Requirements

### Requirement: Persistent top bar
The system SHALL render a persistent top bar that remains visible across all pages. The top bar SHALL contain, from left to right: the AutoDoc logo (linking to the home route `/`), a context-aware search bar, a job status badge, a notifications area, and a user menu.

#### Scenario: Logo links to home
- **WHEN** the user clicks the AutoDoc logo in the top bar
- **THEN** the application SHALL navigate to the root route `/`

#### Scenario: Top bar persists across navigation
- **WHEN** the user navigates between any routes (e.g., `/` to `/repos/{id}/docs`)
- **THEN** the top bar SHALL remain rendered without re-mounting or visual flicker

### Requirement: Context-aware search bar
The system SHALL render a search bar in the top bar that adapts its placeholder text, autocomplete behavior, and search scope based on the current route context. The search bar SHALL be activatable via the keyboard shortcut Cmd+K (macOS) / Ctrl+K (other platforms).

#### Scenario: Search on repository list page
- **WHEN** the user is on the root route `/`
- **THEN** the search bar SHALL display the placeholder "Search repositories..." and provide autocomplete suggestions matching repository names

#### Scenario: Search inside a repository
- **WHEN** the user is on any route matching `/repos/{id}/*`
- **THEN** the search bar SHALL display the placeholder "{repo-name} > Search docs..." and execute hybrid search scoped to that repository's documents

#### Scenario: Search on admin pages
- **WHEN** the user is on any route matching `/admin/*`
- **THEN** the search bar SHALL display the placeholder "Search all jobs, repos..." and search across all repositories and jobs

#### Scenario: Keyboard shortcut activation
- **WHEN** the user presses Cmd+K (macOS) or Ctrl+K (other platforms) from any page
- **THEN** the search bar SHALL receive focus and be ready for input

### Requirement: Job status badge
The system SHALL display a badge in the top bar showing the count of currently running jobs. The badge SHALL update in real time or near-real time.

#### Scenario: Running jobs displayed
- **WHEN** there are 3 jobs with status "running" across all repositories
- **THEN** the job status badge SHALL display the number "3"

#### Scenario: No running jobs
- **WHEN** there are zero jobs with status "running"
- **THEN** the job status badge SHALL either be hidden or display "0" in a muted style

#### Scenario: Job count data source
- **WHEN** the job status badge needs the count of running jobs
- **THEN** the system SHALL poll `GET /jobs?status=running&limit=1` and use the total count from the paginated response, refreshing every 30 seconds via TanStack Query

### Requirement: User menu with role display
The system SHALL render a user menu in the top bar that displays the current user's name or avatar and their assigned role (e.g., Reader, Developer, Admin).

#### Scenario: Role visibility
- **WHEN** the user opens the user menu
- **THEN** the menu SHALL display the user's current role (Reader, Developer, or Admin)

### Requirement: Collapsible left sidebar
The system SHALL render a dark-themed left sidebar containing navigation items. The sidebar SHALL support two states: expanded (showing icon + label) and collapsed (showing icon only). The sidebar SHALL contain a "Repositories" navigation item, a "Pinned Repos" section for quick access, and an "Admin" section at the bottom.

#### Scenario: Sidebar expanded state
- **WHEN** the sidebar is in expanded state
- **THEN** each navigation item SHALL display both its icon and its text label

#### Scenario: Sidebar collapsed state
- **WHEN** the user collapses the sidebar
- **THEN** the sidebar SHALL display only icons for each navigation item and the main content area SHALL expand to fill the freed horizontal space

#### Scenario: Active item indicator
- **WHEN** a sidebar navigation item corresponds to the current route
- **THEN** that item SHALL display a left blue border accent to indicate active state

#### Scenario: Admin section visibility
- **WHEN** the current user has the Admin role
- **THEN** the sidebar SHALL display the "Admin" section at the bottom of the navigation

#### Scenario: Admin section hidden for non-admins
- **WHEN** the current user has the Reader or Developer role
- **THEN** the sidebar SHALL NOT display the "Admin" section

### Requirement: Pinned repositories in sidebar
The system SHALL display a "Pinned Repos" section in the sidebar listing repositories the user has pinned for quick access. Pinned repos MUST persist across sessions.

#### Scenario: Pinned repo navigation
- **WHEN** the user clicks a pinned repository in the sidebar
- **THEN** the application SHALL navigate to that repository's workspace at `/repos/{id}`

#### Scenario: Pin persistence
- **WHEN** the user pins a repository and later returns to the application in a new session
- **THEN** the pinned repository SHALL still appear in the "Pinned Repos" section

### Requirement: Main content area
The system SHALL render a main content area that fills all remaining viewport space not occupied by the top bar and sidebar. The main content area SHALL be the render target for route-specific page content.

#### Scenario: Layout fill
- **WHEN** the application renders any page
- **THEN** the main content area SHALL occupy 100% of the remaining width (viewport minus sidebar) and remaining height (viewport minus top bar) without scrollbars on the shell itself

### Requirement: Deep-linkable URL structure
The system SHALL support deep linking for all navigable views via the following URL structure: `/` (repository list), `/repos/{id}` (repository workspace - overview), `/repos/{id}/docs` (documentation), `/repos/{id}/search` (search), `/repos/{id}/chat` (chat - future), `/repos/{id}/jobs` (jobs), `/repos/{id}/quality` (quality), `/repos/{id}/settings` (settings), and `/admin/*` (admin pages).

#### Scenario: Direct URL navigation
- **WHEN** a user navigates directly to `/repos/42/docs` via browser URL bar or bookmark
- **THEN** the application SHALL render the dashboard shell (top bar, sidebar, main content) with the Docs tab active for repository ID 42

#### Scenario: Browser back/forward
- **WHEN** the user navigates from `/` to `/repos/42/jobs` and then presses the browser back button
- **THEN** the application SHALL return to `/` with the repository list page rendered
