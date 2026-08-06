"""Strict row-filter validation and parameterized SQLGlot compilation."""

from dataclasses import dataclass
from uuid import UUID

from sqlglot import exp

from app.exceptions import ApplicationError
from models import ColumnPermission, DatabaseColumn
from schemas.permissions import RowFilterDSL


class InvalidRowFilterError(ApplicationError):
    status_code = 400
    detail = "Invalid row filter"


@dataclass(frozen=True)
class RuntimeFilterContext:
    user_id: UUID
    tenant_id: UUID


@dataclass(frozen=True)
class CompiledFilter:
    expression: exp.Expression
    parameters: dict[str, object]
    audit: dict[str, object]


def normalize_row_filter(value: RowFilterDSL | None) -> dict[str, object]:
    return {} if value is None else value.model_dump(mode="json")


def validate_row_filter(
    value: RowFilterDSL | None,
    *,
    columns: list[DatabaseColumn],
    explicit_permissions: list[ColumnPermission],
) -> dict[str, object]:
    if value is None:
        return {}
    by_id = {column.id: column for column in columns}
    capabilities = {item.column_id: item.can_filter for item in explicit_permissions}
    for clause in value.all:
        column = by_id.get(clause.column_id)
        if column is None:
            raise InvalidRowFilterError
        if explicit_permissions:
            allowed = capabilities.get(column.id, False)
        else:
            allowed = not column.is_sensitive
        if not allowed:
            raise InvalidRowFilterError
        if clause.operator in (
            "gt",
            "gte",
            "lt",
            "lte",
        ) and column.data_type.casefold() in (
            "boolean",
            "json",
            "jsonb",
        ):
            raise InvalidRowFilterError
    return value.model_dump(mode="json")


def compile_row_filter(
    normalized: dict[str, object],
    *,
    columns: dict[UUID, DatabaseColumn],
    table_alias: str,
    context: RuntimeFilterContext,
    parameter_prefix: str,
) -> CompiledFilter | None:
    if not normalized:
        return None
    clauses = normalized.get("all")
    if normalized.get("version") != 1 or not isinstance(clauses, list) or not clauses:
        raise InvalidRowFilterError
    expressions: list[exp.Expression] = []
    parameters: dict[str, object] = {}
    audit_clauses: list[dict[str, object]] = []
    for index, raw in enumerate(clauses):
        if not isinstance(raw, dict):
            raise InvalidRowFilterError
        try:
            column_id = UUID(str(raw["column_id"]))
            operator = str(raw["operator"])
            column = columns[column_id]
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidRowFilterError from exc
        left = exp.column(column.column_name, table=table_alias)
        if operator == "is_null":
            expression = exp.Is(this=left, expression=exp.Null())
        elif operator == "is_not_null":
            expression = exp.Not(this=exp.Is(this=left, expression=exp.Null()))
        else:
            value_spec = raw.get("value")
            if not isinstance(value_spec, dict):
                raise InvalidRowFilterError
            value = value_spec.get("value")
            if value_spec.get("source") == "context":
                value = (
                    context.user_id if value == "current_user_id" else context.tenant_id
                )
            name = f"{parameter_prefix}_{index}"
            if operator in ("in", "not_in"):
                if not isinstance(value, list) or not value:
                    raise InvalidRowFilterError
                placeholders = []
                for item_index, item in enumerate(value):
                    item_name = f"{name}_{item_index}"
                    parameters[item_name] = item
                    placeholders.append(exp.Placeholder(this=item_name))
                expression = exp.In(this=left, expressions=placeholders)
                if operator == "not_in":
                    expression = exp.Not(this=expression)
            else:
                parameters[name] = str(value) if isinstance(value, UUID) else value
                right = exp.Placeholder(this=name)
                operator_types = {
                    "eq": exp.EQ,
                    "neq": exp.NEQ,
                    "gt": exp.GT,
                    "gte": exp.GTE,
                    "lt": exp.LT,
                    "lte": exp.LTE,
                }
                try:
                    expression = operator_types[operator](this=left, expression=right)
                except KeyError as exc:
                    raise InvalidRowFilterError from exc
        expressions.append(expression)
        audit_clauses.append({"column_id": str(column_id), "operator": operator})
    combined = expressions[0]
    for expression in expressions[1:]:
        combined = exp.and_(combined, expression)
    return CompiledFilter(
        expression=combined,
        parameters=parameters,
        audit={"version": 1, "clauses": audit_clauses},
    )
