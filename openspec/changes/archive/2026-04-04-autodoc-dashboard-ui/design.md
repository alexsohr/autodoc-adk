## Context

AutoDoc ADK has a Python backend (FastAPI REST API, Prefect flows, ADK agents) with no UI. The existing API covers CRUD for repositories, jobs, documents, and search. The deployment stack uses Docker Compose for local dev and Kustomize-based K8s overlays for production. A UX design spec (`docs/superpowers/specs/2026-03-31-dashboard-ux-design.md`) defines the full dashboard experience across 14 sections. Visual designs are in the Stitch project "Repo Landing Page" (ID: `17903516435494788863`) with 12 screens covering all major views.

The frontend will be a separate SPA served by nginx, communicating with the existing FastAPI API. The UI uses JP Morgan's Salt Design System (`@salt-ds`) for components and theming.

**Constraints:**
- Internal enterprise tool — desktop-first, no public auth/billing
- API endpoints should be minimal and multipurpose — avoid one-endpoint-per-view pattern
- The web app deploys as its own container, independent of the API
- Existing API endpoints must not break

## Goals / Non-Goals

**Goals:**
- Build a production-ready React SPA covering all UX spec sections (landing, repo workspace tabs, admin pages)
- Add the minimum set of new API endpoints needed by the dashboard
- Deploy the web app as a standalone container in Docker Compose and Kubernetes
- Use Salt DS components throughout for consistent, accessible UI

**Non-Goals:**
- Chat tab (marked "future" in UX spec) — placeholder only
- MCP Access settings sub-tab (marked "future") — placeholder only
- Real-time WebSocket updates for job progress — polling is sufficient for v1
- Mobile responsiveness — desktop-first per UX spec
- User authentication/authorization — the app runs behind SSO/VPN; role info comes from SSO headers
- Internationalization
- Dark mode — light mode only for v1; Salt DS supports dark mode via a single prop change when needed later
- User preferences sync across devices — LocalStorage is per-browser; no backend preference API in v1

## Decisions

### 1. Tech Stack: Vite + React 19 + TypeScript + Salt DS

**Choice:** Vite as bundler, React 19, TypeScript strict mode, Salt DS (`@salt-ds/core`, `@salt-ds/data-grid`, `@salt-ds/icons`, `@salt-ds/lab`).

**Why:** Vite provides fast dev server and optimized builds. Salt DS is mandated by the user and provides enterprise-grade accessible components. TypeScript catches errors at build time without needing a separate type checker in CI.

**Alternatives considered:**
- Next.js — SSR is unnecessary for an internal tool behind SSO; adds complexity
- Webpack — slower DX than Vite, no meaningful benefit here

### 2. State Management: TanStack Query + React Context

**Choice:** TanStack Query (React Query) for server state (API calls, caching, polling). React Context for lightweight client state (sidebar collapse, user role, active repo).

**Why:** TanStack Query handles caching, refetching, pagination, and polling out of the box — covers 90% of dashboard state needs. No global state library (Redux, Zustand) is needed given the read-heavy nature of the app.

**Alternatives considered:**
- Redux Toolkit + RTK Query — heavier, more boilerplate for a read-heavy dashboard
- SWR — less feature-rich than TanStack Query for pagination and polling

### 3. Routing: React Router v7

**Choice:** React Router v7 with route-based code splitting via `React.lazy()`.

**Why:** The URL structure from the UX spec maps directly to nested routes. Code splitting keeps initial bundle small — users loading the landing page don't download admin page code.

### 4. Markdown Rendering: react-markdown + remark-gfm + mermaid

**Choice:** `react-markdown` with `remark-gfm` plugin for GitHub-flavored markdown, `react-syntax-highlighter` for code blocks, `mermaid` (client-side) for diagram rendering.

**Why:** The docs tab and chat responses must render full GFM including tables, task lists, code blocks with syntax highlighting, and mermaid diagrams. This combination covers all requirements from UX spec section 14.

### 5. API Strategy: Minimal New Endpoints with Aggregation

**Choice:** Add a small set of new aggregation endpoints rather than one endpoint per dashboard view. The frontend composes multiple API calls where needed.

**New endpoints required:**
| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /repositories/{id}/overview` | Repo overview aggregation | page_count, avg_quality, scope_summaries, last_job, recent_activity |
| `GET /repositories/{id}/quality` | Quality tab data | agent_scores, page_scores (paginated), token_breakdown |
| `GET /repositories/{id}/quality/pages/{page_key}` | Critic feedback detail | per-criterion scores, feedback text, attempt history |
| `GET /admin/health` | System health | api_status, prefect_status, db_status, workers, work_pools |
| `GET /admin/usage` | Usage & costs | token_totals, cost_estimate, top_repos, usage_by_model |
| `GET /admin/mcp` | MCP server status | endpoint, tools, status, usage_stats |
| `GET /jobs/{id}/progress` | Running job pipeline stages | stages[], per_scope_progress[] |

**Existing endpoints reused as-is:**
- `GET /repositories` — landing page card grid
- `GET /repositories/{id}` — repo info panel
- `GET /jobs`, `GET /jobs/{id}`, `POST /jobs`, `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry` — jobs tab
- `GET /documents/{id}/scopes`, `GET /documents/{id}/wiki`, `GET /documents/{id}/pages/{key}` — docs tab
- `GET /documents/{id}/search` — search tab
- `GET /jobs/{id}/tasks`, `GET /jobs/{id}/logs` — job detail expansion
- `GET /health` — admin health (existing, extended by new `/admin/health`)

**Why minimal:** The user explicitly requested minimum endpoints. The overview and quality endpoints aggregate data that would otherwise require 3-5 separate calls per page load. Admin endpoints are new domains with no existing coverage.

### 6. Deployment: Nginx Static Server + API Reverse Proxy

**Choice:** Multi-stage Docker build — Node.js builds the Vite app, nginx serves static files. Nginx reverse-proxies `/api/*` requests to the FastAPI service.

```
[Browser] → [nginx :3000]
                ├── /api/* → proxy_pass → [autodoc-api:8080]
                └── /* → serve static files (index.html fallback for SPA routing)
```

**Why:** Decouples frontend deployment from backend. Nginx handles static file caching, compression, and SPA routing fallback. No CORS needed in production since both frontend and API share the same origin via the proxy.

**Dev mode:** Vite dev server on port 5173 with a proxy config pointing `/api` to `localhost:8080`. CORS middleware added to FastAPI for dev only.

**Alternatives considered:**
- Serve from FastAPI (StaticFiles) — couples frontend/backend deployments, slower static file serving
- CDN — overkill for internal tool

### 7. Project Structure: `web/` at Repository Root

**Choice:** Place the React app in `web/` at the repository root, as a standard Vite project.

```
web/
  public/
  src/
    api/              # API client, TanStack Query hooks
    components/       # Shared reusable components (StatusBadge, MetricCard, DataTable, etc.)
    features/         # Feature modules (repos, jobs, docs, search, quality, settings, admin)
    hooks/            # Custom React hooks (useLocalStorage, useAuth, etc.)
    routes/           # Route definitions and lazy-loaded page components
    theme/            # Custom Salt DS theme (autodoc-theme.css) mapping Stitch tokens
    types/            # TypeScript types matching API schemas
    utils/            # Shared utilities (formatters.ts, constants.ts)
    App.tsx
    main.tsx
  .storybook/         # Storybook configuration
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  nginx.conf
  Dockerfile
```

**Why:** Keeps frontend isolated from Python code. Standard Vite layout is familiar to any React developer. The `features/` folder groups components by domain (repo workspace tabs map to feature folders).

### 8. Job Progress Polling

**Choice:** Poll `GET /jobs/{id}/progress` every 3 seconds for running jobs using TanStack Query's `refetchInterval`. Stop polling when status leaves RUNNING.

**Why:** WebSockets add infrastructure complexity (sticky sessions, K8s ingress config) for marginal UX improvement. Polling at 3s is sufficient for showing pipeline stage transitions and per-scope progress.

### 10. Theming: Custom Salt DS Theme from Stitch Design Tokens

**Choice:** Create a single CSS custom properties file (`web/src/theme/autodoc-theme.css`) that maps the Stitch design system tokens to Salt DS CSS variables. Load via `SaltProvider` in `main.tsx`. Light mode only for v1.

**Why:** Salt DS components read from CSS custom properties (e.g., `--salt-actionable-primary-background`). By overriding these at the theme level, every Salt DS component automatically inherits the Stitch visual language — colors, typography, spacing. This is a "configure once" approach; no per-component styling needed for design system compliance.

**Key mappings from Stitch:**
- Primary: `#264dd9` → Salt DS `--salt-palette-interact-*`
- Surface hierarchy: 5-tier tonal system → Salt DS `--salt-container-*` and `--salt-palette-neutral-*`
- No 1px borders → Override Salt DS component border tokens to `none` or use tonal separation
- Glassmorphism for floating elements → Override Salt DS overlay/dialog background tokens with opacity + backdrop-blur
- Primary CTA gradient → Override Salt DS `--salt-actionable-cta-background` with linear-gradient

**Alternatives considered:**
- Per-component CSS overrides — faster to start, but creates inconsistency as components multiply; violates the design system's "configure once" principle

### 11. Error Handling: Per-Section Error Boundaries

**Choice:** Each data-fetching section on a page is wrapped in a `SectionErrorBoundary` component. Errors are isolated — if one section's API call fails, only that section shows an error panel; the rest of the page continues to function.

**Why:** The dashboard pages compose multiple independent API calls (e.g., Overview tab calls `/overview` + recent activity + last job). A global error boundary would mean a single 500 response takes down the entire page. Per-section boundaries provide graceful degradation.

**Implementation:** TanStack Query's `useQuery` returns `{ isLoading, isError, error, data }`. The `SectionErrorBoundary` wraps each section and renders:
- **Loading** → Salt DS `Skeleton` placeholder mimicking the section's layout
- **Error** → Error panel with message + "Retry" button (calls `refetch()`)
- **Success** → Normal content
- **Empty** → `EmptyState` component with contextual message + optional CTA

### 12. Persistent UI State: LocalStorage

**Choice:** User-specific UI preferences (pinned repos, sidebar collapse state) are stored in the browser's LocalStorage under a namespaced key prefix (`autodoc:`). No backend API or database table needed.

**Why:** This is an internal enterprise tool where users typically use one workstation. LocalStorage survives page refreshes and browser restarts. If the user switches browsers, they lose pins — acceptable for v1. Adding a backend user preferences API later is straightforward without breaking the LocalStorage approach.

**State stored:**
- `autodoc:pinned-repos` — array of repository UUIDs
- `autodoc:sidebar-collapsed` — boolean

**Fallback:** If LocalStorage is unavailable (private browsing, storage quota), fall back to in-memory state. The app works normally but preferences are lost on refresh.

### 13. Frontend Testing: Component Tests + Storybook

**Choice:** Vitest + Testing Library for shared component tests. Storybook for visual component catalog and manual testing.

**Why:** Shared components are the foundation — every page depends on them. Testing them ensures the reusable layer is solid. Storybook provides a visual playground for developers (and implementing agents) to see all component variants in isolation, similar to how Swagger documents API endpoints.

**What gets tested:**
- All shared components (~10 components × 2-4 test cases = ~30 tests)
- Formatting utilities (pure functions, easy to test)
- NOT page-level components (those change frequently; test via manual QA)
- NOT E2E flows (backend E2E suite already validates API behavior)

**Storybook scope:**
- One story file per shared component
- Stories cover all variants (e.g., StatusBadge: healthy, running, failed, pending, cancelled)
- Theme is loaded so components render with the actual Stitch design system

### 14. Shared Formatting Utilities

**Choice:** A single `web/src/utils/formatters.ts` module with pure functions for consistent data display: `formatRelativeTime()`, `formatScore()`, `formatTokens()`, `formatDuration()`.

**Why:** Multiple pages display the same data types (timestamps, scores, token counts, durations). Without shared formatters, each page formats independently — one shows "2 hours ago" while another shows "2h" while another shows "120 min ago." This is the frontend equivalent of Pydantic serializers: define the format once, use everywhere.

### 9. Role-Based Visibility

**Choice:** SSO proxy headers provide the user's role (Reader/Developer/Admin). The API returns user info from an auth context. The frontend conditionally renders UI elements based on role — no separate permission API needed.

**Implementation:** A `GET /auth/me` endpoint returns `{username, role, email}` derived from SSO headers. React Context stores this and components check `role` before rendering gated sections.

**New endpoint:**
| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /auth/me` | Current user info from SSO headers | username, role, email |

## Risks / Trade-offs

- **Salt DS learning curve** → Mitigated by extensive component docs (560+ code snippets in Context7). AG Grid theme available for data-heavy tables.
- **Polling vs WebSocket for job progress** → 3s polling adds ~20 req/min per active watcher. Acceptable for internal tool with <100 concurrent users. Can upgrade to WebSocket later.
- **New aggregation endpoints couple frontend needs to backend** → Mitigated by designing endpoints to return general-purpose data structures, not view-specific shapes. The overview endpoint returns building blocks (counts, scores, activity) that multiple views could use.
- **Monorepo complexity (Python + Node.js)** → Mitigated by keeping `web/` fully independent with its own package.json, Dockerfile, and build pipeline. No shared build tooling.
- **Bundle size with mermaid.js** → Mermaid is ~2MB. Mitigated by lazy-loading the mermaid renderer only when a diagram code block is encountered in the docs tab.

## Migration Plan

1. **Phase 1 — Scaffolding + Theme + Shared Components**: Set up `web/` with Vite + React + Salt DS. Create custom theme from Stitch tokens. Build shared component library (StatusBadge, MetricCard, DataTable, etc.) with Storybook stories and component tests. Deploy nginx container.
2. **Phase 2 — Core views**: Landing page, repo workspace (Overview, Docs, Search, Jobs tabs) using shared components. Add aggregation endpoints as needed.
3. **Phase 3 — Advanced views**: Quality tab, Settings tab, Admin pages. Add quality and admin API endpoints.
4. **Phase 4 — Polish**: Per-section error boundaries, loading skeletons, empty states, keyboard navigation, responsive sidebar collapse, LocalStorage persistence for pins/sidebar.

**Rollback:** The web container is independent. Removing it from K8s has zero impact on backend services.

## Open Questions

- **SSO header format**: What exact headers does the SSO proxy set? Need to confirm header names for username, email, and role extraction.
- **AG Grid license**: Salt DS provides an AG Grid theme but AG Grid Enterprise features (server-side row model) require a license. Confirm if we have one, or stick to AG Grid Community.
