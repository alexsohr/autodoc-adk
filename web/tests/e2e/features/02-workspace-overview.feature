# Source UI doc:    docs/ui/02-repo-workspace-overview.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/{WorkspacePage,RepoListPage,Sidebar,TopBar}.ts
# Migration: replaces specs/02-workspace-overview.spec.ts (deleted in this PR).

@area-workspace
Feature: Repo Workspace — Overview
  As a dashboard user opening a repository workspace
  I see the breadcrumb, metric cards, current job, repo info, recent activity,
  and the seven workspace tabs.

  @smoke
  Scenario: PTS-2.1 — Full workspace load with data
    Given I open the "digitalClock" repository workspace
    Then the URL path matches the repository workspace pattern
    And the breadcrumb shows "Repositories" and the "digitalClock" repository name
    And the "Doc Pages" overview metric card is visible
    And the "Avg Quality" overview metric card is visible
    And the "Scopes" overview metric card is visible
    And the "Last Generated" overview metric card is visible
    And the "Run Full Generation" button is visible
    And the Overview Current Job card is visible
    And the Overview Repository Info panel is visible
    And the Overview Recent Activity panel is visible
    And the Overview Scope Breakdown table is visible
    And the workspace "Overview" tab is visible
    And the workspace "Docs" tab is visible
    And the workspace "Search" tab is visible
    And the workspace "Chat" tab is visible
    And the workspace "Jobs" tab is visible
    And the workspace "Quality" tab is visible
    And the workspace "Settings" tab is visible

  @todo
  Scenario: PTS-2.2 — Tab navigation preserves repo context
    Given I open the "digitalClock" repository workspace
    When I click the workspace "Overview" tab
    Then the URL path corresponds to the "Overview" workspace tab
    And the workspace "Overview" tab is marked active
    And the "Overview" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Docs" tab
    Then the URL path corresponds to the "Docs" workspace tab
    And the workspace "Docs" tab is marked active
    And the "Docs" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Search" tab
    Then the URL path corresponds to the "Search" workspace tab
    And the workspace "Search" tab is marked active
    And the "Search" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Chat" tab
    Then the URL path corresponds to the "Chat" workspace tab
    And the workspace "Chat" tab is marked active
    And the "Chat" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Jobs" tab
    Then the URL path corresponds to the "Jobs" workspace tab
    And the workspace "Jobs" tab is marked active
    And the "Jobs" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Quality" tab
    Then the URL path corresponds to the "Quality" workspace tab
    And the workspace "Quality" tab is marked active
    And the "Quality" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
    When I click the workspace "Settings" tab
    Then the URL path corresponds to the "Settings" workspace tab
    And the workspace "Settings" tab is marked active
    And the "Settings" tab content is rendered
    And the breadcrumb still shows the "digitalClock" repository name
    And the "Run Full Generation" button is still visible
