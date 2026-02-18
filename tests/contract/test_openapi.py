"""OpenAPI contract validation tests.

Validates that the openapi.yaml specification is well-formed and that
key structural properties of the API contract are correct. Checks
endpoint definitions, required fields, enum values, and schema
references against the spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.contract

SPEC_PATH = Path(__file__).resolve().parents[2] / "specs" / "001-autodoc-adk-docgen" / "contracts" / "openapi.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    """Load and parse the OpenAPI specification."""
    assert SPEC_PATH.exists(), f"OpenAPI spec not found at {SPEC_PATH}"
    with SPEC_PATH.open() as f:
        return yaml.safe_load(f)


# ===================================================================
# Spec-level validation
# ===================================================================


class TestSpecStructure:
    """Validate top-level spec structure."""

    def test_openapi_version(self, spec: dict):
        """Spec declares OpenAPI 3.1.0."""
        assert spec["openapi"] == "3.1.0"

    def test_info_title(self, spec: dict):
        """Spec has a title."""
        assert "title" in spec["info"]
        assert spec["info"]["title"] == "AutoDoc ADK Documentation Generator API"

    def test_info_version(self, spec: dict):
        """Spec has a version."""
        assert "version" in spec["info"]
        assert spec["info"]["version"] == "1.0.0"

    def test_has_paths(self, spec: dict):
        """Spec defines at least one path."""
        assert "paths" in spec
        assert len(spec["paths"]) > 0

    def test_has_components_schemas(self, spec: dict):
        """Spec defines component schemas."""
        assert "components" in spec
        assert "schemas" in spec["components"]
        assert len(spec["components"]["schemas"]) > 0


# ===================================================================
# Endpoint existence
# ===================================================================


class TestEndpointExistence:
    """Verify all expected endpoints are defined in the spec."""

    EXPECTED_PATHS = (
        "/repositories",
        "/repositories/{repository_id}",
        "/jobs",
        "/jobs/{job_id}",
        "/jobs/{job_id}/structure",
        "/jobs/{job_id}/tasks",
        "/jobs/{job_id}/logs",
        "/jobs/{job_id}/cancel",
        "/jobs/{job_id}/retry",
        "/documents/{repository_id}",
        "/documents/{repository_id}/pages/{page_key}",
        "/documents/{repository_id}/search",
        "/documents/{repository_id}/scopes",
        "/webhooks/push",
        "/health",
    )

    @pytest.mark.parametrize("path", EXPECTED_PATHS)
    def test_path_exists(self, spec: dict, path: str):
        """Each expected path must be defined in the spec."""
        assert path in spec["paths"], f"Missing path: {path}"

    def test_repositories_post(self, spec: dict):
        """POST /repositories is defined."""
        assert "post" in spec["paths"]["/repositories"]

    def test_repositories_get(self, spec: dict):
        """GET /repositories is defined."""
        assert "get" in spec["paths"]["/repositories"]

    def test_repositories_id_get(self, spec: dict):
        """GET /repositories/{repository_id} is defined."""
        assert "get" in spec["paths"]["/repositories/{repository_id}"]

    def test_repositories_id_patch(self, spec: dict):
        """PATCH /repositories/{repository_id} is defined."""
        assert "patch" in spec["paths"]["/repositories/{repository_id}"]

    def test_repositories_id_delete(self, spec: dict):
        """DELETE /repositories/{repository_id} is defined."""
        assert "delete" in spec["paths"]["/repositories/{repository_id}"]

    def test_jobs_post(self, spec: dict):
        """POST /jobs is defined."""
        assert "post" in spec["paths"]["/jobs"]

    def test_jobs_get(self, spec: dict):
        """GET /jobs is defined."""
        assert "get" in spec["paths"]["/jobs"]

    def test_jobs_id_get(self, spec: dict):
        """GET /jobs/{job_id} is defined."""
        assert "get" in spec["paths"]["/jobs/{job_id}"]

    def test_cancel_post(self, spec: dict):
        """POST /jobs/{job_id}/cancel is defined."""
        assert "post" in spec["paths"]["/jobs/{job_id}/cancel"]

    def test_retry_post(self, spec: dict):
        """POST /jobs/{job_id}/retry is defined."""
        assert "post" in spec["paths"]["/jobs/{job_id}/retry"]

    def test_webhooks_push_post(self, spec: dict):
        """POST /webhooks/push is defined."""
        assert "post" in spec["paths"]["/webhooks/push"]

    def test_health_get(self, spec: dict):
        """GET /health is defined."""
        assert "get" in spec["paths"]["/health"]


# ===================================================================
# Schema validation — RepositoryResponse
# ===================================================================


class TestRepositoryResponseSchema:
    """Validate the RepositoryResponse schema in the spec."""

    def test_exists(self, spec: dict):
        """RepositoryResponse schema is defined."""
        assert "RepositoryResponse" in spec["components"]["schemas"]

    def test_required_fields(self, spec: dict):
        """RepositoryResponse has all required fields."""
        schema = spec["components"]["schemas"]["RepositoryResponse"]
        required = set(schema.get("required", []))
        expected = {
            "id", "url", "provider", "org", "name",
            "branch_mappings", "public_branch",
            "created_at", "updated_at",
        }
        assert expected <= required, f"Missing required: {expected - required}"

    def test_id_is_uuid(self, spec: dict):
        """id field is uuid format."""
        schema = spec["components"]["schemas"]["RepositoryResponse"]
        assert schema["properties"]["id"]["format"] == "uuid"


# ===================================================================
# Schema validation — JobResponse
# ===================================================================


class TestJobResponseSchema:
    """Validate the JobResponse schema in the spec."""

    def test_exists(self, spec: dict):
        """JobResponse schema is defined."""
        assert "JobResponse" in spec["components"]["schemas"]

    def test_required_fields(self, spec: dict):
        """JobResponse has all required fields."""
        schema = spec["components"]["schemas"]["JobResponse"]
        required = set(schema.get("required", []))
        expected = {
            "id", "repository_id", "status", "mode", "branch",
            "force", "dry_run", "created_at", "updated_at",
        }
        assert expected <= required, f"Missing required: {expected - required}"

    def test_status_references_job_status_enum(self, spec: dict):
        """status field references the JobStatus schema."""
        schema = spec["components"]["schemas"]["JobResponse"]
        status_prop = schema["properties"]["status"]
        assert "$ref" in status_prop
        assert status_prop["$ref"].endswith("/JobStatus")


# ===================================================================
# Schema validation — Enums
# ===================================================================


class TestEnumSchemas:
    """Validate enum schemas match expected values."""

    def test_job_status_values(self, spec: dict):
        """JobStatus enum has the correct values."""
        schema = spec["components"]["schemas"]["JobStatus"]
        expected = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        actual = set(schema["enum"])
        assert expected == actual

    def test_job_mode_values(self, spec: dict):
        """JobMode enum has the correct values."""
        schema = spec["components"]["schemas"]["JobMode"]
        expected = {"full", "incremental"}
        actual = set(schema["enum"])
        assert expected == actual

    def test_git_provider_values(self, spec: dict):
        """GitProvider enum has the correct values."""
        schema = spec["components"]["schemas"]["GitProvider"]
        expected = {"github", "bitbucket"}
        actual = set(schema["enum"])
        assert expected == actual

    def test_page_importance_values(self, spec: dict):
        """PageImportance enum has the correct values."""
        schema = spec["components"]["schemas"]["PageImportance"]
        expected = {"high", "medium", "low"}
        actual = set(schema["enum"])
        assert expected == actual

    def test_page_type_values(self, spec: dict):
        """PageType enum has the correct values."""
        schema = spec["components"]["schemas"]["PageType"]
        expected = {"api", "module", "class", "overview"}
        actual = set(schema["enum"])
        assert expected == actual

    def test_health_status_values(self, spec: dict):
        """HealthResponse status enum has the correct values."""
        schema = spec["components"]["schemas"]["HealthResponse"]
        status_prop = schema["properties"]["status"]
        expected = {"healthy", "degraded", "unhealthy"}
        actual = set(status_prop["enum"])
        assert expected == actual

    def test_dependency_health_status_values(self, spec: dict):
        """DependencyHealth status enum has the correct values."""
        schema = spec["components"]["schemas"]["DependencyHealth"]
        status_prop = schema["properties"]["status"]
        expected = {"healthy", "unhealthy"}
        actual = set(status_prop["enum"])
        assert expected == actual

    def test_search_type_values(self, spec: dict):
        """SearchResponse search_type enum has the correct values."""
        schema = spec["components"]["schemas"]["SearchResponse"]
        search_type_prop = schema["properties"]["search_type"]
        expected = {"text", "semantic", "hybrid"}
        actual = set(search_type_prop["enum"])
        assert expected == actual


# ===================================================================
# Schema validation — Document schemas
# ===================================================================


class TestDocumentSchemas:
    """Validate document-related schemas."""

    def test_wiki_page_response_required_fields(self, spec: dict):
        """WikiPageResponse has required fields."""
        schema = spec["components"]["schemas"]["WikiPageResponse"]
        required = set(schema.get("required", []))
        expected = {"page_key", "title", "content"}
        assert expected <= required

    def test_wiki_page_response_has_quality_score(self, spec: dict):
        """WikiPageResponse includes quality_score property."""
        schema = spec["components"]["schemas"]["WikiPageResponse"]
        assert "quality_score" in schema["properties"]

    def test_search_result_required_fields(self, spec: dict):
        """SearchResult has required fields."""
        schema = spec["components"]["schemas"]["SearchResult"]
        required = set(schema.get("required", []))
        expected = {"page_key", "title", "snippet", "score"}
        assert expected <= required

    def test_search_result_has_chunk_fields(self, spec: dict):
        """SearchResult includes best_chunk_content and best_chunk_heading_path."""
        schema = spec["components"]["schemas"]["SearchResult"]
        props = schema["properties"]
        assert "best_chunk_content" in props
        assert "best_chunk_heading_path" in props

    def test_search_response_required_fields(self, spec: dict):
        """SearchResponse has required fields."""
        schema = spec["components"]["schemas"]["SearchResponse"]
        required = set(schema.get("required", []))
        expected = {"results", "total", "search_type"}
        assert expected <= required

    def test_scope_info_required_fields(self, spec: dict):
        """ScopeInfo has scope_path as required."""
        schema = spec["components"]["schemas"]["ScopeInfo"]
        required = set(schema.get("required", []))
        assert "scope_path" in required

    def test_scopes_response_required_fields(self, spec: dict):
        """ScopesResponse has scopes as required."""
        schema = spec["components"]["schemas"]["ScopesResponse"]
        required = set(schema.get("required", []))
        assert "scopes" in required


# ===================================================================
# Schema validation — Webhook schemas
# ===================================================================


class TestWebhookSchemas:
    """Validate webhook-related schemas."""

    def test_webhook_accepted_response_exists(self, spec: dict):
        """WebhookAcceptedResponse schema is defined."""
        assert "WebhookAcceptedResponse" in spec["components"]["schemas"]

    def test_webhook_accepted_response_has_job_id(self, spec: dict):
        """WebhookAcceptedResponse has job_id as required."""
        schema = spec["components"]["schemas"]["WebhookAcceptedResponse"]
        required = set(schema.get("required", []))
        assert "job_id" in required
        assert schema["properties"]["job_id"]["format"] == "uuid"

    def test_webhook_payload_exists(self, spec: dict):
        """WebhookPayload schema (for callback_url) is defined."""
        assert "WebhookPayload" in spec["components"]["schemas"]

    def test_webhook_payload_required_fields(self, spec: dict):
        """WebhookPayload has required fields."""
        schema = spec["components"]["schemas"]["WebhookPayload"]
        required = set(schema.get("required", []))
        expected = {"job_id", "status", "repository_id", "branch", "completed_at"}
        assert expected <= required


# ===================================================================
# Schema validation — Paginated responses
# ===================================================================


class TestPaginatedSchemas:
    """Validate pagination schemas."""

    @pytest.mark.parametrize(
        "schema_name",
        [
            "PaginatedRepositoryResponse",
            "PaginatedJobResponse",
            "PaginatedWikiResponse",
        ],
    )
    def test_has_required_pagination_fields(self, spec: dict, schema_name: str):
        """Paginated schemas have items, next_cursor, and limit as required."""
        schema = spec["components"]["schemas"][schema_name]
        required = set(schema.get("required", []))
        expected = {"items", "next_cursor", "limit"}
        assert expected <= required, f"{schema_name} missing: {expected - required}"

    @pytest.mark.parametrize(
        "schema_name",
        [
            "PaginatedRepositoryResponse",
            "PaginatedJobResponse",
            "PaginatedWikiResponse",
        ],
    )
    def test_next_cursor_is_nullable(self, spec: dict, schema_name: str):
        """next_cursor must be nullable (can be null at end of results)."""
        schema = spec["components"]["schemas"][schema_name]
        next_cursor = schema["properties"]["next_cursor"]
        assert next_cursor.get("nullable") is True or next_cursor.get("type") == "string"


# ===================================================================
# Schema validation — Quality schemas
# ===================================================================


class TestQualitySchemas:
    """Validate quality-related schemas."""

    def test_quality_report_exists(self, spec: dict):
        """QualityReport schema is defined."""
        assert "QualityReport" in spec["components"]["schemas"]

    def test_quality_report_required_fields(self, spec: dict):
        """QualityReport has required fields."""
        schema = spec["components"]["schemas"]["QualityReport"]
        required = set(schema.get("required", []))
        expected = {"overall_score", "quality_threshold", "passed", "total_pages"}
        assert expected <= required

    def test_token_usage_exists(self, spec: dict):
        """TokenUsage schema is defined."""
        assert "TokenUsage" in spec["components"]["schemas"]

    def test_token_usage_required_fields(self, spec: dict):
        """TokenUsage has required fields."""
        schema = spec["components"]["schemas"]["TokenUsage"]
        required = set(schema.get("required", []))
        expected = {"total_input_tokens", "total_output_tokens", "total_tokens"}
        assert expected <= required


# ===================================================================
# Schema validation — Health schemas
# ===================================================================


class TestHealthSchemas:
    """Validate health-related schemas."""

    def test_health_response_exists(self, spec: dict):
        """HealthResponse schema is defined."""
        assert "HealthResponse" in spec["components"]["schemas"]

    def test_health_response_required_fields(self, spec: dict):
        """HealthResponse has required fields."""
        schema = spec["components"]["schemas"]["HealthResponse"]
        required = set(schema.get("required", []))
        expected = {"status", "dependencies", "timestamp"}
        assert expected <= required

    def test_health_dependencies_has_required_services(self, spec: dict):
        """HealthResponse dependencies must include database, prefect, otel."""
        schema = spec["components"]["schemas"]["HealthResponse"]
        deps = schema["properties"]["dependencies"]
        required = set(deps.get("required", []))
        expected = {"database", "prefect", "otel"}
        assert expected <= required


# ===================================================================
# Schema validation — Error schema
# ===================================================================


class TestErrorSchema:
    """Validate the ErrorResponse schema."""

    def test_error_response_exists(self, spec: dict):
        """ErrorResponse schema is defined."""
        assert "ErrorResponse" in spec["components"]["schemas"]

    def test_error_response_has_detail(self, spec: dict):
        """ErrorResponse has detail as required field."""
        schema = spec["components"]["schemas"]["ErrorResponse"]
        required = set(schema.get("required", []))
        assert "detail" in required

    def test_error_response_detail_is_string(self, spec: dict):
        """detail field is a string."""
        schema = spec["components"]["schemas"]["ErrorResponse"]
        assert schema["properties"]["detail"]["type"] == "string"


# ===================================================================
# Response code validation
# ===================================================================


class TestResponseCodes:
    """Validate that expected response codes are documented."""

    def test_repositories_post_responses(self, spec: dict):
        """POST /repositories has 201, 409, 422 responses."""
        responses = spec["paths"]["/repositories"]["post"]["responses"]
        assert "201" in responses
        assert "409" in responses
        assert "422" in responses

    def test_repositories_get_id_responses(self, spec: dict):
        """GET /repositories/{repository_id} has 200, 404 responses."""
        responses = spec["paths"]["/repositories/{repository_id}"]["get"]["responses"]
        assert "200" in responses
        assert "404" in responses

    def test_repositories_delete_responses(self, spec: dict):
        """DELETE /repositories/{repository_id} has 204, 404 responses."""
        responses = spec["paths"]["/repositories/{repository_id}"]["delete"]["responses"]
        assert "204" in responses
        assert "404" in responses

    def test_jobs_post_responses(self, spec: dict):
        """POST /jobs has 201, 200, 404, 422 responses."""
        responses = spec["paths"]["/jobs"]["post"]["responses"]
        assert "201" in responses
        assert "200" in responses  # idempotency
        assert "404" in responses
        assert "422" in responses

    def test_cancel_responses(self, spec: dict):
        """POST /jobs/{job_id}/cancel has 200, 404, 409 responses."""
        responses = spec["paths"]["/jobs/{job_id}/cancel"]["post"]["responses"]
        assert "200" in responses
        assert "404" in responses
        assert "409" in responses

    def test_retry_responses(self, spec: dict):
        """POST /jobs/{job_id}/retry has 200, 404, 409 responses."""
        responses = spec["paths"]["/jobs/{job_id}/retry"]["post"]["responses"]
        assert "200" in responses
        assert "404" in responses
        assert "409" in responses

    def test_webhooks_push_responses(self, spec: dict):
        """POST /webhooks/push has 202, 204, 400 responses."""
        responses = spec["paths"]["/webhooks/push"]["post"]["responses"]
        assert "202" in responses
        assert "204" in responses
        assert "400" in responses

    def test_search_responses(self, spec: dict):
        """GET /documents/{repository_id}/search has 200, 404 responses."""
        responses = spec["paths"]["/documents/{repository_id}/search"]["get"]["responses"]
        assert "200" in responses
        assert "404" in responses

    def test_get_wiki_responses(self, spec: dict):
        """GET /documents/{repository_id} has 200, 404 responses."""
        responses = spec["paths"]["/documents/{repository_id}"]["get"]["responses"]
        assert "200" in responses
        assert "404" in responses

    def test_get_page_responses(self, spec: dict):
        """GET /documents/{repository_id}/pages/{page_key} has 200, 404 responses."""
        path = "/documents/{repository_id}/pages/{page_key}"
        responses = spec["paths"][path]["get"]["responses"]
        assert "200" in responses
        assert "404" in responses

    def test_scopes_responses(self, spec: dict):
        """GET /documents/{repository_id}/scopes has 200, 404 responses."""
        responses = spec["paths"]["/documents/{repository_id}/scopes"]["get"]["responses"]
        assert "200" in responses
        assert "404" in responses


# ===================================================================
# Parameter validation
# ===================================================================


class TestParameters:
    """Validate shared parameter definitions."""

    def test_cursor_param_exists(self, spec: dict):
        """CursorParam is defined in components/parameters."""
        assert "CursorParam" in spec["components"]["parameters"]

    def test_limit_param_exists(self, spec: dict):
        """LimitParam is defined in components/parameters."""
        assert "LimitParam" in spec["components"]["parameters"]

    def test_limit_param_constraints(self, spec: dict):
        """LimitParam has minimum=1, maximum=100, default=20."""
        limit = spec["components"]["parameters"]["LimitParam"]
        schema = limit["schema"]
        assert schema["minimum"] == 1
        assert schema["maximum"] == 100
        assert schema["default"] == 20

    def test_repository_id_path_param(self, spec: dict):
        """RepositoryIdPath param is uuid format."""
        param = spec["components"]["parameters"]["RepositoryIdPath"]
        assert param["in"] == "path"
        assert param["required"] is True
        assert param["schema"]["format"] == "uuid"

    def test_job_id_path_param(self, spec: dict):
        """JobIdPath param is uuid format."""
        param = spec["components"]["parameters"]["JobIdPath"]
        assert param["in"] == "path"
        assert param["required"] is True
        assert param["schema"]["format"] == "uuid"

    def test_branch_query_param(self, spec: dict):
        """BranchQuery param is defined."""
        assert "BranchQuery" in spec["components"]["parameters"]
        param = spec["components"]["parameters"]["BranchQuery"]
        assert param["in"] == "query"
        assert param["required"] is False

    def test_scope_query_param(self, spec: dict):
        """ScopeQuery param is defined."""
        assert "ScopeQuery" in spec["components"]["parameters"]
        param = spec["components"]["parameters"]["ScopeQuery"]
        assert param["in"] == "query"
        assert param["required"] is False


# ===================================================================
# Ref integrity
# ===================================================================


class TestRefIntegrity:
    """Validate that all $ref pointers resolve to existing schemas."""

    def _collect_refs(self, obj: object, refs: list[str]) -> None:
        """Recursively collect all $ref values."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                refs.append(obj["$ref"])
            for v in obj.values():
                self._collect_refs(v, refs)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_refs(item, refs)

    def test_all_refs_resolve(self, spec: dict):
        """All $ref pointers in the spec resolve to existing definitions."""
        refs: list[str] = []
        self._collect_refs(spec, refs)

        for ref in refs:
            if not ref.startswith("#/"):
                continue  # skip external refs

            parts = ref.lstrip("#/").split("/")
            node = spec
            for part in parts:
                assert part in node, f"Broken $ref: {ref} (missing '{part}')"
                node = node[part]
