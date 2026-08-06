"""SQLGlot PostgreSQL AST validation against effective capabilities."""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.config import Settings, get_settings
from services.database.column_lineage import ColumnLineageAnalyzer, ColumnLineageError
from services.database.permission_resolver import (
    EffectiveColumn,
    EffectiveSchema,
    EffectiveTable,
)

SAFE_FUNCTIONS = {
    "ABS",
    "AVG",
    "CAST",
    "COALESCE",
    "COUNT",
    "DATE_TRUNC",
    "EXTRACT",
    "GREATEST",
    "LEAST",
    "LENGTH",
    "LOWER",
    "MAX",
    "MIN",
    "NULLIF",
    "ROUND",
    "SUM",
    "UPPER",
}
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    expression: exp.Expression | None
    normalized_sql: str | None
    errors: tuple[ValidationError, ...]
    referenced_tables: tuple[str, ...]
    referenced_columns: tuple[str, ...]


class QueryValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, sql: str, allowed: EffectiveSchema) -> ValidationResult:
        errors: list[ValidationError] = []
        try:
            expressions = sqlglot.parse(sql, read="postgres")
        except ParseError:
            return self._rejected("INVALID_SQL", "SQL could not be parsed")
        if len(expressions) != 1 or expressions[0] is None:
            return self._rejected(
                "MULTIPLE_STATEMENTS", "Exactly one statement is required"
            )
        expression = expressions[0]
        if any(node.comments for node in expression.walk()):
            errors.append(
                ValidationError("COMMENTS_BLOCKED", "SQL comments are not allowed")
            )
        if not isinstance(
            expression, (exp.Select, exp.Union, exp.Intersect, exp.Except)
        ):
            errors.append(
                ValidationError(
                    "READ_ONLY_REQUIRED", "Only read-only SELECT queries are allowed"
                )
            )
        blocked_nodes = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Merge,
            exp.Create,
            exp.Drop,
            exp.Alter,
            exp.Command,
            exp.Copy,
            exp.Grant,
            exp.Revoke,
            exp.Lock,
            exp.Into,
        )
        if any(isinstance(node, blocked_nodes) for node in expression.walk()):
            errors.append(
                ValidationError("BLOCKED_OPERATION", "The SQL operation is not allowed")
            )
        if any(isinstance(node, exp.Star) for node in expression.walk()):
            errors.append(ValidationError("STAR_BLOCKED", "SELECT star is not allowed"))
        errors.extend(self._complexity_errors(expression))
        tables = allowed.table_by_qualified_name()
        table_names: set[str] = set()
        column_names: set[str] = set()
        for scope in traverse_scope(expression):
            scope_errors, scope_tables, scope_columns = self._validate_scope(
                scope, tables
            )
            errors.extend(scope_errors)
            table_names.update(scope_tables)
            column_names.update(scope_columns)
        for function in expression.find_all(exp.Func):
            # SQLGlot represents CASE branches as exp.If nodes. They are part of
            # the CASE AST, not calls to an unknown PostgreSQL function.
            if isinstance(function, (exp.Binary, exp.Case, exp.If)):
                continue
            name = (
                function.name.upper()
                if isinstance(function, exp.Anonymous)
                else function.sql_name().upper()
            )
            if name not in SAFE_FUNCTIONS:
                errors.append(
                    ValidationError(
                        "FUNCTION_BLOCKED", "The SQL function is not allowed"
                    )
                )
        try:
            ColumnLineageAnalyzer(allowed).analyze(expression)
        except ColumnLineageError as exc:
            errors.append(ValidationError(exc.code, exc.message))
        if errors:
            unique = tuple(dict.fromkeys((item.code, item.message) for item in errors))
            return ValidationResult(
                accepted=False,
                expression=None,
                normalized_sql=None,
                errors=tuple(ValidationError(*item) for item in unique),
                referenced_tables=tuple(sorted(table_names)),
                referenced_columns=tuple(sorted(column_names)),
            )
        return ValidationResult(
            accepted=True,
            expression=expression,
            normalized_sql=expression.sql(dialect="postgres", pretty=False),
            errors=(),
            referenced_tables=tuple(sorted(table_names)),
            referenced_columns=tuple(sorted(column_names)),
        )

    def _validate_scope(
        self, scope: Scope, allowed: dict[tuple[str, str], EffectiveTable]
    ) -> tuple[list[ValidationError], set[str], set[str]]:
        errors: list[ValidationError] = []
        aliases: dict[str, EffectiveTable] = {}
        referenced_tables: set[str] = set()
        referenced_columns: set[str] = set()
        for alias, source in scope.sources.items():
            if not isinstance(source, exp.Table):
                continue
            schema_name = source.db
            if (
                schema_name.casefold() in SYSTEM_SCHEMAS
                or schema_name.casefold().startswith("pg_")
            ):
                errors.append(
                    ValidationError(
                        "SYSTEM_SCHEMA_BLOCKED", "System schemas are not allowed"
                    )
                )
                continue
            matches = [
                table
                for (schema, name), table in allowed.items()
                if name == source.name and (not schema_name or schema == schema_name)
            ]
            if len(matches) != 1:
                errors.append(
                    ValidationError(
                        "TABLE_NOT_ALLOWED", "A referenced table is not allowed"
                    )
                )
                continue
            table = matches[0]
            aliases[alias] = table
            referenced_tables.add(
                f"{table.schema.schema_name}.{table.metadata.table_name}"
            )
        for column in scope.columns:
            if not column.name:
                continue
            table: EffectiveTable | None = None
            capability: EffectiveColumn | None = None
            if column.table:
                table = aliases.get(column.table)
                if table is None:
                    # A derived scope or CTE is validated at its base scopes.
                    continue
                capability = next(
                    (
                        item
                        for item in table.columns
                        if item.metadata.column_name == column.name
                    ),
                    None,
                )
            else:
                candidates = [
                    (item, candidate)
                    for item in aliases.values()
                    for candidate in item.columns
                    if candidate.metadata.column_name == column.name
                ]
                if len(candidates) == 1:
                    table, capability = candidates[0]
                elif aliases:
                    errors.append(
                        ValidationError(
                            "AMBIGUOUS_OR_HIDDEN_COLUMN",
                            "A column is ambiguous or not allowed",
                        )
                    )
                    continue
                else:
                    continue
            if capability is None or table is None or not capability.readable:
                errors.append(
                    ValidationError(
                        "COLUMN_NOT_ALLOWED", "A referenced column is not allowed"
                    )
                )
                continue
            referenced_columns.add(
                f"{table.schema.schema_name}.{table.metadata.table_name}.{capability.metadata.column_name}"
            )
            if (
                self._has_scope_ancestor(
                    column, (exp.Where, exp.Join, exp.Having), scope.expression
                )
                and not capability.filterable
            ):
                errors.append(
                    ValidationError(
                        "COLUMN_NOT_FILTERABLE", "A column cannot be used for filtering"
                    )
                )
            if (
                self._has_scope_ancestor(column, (exp.AggFunc,), scope.expression)
                and not capability.aggregatable
            ):
                errors.append(
                    ValidationError(
                        "COLUMN_NOT_AGGREGATABLE", "A column cannot be aggregated"
                    )
                )
        return errors, referenced_tables, referenced_columns

    @staticmethod
    def _has_scope_ancestor(
        node: exp.Expression,
        kinds: tuple[type[exp.Expression], ...],
        boundary: exp.Expression,
    ) -> bool:
        current = node.parent
        while current is not None and current is not boundary:
            if isinstance(current, kinds):
                return True
            current = current.parent
        return isinstance(current, kinds)

    def _complexity_errors(self, expression: exp.Expression) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if (
            sum(1 for _ in expression.find_all(exp.Join))
            > self.settings.safe_query_max_joins
        ):
            errors.append(
                ValidationError("TOO_MANY_JOINS", "Query join limit exceeded")
            )
        if (
            sum(1 for _ in expression.find_all(exp.CTE))
            > self.settings.safe_query_max_ctes
        ):
            errors.append(ValidationError("TOO_MANY_CTES", "Query CTE limit exceeded"))
        if any(
            len(select.expressions) > self.settings.safe_query_max_selected_columns
            for select in expression.find_all(exp.Select)
        ):
            errors.append(
                ValidationError("TOO_MANY_COLUMNS", "Selected-column limit exceeded")
            )
        for subquery in expression.find_all(exp.Subquery):
            depth = 0
            current = subquery.parent
            while current is not None:
                if isinstance(current, exp.Subquery):
                    depth += 1
                current = current.parent
            if depth + 1 > self.settings.safe_query_max_subquery_depth:
                errors.append(
                    ValidationError(
                        "SUBQUERY_TOO_DEEP", "Subquery depth limit exceeded"
                    )
                )
                break
        return errors

    @staticmethod
    def _rejected(code: str, message: str) -> ValidationResult:
        return ValidationResult(
            False, None, None, (ValidationError(code, message),), (), ()
        )


def sanitized_sql(sql: str) -> str:
    try:
        expressions = sqlglot.parse(sql, read="postgres")
        if len(expressions) != 1:
            return "[multiple statements removed]"
        expression = expressions[0].copy()
        expression = expression.transform(
            lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node
        )
        return expression.sql(dialect="postgres", pretty=False)
    except Exception:  # noqa: BLE001 - sanitization must never expose the input
        return "[unparseable SQL removed]"
