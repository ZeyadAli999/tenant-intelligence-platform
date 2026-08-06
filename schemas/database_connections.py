"""Safe request and response contracts for runtime database connections."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from schemas.common import APIModel


class PostgreSQLSSLSettings(APIModel):
    mode: Literal["require", "verify-ca", "verify-full"] = "verify-full"


class PostgreSQLConnectionOptions(APIModel):
    application_name: str = Field(
        default="text-to-sql-schema-discovery",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_. -]+$",
    )


class DatabaseConnectionCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    database_type: str = Field(min_length=1, max_length=50)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=1024)
    ssl_enabled: bool = False
    ssl_settings: PostgreSQLSSLSettings = Field(default_factory=PostgreSQLSSLSettings)
    connection_options: PostgreSQLConnectionOptions = Field(
        default_factory=PostgreSQLConnectionOptions
    )

    @field_validator("name", "database_type", "host", "database_name", "username")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class DatabaseConnectionUpdateRequest(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    database_type: str | None = Field(default=None, min_length=1, max_length=50)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: SecretStr | None = Field(default=None, min_length=1, max_length=1024)
    ssl_enabled: bool | None = None
    ssl_settings: PostgreSQLSSLSettings | None = None
    connection_options: PostgreSQLConnectionOptions | None = None

    @field_validator("name", "database_type", "host", "database_name", "username")
    @classmethod
    def reject_blank_optional_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("value must not be blank")
        return value


class DatabaseConnectionResponse(APIModel):
    id: UUID
    name: str
    database_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool
    status: str
    last_tested_at: datetime | None
    last_test_message: str | None
    schema_sync_status: str
    last_schema_sync_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DatabaseConnectionListResponse(APIModel):
    items: list[DatabaseConnectionResponse]
    total: int
    page: int
    page_size: int


class ConnectionTestResponse(APIModel):
    success: bool
    status: str
    error_code: str | None
    message: str
    tested_at: datetime


class SchemaSyncResponse(APIModel):
    success: bool
    status: str
    message: str
    schema_count: int
    table_count: int
    column_count: int
    synced_at: datetime | None


class DatabaseSchemaResponse(APIModel):
    id: UUID
    schema_name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class DatabaseSchemaListResponse(APIModel):
    items: list[DatabaseSchemaResponse]
    total: int
    page: int
    page_size: int


class DatabaseColumnResponse(APIModel):
    id: UUID
    column_name: str
    data_type: str
    ordinal_position: int | None
    is_nullable: bool | None
    is_primary_key: bool
    is_foreign_key: bool
    referenced_schema: str | None
    referenced_table: str | None
    referenced_column: str | None
    description: str | None


class DatabaseTableResponse(APIModel):
    id: UUID
    schema_name: str
    table_name: str
    table_type: str
    description: str | None
    estimated_row_count: int | None
    primary_key_columns: list[str]
    is_enabled: bool
    is_sensitive: bool
    columns: list[DatabaseColumnResponse]
    created_at: datetime
    updated_at: datetime


class DatabaseTableListResponse(APIModel):
    items: list[DatabaseTableResponse]
    total: int
    page: int
    page_size: int
