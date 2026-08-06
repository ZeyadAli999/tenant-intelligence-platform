"""Environment-backed application configuration."""

import base64
import binascii
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    app_name: str = "Tenant Intelligence"
    app_version: str = "1.0.0"
    api_prefix: Literal["/api"] = "/api"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    database_url: str = Field(min_length=1, repr=False)
    database_echo: bool = False
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_minutes: int = Field(default=15, ge=1, le=60)
    jwt_refresh_token_days: int = Field(default=30, ge=1, le=90)
    connection_encryption_key: SecretStr
    result_masking_key: SecretStr
    allow_private_database_hosts: bool = False
    customer_database_connect_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=30.0,
    )
    customer_database_command_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=60.0,
    )
    safe_query_lock_timeout_ms: int = Field(default=1000, ge=100, le=10000)
    safe_query_max_rows: int = Field(default=100, ge=1, le=1000)
    safe_query_max_columns: int = Field(default=50, ge=1, le=200)
    safe_query_max_result_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    safe_query_max_cell_length: int = Field(default=4096, ge=32, le=65536)
    safe_query_max_joins: int = Field(default=8, ge=0, le=20)
    safe_query_max_subquery_depth: int = Field(default=4, ge=0, le=10)
    safe_query_max_ctes: int = Field(default=5, ge=0, le=20)
    safe_query_max_selected_columns: int = Field(default=50, ge=1, le=200)
    groq_api_key: SecretStr
    groq_model: str = Field(default="openai/gpt-oss-120b", min_length=1, max_length=100)
    groq_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    groq_max_output_tokens: int = Field(default=1200, ge=100, le=10000)
    groq_max_retries: int = Field(default=2, ge=0, le=3)
    llm_schema_max_tables: int = Field(default=8, ge=1, le=30)
    llm_schema_max_columns: int = Field(default=60, ge=1, le=200)
    chat_max_message_length: int = Field(default=4000, ge=100, le=20000)
    chat_history_messages: int = Field(default=10, ge=0, le=50)
    chat_graph_recursion_limit: int = Field(default=20, ge=5, le=50)
    redis_url: str = Field(min_length=1, repr=False)
    minio_endpoint: str = Field(min_length=1, max_length=255)
    minio_secure: bool = False
    minio_bucket: str = Field(
        default="documents", pattern=r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
    )
    minio_root_user: SecretStr
    minio_root_password: SecretStr
    minio_app_access_key: SecretStr
    minio_app_secret_key: SecretStr
    embedding_model: Literal[
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ] = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = Field(default=384, ge=384, le=384)
    embedding_cache_dir: str = "/var/cache/fastembed"
    embedding_batch_size: int = Field(default=32, ge=1, le=128)
    document_max_file_bytes: int = Field(default=26_214_400, ge=1024, le=104_857_600)
    document_max_extracted_characters: int = Field(
        default=5_000_000, ge=1000, le=20_000_000
    )
    document_max_pages: int = Field(default=1000, ge=1, le=5000)
    document_max_spreadsheet_rows: int = Field(default=100_000, ge=1, le=1_000_000)
    document_max_spreadsheet_cells: int = Field(default=1_000_000, ge=1, le=5_000_000)
    document_chunk_target_tokens: int = Field(default=450, ge=50, le=2000)
    document_chunk_overlap_tokens: int = Field(default=60, ge=0, le=500)
    document_max_chunks_per_file: int = Field(default=10_000, ge=1, le=50_000)
    document_dense_candidates: int = Field(default=30, ge=1, le=200)
    document_lexical_candidates: int = Field(default=30, ge=1, le=200)
    document_final_top_k: int = Field(default=8, ge=1, le=30)
    document_min_relevance: float = Field(default=0.15, ge=0, le=1)
    document_max_evidence_characters: int = Field(default=24_000, ge=1000, le=100_000)

    @field_validator("debug")
    @classmethod
    def require_debug_disabled(cls, value: bool) -> bool:
        """Keep traceback responses disabled in every deployment environment."""
        if value:
            raise ValueError("DEBUG must remain false")
        return value

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql_url(cls, value: str) -> str:
        """Reject database URLs that would silently use a synchronous driver."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def require_strong_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Reject missing, placeholder, short, or trivially repeated HMAC secrets."""
        secret = value.get_secret_value()
        normalized = secret.strip().casefold()
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        if normalized.startswith(("replace-", "change-me", "changeme")):
            raise ValueError("JWT_SECRET must not use a placeholder value")
        if len(set(secret)) < 8:
            raise ValueError("JWT_SECRET does not contain enough character diversity")
        return value

    @field_validator("connection_encryption_key")
    @classmethod
    def require_aes_256_key(cls, value: SecretStr) -> SecretStr:
        """Require one base64url-encoded 256-bit AES key without a fallback."""
        encoded = value.get_secret_value().strip()
        if encoded.casefold().startswith(("replace-", "change-me", "changeme")):
            raise ValueError("CONNECTION_ENCRYPTION_KEY must not be a placeholder")
        try:
            padding = "=" * (-len(encoded) % 4)
            decoded = base64.b64decode(
                encoded + padding,
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "CONNECTION_ENCRYPTION_KEY must be valid base64url"
            ) from exc
        if len(decoded) != 32:
            raise ValueError(
                "CONNECTION_ENCRYPTION_KEY must decode to exactly 32 bytes"
            )
        return SecretStr(encoded)

    @field_validator("result_masking_key")
    @classmethod
    def require_strong_masking_key(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret.encode()) < 32 or secret.casefold().startswith(
            ("replace-", "change-me", "changeme")
        ):
            raise ValueError(
                "RESULT_MASKING_KEY must contain at least 32 non-placeholder bytes"
            )
        return value

    @field_validator("groq_model")
    @classmethod
    def require_safe_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or normalized.casefold().startswith(
            ("replace-", "change-me")
        ):
            raise ValueError("GROQ_MODEL must be a non-placeholder model name")
        if normalized != "openai/gpt-oss-120b":
            raise ValueError("GROQ_MODEL must be openai/gpt-oss-120b")
        return normalized

    @field_validator("groq_api_key")
    @classmethod
    def require_groq_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if len(key) < 20 or key.casefold().startswith(
            ("replace-", "change-me", "changeme", "your-")
        ):
            raise ValueError("GROQ_API_KEY must be a non-placeholder local secret")
        return SecretStr(key)

    @field_validator(
        "minio_root_user",
        "minio_root_password",
        "minio_app_access_key",
        "minio_app_secret_key",
    )
    @classmethod
    def require_storage_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().strip()
        if len(secret) < 8 or secret.casefold().startswith(
            ("replace-", "change-me", "changeme", "your-")
        ):
            raise ValueError("Object-storage credentials must be non-placeholder")
        return SecretStr(secret)

    @field_validator("redis_url")
    @classmethod
    def require_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        return value

    @field_validator("minio_endpoint")
    @classmethod
    def require_structured_minio_endpoint(cls, value: str) -> str:
        endpoint = value.strip()
        if "://" in endpoint or any(character in endpoint for character in "/?#@"):
            raise ValueError("MINIO_ENDPOINT must be host:port without URL syntax")
        return endpoint


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""
    return Settings()
