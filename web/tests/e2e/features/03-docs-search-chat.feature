# Source UI doc:    docs/ui/03-repo-workspace-docs-search-chat.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/{DocsTab,SearchTab,WorkspacePage}.ts
# Migration: replaces specs/03-docs-search-chat.spec.ts (deleted in this PR).

@area-docs-search-chat
Feature: Repo Workspace — Docs / Search / Chat
  As a dashboard user inside a repository workspace
  I can browse generated documentation, search across pages, and see
  graceful behaviour when the search backend is unavailable.

  # @known-gap: 00-index.md § PTS-2.4 observation — "The search API returned
  # 503 (Service Unavailable) -- the embedding service required for
  # hybrid/semantic search is not running in the current environment."
  # The 5th acceptance bullet ("results display ... OR error/empty state if
  # the backend is unavailable") is exercised here via the documented 503
  # branch using stubSearch503 from support/api-stubs.ts.
  @smoke @known-gap
  Scenario: PTS-2.4 — Search tab with query
    Given the search documents endpoint returns 503
    And I open the "digitalClock" repository workspace
    When I open the workspace "Search" tab
    Then the search input is visible with placeholder "Search documentation..."
    And the search mode button "Hybrid" is visible
    And the search mode button "Semantic" is visible
    And the search mode button "Full Text" is visible
    And the Search submit button is disabled
    When I type "tkinter window" into the search input
    Then the Search submit button is enabled
    When I click the Search submit button
    Then the URL matches the pattern "/search\?q=tkinter\+window"
    And the search results area shows a service-unavailable error state

  @todo
  Scenario: PTS-2.3 — Docs tab with real content
    Given I open the "digitalClock" repository workspace
    When I open the workspace "Docs" tab
    Then the docs scope selector shows at least one scope with its page count
    And the doc tree renders hierarchical sections with folder and page nodes
    And the doc viewer auto-navigates to the first page in the tree
    And the doc viewer breadcrumb path is visible
    And the doc viewer quality score pill is visible
    And the doc viewer importance badge is visible
    And the page viewer renders headings, paragraphs, lists, tables, and code blocks
    And the doc viewer renders Mermaid diagrams
    And the doc viewer shows source file links
    And the doc viewer prev and next navigation buttons are present
    When I click a different page in the doc tree
    Then the doc viewer updates to show that page
