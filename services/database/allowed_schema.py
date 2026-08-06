"""Permission-filtered schema projection with hidden relationships removed."""

from schemas.permissions import (
    AllowedColumnResponse,
    AllowedSchemaResponse,
    AllowedTableResponse,
)
from services.database.permission_resolver import EffectiveSchema


def allowed_schema_response(schema: EffectiveSchema) -> AllowedSchemaResponse:
    visible_tables = {
        (table.schema.schema_name, table.metadata.table_name): table
        for table in schema.tables
    }
    visible_columns = {
        (
            table.schema.schema_name,
            table.metadata.table_name,
            column.metadata.column_name,
        )
        for table in schema.tables
        for column in table.columns
        if column.readable
    }
    tables: list[AllowedTableResponse] = []
    for table in schema.tables:
        columns: list[AllowedColumnResponse] = []
        for column in table.columns:
            if not column.readable:
                continue
            reference = (
                column.metadata.referenced_schema,
                column.metadata.referenced_table,
                column.metadata.referenced_column,
            )
            reference_visible = reference in visible_columns
            columns.append(
                AllowedColumnResponse(
                    id=column.metadata.id,
                    name=column.metadata.column_name,
                    data_type=column.metadata.data_type,
                    readable=True,
                    filterable=column.filterable,
                    aggregatable=column.aggregatable,
                    mask_type=column.mask_type,
                    is_primary_key=column.metadata.is_primary_key,
                    is_foreign_key=column.metadata.is_foreign_key and reference_visible,
                    referenced_schema=column.metadata.referenced_schema
                    if reference_visible
                    else None,
                    referenced_table=column.metadata.referenced_table
                    if reference_visible
                    else None,
                    referenced_column=column.metadata.referenced_column
                    if reference_visible
                    else None,
                )
            )
        if (
            columns
            and (table.schema.schema_name, table.metadata.table_name) in visible_tables
        ):
            tables.append(
                AllowedTableResponse(
                    id=table.metadata.id,
                    schema_name=table.schema.schema_name,
                    table_name=table.metadata.table_name,
                    table_type=table.metadata.table_type,
                    columns=columns,
                )
            )
    return AllowedSchemaResponse(connection_id=schema.connection_id, tables=tables)
