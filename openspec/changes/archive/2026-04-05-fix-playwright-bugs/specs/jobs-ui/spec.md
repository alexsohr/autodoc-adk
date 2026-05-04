## MODIFIED Requirements

### Requirement: Jobs tab status filters use correct case
The Jobs tab status filter values SHALL use uppercase strings matching the backend `JobStatus` enum (`"PENDING"`, `"RUNNING"`, `"COMPLETED"`, `"FAILED"`, `"CANCELLED"`). Filter counts and API filter queries SHALL use these uppercase values.

#### Scenario: Filter counts reflect actual job statuses
- **WHEN** the Jobs tab loads with 2 RUNNING and 5 FAILED jobs
- **THEN** the filter pills SHALL display "Running (2)" and "Failed (5)" — not "(0)"

#### Scenario: Clicking a status filter sends uppercase to backend
- **WHEN** the user clicks the "Failed" filter pill
- **THEN** the API call SHALL send `status=FAILED` (uppercase) matching the backend `JobStatus` enum
- **AND** only FAILED jobs SHALL be displayed

### Requirement: Jobs tab displays error state on API failure
When the jobs API call fails (network error, 422, 500, etc.), the Jobs tab SHALL display an error state instead of showing infinite skeleton loading bars. The error state SHALL include a description of the problem and a "Retry" button.

#### Scenario: API returns error
- **WHEN** the user navigates to the Jobs tab and the API request fails for any reason
- **THEN** the skeleton loaders SHALL be replaced with an error message such as "Failed to load jobs" and a "Retry" button

#### Scenario: Retry after error
- **WHEN** the user clicks the "Retry" button on the error state
- **THEN** the system SHALL re-fetch the jobs data and display either the results or the error state again
