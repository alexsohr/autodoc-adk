# Source UI doc:    docs/ui/01-repository-list-and-navigation.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/{RepoListPage,Sidebar,TopBar,AddRepoDialog}.ts
# Migration: replaces specs/01-repo-list-and-nav.spec.ts (deleted in this PR).

@area-repo-list
Feature: Repository List & Global Navigation
  As a dashboard user landing on the AutoDoc home page
  I can see all registered repositories, filter them, search them,
  open the Add Repository dialog, and navigate the sidebar/topbar.

  @smoke
  Scenario: PTS-1.1 — Full page load and render
    Given I am on the AutoDoc dashboard home page
    Then the page title contains "AutoDoc"
    And the "Repositories" heading is visible
    And the page subtitle indicates how many repositories are registered
    And all five repository filter tabs are visible
    And the "digitalClock" repository card is visible
    And the Add Repository CTA card is visible
    And the pagination footer matches the format "Showing X-Y of Z"
    And the sidebar Repositories link is marked active
    And the TopBar global search is visible
    And the TopBar notifications bell is visible
    And the TopBar user avatar is visible

  @todo
  Scenario: PTS-1.2 — End-to-end Add Repository flow
    Given I am on the AutoDoc dashboard home page
    When I open the Add Repository dialog
    Then the dialog shows a URL input, branch mapping section, and submit button
    And the submit button is disabled while the URL field is empty
    When I enter a GitHub repository URL
    Then the provider is auto-detected as "GitHub"
    And the submit button is enabled because the default branch mapping is complete
    When I add a second branch mapping row
    Then the Remove button on every branch mapping row is enabled

  # @known-gap: 00-index.md § Known Gaps — Pending filter count mismatch (RepositoryResponse.status not classified consistently)
  @todo @known-gap
  Scenario: PTS-1.3 — Filter and search interaction
    Given I am on the AutoDoc dashboard home page
    When I click the "Pending" filter tab
    Then only repositories with Pending status are displayed
    When I click the "All" filter tab
    And I type "debug" into the repository search field
    Then only repositories whose full name matches "debug" are displayed
    And the pagination footer reflects the filtered count
    When I clear the repository search field
    Then all repository cards matching the active filter are restored

  @todo
  Scenario: PTS-1.4 — Navigation from card to workspace
    Given I am on the AutoDoc dashboard home page
    When I click the "digitalClock" repository card
    Then the URL changes to the repository workspace path
    And the breadcrumb shows "Repositories > Digital-clock-in-Python"
    And the workspace header displays the repository name, status, and owner path
    And the workspace tab navigation bar shows all 7 tabs
    And the Overview tab metric cards, current job card, repository info, and recent activity panels are populated
    And the TopBar global search placeholder changes to "Search documentation..."

  @todo
  Scenario: PTS-1.5 — Global search from home page
    Given I am on the AutoDoc dashboard home page
    When I type "clock" into the TopBar global search
    Then a debounced search across repositories is triggered
    And a results dropdown appears below the search bar
    And the dropdown shows matching documentation entries or a "No results found" message
    And the search field still displays "clock"

  @todo @as-developer
  Scenario: PTS-1.6 — Sidebar navigation from home
    Given I am on the AutoDoc dashboard home page
    When I click the sidebar "System Health" link
    Then the URL changes to "/admin/health"
    And the System Health page content is displayed
    And the sidebar System Health link is marked active
    When I click the sidebar "All Jobs" link
    Then the URL changes to "/admin/jobs"
    And the All Jobs page content is displayed
    And the sidebar All Jobs link is marked active
    When I click the sidebar "Repositories" link
    Then the URL changes to "/"
    And the full repository list page is restored
    And the sidebar Repositories link is marked active
