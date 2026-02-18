<!-- FOR AI AGENTS -->

# src/config

Centralized application configuration: Pydantic BaseSettings for env vars, LLM model factory, and OpenTelemetry/logging setup. The telemetry module MUST be configured before any ADK import.

## Files

| File | Purpose |
|------|---------|
| `settings.py` | `Settings(BaseSettings)` with all env vars + `get_settings()` cached singleton |
| `models.py` | `get_model(model_name)` factory -- returns raw string for Gemini or `LiteLlm` wrapper |
| `telemetry.py` | `configure_telemetry()`, `CorrelationFilter`, `set_correlation_context()` |

## settings.py

`Settings` inherits from `pydantic_settings.BaseSettings`. Reads `.env` file, ignores unknown keys.

### Env var groups

- **Database**: `DATABASE_URL`, `DB_POOL_SIZE` (5), `DB_MAX_OVERFLOW` (10), `DB_POOL_TIMEOUT` (30), `DB_POOL_RECYCLE` (3600)
- **Prefect**: `PREFECT_API_URL`, `PREFECT_WORK_POOL` ("local-dev"), `AUTODOC_FLOW_DEPLOYMENT_PREFIX` ("dev")
- **Application**: `APP_COMMIT_SHA`
- **LLM defaults**: `DEFAULT_MODEL` ("gemini-2.5-flash")
- **Per-agent model overrides** (empty string = falls back to `DEFAULT_MODEL`): `STRUCTURE_GENERATOR_MODEL`, `STRUCTURE_CRITIC_MODEL`, `PAGE_GENERATOR_MODEL`, `PAGE_CRITIC_MODEL`, `README_GENERATOR_MODEL`, `README_CRITIC_MODEL`
- **Embedding**: `EMBEDDING_MODEL` ("text-embedding-3-large"), `EMBEDDING_DIMENSIONS` (3072), `EMBEDDING_BATCH_SIZE` (100)
- **Quality**: `QUALITY_THRESHOLD` (7.0), `MAX_AGENT_ATTEMPTS` (3), `STRUCTURE_COVERAGE_CRITERION_FLOOR` (5.0), `PAGE_ACCURACY_CRITERION_FLOOR` (5.0)
- **Repo limits**: `MAX_REPO_SIZE` (500MB), `MAX_TOTAL_FILES` (5000), `MAX_FILE_SIZE` (1MB)
- **Chunking**: `CHUNK_MAX_TOKENS` (512), `CHUNK_OVERLAP_TOKENS` (50), `CHUNK_MIN_TOKENS` (50)
- **Session archival**: `SESSION_ARCHIVE_BUCKET`
- **OTEL**: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` ("autodoc-adk")

### Key method

`Settings.get_agent_model(agent_name)` resolves per-agent model string. Valid agent names: `structure_generator`, `structure_critic`, `page_generator`, `page_critic`, `readme_generator`, `readme_critic`. Returns the agent-specific override or `DEFAULT_MODEL` when the override is empty.

### Access pattern

```python
from src.config.settings import get_settings

s = get_settings()  # cached singleton, never construct Settings() directly
```

## models.py

`get_model(model_name)` returns `str | LiteLlm`:

- Names starting with `"gemini-"` return the raw string (ADK uses natively).
- Names starting with `"vertex_ai/"`, `"azure/"`, `"bedrock/"`, or `"openai/"` return `LiteLlm(model=name)`.
- Anything else raises `ValueError`.

```python
from src.config.models import get_model
from src.config.settings import get_settings

s = get_settings()
model = get_model(s.get_agent_model("page_generator"))
```

## telemetry.py

`configure_telemetry()` sets up OpenTelemetry tracing and JSON structured logging. Idempotent (subsequent calls are no-ops). Reads `OTEL_SERVICE_NAME`, `APP_COMMIT_SHA`, `OTEL_EXPORTER_OTLP_ENDPOINT`, and `LOG_LEVEL` from env.

Pipeline: `TracerProvider` with `OTLPSpanExporter` (gRPC) + `BatchSpanProcessor`. `LoggingInstrumentor` injects `otelTraceID`/`otelSpanID` into records. `JsonFormatter` outputs structured JSON with renamed fields (`timestamp`, `level`, `trace_id`, `span_id`, `service`).

`CorrelationFilter` reads from `contextvars` and injects `job_id`, `agent_name`, `task_name` into every log record.

`set_correlation_context(*, job_id, agent_name, task_name)` updates the contextvar. Only non-None arguments are changed; the rest retain current values.

## Heuristics

| When | Do |
|------|----|
| Adding new config | Add field to `Settings` in `settings.py` using `UPPER_SNAKE_CASE` env var naming |
| Need an LLM instance | Call `get_model()` -- never instantiate LLM classes directly |
| Need log correlation | Call `set_correlation_context(job_id=..., agent_name=..., task_name=...)` |
| Changing telemetry | Ensure `configure_telemetry()` still runs before any ADK import at app entry point |
| Adding a criterion floor | Add `*_CRITERION_FLOOR` float field to `Settings`; consume in quality loop config |
| Adding a new agent model | Add `*_MODEL: str = ""` field to `Settings`; add mapping entry in `get_agent_model()` |

## Boundaries

**Always:**
- Use `get_settings()` singleton -- never construct `Settings()` directly
- Use `get_model()` factory for LLM instances
- Call `configure_telemetry()` before ADK imports in the application entry point

**Ask first:**
- Adding new model provider prefixes to `_LITELLM_PREFIXES`
- Changing default threshold or limit values
- Modifying the telemetry pipeline or log format

**Never:**
- Instantiate LLM models directly (bypass `get_model()`)
- Use `os.environ` / `os.getenv` instead of `Settings` fields (except inside `telemetry.py` which deliberately avoids importing Settings to prevent circular deps)
- Import ADK modules in `telemetry.py` (circular dependency -- ADK reads TracerProvider at import time)
