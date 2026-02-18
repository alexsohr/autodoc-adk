"""Tests for flow inter-task Pydantic DTOs."""
from __future__ import annotations

import uuid

from src.flows.schemas import (
    CloneInput,
    PageTaskResult,
    PrRepositoryInfo,
    ReadmeTaskResult,
    ScopeProcessingResult,
    StructureTaskResult,
    TokenUsageResult,
)


class TestTokenUsageResult:
    def test_defaults(self):
        t = TokenUsageResult()
        assert t.input_tokens == 0
        assert t.calls == 0

    def test_from_values(self):
        t = TokenUsageResult(input_tokens=100, output_tokens=50, total_tokens=150, calls=2)
        assert t.total_tokens == 150


class TestStructureTaskResult:
    def test_roundtrip_json(self):
        r = StructureTaskResult(
            final_score=8.5,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=100, output_tokens=50, total_tokens=150, calls=1),
            output_title="Test",
            output_description="Desc",
            sections_json=[{"title": "Core", "pages": [], "subsections": []}],
        )
        data = r.model_dump(mode="json")
        restored = StructureTaskResult.model_validate(data)
        assert restored.final_score == 8.5
        assert restored.sections_json[0]["title"] == "Core"

    def test_nullable_output(self):
        r = StructureTaskResult(
            final_score=0.0,
            passed_quality_gate=False,
            below_minimum_floor=True,
            attempts=3,
            token_usage=TokenUsageResult(),
        )
        assert r.output_title is None
        assert r.sections_json is None


class TestPageTaskResult:
    def test_roundtrip_json(self):
        r = PageTaskResult(
            page_key="core-overview",
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=80, output_tokens=40, total_tokens=120, calls=1),
        )
        data = r.model_dump(mode="json")
        restored = PageTaskResult.model_validate(data)
        assert restored.page_key == "core-overview"


class TestReadmeTaskResult:
    def test_roundtrip_json(self):
        r = ReadmeTaskResult(
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            content="# README",
            token_usage=TokenUsageResult(),
        )
        assert r.content == "# README"


class TestCloneInput:
    def test_from_values(self):
        c = CloneInput(url="https://github.com/org/repo", provider="github", access_token="tok")
        assert c.provider == "github"

    def test_optional_token(self):
        c = CloneInput(url="https://github.com/org/repo", provider="github")
        assert c.access_token is None


class TestPrRepositoryInfo:
    def test_from_values(self):
        p = PrRepositoryInfo(
            url="https://github.com/org/repo",
            provider="github",
            name="repo",
            public_branch="main",
        )
        assert p.name == "repo"


class TestScopeProcessingResult:
    def test_defaults(self):
        r = ScopeProcessingResult()
        assert r.structure_result is None
        assert r.page_results == []
        assert r.readme_result is None
        assert r.embedding_count == 0

    def test_full(self):
        r = ScopeProcessingResult(
            structure_result=StructureTaskResult(
                final_score=8.5,
                passed_quality_gate=True,
                below_minimum_floor=False,
                attempts=1,
                token_usage=TokenUsageResult(),
            ),
            page_results=[
                PageTaskResult(
                    page_key="p1",
                    final_score=7.0,
                    passed_quality_gate=True,
                    below_minimum_floor=False,
                    attempts=1,
                    token_usage=TokenUsageResult(),
                ),
            ],
            wiki_structure_id=uuid.uuid4(),
            embedding_count=10,
        )
        assert len(r.page_results) == 1

    def test_roundtrip_json(self):
        sid = uuid.uuid4()
        r = ScopeProcessingResult(wiki_structure_id=sid, embedding_count=5)
        data = r.model_dump(mode="json")
        restored = ScopeProcessingResult.model_validate(data)
        assert restored.wiki_structure_id == sid
