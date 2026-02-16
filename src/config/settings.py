from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://autodoc:autodoc@localhost:5432/autodoc"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # Prefect
    PREFECT_API_URL: str = "http://localhost:4200/api"
    PREFECT_WORK_POOL: str = "local-dev"
    AUTODOC_FLOW_DEPLOYMENT_PREFIX: str = "dev"

    # Application
    APP_COMMIT_SHA: str = ""

    # Default LLM Model
    DEFAULT_MODEL: str = "gemini-2.5-flash"

    # Per-agent model overrides (fall back to DEFAULT_MODEL if empty)
    STRUCTURE_GENERATOR_MODEL: str = ""
    STRUCTURE_CRITIC_MODEL: str = ""
    PAGE_GENERATOR_MODEL: str = ""
    PAGE_CRITIC_MODEL: str = ""
    README_GENERATOR_MODEL: str = ""
    README_CRITIC_MODEL: str = ""

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072
    EMBEDDING_BATCH_SIZE: int = 100

    # Quality thresholds
    QUALITY_THRESHOLD: float = 7.0
    MAX_AGENT_ATTEMPTS: int = 3
    STRUCTURE_COVERAGE_CRITERION_FLOOR: float = 5.0
    PAGE_ACCURACY_CRITERION_FLOOR: float = 5.0

    # Repository size limits
    MAX_REPO_SIZE: int = 524_288_000  # 500MB
    MAX_TOTAL_FILES: int = 5000
    MAX_FILE_SIZE: int = 1_048_576  # 1MB

    # Chunk settings
    CHUNK_MAX_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 50
    CHUNK_MIN_TOKENS: int = 50

    # Session archival
    SESSION_ARCHIVE_BUCKET: str = ""

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "autodoc-adk"

    def get_agent_model(self, agent_name: str) -> str:
        """Return the model configured for a specific agent, falling back to DEFAULT_MODEL.

        Args:
            agent_name: One of "structure_generator", "structure_critic",
                "page_generator", "page_critic", "readme_generator", "readme_critic".

        Returns:
            The model string for the requested agent.

        Raises:
            ValueError: If *agent_name* is not a recognised agent name.
        """
        agent_model_fields: dict[str, str] = {
            "structure_generator": "STRUCTURE_GENERATOR_MODEL",
            "structure_critic": "STRUCTURE_CRITIC_MODEL",
            "page_generator": "PAGE_GENERATOR_MODEL",
            "page_critic": "PAGE_CRITIC_MODEL",
            "readme_generator": "README_GENERATOR_MODEL",
            "readme_critic": "README_CRITIC_MODEL",
        }

        field_name = agent_model_fields.get(agent_name)
        if field_name is None:
            raise ValueError(
                f"Unknown agent name {agent_name!r}. "
                f"Expected one of: {', '.join(sorted(agent_model_fields))}"
            )

        value: str = getattr(self, field_name)
        return value if value else self.DEFAULT_MODEL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton :class:`Settings` instance."""
    return Settings()
