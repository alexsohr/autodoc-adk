# Source UI doc:    docs/ui/06-admin-usage-and-mcp.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/admin/{UsagePage,McpPage}.ts
# Migration: replaces specs/06-admin-usage-and-mcp.spec.ts (deleted in this PR).

@area-admin-usage-and-mcp
Feature: Admin — Usage & Costs / MCP Servers
  As an admin or developer
  I can see token usage and cost metrics across repositories,
  and inspect the MCP server status, registered tools, and integration guides.

  # @known-gap: 00-index.md § Known Gaps — "Usage by model chart — Backend
  # admin.py has TODO, always returns []" (00-index.md:135). The "Usage by
  # Model" chart therefore renders the SectionErrorBoundary EmptyState with
  # message "No model usage data" instead of bars. The empty-state assertion
  # below encodes the documented current behavior; when the backend gap is
  # closed, the assertion should flip to the populated chart.
  @smoke @admin @as-developer @known-gap
  Scenario: PTS-3.3 — Usage & Costs page loads
    When I open the Usage and Costs page
    Then the Usage and Costs heading is visible
    And the Usage and Costs subtitle is visible
    And the Usage and Costs range button "7 days" is visible
    And the Usage and Costs range button "30 days" is visible
    And the Usage and Costs range button "90 days" is visible
    And the Usage and Costs range button "All time" is visible
    And the Usage and Costs range button "30 days" is marked active
    When I click the Usage and Costs range button "90 days"
    Then the Usage and Costs range button "90 days" is marked active
    And the Usage and Costs metric card "Total Tokens" is visible
    And the Usage and Costs metric card "Estimated Cost" is visible
    And the Usage and Costs metric card "Total Jobs" is visible
    And the Usage and Costs metric card "Total Tokens" shows a non-zero value
    And the Usage and Costs metric card "Estimated Cost" shows a non-zero value
    And the Usage and Costs metric card "Total Jobs" shows a non-zero value
    And the Usage and Costs metric card "Total Tokens" shows secondary text
    And the Usage and Costs metric card "Estimated Cost" shows secondary text
    And the Usage and Costs metric card "Total Jobs" shows secondary text
    And the Top Repositories chart heading is visible
    And the Usage by Model section shows the empty-state placeholder
    And the Cost Efficiency Tip banner is visible
    And no console errors were logged during Usage and Costs page load

  # @known-gap: 00-index.md § Known Gaps — "MCP total_calls — Always 0, not
  # tracked server-side" (00-index.md:136). The Total Calls summary card will
  # render "0" until server-side tracking lands.
  # @known-gap: 00-index.md § Known Gaps — "MCP integration URLs — Hardcoded
  # to http://localhost:8080/mcp" (00-index.md:145). The Agent Integration
  # Guide tabs surface this hardcoded URL until config-driven URLs land.
  @todo @admin @known-gap
  Scenario: PTS-3.4 — MCP Servers page loads
    When I open the MCP Servers page
    Then the MCP Servers heading is visible
    And the MCP Servers subtitle is visible
    And the MCP Server Status card is visible with a status badge
    And the MCP Server Status card shows the endpoint URL with a copy button
    And the MCP Server Status card shows the available tools list
    And the MCP summary metric card "Total Calls" is visible
    And the MCP summary metric card "Available Tools" is visible
    And the MCP summary metric card "Server Status" is visible
    And the MCP Agent Integration Guide tab "VS Code" is visible
    And the MCP Agent Integration Guide tab "Claude Code" is visible
    And the MCP Agent Integration Guide tab "Generic MCP Client" is visible
    When I click the MCP Agent Integration Guide tab "Claude Code"
    Then the MCP Agent Integration Guide shows the matching code snippet
    And the MCP Security Context section "Transport" is visible
    And the MCP Security Context section "Authentication" is visible
    And the MCP Security Context section "Rate Limiting" is visible
    And the MCP Security Context section "Data Access" is visible
    And no console errors were logged during MCP Servers page load
