# Admin Pages Specification

**Routes:** `/admin/*`
**Visibility:** Admin role only (via sidebar navigation)
**Change:** autodoc-dashboard-ui

## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screens**:
  - "System Health" (screen `1c8ab415deb747cd8ffe3ccff8cf1710`) — status cards, work pools table
  - "All Jobs" (screen `3dda03a8d61c45c39932ad7867bbd161`) — cross-repo job table, filters
  - "Usage & Costs" (screen `6ddc7ded1727449ea7a7df3ebf492dc3`) — metric cards, bar charts, time range selector
  - "MCP Servers - Integration Guide" (screen `4189728933ed463f8b6109609729bd70`) — server status, usage stats, integration guide
- **Design System**: "The Digital Curator" — status cards use tonal layering with functional color tokens for health indicators, tables use `surface_container_lowest` rows on `surface_container_low` background (no row borders), bar charts use `primary` and `secondary` palette
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`, `@salt-ds/data-grid`). Use Salt DS `Card` for status/metric cards, Salt DS data grid for job and work pool tables, `StatusIndicator` for health badges, `Badge`/`Pill` for status indicators, `ToggleButtonGroup` for filter pills, `Dropdown` for time range selector, `Button` for CSV export, `GridLayout`/`StackLayout` for arrangement.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes. Use only the Stitch designs listed above.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **MetricCard** — for System Health status cards (4) and Usage & Costs metric cards (3)
- **StatusBadge** — for health status indicators and MCP server status
- **DataTable** — for Work Pools table and All Jobs cross-repo table
- **FilterBar** — for All Jobs status filter pills with counts
- **SectionErrorBoundary** — wrapping each admin page section
- **formatTokens**, **formatRelativeTime**, **formatDuration** — from shared formatting utilities

**Status:** Draft
**Date:** 2026-04-04

---

## ADDED Requirements

### Requirement: Admin Sidebar Navigation

The Admin sidebar section is defined in `dashboard-shell/spec.md` (Requirement: Collapsible left sidebar, scenarios for Admin section visibility). This spec does not redefine sidebar behavior — it defines the content of admin pages that the sidebar links to.

#### Scenario: Admin routes are guarded
- **WHEN** a non-Admin user navigates directly to any `/admin/*` route
- **THEN** the system SHALL redirect to `/` or display an access-denied message

---

### Requirement: System Health Page

The System Health page (`/admin/health`) SHALL display four status cards and a Work Pools Table.

The four status cards SHALL be:

1. **API:** health status, uptime duration, and average latency
2. **Prefect Server:** health status and work pool count
3. **Database:** health status, PostgreSQL version, pgvector extension status, and storage usage
4. **Workers:** health status and capacity utilization

The Work Pools Table SHALL display columns for: pool name, type (K8s or Process), active jobs / concurrency limit, queued jobs count, and status (Healthy, Near Capacity, Down, or Idle).

#### Scenario: Status cards display current system state

WHEN an Admin navigates to `/admin/health`
THEN the system SHALL display four status cards reflecting the current health and metrics of the API, Prefect Server, Database, and Workers subsystems.

#### Scenario: API status card content

WHEN the API status card is displayed
THEN it SHALL show the API health status (healthy or unhealthy), the uptime duration since last restart, and the average response latency.

#### Scenario: Prefect Server status card content

WHEN the Prefect Server status card is displayed
THEN it SHALL show the Prefect Server health status and the total number of configured work pools.

#### Scenario: Database status card content

WHEN the Database status card is displayed
THEN it SHALL show the database health status, the PostgreSQL version (MUST be 18+), whether the pgvector extension is installed, and current storage usage.

#### Scenario: Workers status card content

WHEN the Workers status card is displayed
THEN it SHALL show the overall worker health status and the aggregate capacity utilization across all work pools.

#### Scenario: Work Pools Table displays all pools

WHEN the System Health page is displayed
THEN the Work Pools Table SHALL list all configured work pools with columns for pool name, type, active/limit ratio, queued count, and status.

#### Scenario: Work pool status values

WHEN a work pool row is displayed
THEN the status column SHALL show one of: "Healthy" (active < 80% of limit), "Near Capacity" (active >= 80% of limit), "Down" (no heartbeat from workers), or "Idle" (zero active and zero queued jobs).

### Requirement: Worker Capacity Visualization
The System Health page SHALL display a "Worker Capacity" section showing resource utilization trends.

#### Scenario: Capacity metrics displayed
- **WHEN** the System Health page is displayed
- **THEN** it SHALL show: current peak utilization percentage with trend indicator (↑/↓), and average queue wait time in seconds

#### Scenario: Utilization trend chart
- **WHEN** the Worker Capacity section is displayed
- **THEN** it SHALL render a utilization trend visualization for the last 24 hours

### Requirement: Auto-Scale Status
The System Health page SHALL display a "Scale On-Demand" section describing the current auto-scaling configuration.

#### Scenario: Auto-scale status displayed
- **WHEN** the System Health page is displayed and auto-scaling is configured
- **THEN** it SHALL show the auto-scaling rules (e.g., "spin up N additional nodes if queue exceeds X tasks for Y minutes"), with "Configure Auto-Scale" and "View Logs" action links

### Requirement: System Health Footer Stats
The System Health page SHALL display footer status indicators showing last sync time, encryption status, throughput, and history retention period.

#### Scenario: Footer stats displayed
- **WHEN** the System Health page is displayed
- **THEN** it SHALL show: last data sync time (using `formatRelativeTime`), encryption protocol status (e.g., "TLS 1.3 Active"), current throughput, and log/metric history retention period

---

### Requirement: All Jobs Page

The All Jobs page (`/admin/jobs`) SHALL display a cross-repository job table with filtering, expandable rows, and pagination.

The page SHALL display status filter pills at the top, each showing the count of jobs in that status. The page SHALL support filtering by repository, branch, and status.

The table columns SHALL be: repository name (clickable, navigating to the repository workspace), mode (full or incremental), branch, status, current stage, duration, and started timestamp.

Rows SHALL be expandable to reveal additional job details. The table SHALL be paginated.

#### Scenario: Job table displays jobs across all repositories

WHEN an Admin navigates to `/admin/jobs`
THEN the system SHALL display a table containing jobs from all registered repositories, not limited to a single repository.

#### Scenario: Status filter pills with counts

WHEN the All Jobs page is displayed
THEN status filter pills SHALL appear above the table, one per status value (e.g., Pending, Running, Completed, Failed), each displaying the count of jobs in that status.

#### Scenario: Filtering by status pill

WHEN an Admin clicks a status filter pill
THEN the table SHALL filter to show only jobs matching the selected status.

#### Scenario: Filtering by repository

WHEN an Admin selects a repository from the repository filter
THEN the table SHALL display only jobs belonging to that repository.

#### Scenario: Filtering by branch

WHEN an Admin selects a branch from the branch filter
THEN the table SHALL display only jobs targeting that branch.

#### Scenario: Repository name navigates to workspace

WHEN an Admin clicks a repository name in the table
THEN the system SHALL navigate to the corresponding repository workspace.

#### Scenario: Expandable rows reveal job details

WHEN an Admin expands a job row
THEN the system SHALL display additional details about the job, including task-level progress, error messages (if any), and agent scores (if available).

#### Scenario: Pagination

WHEN the number of jobs exceeds the page size
THEN the table SHALL display pagination controls allowing navigation between pages of results.

---

### Requirement: Usage and Costs Page

The Usage & Costs page (`/admin/usage`) SHALL display three metric cards, two horizontal bar charts, a time range selector, and a CSV export button.

The three metric cards SHALL show: total tokens consumed this month, estimated cost this month, and total jobs executed this month.

The page SHALL include a "Top Repositories by Token Usage" horizontal bar chart ranking repositories by token consumption, and a "Usage by Model" horizontal bar chart showing token consumption broken down by LLM model.

The time range selector SHALL allow filtering all displayed metrics and charts to a specific period. A CSV export button SHALL export the currently displayed data.

#### Scenario: Metric cards display current month totals

WHEN an Admin navigates to `/admin/usage`
THEN the system SHALL display three metric cards showing total tokens this month, estimated cost this month, and total jobs this month.

#### Scenario: Top repositories bar chart

WHEN the Usage & Costs page is displayed
THEN the system SHALL render a horizontal bar chart ranking repositories by total token usage within the selected time range, ordered from highest to lowest.

#### Scenario: Usage by model bar chart

WHEN the Usage & Costs page is displayed
THEN the system SHALL render a horizontal bar chart showing token consumption grouped by LLM model (e.g., gemini-2.5-flash, text-embedding-3-large) within the selected time range.

#### Scenario: Time range selector filters data

WHEN an Admin selects a different time range (e.g., last 7 days, last 30 days, custom range)
THEN all metric cards and bar charts SHALL update to reflect data within the selected time range.

#### Scenario: CSV export

WHEN an Admin clicks the CSV export button
THEN the system SHALL generate and download a CSV file containing the token usage, cost, and job data for the currently selected time range.

### Requirement: Daily Burn Rate
The Usage & Costs page SHALL display a daily burn rate below the estimated cost metric card.

#### Scenario: Burn rate displayed
- **WHEN** the estimated cost metric card is displayed
- **THEN** it SHALL include a secondary line showing the current daily burn rate (e.g., "$4.60/day") calculated from the selected time period

### Requirement: Job Success Rate
The Usage & Costs page SHALL display the job success rate alongside the total jobs metric.

#### Scenario: Success rate displayed
- **WHEN** the total jobs metric card is displayed
- **THEN** it SHALL include a secondary indicator showing the success rate percentage (e.g., "98% ✓") calculated as completed / (completed + failed) jobs

### Requirement: Cost Efficiency Recommendations
The Usage & Costs page SHALL display an AI-generated "Cost Efficiency Tip" section with actionable optimization suggestions.

#### Scenario: Efficiency tip displayed
- **WHEN** the Usage & Costs page is displayed and optimization opportunities exist
- **THEN** it SHALL display a tip card suggesting model optimization (e.g., "Switching non-critical jobs to Flash could save $X/mo") with an "Optimize Settings" action link

### Requirement: Recent Cost Centers Table
The Usage & Costs page SHALL display a "Recent Cost Centers" table showing individual high-cost operations.

#### Scenario: Cost centers table displayed
- **WHEN** the Usage & Costs page is displayed
- **THEN** it SHALL display a table with columns: transaction ID, service/action description (with token count), status (Settled/Processing), and amount (USD). The table SHALL be paginated with a "Full History" link.

---

### Requirement: MCP Servers Page

The MCP Servers page (`/admin/mcp`) SHALL display a server status card and a usage statistics card.

The server status card SHALL show: the MCP endpoint URL, the list of available tools, and the server's running state (Running or Stopped).

The usage statistics card SHALL show: total requests in the last 30 days, count of unique agents that have called the server, and the success rate (percentage of requests returning a successful response).

#### Scenario: Server status card displays configuration

WHEN an Admin navigates to `/admin/mcp`
THEN the server status card SHALL display the MCP endpoint URL, the list of registered tools, and whether the server is currently Running or Stopped.

#### Scenario: Server running state indicator

WHEN the MCP server is reachable and responding to health checks
THEN the running state SHALL display "Running" with a green indicator.

WHEN the MCP server is not reachable
THEN the running state SHALL display "Stopped" with a red indicator.

#### Scenario: Usage statistics card displays 30-day metrics

WHEN the MCP Servers page is displayed
THEN the usage statistics card SHALL show the total number of MCP requests in the last 30 days, the count of distinct agents that issued requests, and the success rate as a percentage.

#### Scenario: Available tools list

WHEN the server status card is displayed and the MCP server is running
THEN the available tools list SHALL enumerate all tools registered with the FastMCP server, reflecting the current deployment configuration.

### Requirement: MCP Integration Guide
The MCP Servers page SHALL include an "Agent Integration Guide" section below the server status and usage cards. The guide SHALL provide ready-to-copy code snippets for connecting AI tools to the AutoDoc MCP server.

#### Scenario: Integration guide displays code snippets
- **WHEN** the MCP Servers page is displayed
- **THEN** it SHALL render code snippet blocks for at least three integration targets: VS Code / GitHub Copilot (mcpServers JSON config), Claude Code (CLI command), and a generic MCP client (JSON config). Each snippet SHALL include a copy-to-clipboard button.

#### Scenario: Snippets use actual server endpoint
- **WHEN** the integration guide renders code snippets
- **THEN** the snippets SHALL use the actual MCP server endpoint URL from the server status card, not hardcoded placeholder values

### Requirement: MCP Security Context
The MCP Servers page SHALL display a "Security Context" panel showing authentication method, last credential rotation time, and IP restriction status.

#### Scenario: Security context displayed
- **WHEN** the MCP Servers page is displayed
- **THEN** it SHALL show the authentication method (e.g., mTLS / Bearer), the time since the last credential rotation (using `formatRelativeTime`), and whether IP restriction is enabled or disabled

### Requirement: MCP Real-time Telemetry
The MCP Servers page SHALL display a "Real-time Telemetry" panel showing average latency, peak load, and memory usage.

#### Scenario: Telemetry metrics displayed
- **WHEN** the MCP Servers page is displayed
- **THEN** it SHALL show average response latency (ms), peak request load (rps), and current memory usage (GB) for the MCP server
