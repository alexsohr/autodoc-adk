## Why

AutoDoc ADK has a fully functional backend (API, agents, flows, search) but no user-facing interface. Users cannot browse generated documentation, monitor job progress, inspect quality scores, or manage repositories without direct API calls. An internal enterprise dashboard is needed to make AutoDoc usable by the wider organization — developers, readers, and admins alike.

## What Changes

- **New React SPA** (`web/`) built on Salt Design System (JP Morgan's `@salt-ds` component library), bundled with Vite, deployed as a standalone container in Kubernetes
- **New API endpoints** to fill gaps between the existing REST API and dashboard requirements:
  - Repository overview aggregations (page counts, avg quality, scope summaries, recent activity)
  - Quality tab data (per-page scores, critic feedback, agent score trends, token breakdowns)
  - Admin endpoints: system health details (workers, pools), cross-repo usage/cost aggregation, MCP server status
  - Job pipeline stage progress (real-time stage tracking for running jobs)
- **New deployment artifacts**: Dockerfile for the web container, Kustomize overlay entries, Makefile targets, nginx-based static file serving with API proxy
- **CORS configuration** on the FastAPI API to allow requests from the dashboard origin

## Capabilities

### New Capabilities
- `dashboard-shell`: Global layout — top bar with context-aware search, collapsible sidebar with pinned repos, admin section, and main content area with React Router navigation
- `repo-landing`: Repository card grid landing page with status badges, metrics, filtering, pagination, and "Add Repository" flow
- `repo-workspace`: Tabbed repo workspace (Overview, Docs, Search, Jobs, Quality, Settings) with tab-level routing
- `docs-browser`: Documentation browser with scope-selectable tree sidebar, markdown rendering (GFM + mermaid + syntax highlighting), breadcrumbs, and prev/next navigation
- `search-ui`: Repo-scoped search with hybrid/semantic/text mode pills, scope filtering, scored result cards with snippet highlighting
- `jobs-ui`: Job history table with status filters, running job pipeline visualization, per-scope progress, trigger/cancel/retry actions, log viewer
- `quality-ui`: Agent score cards with trends, per-page quality table with critic feedback drill-down, token usage breakdown
- `settings-ui`: Repository settings sub-tabs (General, Branches, Webhooks, AutoDoc Config, Danger Zone) with YAML editor, validation, and save modes
- `admin-pages`: Admin-only pages — System Health, All Jobs (cross-repo), Usage & Costs, MCP Servers
- `api-dashboard-support`: New/extended API endpoints that the dashboard requires beyond existing coverage — aggregations, quality details, admin health, usage stats
- `shared-components`: Reusable component library (StatusBadge, ScoreBadge, MetricCard, PipelineVisualization, DataTable, FilterBar, ConfirmDialog, SectionErrorBoundary, EmptyState), custom Salt DS theme, shared formatting utilities, LocalStorage state persistence, and Storybook component catalog
- `web-deployment`: Dockerfile, K8s manifests, Makefile targets, and nginx config for the web container

### Modified Capabilities
- `k8s-manifests`: Add web service deployment, service, and ingress rule to existing Kustomize overlays

## Impact

- **New code**: `web/` directory (React app ~50-80 components), new API routes in `src/api/routes/`
- **Modified code**: `deployment/` (Docker, K8s, Makefile), `src/api/app.py` (CORS middleware)
- **New dependencies**: Node.js/npm for the web app build; no new Python dependencies expected (aggregation queries use existing SQLAlchemy)
- **Infrastructure**: One additional container (web) in Docker Compose and K8s; nginx serves static files and reverse-proxies `/api` to the FastAPI service
- **No breaking changes** to existing API endpoints or backend behavior
