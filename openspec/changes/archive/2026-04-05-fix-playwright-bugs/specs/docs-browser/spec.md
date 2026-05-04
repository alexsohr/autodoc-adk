## MODIFIED Requirements

### Requirement: Docs tab displays actionable empty state when no scopes exist
When the scopes API returns an empty list (no documentation generated yet), the Docs tab SHALL display a helpful empty state message guiding the user to generate documentation, instead of the generic "No documentation tree available."

#### Scenario: Scopes API returns empty list
- **WHEN** the user navigates to the Docs tab and the scopes endpoint returns an empty list
- **THEN** the Docs tab SHALL display an empty state message such as "No documentation scopes found. Run a documentation generation job to create scopes."

### Requirement: Docs tab displays error state on scopes API failure
When the scopes API call fails (network error, 500, etc.), the Docs tab SHALL display an error state with a "Retry" button.

#### Scenario: Scopes API returns error
- **WHEN** the user navigates to the Docs tab and the scopes endpoint fails
- **THEN** the Docs tab SHALL display an error message such as "Failed to load documentation scopes" and a "Retry" button
