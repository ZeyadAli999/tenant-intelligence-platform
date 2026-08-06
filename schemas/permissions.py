"""Strict permission, row-filter, and allowed-schema API contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from schemas.common import APIModel

RowOperator = Literal[
    "eq", "neq", "in", "not_in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"
]
MaskType = Literal["redact", "partial", "hash", "null"]


class RowFilterValue(APIModel):
    source: Literal["literal", "context"]
    value: object

    @model_validator(mode="after")
    def validate_context(self) -> "RowFilterValue":
        if self.source == "context" and self.value not in (
            "current_user_id",
            "current_tenant_id",
        ):
            raise ValueError("Unsupported row-filter context value")
        return self


class RowFilterClause(APIModel):
    column_id: UUID
    operator: RowOperator
    value: RowFilterValue | None = None

    @model_validator(mode="after")
    def validate_operator_value(self) -> "RowFilterClause":
        null_operator = self.operator in ("is_null", "is_not_null")
        if null_operator and self.value is not None:
            raise ValueError("Null operators do not accept a value")
        if not null_operator and self.value is None:
            raise ValueError("This operator requires a value")
        if self.operator in ("in", "not_in") and (
            self.value is None
            or self.value.source != "literal"
            or not isinstance(self.value.value, list)
            or not self.value.value
        ):
            raise ValueError("Set operators require a non-empty literal list")
        return self


class RowFilterDSL(APIModel):
    version: Literal[1]
    all: list[RowFilterClause] = Field(min_length=1, max_length=20)


class TablePermissionCreateRequest(APIModel):
    role_id: UUID | None = None
    user_id: UUID | None = None
    connection_id: UUID
    table_id: UUID
    can_read: bool = True
    row_filter: RowFilterDSL | None = None

    @model_validator(mode="after")
    def exactly_one_subject(self) -> "TablePermissionCreateRequest":
        if (self.role_id is None) == (self.user_id is None):
            raise ValueError("Exactly one permission subject is required")
        return self


class TablePermissionUpdateRequest(APIModel):
    can_read: bool | None = None
    row_filter: RowFilterDSL | None = None


class TablePermissionResponse(APIModel):
    id: UUID
    role_id: UUID | None
    user_id: UUID | None
    connection_id: UUID
    table_id: UUID
    can_read: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    row_filter: dict[str, object]
    created_at: datetime


class TablePermissionListResponse(APIModel):
    items: list[TablePermissionResponse]
    total: int
    page: int
    page_size: int


class ColumnPermissionItem(APIModel):
    column_id: UUID
    can_read: bool = True
    can_filter: bool = True
    can_aggregate: bool = True
    mask_type: MaskType | None = None


class ColumnPermissionReplaceRequest(APIModel):
    items: list[ColumnPermissionItem] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_columns(self) -> "ColumnPermissionReplaceRequest":
        ids = [item.column_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Column permissions must be unique")
        return self


class ColumnPermissionResponse(APIModel):
    id: UUID
    column_id: UUID
    can_read: bool
    can_filter: bool
    can_aggregate: bool
    mask_type: MaskType | None


class ColumnPermissionListResponse(APIModel):
    items: list[ColumnPermissionResponse]


class AllowedColumnResponse(APIModel):
    id: UUID
    name: str
    data_type: str
    readable: bool
    filterable: bool
    aggregatable: bool
    mask_type: MaskType | None
    is_primary_key: bool
    is_foreign_key: bool
    referenced_schema: str | None
    referenced_table: str | None
    referenced_column: str | None


class AllowedTableResponse(APIModel):
    id: UUID
    schema_name: str
    table_name: str
    table_type: str
    columns: list[AllowedColumnResponse]


class AllowedSchemaResponse(APIModel):
    connection_id: UUID
    tables: list[AllowedTableResponse]
