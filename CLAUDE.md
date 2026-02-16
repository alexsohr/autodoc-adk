# autodoc-adk Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-15

## Active Technologies
- PostgreSQL 18+ with pgvector extension (single database); pgvector vector(3072) for content chunk embeddings; separate `prefect` database on same PostgreSQL instance for Prefect Server (auto-managed by Prefect) (001-autodoc-adk-docgen)
- Python 3.11+ + Google ADK (with DatabaseSessionService, LoopAgent, LlmAgent), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP (001-autodoc-adk-docgen)
- PostgreSQL 18+ with pgvector extension (single instance, two databases: `autodoc` for application, `prefect` for Prefect Server); S3/compatible for session archival only (001-autodoc-adk-docgen)

- Python 3.11+ + Google ADK (with DatabaseSessionService), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), S3/compatible object storage (session archival only) (001-autodoc-adk-docgen)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 001-autodoc-adk-docgen: Added Python 3.11+ + Google ADK (with DatabaseSessionService, LoopAgent, LlmAgent), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), LiteLLM (via ADK's built-in LiteLlm wrapper), FastMCP
- 001-autodoc-adk-docgen: Added Python 3.11+ + Google ADK (with DatabaseSessionService), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), S3/compatible object storage (session archival only)
- 001-autodoc-adk-docgen: Added Python 3.11+ + Google ADK (with DatabaseSessionService), Prefect 3, FastAPI, SQLAlchemy async + asyncpg, pgvector, Pydantic BaseSettings, OpenTelemetry (TracerProvider + LoggingInstrumentor), S3/compatible object storage (session archival only)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
