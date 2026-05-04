## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screen**: "Repo Search Tab" (screen `2bfe99bfcdc54e2aab7add9ff0083d75`) — use `mcp__stitch__get_screen` with projectId `17903516435494788863` and screenId `2bfe99bfcdc54e2aab7add9ff0083d75` to fetch the design
- **Design System**: "The Digital Curator" — search result cards use tonal layering, relevance score badges use functional color tokens (green ≥0.8, orange 0.6-0.8, gray <0.6), keyword highlighting uses mark-style yellow
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`). Use Salt DS `Input` or `SearchInput` for the search field, `ToggleButtonGroup`/`ToggleButton` for mode pills, `Dropdown` for scope filter, `Card` for result cards, `Badge`/`Pill` for score badges, `Button` for "Load more", and `StackLayout` for results list.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch design listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **ScoreBadge** — for relevance score badges on result cards (scale: relevance, thresholds: green ≥0.8, orange ≥0.6, gray <0.6)
- **FilterBar** — for search mode pills (Hybrid/Semantic/Text)
- **SectionErrorBoundary** — wrapping the results area for loading/error states
- **EmptyState** — when search returns no results

## ADDED Requirements

### Requirement: Search input with submit action
The system SHALL render a prominent search input field at the top of the Search tab with the placeholder text "Search documentation..." and an adjacent search button. The search input SHALL be the primary focal element of the tab.

#### Scenario: Search input placeholder
- **WHEN** the user navigates to `/repos/{id}/search` with no query parameter
- **THEN** the search input SHALL display the placeholder text "Search documentation..." and the results area SHALL be empty

#### Scenario: Submitting a search query
- **WHEN** the user types a query into the search input and clicks the search button or presses Enter
- **THEN** the system SHALL execute the search and display results in the results area below

#### Scenario: URL updated on search
- **WHEN** the user submits a search query "authentication"
- **THEN** the browser URL SHALL update to `/repos/{id}/search?q=authentication&type={selected_mode}` without a full page reload

### Requirement: Search mode pills
The system SHALL display search mode selector pills below the search input. The available modes SHALL be "Hybrid", "Semantic", and "Text". The "Hybrid" mode SHALL be selected by default.

#### Scenario: Default mode selection
- **WHEN** the user navigates to the Search tab without a `type` query parameter
- **THEN** the "Hybrid" pill SHALL be visually selected as the active mode

#### Scenario: Switching search mode
- **WHEN** the user clicks the "Semantic" pill
- **THEN** the "Semantic" pill SHALL become visually selected, the previously selected pill SHALL become deselected, and if a query is present the search SHALL re-execute using semantic mode

#### Scenario: Mode preserved in URL
- **WHEN** the user selects "Text" mode and submits a query "setup guide"
- **THEN** the URL SHALL update to include `type=text` (e.g., `/repos/{id}/search?q=setup+guide&type=text`)

### Requirement: Scope filter dropdown
The system SHALL display a scope filter dropdown that allows the user to filter search results by scope. The default selection SHALL be "All scopes".

#### Scenario: Default scope filter
- **WHEN** the Search tab loads
- **THEN** the scope filter dropdown SHALL display "All scopes" as the selected option

#### Scenario: Filtering by specific scope
- **WHEN** the user selects a specific scope from the dropdown and a query is present
- **THEN** the search SHALL re-execute with results filtered to only the selected scope

### Requirement: Results count and timing header
The system SHALL display a results header above the result list showing the total result count, the query, and the elapsed search time.

#### Scenario: Results header displayed
- **WHEN** a search for "authentication" returns 12 results in 0.3 seconds
- **THEN** the results header SHALL display text matching the format: "12 results for 'authentication' . 0.3s"

#### Scenario: No results found
- **WHEN** a search query returns zero results
- **THEN** the results header SHALL display "0 results for '{query}'" and the results area SHALL show an empty state message

### Requirement: Result cards with page navigation
Each search result SHALL be rendered as a card containing the page title, breadcrumb path, relevance score badge, search mode indicator, content snippet, chunk source, and importance level. The page title SHALL be clickable and navigate to the corresponding page in the Docs tab.

#### Scenario: Clicking a result page title
- **WHEN** the user clicks the page title on a search result card
- **THEN** the application SHALL navigate to `/repos/{id}/docs/{scope}/{page_key}` for that page

#### Scenario: Breadcrumb path displayed
- **WHEN** a search result belongs to scope "backend", section "API", subsection "Auth"
- **THEN** the result card SHALL display the breadcrumb path "backend > API > Auth" beneath the page title

#### Scenario: Chunk source and importance level
- **WHEN** a search result card is rendered
- **THEN** the card SHALL display the chunk source identifier and the importance level of the matched content

### Requirement: Relevance score badge with color coding
Each result card SHALL display a relevance score badge. The badge color MUST be determined by the score value: green for scores >= 0.8, orange for scores >= 0.6 and < 0.8, and gray for scores < 0.6.

#### Scenario: High relevance score badge
- **WHEN** a search result has a relevance score of 0.92
- **THEN** the score badge SHALL display "0.92" with a green background color

#### Scenario: Medium relevance score badge
- **WHEN** a search result has a relevance score of 0.71
- **THEN** the score badge SHALL display "0.71" with an orange background color

#### Scenario: Low relevance score badge
- **WHEN** a search result has a relevance score of 0.45
- **THEN** the score badge SHALL display "0.45" with a gray background color

### Requirement: Search mode indicator on result cards
Each result card SHALL display an indicator showing which search mode produced the result.

#### Scenario: Mode indicator displayed
- **WHEN** a search result was produced by the "Semantic" search mode
- **THEN** the result card SHALL display a "Semantic" label or icon as the search mode indicator

### Requirement: Snippet with keyword highlighting
Each result card SHALL display a content snippet from the matched chunk. Keywords matching the search query SHALL be highlighted using a yellow mark style.

#### Scenario: Keywords highlighted in snippet
- **WHEN** a search for "authentication token" returns a result with snippet text containing the words "authentication" and "token"
- **THEN** each occurrence of "authentication" and "token" in the snippet SHALL be wrapped in a highlight element with yellow background styling

### Requirement: Score-based opacity for results
The system SHALL apply visual opacity scaling to result cards based on their relevance score. Lower-scoring results SHALL appear slightly faded compared to higher-scoring results.

#### Scenario: High-score result fully opaque
- **WHEN** a search result has a relevance score of 0.95
- **THEN** the result card SHALL be rendered at full opacity

#### Scenario: Low-score result faded
- **WHEN** a search result has a relevance score of 0.35
- **THEN** the result card SHALL be rendered with reduced opacity (visually faded) compared to higher-scoring results

### Requirement: Load more pagination
The system SHALL paginate search results using a "Load more" button rather than infinite scroll. The button SHALL appear below the last visible result when additional results are available.

#### Scenario: Load more button displayed
- **WHEN** a search returns more results than the initial page size
- **THEN** a "Load more" button SHALL be displayed below the last visible result card

#### Scenario: Clicking load more appends results
- **WHEN** the user clicks the "Load more" button
- **THEN** the next page of results SHALL be appended below the existing results without replacing them, and the button SHALL remain visible if more results exist

#### Scenario: All results loaded
- **WHEN** all search results have been loaded
- **THEN** the "Load more" button SHALL NOT be displayed

### Requirement: Deep-linkable search URLs
The system SHALL support deep linking for search queries. The URL SHALL preserve the query string and search type so that sharing or bookmarking a search URL reproduces the same results.

#### Scenario: Direct navigation to search URL
- **WHEN** a user navigates directly to `/repos/42/search?q=deployment&type=semantic`
- **THEN** the Search tab SHALL load with "deployment" pre-filled in the search input, the "Semantic" pill selected, and the search results displayed for that query in semantic mode

#### Scenario: Browser back restores search state
- **WHEN** the user performs a search, navigates away, and presses the browser back button
- **THEN** the Search tab SHALL restore the previous query, selected mode, and results
