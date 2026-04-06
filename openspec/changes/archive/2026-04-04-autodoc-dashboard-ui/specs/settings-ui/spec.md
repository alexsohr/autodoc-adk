# Settings Tab Specification

**Route:** `/repos/{id}/settings`
**Visibility:** Developer, Admin
**Change:** autodoc-dashboard-ui

## Design References

- **Stitch Project**: "Repo Landing Page" (ID: `17903516435494788863`)
- **Stitch Screen**: No dedicated Stitch design exists for the Settings tab. Implementation SHALL follow the UX design spec (section 11) and the general visual language established in other Stitch screens (tonal layering, no-line rule, functional color tokens). Use the shell/sidebar pattern from any Stitch screen as the layout context.
- **Design System**: "The Digital Curator" — form inputs use `surface_container_high` background with primary bottom-bar on focus, danger zone uses `error`/`error_container` tokens, cards/sections use tonal layering without borders
- **Component Library**: All UI components SHALL be implemented using `@salt-ds` packages (`@salt-ds/core`, `@salt-ds/icons`, `@salt-ds/lab`). Use Salt DS `Tabs`/`Tab` for sub-tab navigation, `FormField`/`Input` for form inputs, `Switch` for toggles, `Button` for actions, `Dropdown` for selectors, `Dialog` for confirmation modals, `Card` for sections, and `StackLayout` for arrangement. The YAML editor is an exception — use a third-party code editor (CodeMirror or Monaco) as Salt DS does not provide one.
- **Note**: Do NOT reference `.superpowers/brainstorm/` wireframes.

## Shared Component Usage

This spec uses the following shared components from `shared-components/spec.md`:
- **ConfirmDialog** — for Danger Zone confirmation dialogs (delete docs, unregister repo)
- **DataTable** — for branch mappings table and webhook deliveries log
- **StatusBadge** — for webhook health status indicator
- **SectionErrorBoundary** — wrapping each sub-tab for independent loading/error states

**Status:** Draft
**Date:** 2026-04-04

---

## ADDED Requirements

### Requirement: Sub-Tab Navigation

The Settings tab SHALL provide sub-tab navigation with the following tabs: General, Branches, Webhooks, AutoDoc Config, and Danger Zone.

#### Scenario: Sub-tabs are rendered and navigable

WHEN a user navigates to `/repos/{id}/settings`
THEN the system SHALL display a sub-tab bar with five tabs: General, Branches, Webhooks, AutoDoc Config, and Danger Zone, with General selected by default.

#### Scenario: Switching between sub-tabs

WHEN a user clicks a sub-tab label
THEN the system SHALL display the content for that sub-tab without a full page reload.

---

### Requirement: General Sub-Tab

The General sub-tab SHALL display the following fields and controls:

- Repository URL (read-only)
- Provider (read-only, e.g., GitHub or Bitbucket)
- Access token (masked display with an Update button to replace it)
- Description (editable text field)
- Auto-generation schedule: toggle to enable/disable, mode selector, frequency selector, day-of-week selection, and a "Next run" preview showing the computed next execution time
- Pin to sidebar toggle

#### Scenario: Read-only fields are not editable

WHEN the General sub-tab is displayed
THEN the repository URL and provider fields SHALL be rendered as read-only text and MUST NOT be editable by the user.

#### Scenario: Access token is masked

WHEN the General sub-tab is displayed
THEN the access token SHALL be masked (e.g., showing only the last four characters) and SHALL NOT be retrievable in plaintext by the client.

#### Scenario: Updating the access token

WHEN a user clicks the Update button next to the access token field and submits a new token
THEN the system SHALL store the new token and display a success confirmation.

#### Scenario: Editing the description

WHEN a user modifies the description field and saves
THEN the system SHALL persist the updated description and reflect it in the repository workspace.

#### Scenario: Configuring auto-generation schedule

WHEN a user enables the auto-generation toggle and selects a mode, frequency, and day(s)
THEN the system SHALL display a "Next run" preview showing the computed next execution timestamp based on the selected configuration.

#### Scenario: Saving schedule changes

WHEN a user modifies the auto-generation schedule and saves
THEN the system SHALL persist the schedule configuration and the Prefect deployment SHALL reflect the updated schedule.

#### Scenario: Pin to sidebar toggle

WHEN a user toggles the "Pin to sidebar" control
THEN the repository SHALL appear in or be removed from the sidebar's pinned repositories section accordingly.

---

### Requirement: Branches Sub-Tab

The Branches sub-tab SHALL display a branch mappings table showing source branch to documentation branch mappings.

The sub-tab SHALL allow adding, removing, and editing branch mappings. It SHALL also include a setting for designating the public-facing documentation branch.

#### Scenario: Branch mappings table displays current configuration

WHEN the Branches sub-tab is displayed
THEN the system SHALL render a table with columns for source branch and documentation branch, showing all configured mappings.

#### Scenario: Adding a new branch mapping

WHEN a user clicks an "Add Mapping" button and fills in the source and documentation branch fields
THEN the system SHALL add the new mapping to the table and persist it on save.

#### Scenario: Removing a branch mapping

WHEN a user removes a branch mapping row
THEN the system SHALL remove that mapping from the configuration on save.

#### Scenario: Setting the public branch

WHEN a user designates a branch as the public documentation branch
THEN the system SHALL persist that setting and use it as the default branch for public-facing documentation URLs.

---

### Requirement: Webhooks Sub-Tab

The Webhooks sub-tab SHALL display the webhook endpoint URL and secret (both copyable), an event filter control (push only, or push and pull request), a status indicator showing the webhook's current health, and a recent deliveries log.

The recent deliveries log SHALL display columns for: timestamp, event type, HTTP status code, and response time.

#### Scenario: Webhook URL and secret are copyable

WHEN the Webhooks sub-tab is displayed
THEN the webhook URL and secret SHALL each have a copy-to-clipboard button that copies the value when clicked.

#### Scenario: Event filter configuration

WHEN a user selects an event filter option (push only or push + PR)
THEN the system SHALL update the webhook configuration to fire only for the selected event types.

#### Scenario: Status indicator reflects webhook health

WHEN the Webhooks sub-tab is displayed
THEN the status indicator SHALL show a green/healthy state if recent deliveries succeeded, or a red/unhealthy state if recent deliveries failed.

#### Scenario: Recent deliveries log is displayed

WHEN the webhook has received at least one delivery
THEN the recent deliveries log SHALL display entries with timestamp, event type, HTTP status code, and response time, ordered by most recent first.

---

### Requirement: AutoDoc Config Sub-Tab

The AutoDoc Config sub-tab SHALL display the configuration source indicator ("Loaded from repo" when an `.autodoc.yaml` file exists in the repository, or "Using defaults" when no file is found).

When the repository contains multiple scopes (multiple `.autodoc.yaml` files), the sub-tab SHALL display a tab per scope.

The sub-tab SHALL provide an in-browser YAML editor with syntax highlighting for editing the configuration. When no config file exists in the repository, the editor SHALL display the default configuration.

The sub-tab SHALL include a Validate button, Save options, and a Diff view.

#### Scenario: Config source indicator shows correct state

WHEN the repository contains an `.autodoc.yaml` file
THEN the config source indicator SHALL display "Loaded from repo".

WHEN the repository does not contain an `.autodoc.yaml` file
THEN the config source indicator SHALL display "Using defaults".

#### Scenario: Multi-scope tabs

WHEN the repository contains multiple `.autodoc.yaml` files (multiple scopes)
THEN the sub-tab SHALL render one tab per scope, each showing the corresponding configuration.

#### Scenario: YAML editor with syntax highlighting

WHEN a user views or edits the AutoDoc configuration
THEN the system SHALL render the YAML content in an editor with syntax highlighting.

#### Scenario: Default config displayed when no file exists

WHEN no `.autodoc.yaml` file exists in the repository
THEN the editor SHALL display the system's default AutoDoc configuration as a starting point.

#### Scenario: Validate button checks configuration

WHEN a user clicks the Validate button
THEN the system SHALL validate the YAML syntax, check that referenced paths exist, verify model identifiers are recognized, and confirm threshold values are within valid ranges. Validation errors SHALL be displayed inline.

#### Scenario: Save as "Commit to repo" creates a pull request

WHEN a user selects "Commit to repo" from the Save options
THEN the system SHALL create a pull request in the source repository containing the updated `.autodoc.yaml` file.

#### Scenario: Save as "Save as override" stores in database

WHEN a user selects "Save as override" from the Save options
THEN the system SHALL persist the configuration in the AutoDoc database as a repository-level override, without modifying the source repository.

#### Scenario: Diff view shows changes

WHEN the user has modified the YAML and a committed version exists
THEN the system SHALL provide a Diff view showing the differences between the editor content and the committed version in the repository.

---

### Requirement: Danger Zone Sub-Tab

The Danger Zone sub-tab SHALL be rendered with a red-bordered visual treatment to indicate destructive actions.

The sub-tab SHALL provide two destructive actions: "Delete all generated documentation" and "Unregister repository." Both actions MUST require explicit confirmation via a confirmation dialog before execution.

#### Scenario: Danger Zone visual treatment

WHEN the Danger Zone sub-tab is displayed
THEN the section SHALL be rendered with a red border and warning styling to signal destructive operations.

#### Scenario: Delete all generated documentation

WHEN a user clicks "Delete all generated documentation" and confirms the action in the confirmation dialog
THEN the system SHALL delete all wiki structures, wiki pages, page chunks, and associated embeddings for the repository. Job history SHALL be retained.

#### Scenario: Delete documentation requires confirmation

WHEN a user clicks "Delete all generated documentation"
THEN the system SHALL display a confirmation dialog requiring the user to explicitly confirm before proceeding. The action MUST NOT execute without confirmation.

#### Scenario: Unregister repository

WHEN a user clicks "Unregister repository" and confirms the action in the confirmation dialog
THEN the system SHALL remove the repository record and all associated data (jobs, documentation, embeddings, configuration overrides) from the system.

#### Scenario: Unregister repository requires confirmation

WHEN a user clicks "Unregister repository"
THEN the system SHALL display a confirmation dialog requiring the user to explicitly confirm before proceeding. The action MUST NOT execute without confirmation.
