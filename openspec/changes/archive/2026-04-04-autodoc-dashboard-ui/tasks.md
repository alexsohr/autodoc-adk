## 1. Project Scaffolding

- [x] 1.1 Initialize Vite + React + TypeScript project in `web/` with `npm create vite@latest`; configure `tsconfig.json` with strict mode
- [x] 1.2 Install core dependencies: `@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`, `@salt-ds/theme`, `react-router`, `@tanstack/react-query`
- [x] 1.3 Install rendering dependencies: `react-markdown`, `remark-gfm`, `react-syntax-highlighter`, `mermaid`
- [x] 1.4 Install dev/testing dependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@storybook/react-vite`, `jsdom`
- [x] 1.5 Configure Vite: dev server proxy (`/api` → `localhost:8080`), build output, path aliases (`@/` → `src/`)
- [x] 1.6 Set up SaltProvider in `main.tsx` with custom theme CSS import; verify Salt DS renders correctly with a test component
- [x] 1.7 Set up TanStack QueryClientProvider in `main.tsx` with default stale time and retry config

## 2. Custom Theme & Design Tokens

- [x] 2.1 Create `web/src/theme/autodoc-theme.css` mapping Stitch design tokens to Salt DS CSS custom properties: primary (#264dd9), surface hierarchy (5-tier tonal system), success (#2e7d32), warning (#e65100), error (#c62828)
- [x] 2.2 Override Salt DS border tokens to enforce the "no 1px borders" rule — sections use tonal layering via background color shifts
- [x] 2.3 Override Salt DS overlay/dialog tokens to apply glassmorphism (85% opacity + 20px backdrop-blur) on floating elements
- [x] 2.4 Override Salt DS primary CTA button to use the signature gradient (135°, #264dd9 → #4568f3) instead of flat color
- [x] 2.5 Configure `SaltProvider` in `main.tsx` to load the custom theme with `mode="light"` (dark mode explicitly out of scope)
- [x] 2.6 Verify theme renders correctly by creating a test page with Card, Button, Badge, Input, Dialog samples

## 3. Shared Formatting Utilities

- [x] 3.1 Create `web/src/utils/formatters.ts` with pure functions: `formatRelativeTime(timestamp)`, `formatScore(score)`, `formatTokens(count)`, `formatDuration(seconds)`
- [x] 3.2 Write Vitest unit tests for all formatter functions covering edge cases (zero, null, very large numbers, future timestamps)

## 4. Shared Reusable Components

- [x] 4.1 Build `StatusBadge` component: accepts entity status string, renders color-coded pill (Healthy/green, Running/orange, Failed/red, Pending/purple, Cancelled/gray). Wraps Salt DS `Pill` or `Badge`.
- [x] 4.2 Build `ScoreBadge` component: accepts numeric score, renders color-coded badge (green ≥8.0, orange 7.0–7.9, red <7.0) displaying "X.Y/10" using `formatScore()`
- [x] 4.3 Build `MetricCard` component: accepts label, value, optional delta (with direction ↑/↓ and color), optional subtitle. Wraps Salt DS `Card`.
- [x] 4.4 Build `PipelineVisualization` component: accepts array of stage objects (name, status, duration), renders horizontal pipeline (Clone→Discover→Structure→Pages→README→PR) with green/blue/gray stage states and animation on active stage
- [x] 4.5 Build `DataTable` component: wraps Salt DS data grid with consistent styling, sortable columns, row expansion support, and integrated `Pagination` footer showing "Showing X–Y of Z"
- [x] 4.6 Build `FilterBar` component: accepts filter options (with optional counts), renders Salt DS `ToggleButtonGroup` pills; fires onChange callback with selected value
- [x] 4.7 Build `ConfirmDialog` component: wraps Salt DS `Dialog` for destructive actions; accepts title, message, confirmLabel; confirm button disabled for 2s to prevent accidental double-clicks
- [x] 4.8 Build `SectionErrorBoundary` component: wraps a section and renders Salt DS `Skeleton` during loading, error panel with "Retry" button on failure, `EmptyState` when data is empty, or normal content on success. Integrates with TanStack Query's `{ isLoading, isError, data }` pattern.
- [x] 4.9 Build `EmptyState` component: accepts icon, message, and optional action (label + onClick); renders centered empty state with friendly message and optional CTA button
- [x] 4.10 Write Vitest + Testing Library tests for all shared components (~3 test cases each, ~30 tests total)

## 5. Storybook Setup

- [x] 5.1 Initialize Storybook for Vite + React in `web/.storybook/`; configure to load the custom Salt DS theme
- [x] 5.2 Create story files for all shared components: `StatusBadge.stories.tsx`, `ScoreBadge.stories.tsx`, `MetricCard.stories.tsx`, `PipelineVisualization.stories.tsx`, `DataTable.stories.tsx`, `FilterBar.stories.tsx`, `ConfirmDialog.stories.tsx`, `SectionErrorBoundary.stories.tsx`, `EmptyState.stories.tsx` — each showing all variants and states

## 6. LocalStorage State Persistence

- [x] 6.1 Create `useLocalStorage` hook in `web/src/hooks/useLocalStorage.ts`: generic typed hook that reads/writes to LocalStorage with `autodoc:` key prefix; falls back to in-memory state if LocalStorage is unavailable
- [x] 6.2 Create `usePinnedRepos` hook: uses `useLocalStorage('pinned-repos')` to manage array of pinned repo UUIDs; exposes `pinRepo(id)`, `unpinRepo(id)`, `isPinned(id)`, `pinnedRepoIds`
- [x] 6.3 Create `useSidebarState` hook: uses `useLocalStorage('sidebar-collapsed')` to persist sidebar collapsed/expanded boolean

## 7. API Client & TypeScript Types

- [x] 7.1 Create TypeScript types in `web/src/types/` matching all API response schemas: Repository, Job, WikiStructure, WikiPage, SearchResult, Scope, etc.
- [x] 7.2 Create API client module (`web/src/api/client.ts`) with base fetch wrapper (handles JSON, errors, auth headers)
- [x] 7.3 Create TanStack Query hooks for existing endpoints: `useRepositories`, `useRepository`, `useJobs`, `useJob`, `useJobTasks`, `useJobLogs`, `useScopes`, `useWikiStructure`, `useWikiPage`, `useSearch`
- [x] 7.4 Create TanStack Query mutation hooks: `useCreateRepository`, `useUpdateRepository`, `useDeleteRepository`, `useCreateJob`, `useCancelJob`, `useRetryJob`
- [x] 7.5 Create TanStack Query hooks for new endpoints: `useRepoOverview`, `useRepoQuality`, `usePageQuality`, `useJobProgress`, `useAdminHealth`, `useAdminUsage`, `useAdminMcp`, `useAuthMe`, `useRepoSchedule`, `useUpdateSchedule`, `useCommitConfig`

## 8. Dashboard Shell & Routing

- [x] 8.1 Create React Router v7 route definitions with lazy-loaded page components; implement URL structure from UX spec (`/`, `/repos/:id/*`, `/admin/*`)
- [x] 8.2 Build `AppLayout` component: three-zone layout (top bar, sidebar, main content) using Salt DS `BorderLayout`
- [x] 8.3 Build `TopBar` component: logo (links to `/`), global job status badge (using `StatusBadge`), notifications area placeholder, user menu with role display
- [x] 8.4 Build `Sidebar` component: dark theme, "Repositories" nav item, pinned repos section (using `usePinnedRepos`), admin section (role-gated), collapse to icon-only mode (using `useSidebarState`)
- [x] 8.5 Build `ContextSearch` component: adapts placeholder and behavior based on current route (repo list → repo name search, inside repo → doc search, admin → global search); `⌘K` keyboard shortcut to focus
- [x] 8.6 Create auth context: `useAuthMe` hook populates `AuthContext` with username, role, email; role-based conditional rendering helper

## 9. Backend: New API Endpoints

- [x] 9.1 Add `GET /auth/me` endpoint: extract username, email, role from SSO proxy headers (X-Forwarded-User, X-Forwarded-Email, X-Forwarded-Role); return JSON with defaults for dev mode
- [x] 9.2 Add `GET /repositories/{id}/overview` endpoint: aggregate page count, avg quality score, scope summaries, last job, recent activity (last 20 events from job history)
- [x] 9.3 Add `GET /repositories/{id}/quality` endpoint: agent scores (current + previous + trend for last 5 runs), paginated page scores (page_key, title, scope, score, attempts, tokens), token breakdown per agent
- [x] 9.4 Add `GET /repositories/{id}/quality/pages/{page_key}` endpoint: per-criterion scores, critic feedback text, attempt history
- [x] 9.5 Add `GET /jobs/{id}/progress` endpoint: pipeline stages with status/timing, per-scope progress (pages_completed/total)
- [x] 9.6 Add `GET /admin/health` endpoint: API uptime/latency, Prefect server status + pool count, database version/pgvector/storage, worker pool details
- [x] 9.7 Add `GET /admin/usage` endpoint: token totals, cost estimate, job count, top repos by tokens, usage by model; query params for time range (this_month, last_30d, last_90d, custom)
- [x] 9.8 Add `GET /admin/mcp` endpoint: MCP server endpoint URL, tools list, running/stopped status, usage stats (requests, agents, success rate)
- [x] 9.9 Add `PATCH /repositories/{id}/schedule` endpoint: create/update auto-generation schedule (enabled, mode, frequency, day_of_week); creates/updates corresponding Prefect deployment schedule
- [x] 9.10 Add `GET /repositories/{id}/schedule` endpoint: return current schedule config
- [x] 9.11 Add `POST /repositories/{id}/config` endpoint: accept scope_path + yaml_content, create PR in source repo with updated .autodoc.yaml via Git provider
- [x] 9.12 Add CORS middleware to FastAPI `create_app()` for development mode (allow localhost:5173 origin)
- [x] 9.13 Add Pydantic schemas for all new endpoint responses in `src/api/schemas/`

## 10. Repository Landing Page

- [x] 10.1 Build `RepoListPage` component: page header with title + count, `FilterBar` for status filter, text input for name search, "+ Add Repo" button
- [x] 10.2 Build `RepoCard` component: repo name + `StatusBadge`, description, `MetricCard`-style metrics (page count, avg quality, last generated using `formatRelativeTime`), tags (language, scope count, provider)
- [x] 10.3 Build running card variant: inline progress bar with stage info (e.g., "Generating pages 3/5 scopes")
- [x] 10.4 Build failed card variant: inline error snippet (error type + message truncated)
- [x] 10.5 Build `AddRepoCard` (dashed border) and `AddRepoDialog` (using `ConfirmDialog` pattern): form with URL, provider selector, branch mappings, access token; validation and submission via `useCreateRepository` mutation
- [x] 10.6 Implement card grid layout using Salt DS `GridLayout`; responsive columns (3→2→1)
- [x] 10.7 Implement client-side filtering (name/description text, status dropdown) and cursor-based pagination with "Showing X-Y of Z"
- [x] 10.8 Wrap the page in `SectionErrorBoundary` for error/loading/empty states

## 11. Repo Workspace Shell

- [x] 11.1 Build `RepoWorkspace` layout component: fetch repo data via `useRepository`, tab bar using Salt DS `Tabs`/`TabBar`, routed tab content area
- [x] 11.2 Implement tab-route mapping: Overview (`/repos/:id`), Docs (`docs`), Search (`search`), Chat (`chat`), Jobs (`jobs`), Quality (`quality`), Settings (`settings`)
- [x] 11.3 Implement role-based tab visibility: Quality + Settings visible only to Developer/Admin; Chat shows "(Coming Soon)" badge
- [x] 11.4 Add repo context provider: shares repo data, branch, and active scope across all tabs

## 12. Overview Tab

- [x] 12.1 Build `OverviewTab` component using `useRepoOverview` hook; 4 `MetricCard` components in top row (Doc Pages, Avg Quality, Scopes, Last Generated) with deltas
- [x] 12.2 Build `LatestJobCard`: `StatusBadge`, mode, branch, commit, `PipelineVisualization`, trigger buttons ("Run Full Generation" primary, "Incremental Update" secondary), token usage, PR link
- [x] 12.3 Build `ScopeBreakdownTable` using `DataTable`: columns (scope path, page count, avg quality with `ScoreBadge`, structure summary, status)
- [x] 12.4 Build `RepoInfoPanel`: provider, branches, webhook status, job count, external link
- [x] 12.5 Build `ActivityTimeline`: color-coded event list (green completions, blue updates, red failures), each entry with description + `formatRelativeTime` + detail
- [x] 12.6 Wrap each section in `SectionErrorBoundary` for independent error/loading/empty handling

## 13. Docs Browser Tab

- [x] 13.1 Build `DocsTab` layout: split view with doc tree sidebar (left) and page content area (right)
- [x] 13.2 Build `ScopeSelector`: dropdown at top of tree sidebar to switch between scopes via `useScopes`
- [x] 13.3 Build `DocTree` component: recursive tree rendering of WikiStructure hierarchy (sections → subsections → pages), active page highlighted; fetch structure via `useWikiStructure`
- [x] 13.4 Build `DocBreadcrumb`: scope › section › subsection › page with each segment clickable
- [x] 13.5 Build `PageContent` component: page title + metadata bar (`ScoreBadge`, `formatRelativeTime`, importance, "View source files" link), fetch content via `useWikiPage`
- [x] 13.6 Build `MarkdownRenderer` component: react-markdown with remark-gfm, custom renderers for code blocks (react-syntax-highlighter), tables, and mermaid diagrams (lazy-loaded mermaid.js rendering fenced code blocks with language "mermaid" as SVG)
- [x] 13.7 Build prev/next page footer navigation: determine adjacent pages from tree structure, render as links

## 14. Search Tab

- [x] 14.1 Build `SearchTab` component: search input with button, `FilterBar` with search mode pills (Hybrid/Semantic/Text), scope filter dropdown
- [x] 14.2 Implement search execution: call `useSearch` hook with query, type, scope params; show result count + timing header
- [x] 14.3 Build `SearchResultCard`: page title (links to Docs tab), breadcrumb path, `ScoreBadge` for relevance (green ≥0.8, orange 0.6-0.8, gray <0.6), snippet with `<mark>` highlighting, chunk source + importance
- [x] 14.4 Implement score-based opacity on result cards and "Load more" button for pagination
- [x] 14.5 Sync search query and type to URL query params for deep linking

## 15. Jobs Tab

- [x] 15.1 Build `JobsTab` component: header with `FilterBar` (status pills with counts), trigger buttons with dry run toggle (role-gated to Developer/Admin)
- [x] 15.2 Build `RunningJobCard`: expanded view with blue border, `PipelineVisualization` (stages with green/blue/gray states + animation on active), per-scope progress bars, cancel button (using `ConfirmDialog`)
- [x] 15.3 Implement job progress polling: `useJobProgress` with 3-second `refetchInterval` while status is RUNNING, stop when terminal
- [x] 15.4 Build `CompletedJobRow` using `DataTable` row: `StatusBadge`, mode, branch, commit, pages, `ScoreBadge`, `formatTokens`, `formatDuration`, PR link; expandable to full `PipelineVisualization`
- [x] 15.5 Build `FailedJobRow`: collapsed + red error box (monospace), error type + detail, "Retry" link
- [x] 15.6 Build `CancelledJobRow`: dimmed row with cancelled-at stage info
- [x] 15.7 Build `JobDetailView` for `/repos/:id/jobs/:jobId`: full `PipelineVisualization`, log viewer (fetch via `useJobLogs`, displayed in scrollable monospace panel), task states table
- [x] 15.8 Implement job list pagination ("Showing 1-5 of 47")

## 16. Quality Tab

- [x] 16.1 Build `QualityTab` component (Developer/Admin only): fetch data via `useRepoQuality`, wrap sections in `SectionErrorBoundary`
- [x] 16.2 Build `AgentScoreCards` (3 columns): one per agent, large current score, delta (↑/↓ colored) using `MetricCard`, sparkline/mini bar chart for last 5 runs
- [x] 16.3 Build `PageQualityTable` using `DataTable`: filters (run selector, scope selector), columns (page name linked to Docs, scope, `ScoreBadge`, attempt count, `formatTokens`), sortable, paginated
- [x] 16.4 Build `CriticFeedbackPanel`: expandable on page selection from table; per-criterion progress bars (accuracy, completeness, clarity, structure), critic feedback text, attempt history; fetch via `usePageQuality`
- [x] 16.5 Build `TokenUsageBreakdown`: per-agent horizontal bars with proportional widths, total

## 17. Settings Tab

- [x] 17.1 Build `SettingsTab` layout (Developer/Admin only): sub-tab navigation (General, Branches, Webhooks, AutoDoc Config, Danger Zone)
- [x] 17.2 Build `GeneralSettings`: read-only repo URL + provider, masked access token with Update, editable description, auto-generation schedule (toggle, mode, frequency, day selector, "Next run" preview), pin to sidebar toggle (using `usePinnedRepos`)
- [x] 17.3 Build `BranchSettings` using `DataTable`: branch mappings table with add/remove/edit rows, public branch input
- [x] 17.4 Build `WebhookSettings`: webhook URL + secret (copy buttons), event filter selector, `StatusBadge` indicator, recent deliveries log using `DataTable`
- [x] 17.5 Build `AutoDocConfigEditor`: config source indicator, multi-scope tabs, syntax-highlighted YAML editor (CodeMirror or Monaco), default config display with annotations, Validate button with inline errors, Save options ("Commit to repo" / "Save as override"), diff view
- [x] 17.6 Build `DangerZone`: red-bordered section, "Delete all docs" and "Unregister repo" buttons using `ConfirmDialog`

## 18. Admin Pages

- [x] 18.1 Build `AdminLayout`: admin-specific sidebar highlighting, route guard (Admin role only, redirect others)
- [x] 18.2 Build `SystemHealthPage` (`/admin/health`): 4 `MetricCard` components (API, Prefect, Database, Workers), Work Pools `DataTable` (name, type, active/limit, queued, `StatusBadge`), Worker Capacity section (peak utilization %, avg wait time, 24h trend chart), Auto-Scale Status section (scaling rules, configure/logs links), footer stats (sync time, encryption, throughput, retention); fetch via `useAdminHealth`; wrap in `SectionErrorBoundary`
- [x] 18.3 Build `AllJobsPage` (`/admin/jobs`): cross-repo `DataTable` with `FilterBar` (status pills + counts), search/filter input, columns (repository clickable, mode, branch, `StatusBadge`, stage, `formatDuration`, `formatRelativeTime`), expandable rows, paginated
- [x] 18.4 Build `UsageCostsPage` (`/admin/usage`): 3 `MetricCard` components (tokens with `formatTokens`, estimated cost with daily burn rate, total jobs with success rate %), horizontal bar charts for top repos + usage by model, "Cost Efficiency Tip" card with optimization suggestion, "Recent Cost Centers" `DataTable` (transaction ID, service/action, status, amount), time range selector, CSV export button; fetch via `useAdminUsage`
- [x] 18.5 Build `McpServersPage` (`/admin/mcp`): server status card (endpoint, tools, `StatusBadge`), usage stats card (requests, agents, success rate), "Agent Integration Guide" section with copy-to-clipboard code snippets for VS Code/Copilot, Claude Code, and generic MCP client (snippets use actual endpoint URL from status card), "Security Context" panel (auth method, last rotation, IP restriction), "Real-time Telemetry" panel (avg latency, peak load, memory); fetch via `useAdminMcp`

## 19. Deployment

- [x] 19.1 Create `web/Dockerfile`: multi-stage build (Node.js builder with `npm ci && npm run build`, nginx runtime copying dist + nginx.conf), non-root user, EXPOSE 3000, HEALTHCHECK
- [x] 19.2 Create `web/nginx.conf`: serve static files, SPA fallback (`try_files $uri /index.html`), reverse proxy `/api/*` to `autodoc-api:8080`, gzip, cache-control for hashed assets
- [x] 19.3 Rename `api` service to `autodoc-api` in `deployment/docker-compose.yml` for consistency with K8s naming; add `web` service (build from `../web`, port 3000, depends_on autodoc-api)
- [x] 19.4 Add Makefile targets: `web-dev` (cd ../web && npm run dev), `web-build` (cd ../web && npm run build), `web-docker` (docker build), `web-storybook` (cd ../web && npm run storybook), `web-test` (cd ../web && npm test)
- [x] 19.5 Add K8s manifests: Deployment (autodoc-web with `app.kubernetes.io/part-of: autodoc` + `app.kubernetes.io/component: web` labels, replicas 1/2, port 3000, probes matching existing timing patterns), Service (ClusterIP:3000), extend `autodoc-config` ConfigMap with `WEB_API_URL`, update Ingress with web routing
- [x] 19.6 Add Kustomize overlay patches: dev-k8s (1 replica, local image) and prod (2 replicas, registry image)

## 20. Polish & Integration

- [x] 20.1 Verify all page sections use `SectionErrorBoundary` for per-section loading skeletons, error panels with retry, and empty states
- [x] 20.2 Add `EmptyState` instances with contextual messages: "No repositories yet" + Add button, "No jobs yet" + Run Generation button, "No search results" + try different query, "No docs generated" + trigger generation, "No quality data" + run a job first
- [x] 20.3 Implement keyboard navigation: `⌘K` for search focus, tab navigation, escape to close dialogs
- [x] 20.4 Add page titles and document head management for each route (e.g., "Overview - repo-name - AutoDoc")
