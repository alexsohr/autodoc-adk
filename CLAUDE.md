# autodoc-adk Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-15

## Active Technologies
- PostgreSQL 18+ with pgvector extension (single instance, two databases: `autodoc` for application, `prefect` for Prefect Server); S3/compatible for session archival only
- Python 3.11+ + Google ADK (with DatabaseSessionService, LoopAgent, LlmAgent), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP

## Project Structure

```text
src/
tests/
```

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Start dev infrastructure (PostgreSQL + Prefect)
cd deployment && make dev-up

# Run database migrations
cd deployment && make migrate

# Start API with hot reload
cd deployment && make api
```

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 001-autodoc-adk-docgen: Initial implementation — Google ADK agents, Prefect 3 flows, FastAPI, SQLAlchemy async, pgvector, LiteLLM, FastMCP


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
