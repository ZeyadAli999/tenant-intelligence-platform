"""Deterministic question-ranked subset of the effective allowed schema."""

import json
import re
from dataclasses import dataclass

from services.database.permission_resolver import EffectiveSchema, EffectiveTable

TOKEN = re.compile(r"[a-z0-9_]+")
STOP_WORDS = {
    "a",
    "all",
    "and",
    "by",
    "for",
    "from",
    "in",
    "me",
    "of",
    "on",
    "show",
    "the",
    "to",
    "what",
    "with",
}


@dataclass(frozen=True)
class RetrievedSchema:
    serialized: str
    table_names: tuple[str, ...]
    column_names: tuple[str, ...]


class AllowedSchemaRetriever:
    def __init__(self, max_tables: int, max_columns: int) -> None:
        self.max_tables = max_tables
        self.max_columns = max_columns

    def retrieve(
        self, question: str, allowed: EffectiveSchema
    ) -> RetrievedSchema | None:
        terms = _normalized_terms(question) - STOP_WORDS
        scored: list[tuple[int, str, EffectiveTable]] = []
        for table in allowed.tables:
            haystack = _normalized_terms(table.metadata.table_name)
            description = (table.metadata.description or "").casefold()
            column_terms = {
                term
                for column in table.columns
                if column.readable
                for term in _normalized_terms(column.metadata.column_name)
            }
            score = (
                5 * len(terms & haystack)
                + 2 * len(terms & column_terms)
                + sum(term in description for term in terms)
            )
            if score:
                scored.append(
                    (
                        score,
                        f"{table.schema.schema_name}.{table.metadata.table_name}",
                        table,
                    )
                )
        if not scored:
            return None
        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [item[2] for item in scored[: self.max_tables]]
        selected_keys = {
            (item.schema.schema_name, item.metadata.table_name) for item in selected
        }
        by_name = {
            (item.schema.schema_name, item.metadata.table_name): item
            for item in allowed.tables
        }
        # Add only visible FK neighbors, deterministically and within the same cap.
        for table in tuple(selected):
            if len(selected) >= self.max_tables:
                break
            for column in table.columns:
                key = (
                    column.metadata.referenced_schema,
                    column.metadata.referenced_table,
                )
                if column.readable and key in by_name and key not in selected_keys:
                    selected.append(by_name[key])
                    selected_keys.add(key)
                    if len(selected) >= self.max_tables:
                        break
        visible_names = {
            (item.schema.schema_name, item.metadata.table_name)
            for item in allowed.tables
        }
        remaining = self.max_columns
        payload_tables: list[dict[str, object]] = []
        visible_columns: list[str] = []
        for table in selected:
            columns = []
            for column in table.columns:
                if not column.readable or remaining <= 0:
                    continue
                reference_visible = (
                    column.metadata.referenced_schema,
                    column.metadata.referenced_table,
                ) in visible_names
                item = {
                    "name": column.metadata.column_name,
                    "type": column.metadata.data_type,
                    "filterable": column.filterable,
                    "aggregatable": column.aggregatable,
                    "masked": column.mask_type is not None,
                    "primary_key": column.metadata.is_primary_key,
                }
                if column.metadata.is_foreign_key and reference_visible:
                    item["references"] = (
                        f"{column.metadata.referenced_schema}.{column.metadata.referenced_table}.{column.metadata.referenced_column}"
                    )
                columns.append(item)
                visible_columns.append(
                    f"{table.schema.schema_name}.{table.metadata.table_name}.{column.metadata.column_name}"
                )
                remaining -= 1
            payload_tables.append(
                {
                    "schema": table.schema.schema_name,
                    "name": table.metadata.table_name,
                    "type": table.metadata.table_type,
                    "description": table.metadata.description,
                    "columns": columns,
                }
            )
        payload = {"metadata_is_untrusted": True, "tables": payload_tables}
        return RetrievedSchema(
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            tuple(
                f"{table.schema.schema_name}.{table.metadata.table_name}"
                for table in selected
            ),
            tuple(visible_columns),
        )


def _normalized_terms(value: str) -> set[str]:
    tokens = set(TOKEN.findall(value.casefold()))
    expanded = {part for token in tokens for part in token.split("_") if part}
    return expanded | {
        term[:-1] for term in expanded if len(term) > 3 and term.endswith("s")
    }
