## ADDED Requirements

### Requirement: Add Repo dialog collects required backend fields
The Add Repository dialog SHALL collect all fields required by `RegisterRepositoryRequest`: `url`, `provider`, `branch_mappings`, and `public_branch`. The `name` and `description` fields (which the backend does not accept) SHALL be removed.

#### Scenario: Minimal repo creation with URL only
- **WHEN** user enters URL `https://github.com/acme/my-repo`
- **THEN** the dialog SHALL auto-detect provider as `"github"`, pre-fill default branch mapping `{"main": "main"}`, set public_branch to `"main"`, and enable the submit button

#### Scenario: Bitbucket URL auto-detection
- **WHEN** user enters URL `https://bitbucket.org/acme/my-repo`
- **THEN** the dialog SHALL auto-detect provider as `"bitbucket"`

### Requirement: URL field auto-extracts repository name for display
When user enters a valid repository URL, the dialog SHALL extract and display the repository slug (last path segment) as a confirmation label, without sending it as a field to the backend.

#### Scenario: GitHub URL name extraction
- **WHEN** user types `https://github.com/acme/my-new-repo`
- **THEN** the dialog SHALL display `"my-new-repo"` as the detected repository name

#### Scenario: URL with .git suffix
- **WHEN** user types `https://github.com/acme/my-repo.git`
- **THEN** the dialog SHALL display `"my-repo"` (with `.git` stripped)

### Requirement: 422 validation errors display field-level detail
When the backend returns a 422 response, the dialog SHALL parse the Pydantic validation error body and display field-specific error messages next to the corresponding form fields.

#### Scenario: Missing branch_mappings error
- **WHEN** user submits a form that results in a 422 with body `{"detail": [{"loc": ["body", "branch_mappings"], "msg": "Field required"}]}`
- **THEN** the dialog SHALL display "Field required" next to the branch mappings input

#### Scenario: public_branch not in mappings error
- **WHEN** user submits with `public_branch: "develop"` but branch_mappings only contains `"main"`
- **THEN** the dialog SHALL display the validation error message from the backend near the public_branch field

### Requirement: Successful creation closes dialog and refreshes list
After a successful `POST /repositories` (201), the dialog SHALL close and the repository list SHALL refetch to show the new entry.

#### Scenario: Successful creation
- **WHEN** user fills valid fields and clicks "Add Repository" and backend returns 201
- **THEN** the dialog SHALL close, and the new repository SHALL appear in the list
