"""AST-only mandatory row filters and query limits."""

from dataclasses import dataclass

from sqlglot import exp

from app.config import Settings, get_settings
from services.database.permission_resolver import EffectiveSchema
from services.database.row_filter import RuntimeFilterContext, compile_row_filter


@dataclass(frozen=True)
class RewrittenQuery:
    sql: str
    parameters: dict[str, object]
    applied_filters: dict[str, object]
    truncated_limit: bool


class QueryRewriter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def rewrite(
        self,
        expression: exp.Expression,
        allowed: EffectiveSchema,
        *,
        context: RuntimeFilterContext,
    ) -> RewrittenQuery:
        tree = expression.copy()
        table_map = allowed.table_by_qualified_name()
        parameters: dict[str, object] = {}
        applied: dict[str, object] = {}
        counter = 0

        def transform(node: exp.Expression) -> exp.Expression:
            nonlocal counter
            if not isinstance(node, exp.Table):
                return node
            matches = [
                item
                for (schema, name), item in table_map.items()
                if name == node.name and (not node.db or schema == node.db)
            ]
            if len(matches) != 1 or not matches[0].row_filters:
                return node
            table = matches[0]
            original_alias = node.alias_or_name
            inner_alias = f"_authorized_{counter}"
            filter_expressions: list[exp.Expression] = []
            filter_audits: list[dict[str, object]] = []
            column_map = {
                column.metadata.id: column.metadata for column in table.columns
            }
            for filter_index, normalized in enumerate(table.row_filters):
                compiled = compile_row_filter(
                    normalized,
                    columns=column_map,
                    table_alias=inner_alias,
                    context=context,
                    parameter_prefix=f"rf_{counter}_{filter_index}",
                )
                if compiled is not None:
                    filter_expressions.append(compiled.expression)
                    parameters.update(compiled.parameters)
                    filter_audits.append(compiled.audit)
            if not filter_expressions:
                return node
            predicate = filter_expressions[0]
            for item in filter_expressions[1:]:
                predicate = exp.or_(predicate, item)
            source = exp.Table(
                this=exp.to_identifier(table.metadata.table_name),
                db=exp.to_identifier(table.schema.schema_name),
                alias=exp.TableAlias(this=exp.to_identifier(inner_alias)),
            )
            filtered = exp.select("*").from_(source).where(predicate)
            applied[
                f"{table.schema.schema_name}.{table.metadata.table_name}#{counter}"
            ] = {"groups": filter_audits}
            counter += 1
            return exp.Subquery(
                this=filtered,
                alias=exp.TableAlias(this=exp.to_identifier(original_alias)),
            )

        tree = tree.transform(transform)
        truncated = self._apply_limit(tree)
        rendered = tree.sql(dialect="postgres", pretty=False)
        for name in parameters:
            rendered = rendered.replace(f"%({name})s", f":{name}")
        return RewrittenQuery(rendered, parameters, applied, truncated)

    def _apply_limit(self, tree: exp.Expression) -> bool:
        # Fetch one sentinel row past the public cap so the adapter can report
        # truncation without ever returning more than the configured maximum.
        fetch_limit = self.settings.safe_query_max_rows + 1
        limit = tree.args.get("limit")
        if limit is None:
            tree.set(
                "limit",
                exp.Limit(expression=exp.Literal.number(fetch_limit)),
            )
            return True
        value = limit.expression
        if not isinstance(value, exp.Literal) or not value.is_int:
            raise ValueError("Unsafe LIMIT")
        if int(value.this) > fetch_limit:
            value.replace(exp.Literal.number(fetch_limit))
            return True
        return False
