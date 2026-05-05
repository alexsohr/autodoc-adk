# Source UI doc:    docs/ui/04-repo-workspace-jobs-quality-settings.md
# PTS catalog:      docs/ui/00-index.md § Page-Level Test Results
# Page Objects:     web/tests/e2e/pages/{JobsTab,QualityTab,SettingsTab,WorkspacePage}.ts
# Migration: replaces specs/04-jobs-quality-settings.spec.ts (deleted in this PR).

@area-jobs-quality-settings
Feature: Repo Workspace — Jobs / Quality / Settings
  As a dashboard user inside a repository workspace
  I can view job history and partitioning, see per-page quality scores
  and agent metrics, and configure repository settings.

  @smoke
  Scenario: PTS-2.5 — Jobs tab partitions render with seeded data
    Given I open the "digitalClock" repository workspace
    When I open the workspace "Jobs" tab
    Then the Jobs tab Completed section is visible
    And the Jobs tab Failed section is visible
    And the Jobs tab Cancelled section is visible
    And the Jobs tab header shows the Dry Run checkbox
    And the Jobs tab header shows the Full Generation button
    And the Jobs tab header shows the Incremental button
    And the Jobs tab filter pill "All" shows count 20
    And the Jobs tab filter pill "Running" shows count 0
    And the Jobs tab filter pill "Completed" shows count 1
    And the Jobs tab filter pill "Failed" shows count 13
    And the Jobs tab filter pill "Cancelled" shows count 6
    And the Jobs tab filter pill "Pending" shows count 0
    And the Jobs tab Failed section column header "Status" is visible
    And the Jobs tab Failed section column header "Mode" is visible
    And the Jobs tab Failed section column header "Branch" is visible
    And the Jobs tab Failed section column header "Created" is visible
    And the Jobs tab Failed section column header "Updated" is visible
    And the Jobs tab Failed section column header "PR" is visible
    And the Jobs tab Failed section has a Retry button on at least one row
    And the Jobs tab has a Details link on at least one row
    And the Jobs tab Failed section pagination footer is visible

  # @known-gap: 00-index.md § PTS-2.6 observation — "these score cards use
  # client-side simulated data with fixed offsets, not real API data" (table
  # row at 00-index.md:140 phrases it as "Score breakdown + token usage charts
  # are client-side simulated"). The acceptance bullet "scores are real values
  # from API" is therefore not currently satisfied; PTS-2.6 is held back until
  # the simulated charts are replaced by real API-driven values.
  @todo @known-gap
  Scenario: PTS-2.6 — Quality tab shows scores
    Given I open the "digitalClock" repository workspace
    When I open the workspace "Quality" tab
    Then the Quality agent card for "Structure Extractor" is visible with score, trend, and run history
    And the Quality agent card for "Page Generator" is visible with score, trend, and run history
    And the Quality agent card for "README Distiller" is visible with score, trend, and run history
    And the Quality tab scope filter buttons are visible
    And the Quality tab Page Quality table shows columns "Page", "Scope", "Score", "Attempts", "Tokens"
    And the Quality tab Page Quality table page titles are clickable links to the Docs tab
    And the Quality tab Page Quality scores are real values from the API

  @todo
  Scenario: PTS-2.7 — Settings tab sub-navigation
    Given I open the "digitalClock" repository workspace
    When I open the workspace "Settings" tab
    Then the Settings sub-tab "General" is visible
    And the Settings sub-tab "Branches" is visible
    And the Settings sub-tab "Webhooks" is visible
    And the Settings sub-tab "AutoDoc Config" is visible
    And the Settings sub-tab "Danger Zone" is visible
    When I click the Settings sub-tab "General"
    Then the Settings sub-tab "General" is marked active
    And the Settings General panel shows repository info fields and a schedule toggle
    When I click the Settings sub-tab "Branches"
    Then the Settings sub-tab "Branches" is marked active
    And the Settings Branches panel shows a branch mapping table
    When I click the Settings sub-tab "Webhooks"
    Then the Settings sub-tab "Webhooks" is marked active
    And the Settings Webhooks panel shows the webhook URL and secret
    When I click the Settings sub-tab "AutoDoc Config"
    Then the Settings sub-tab "AutoDoc Config" is marked active
    And the Settings AutoDoc Config panel shows the YAML editor
    When I click the Settings sub-tab "Danger Zone"
    Then the Settings sub-tab "Danger Zone" is marked active
    And the Settings Danger Zone panel shows delete actions with confirmation
