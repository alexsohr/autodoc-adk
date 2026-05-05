# Source UI doc:    docs/ui/05-admin-health-and-jobs.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/admin/{HealthPage,AllJobsPage}.ts,
#                   web/tests/e2e/pages/Sidebar.ts
# Migration: replaces specs/05-admin-health-and-jobs.spec.ts (deleted in this PR).

@area-admin-health-and-jobs
Feature: Admin — System Health & All Jobs
  As a developer or admin user with access to the admin sidebar
  I can monitor infrastructure health, browse the cross-repository job
  history, and navigate between admin pages via the sidebar.

  @smoke @admin @as-developer
  Scenario: PTS-3.1 — System Health full page
    When I open the System Health page
    Then the System Health heading is visible
    And the System Health subtitle is visible
    And the System Health service card "API Cluster" is visible with a status badge
    And the System Health service card "Prefect Server" is visible with a status badge
    And the System Health service card "PostgreSQL" is visible with a status badge
    And the System Health service card "Active Workers" is visible with a status badge
    And the Work Pools table is visible
    And the Work Pools table column header "Pool Name" is visible
    And the Work Pools table column header "Type" is visible
    And the Work Pools table column header "Concurrency Limit" is visible
    And the Work Pools table column header "Status" is visible
    And the Worker Capacity section is visible
    And the Worker Capacity Current Peak stat is visible
    And the Worker Capacity Avg Wait stat is visible
    And the Scale On-Demand CTA banner is visible
    And the Scale On-Demand banner Configure Auto-Scale button is visible
    And the Scale On-Demand banner View Logs button is visible
    And the System Health footer stat "Last Sync" is visible
    And the System Health footer stat "Encrypted" is visible
    And the System Health footer stat "Throughput" is visible
    And the System Health footer stat "History" is visible
    And no console errors were logged during page load

  # @known-gap: 00-index.md § Known Gaps — "All Jobs CANCELLED filter — Status
  # tracked in counts but absent from filter chips" (00-index.md:143). The
  # acceptance criterion enumerates filter pills as "All, Running, Completed,
  # Failed, Pending" which already reflects the gap; the filter pill steps
  # below match that documented set. CANCELLED is intentionally not asserted
  # until the chip is added.
  # @known-gap: 00-index.md § Known Gaps — "All Jobs pagination — No cursor
  # pagination, only first 20 jobs shown" (00-index.md:142). The pagination
  # step below documents the expected "Showing X-Y of Z + Previous/Next"
  # behavior; implementation will land alongside the pagination feature.
  @todo @admin @known-gap
  Scenario: PTS-3.2 — All Jobs full page with filtering
    When I open the All Jobs page
    Then the All Jobs heading is visible
    And the All Jobs subtitle is visible
    And the All Jobs filter pill "All" shows a count
    And the All Jobs filter pill "Running" shows a count
    And the All Jobs filter pill "Completed" shows a count
    And the All Jobs filter pill "Failed" shows a count
    And the All Jobs filter pill "Pending" shows a count
    When I click the All Jobs filter pill "Failed"
    Then the All Jobs filter pill "Failed" is marked active
    And the All Jobs table only shows rows with status "Failed"
    And the All Jobs table column header "Repository" is visible
    And the All Jobs table column header "Mode" is visible
    And the All Jobs table column header "Branch" is visible
    And the All Jobs table column header "Status" is visible
    And the All Jobs table column header "Stage" is visible
    And the All Jobs table column header "Updated" is visible
    And the All Jobs table column header "Created" is visible
    And the All Jobs search field is visible
    When I click a non-link cell of the first All Jobs row
    Then the All Jobs row detail panel shows Job ID, Commit, Mode, Updated, and Error message
    And the All Jobs pagination footer shows "Showing X-Y of Z" with Previous and Next buttons

  @todo @admin @as-developer
  Scenario: PTS-3.5 — Cross-admin navigation
    Given I am on the AutoDoc dashboard home page
    When I click the "System Health" sidebar link
    Then the URL becomes "/admin/health"
    And the "Infrastructure Snapshot" admin page heading is visible
    And the "System Health" sidebar link is highlighted as active
    When I click the "All Jobs" sidebar link
    Then the URL becomes "/admin/jobs"
    And the "All Jobs" admin page heading is visible
    And the "All Jobs" sidebar link is highlighted as active
    When I click the "Repositories" sidebar link
    Then the URL becomes "/"
    And the home page repository list is fully restored
    And the "Repositories" sidebar link is highlighted as active
    And the navigation transitions are instant client-side routes
