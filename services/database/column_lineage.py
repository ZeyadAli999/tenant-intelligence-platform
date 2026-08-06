"""Scope-aware output lineage from final positions to approved base columns."""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlglot import exp
from sqlglot.optimizer.scope import Scope, build_scope

from services.database.permission_resolver import MASK_STRENGTH, EffectiveSchema


class ColumnLineageError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BaseColumnProvenance:
    table_id: UUID
    column_id: UUID
    qualified_name: str
    mask_type: str | None


@dataclass(frozen=True)
class OutputColumnLineage:
    position: int
    output_name: str
    sources: tuple[BaseColumnProvenance, ...]
    mask_type: str | None


@dataclass(frozen=True)
class ColumnLineage:
    outputs: tuple[OutputColumnLineage, ...]

    @property
    def masking_plan(self) -> tuple[str | None, ...]:
        return tuple(output.mask_type for output in self.outputs)


class ColumnLineageAnalyzer:
    """Resolve each final output through CTE, subquery, and set-operation scopes."""

    def __init__(self, allowed: EffectiveSchema) -> None:
        self.allowed = allowed
        self.tables = allowed.table_by_qualified_name()
        self._cache: dict[int, tuple[OutputColumnLineage, ...]] = {}

    def analyze(self, expression: exp.Expression) -> ColumnLineage:
        root = build_scope(expression)
        if root is None:
            raise ColumnLineageError(
                "LINEAGE_UNRESOLVED", "Result-column lineage could not be resolved"
            )
        outputs = self._scope_outputs(root)
        self._reject_duplicate_names(outputs)
        return ColumnLineage(outputs)

    def _scope_outputs(self, scope: Scope) -> tuple[OutputColumnLineage, ...]:
        cache_key = id(scope)
        if cache_key in self._cache:
            return self._cache[cache_key]
        if isinstance(scope.expression, (exp.Union, exp.Intersect, exp.Except)):
            outputs = self._set_operation_outputs(scope)
        elif isinstance(scope.expression, exp.Select):
            outputs = tuple(
                self._projection_lineage(scope, position, projection)
                for position, projection in enumerate(scope.expression.expressions)
            )
        else:
            raise ColumnLineageError(
                "LINEAGE_UNRESOLVED", "Result-column lineage could not be resolved"
            )
        self._reject_duplicate_names(outputs)
        self._cache[cache_key] = outputs
        return outputs

    def _set_operation_outputs(self, scope: Scope) -> tuple[OutputColumnLineage, ...]:
        branches = [self._scope_outputs(branch) for branch in scope.union_scopes]
        if not branches or any(len(branch) != len(branches[0]) for branch in branches):
            raise ColumnLineageError(
                "LINEAGE_UNRESOLVED", "Set-operation lineage could not be resolved"
            )
        merged: list[OutputColumnLineage] = []
        for position in range(len(branches[0])):
            sources = self._merge_sources(
                source for branch in branches for source in branch[position].sources
            )
            merged.append(
                OutputColumnLineage(
                    position=position,
                    output_name=branches[0][position].output_name,
                    sources=sources,
                    mask_type=self._strongest_mask(sources),
                )
            )
        return tuple(merged)

    def _projection_lineage(
        self, scope: Scope, position: int, projection: exp.Expression
    ) -> OutputColumnLineage:
        expression = projection.unalias()
        sources = self._expression_sources(scope, expression)
        output_name = projection.alias_or_name or expression.key
        if not output_name:
            output_name = f"column_{position + 1}"
        return OutputColumnLineage(
            position=position,
            output_name=output_name,
            sources=sources,
            mask_type=self._strongest_mask(sources),
        )

    def _expression_sources(
        self, scope: Scope, expression: exp.Expression
    ) -> tuple[BaseColumnProvenance, ...]:
        resolved: list[BaseColumnProvenance] = []
        for column in expression.find_all(exp.Column):
            resolved.extend(self._resolve_column(scope, column))
        return self._merge_sources(resolved)

    def _resolve_column(
        self, scope: Scope, column: exp.Column
    ) -> tuple[BaseColumnProvenance, ...]:
        if column.table:
            source = scope.sources.get(column.table)
            candidates = self._source_column(source, column.name)
        else:
            candidates = []
            for source in scope.sources.values():
                candidates.extend(self._source_column(source, column.name))
        unique = self._merge_sources(candidates)
        if not unique:
            raise ColumnLineageError(
                "LINEAGE_UNRESOLVED", "A result column has unresolved provenance"
            )
        if self._candidate_origins(scope, column) > 1:
            raise ColumnLineageError(
                "LINEAGE_UNRESOLVED", "A result column has ambiguous provenance"
            )
        return unique

    def _candidate_origins(self, scope: Scope, column: exp.Column) -> int:
        sources = (
            [scope.sources.get(column.table)]
            if column.table
            else list(scope.sources.values())
        )
        return sum(bool(self._source_column(source, column.name)) for source in sources)

    def _source_column(
        self, source: exp.Table | Scope | None, column_name: str
    ) -> list[BaseColumnProvenance]:
        if isinstance(source, Scope):
            matches = [
                output
                for output in self._scope_outputs(source)
                if output.output_name.casefold() == column_name.casefold()
            ]
            if len(matches) > 1:
                raise ColumnLineageError(
                    "LINEAGE_UNRESOLVED", "A derived column has ambiguous provenance"
                )
            return list(matches[0].sources) if matches else []
        if not isinstance(source, exp.Table):
            return []
        matches = [
            table
            for (schema_name, table_name), table in self.tables.items()
            if table_name == source.name and (not source.db or schema_name == source.db)
        ]
        if len(matches) != 1:
            return []
        table = matches[0]
        column = next(
            (
                item
                for item in table.columns
                if item.readable
                and item.metadata.column_name.casefold() == column_name.casefold()
            ),
            None,
        )
        if column is None:
            return []
        return [
            BaseColumnProvenance(
                table_id=table.metadata.id,
                column_id=column.metadata.id,
                qualified_name=(
                    f"{table.schema.schema_name}.{table.metadata.table_name}."
                    f"{column.metadata.column_name}"
                ),
                mask_type=column.mask_type,
            )
        ]

    @staticmethod
    def _merge_sources(
        sources: Iterable[BaseColumnProvenance],
    ) -> tuple[BaseColumnProvenance, ...]:
        merged: dict[tuple[UUID, UUID], BaseColumnProvenance] = {}
        for source in sources:
            merged[(source.table_id, source.column_id)] = source
        return tuple(sorted(merged.values(), key=lambda source: source.qualified_name))

    @staticmethod
    def _strongest_mask(
        sources: tuple[BaseColumnProvenance, ...],
    ) -> str | None:
        return max(
            (source.mask_type for source in sources),
            key=lambda mask: MASK_STRENGTH[mask],
            default=None,
        )

    @staticmethod
    def _reject_duplicate_names(outputs: tuple[OutputColumnLineage, ...]) -> None:
        names = [output.output_name.casefold() for output in outputs]
        if len(names) != len(set(names)):
            raise ColumnLineageError(
                "DUPLICATE_OUTPUT_COLUMN",
                "Result columns must have unique output names",
            )
