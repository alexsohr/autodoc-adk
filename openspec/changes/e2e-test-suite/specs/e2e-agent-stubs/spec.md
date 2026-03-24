## ADDED Requirements

### Requirement: StructureExtractor stub factory
The system SHALL provide a `make_structure_stub()` factory that returns an `AsyncMock` replacing `StructureExtractor.run()`. The stub SHALL return a valid `AgentResult[WikiStructureSpec]` with two sections and three pages (high/medium/low importance, api/module/overview types). The default quality score SHALL be 8.2. The factory SHALL accept `score` and `below_floor` parameters for override.

#### Scenario: Default structure stub returns valid AgentResult
- **WHEN** `make_structure_stub()` is called with no arguments
- **THEN** it returns a mock whose return value is an `AgentResult[WikiStructureSpec]` with `final_score=8.2`, `passed_quality_gate=True`, `below_minimum_floor=False`, and a structure with 2 sections and 3 pages

#### Scenario: Structure stub with quality failure
- **WHEN** `make_structure_stub(score=3.0, below_floor=True)` is called
- **THEN** the returned mock's `AgentResult` has `final_score=3.0`, `passed_quality_gate=False`, `below_minimum_floor=True`

### Requirement: PageGenerator stub factory
The system SHALL provide a `make_page_stub()` factory that returns an `AsyncMock` replacing `PageGenerator.run()`. The stub SHALL return a valid `AgentResult[GeneratedPage]` with deterministic Markdown content that includes the `page_key` in a heading. The content SHALL reference each source file in the page spec.

#### Scenario: Page stub generates key-identifiable content
- **WHEN** the page stub is called for a page with `page_key="core-module"`
- **THEN** the returned `GeneratedPage.content` contains the string "core-module" in a Markdown heading

#### Scenario: Page stub handles multiple calls
- **WHEN** the page stub is called for three different pages sequentially
- **THEN** each call returns a unique `GeneratedPage` with the correct `page_key` in the content

### Requirement: ReadmeDistiller stub factory
The system SHALL provide a `make_readme_stub()` factory that returns an `AsyncMock` replacing `ReadmeDistiller.run()`. The stub SHALL return a valid `AgentResult[ReadmeOutput]` with a Markdown document referencing the structure title and page titles. Default quality score SHALL be 7.5.

#### Scenario: Readme stub returns valid output
- **WHEN** `make_readme_stub()` is called
- **THEN** it returns a mock whose return value is an `AgentResult[ReadmeOutput]` with `final_score=7.5` and content containing Markdown headings

### Requirement: Git clone stub factory
The system SHALL provide a `make_clone_stub(fixture_path)` factory that patches `clone_repository` to copy the fixture repository to a temporary directory and return `(temp_path, "abc123fake")`. The stub SHALL NOT perform any network operations.

#### Scenario: Clone stub copies fixture repo
- **WHEN** a flow task calls `clone_repository` during an E2E test
- **THEN** the fixture repo is copied to a temp directory and `(temp_path, "abc123fake")` is returned

#### Scenario: Clone stub with error injection
- **WHEN** `make_clone_stub(fixture_path, error=TransientError("network"))` is called
- **THEN** the first invocation raises `TransientError` and subsequent calls succeed

### Requirement: Deterministic embedding stub
The system SHALL provide a `make_embedding_stub()` factory that patches `generate_embeddings()`. The stub SHALL return vectors derived from a SHA-256 hash of the input text, producing deterministic results where identical text always yields identical vectors.

#### Scenario: Same text produces same vector
- **WHEN** the embedding stub is called twice with the text "hello world"
- **THEN** both calls return identical vectors

#### Scenario: Different text produces different vectors
- **WHEN** the embedding stub is called with "hello world" and "goodbye world"
- **THEN** the two vectors are different but both have the configured dimensionality

### Requirement: PR creation stub
The system SHALL provide a `make_pr_stub()` factory that patches `create_autodoc_pr()` to return a fake PR URL string without making any network calls. The stub SHALL also patch `close_stale_autodoc_prs()` as a no-op returning 0.

#### Scenario: PR stub returns fake URL
- **WHEN** the flow calls `create_autodoc_pr()` during an E2E test
- **THEN** it returns `"https://github.com/test/repo/pull/999"` without network activity

### Requirement: Type-safe schema drift detection
All stub factories SHALL construct real Pydantic model instances (not raw dicts) for their return values. If the underlying schema changes in a way that is incompatible with the stub's construction, Pydantic validation SHALL raise an error at test time.

#### Scenario: Schema change breaks stub
- **WHEN** a required field is added to `WikiStructureSpec` and the stub does not provide it
- **THEN** the stub factory raises a Pydantic `ValidationError` when constructing the canned response
