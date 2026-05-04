## ADDED Requirements

### Requirement: Notifications button opens a dropdown
Clicking the bell icon in the TopBar SHALL open a dropdown/popover panel. For this phase, the panel SHALL display a placeholder message indicating no notifications are available.

#### Scenario: Opening notifications panel
- **WHEN** user clicks the bell icon in the TopBar
- **THEN** a dropdown panel SHALL appear below the icon with the message "No new notifications"

#### Scenario: Closing notifications panel
- **WHEN** the notifications panel is open and user clicks outside or presses Escape
- **THEN** the panel SHALL close

### Requirement: Global search shows results in a dropdown
The ContextSearch component SHALL display a results dropdown when the user types a search query. Results SHALL be fetched from the existing per-repository search endpoints.

#### Scenario: Typing a search query
- **WHEN** user types "authentication" in the global search field (or presses ⌘K then types)
- **THEN** after a 300ms debounce, the component SHALL query repositories and display matching page results grouped by repository in a dropdown overlay

#### Scenario: Clicking a search result
- **WHEN** user clicks a search result item
- **THEN** the application SHALL navigate to that page's location (e.g., `/repos/{id}/docs?page={pageKey}`)
- **AND** the search dropdown SHALL close

#### Scenario: Empty search results
- **WHEN** user types a query that matches no pages
- **THEN** the dropdown SHALL display "No results found"

#### Scenario: Search field cleared
- **WHEN** user clears the search field or presses Escape
- **THEN** the dropdown SHALL close
