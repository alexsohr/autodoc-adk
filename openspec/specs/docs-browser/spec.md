## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screen**: "Repo Docs Browser" (screen `bb862f40609c46518af174ce9fafb96e`) — use `mcp__stitch__get_screen` with projectId `17903516435494788863` and screenId `bb862f40609c46518af174ce9fafb96e` to fetch the design
- **Design System**: "The Digital Curator" — doc tree sidebar uses dark tonal background (`surface_container_low`), active page highlighted with `primary_fixed` background, content area uses `surface_container_lowest` for readability
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`). Use Salt DS `SplitLayout` or `BorderLayout` for the sidebar/content split, `Dropdown` for scope selector, `NavigationItem` for tree items, `Breadcrumb` for page breadcrumbs, `Badge` for quality scores, and `StackLayout` for page content arrangement. Markdown rendering uses `react-markdown` + `remark-gfm` + `react-syntax-highlighter` + `mermaid` (these are not Salt DS but are required for content rendering).
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch design listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **ScoreBadge** — for page quality score in metadata bar (scale: quality)
- **SectionErrorBoundary** — wrapping the page content area for loading/error states
- **EmptyState** — when no pages exist for the selected scope
- **formatRelativeTime** — for generation time display in metadata bar

## ADDED Requirements

### Requirement: Doc tree sidebar with scope selector
The system SHALL render a doc tree sidebar on the left side of the Docs tab. The sidebar SHALL contain a scope selector dropdown at the top that lists all available scopes for the repository. Selecting a scope SHALL load the corresponding WikiStructure tree below the dropdown.

#### Scenario: Scope selector lists available scopes
- **WHEN** the user navigates to `/repos/{id}/docs`
- **THEN** the scope selector dropdown SHALL display all scopes defined for the repository, with the first scope selected by default

#### Scenario: Switching scopes loads the corresponding tree
- **WHEN** the user selects a different scope from the scope selector dropdown
- **THEN** the doc tree SHALL update to display the WikiStructure hierarchy for the newly selected scope

### Requirement: Section tree mirroring WikiStructure hierarchy
The doc tree sidebar SHALL render the WikiStructure hierarchy as a navigable tree. Sections SHALL be displayed as uppercase headers, subsections SHALL be nested beneath their parent sections, and pages SHALL be displayed as clickable leaf nodes.

#### Scenario: Sections displayed as uppercase headers
- **WHEN** the doc tree renders a section node from the WikiStructure
- **THEN** the section name SHALL be displayed in uppercase text as a non-clickable group header

#### Scenario: Subsections nested under sections
- **WHEN** a section contains subsections in the WikiStructure hierarchy
- **THEN** the subsections SHALL be rendered as nested items beneath their parent section, visually indented to convey hierarchy

#### Scenario: Pages as clickable leaves
- **WHEN** the doc tree renders a page node
- **THEN** the page title SHALL be rendered as a clickable link that navigates to `/repos/{id}/docs/{scope}/{page_key}` and loads the page content in the content area

#### Scenario: Active page highlighted
- **WHEN** a page is currently displayed in the content area
- **THEN** the corresponding page node in the doc tree SHALL be highlighted with a distinct background color to indicate active state

### Requirement: Breadcrumb navigation
The page content area SHALL display a breadcrumb bar at the top showing the navigation path: scope, section, subsection (if applicable), and page title. Each segment of the breadcrumb SHALL be clickable.

#### Scenario: Breadcrumb reflects current page path
- **WHEN** the user views a page at `/repos/{id}/docs/{scope}/{page_key}` that belongs to section "Getting Started" and subsection "Installation"
- **THEN** the breadcrumb SHALL display "{scope} > Getting Started > Installation > {page_title}" with each segment as a clickable link

#### Scenario: Clicking a breadcrumb section
- **WHEN** the user clicks a section name in the breadcrumb
- **THEN** the doc tree sidebar SHALL scroll to and highlight that section, and the content area SHALL display the first page within that section

#### Scenario: Clicking the scope in breadcrumb
- **WHEN** the user clicks the scope segment of the breadcrumb
- **THEN** the scope selector SHALL update to that scope and the doc tree SHALL display the root of that scope's hierarchy

### Requirement: Page content display with metadata
The page content area SHALL render the page title as an h1 heading followed by a metadata bar. The metadata bar SHALL display the page's quality score, generation time, importance level, and a "View source files" link.

#### Scenario: Metadata bar displays page attributes
- **WHEN** a page with quality score 0.85, generation time "2026-03-28T14:30:00Z", and importance level "high" is loaded
- **THEN** the metadata bar SHALL display the quality score using `ScoreBadge` (e.g., "8.5/10" with color coding), the generation time using `formatRelativeTime` (e.g., "7 days ago"), the importance level as "high", and a "View source files" link

#### Scenario: View source files link
- **WHEN** the user clicks the "View source files" link in the metadata bar
- **THEN** the system SHALL display or navigate to the list of source files that contributed to generating the page

### Requirement: Full GFM markdown rendering
The page content area SHALL render page content as GitHub Flavored Markdown (GFM) with full support for standard and extended syntax elements.

#### Scenario: Headers h1 through h6
- **WHEN** the page content contains markdown headers from h1 (`#`) through h6 (`######`)
- **THEN** the renderer SHALL display each header at its corresponding heading level with appropriate font size and weight

#### Scenario: Code blocks with syntax highlighting
- **WHEN** the page content contains a fenced code block with a language identifier (e.g., ````python`)
- **THEN** the renderer SHALL display the code block with syntax highlighting appropriate for the specified language

#### Scenario: Tables rendered as structured grids
- **WHEN** the page content contains a GFM table with headers and rows
- **THEN** the renderer SHALL display the table as a structured grid with header row styling distinct from data rows

#### Scenario: Ordered and unordered lists
- **WHEN** the page content contains ordered lists (`1.`) or unordered lists (`-` / `*`)
- **THEN** the renderer SHALL display them with proper numbering or bullet markers and correct nesting indentation

#### Scenario: Inline formatting
- **WHEN** the page content contains bold (`**text**`), italic (`*text*`), or inline code (`` `code` ``) markup
- **THEN** the renderer SHALL apply the corresponding visual styling: bold weight, italic style, or monospace with background highlight

#### Scenario: Links and images
- **WHEN** the page content contains markdown links (`[text](url)`) or images (`![alt](src)`)
- **THEN** the renderer SHALL render clickable hyperlinks and inline images respectively

### Requirement: Mermaid diagram rendering
The system SHALL render fenced code blocks with the language identifier "mermaid" as interactive SVG diagrams rather than raw code text.

#### Scenario: Mermaid code block rendered as diagram
- **WHEN** the page content contains a fenced code block with language "mermaid" containing valid Mermaid syntax
- **THEN** the renderer SHALL display the block as an interactive SVG diagram, not as raw text

#### Scenario: Invalid mermaid syntax fallback
- **WHEN** the page content contains a mermaid code block with invalid syntax
- **THEN** the renderer SHALL display an error message within the diagram area indicating the syntax is invalid, and MUST NOT crash or leave a blank space

### Requirement: Prev/Next page navigation
The page content area SHALL display previous and next page navigation links in the footer for sequential reading within the current section.

#### Scenario: Next page link displayed
- **WHEN** the current page is not the last page in its section
- **THEN** the footer SHALL display a "Next" link with the title of the next page, and clicking it SHALL navigate to that page

#### Scenario: Previous page link displayed
- **WHEN** the current page is not the first page in its section
- **THEN** the footer SHALL display a "Previous" link with the title of the previous page, and clicking it SHALL navigate to that page

#### Scenario: First page in section
- **WHEN** the current page is the first page in its section
- **THEN** the footer SHALL NOT display a "Previous" link, and SHALL only display the "Next" link

#### Scenario: Last page in section
- **WHEN** the current page is the last page in its section
- **THEN** the footer SHALL NOT display a "Next" link, and SHALL only display the "Previous" link

### Requirement: Deep-linkable page URLs
The system SHALL support deep linking to individual documentation pages via the URL pattern `/repos/{id}/docs/{scope}/{page_key}`.

#### Scenario: Direct navigation to a page URL
- **WHEN** a user navigates directly to `/repos/42/docs/backend/api-authentication` via the browser URL bar or a shared link
- **THEN** the system SHALL render the Docs tab with the scope selector set to "backend", the doc tree expanded to show the "api-authentication" page highlighted, and the page content fully rendered in the content area

#### Scenario: URL updates on page navigation
- **WHEN** the user clicks a page in the doc tree sidebar
- **THEN** the browser URL SHALL update to `/repos/{id}/docs/{scope}/{page_key}` without a full page reload

### Requirement: Docs tab displays actionable empty state when no scopes exist
When the scopes API returns an empty list (no documentation generated yet), the Docs tab SHALL display a helpful empty state message guiding the user to generate documentation, instead of the generic "No documentation tree available."

#### Scenario: Scopes API returns empty list
- **WHEN** the user navigates to the Docs tab and the scopes endpoint returns an empty list
- **THEN** the Docs tab SHALL display an empty state message such as "No documentation scopes found. Run a documentation generation job to create scopes."

### Requirement: Docs tab displays error state on scopes API failure
When the scopes API call fails (network error, 500, etc.), the Docs tab SHALL display an error state with a "Retry" button.

#### Scenario: Scopes API returns error
- **WHEN** the user navigates to the Docs tab and the scopes endpoint fails
- **THEN** the Docs tab SHALL display an error message such as "Failed to load documentation scopes" and a "Retry" button
