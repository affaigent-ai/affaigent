import os
from dataclasses import dataclass, field


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_int_env(name: str, default: int) -> int:
    return int(_get_env(name, str(default)))


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    model: str
    api_key_env: str
    base_url: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: _get_env("APP_NAME", "Affaigent API"))
    app_env: str = field(default_factory=lambda: _get_env("APP_ENV", "production"))
    app_port: int = field(default_factory=lambda: _get_int_env("APP_PORT", 8000))

    postgres_host: str = field(default_factory=lambda: _get_env("POSTGRES_HOST", "postgres"))
    postgres_port: int = field(default_factory=lambda: _get_int_env("POSTGRES_PORT", 5432))
    postgres_db: str = field(default_factory=lambda: _get_env("POSTGRES_DB", "affaigent"))
    postgres_user: str = field(default_factory=lambda: _get_env("POSTGRES_USER", "affaigent"))
    postgres_password: str = field(default_factory=lambda: _get_env("POSTGRES_PASSWORD", ""))

    qdrant_host: str = field(default_factory=lambda: _get_env("QDRANT_HOST", "qdrant"))
    qdrant_http_port: int = field(default_factory=lambda: _get_int_env("QDRANT_HTTP_PORT", 6333))
    qdrant_api_key: str = field(default_factory=lambda: _get_env("QDRANT_API_KEY", ""))
    qdrant_memory_collection: str = field(default_factory=lambda: _get_env("QDRANT_MEMORY_COLLECTION", "memory_chunks_v2"))
    memory_vector_size: int = field(default_factory=lambda: _get_int_env("MEMORY_VECTOR_SIZE", 768))

    embedding_provider: str = field(default_factory=lambda: _get_env("EMBEDDING_PROVIDER", "tei"))
    embedding_base_url: str = field(default_factory=lambda: _get_env("EMBEDDING_BASE_URL", "http://embeddings:80"))
    embedding_model: str = field(default_factory=lambda: _get_env("EMBEDDING_MODEL", "intfloat/multilingual-e5-base"))

    identities: tuple[str, str, str, str, str] = (
        "dennis_work",
        "dennis_private",
        "linsey_work",
        "linsey_private",
        "shared_private",
    )

    model_profiles: tuple[ModelProfile, ...] = (
        ModelProfile(
            name="claude_primary",
            provider="anthropic",
            model=_get_env("MODEL_ANTHROPIC_PRIMARY", "claude-sonnet-4-20250514"),
            api_key_env="ANTHROPIC_API_KEY",
            enabled=_get_bool_env("MODEL_PROFILE_CLAUDE_PRIMARY_ENABLED", False),
        ),
        ModelProfile(
            name="openai_primary",
            provider="openai",
            model=_get_env("MODEL_OPENAI_PRIMARY", "gpt-5"),
            api_key_env="OPENAI_API_KEY",
            enabled=_get_bool_env("MODEL_PROFILE_OPENAI_PRIMARY_ENABLED", True),
        ),
        ModelProfile(
            name="gemini_primary",
            provider="google",
            model=_get_env("MODEL_GEMINI_PRIMARY", "gemini-2.5-pro"),
            api_key_env="GEMINI_API_KEY",
            enabled=_get_bool_env("MODEL_PROFILE_GEMINI_PRIMARY_ENABLED", False),
        ),
        ModelProfile(
            name="local_fallback",
            provider="openai_compatible",
            model=_get_env("MODEL_LOCAL_FALLBACK", "qwen2.5:14b-instruct"),
            api_key_env="LOCAL_LLM_API_KEY",
            base_url=_get_env("LOCAL_LLM_BASE_URL", "http://host.docker.internal:11434/v1"),
            enabled=_get_bool_env("MODEL_PROFILE_LOCAL_FALLBACK_ENABLED", False),
        ),
    )

    @property
    def postgres_conninfo(self) -> str:
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


settings = Settings()
