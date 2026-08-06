"""Strict row-filter DSL and mandatory AST rewrite tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlglot import parse_one

from schemas.permissions import RowFilterDSL
from services.database.query_rewriter import QueryRewriter
from services.database.row_filter import (
    InvalidRowFilterError,
    RuntimeFilterContext,
    compile_row_filter,
    validate_row_filter,
)
from tests.unit.phase3b_helpers import effective_schema


def dsl(
    column_id: object,
    *,
    operator: str = "eq",
    source: str = "literal",
    value: object = "Egypt",
) -> RowFilterDSL:
    return RowFilterDSL.model_validate(
        {
            "version": 1,
            "all": [
                {
                    "column_id": str(column_id),
                    "operator": operator,
                    "value": {"source": source, "value": value},
                }
            ],
        }
    )


def test_valid_dsl_normalizes_and_parameterizes_without_literal_sql() -> None:
    schema = effective_schema()
    country = schema.tables[0].columns[1].metadata
    normalized = validate_row_filter(
        dsl(country.id),
        columns=[item.metadata for item in schema.tables[0].columns],
        explicit_permissions=[],
    )
    compiled = compile_row_filter(
        normalized,
        columns={country.id: country},
        table_alias="c",
        context=RuntimeFilterContext(uuid4(), uuid4()),
        parameter_prefix="test",
    )
    assert compiled is not None
    assert compiled.parameters == {"test_0": "Egypt"}
    assert "Egypt" not in compiled.expression.sql(dialect="postgres")


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "all": []},
        {
            "version": 1,
            "all": [
                {
                    "column_id": str(uuid4()),
                    "operator": "raw_sql",
                    "value": {"source": "literal", "value": "1=1"},
                }
            ],
        },
        {
            "version": 1,
            "all": [
                {
                    "column_id": str(uuid4()),
                    "operator": "eq",
                    "value": {"source": "context", "value": "client_supplied"},
                }
            ],
        },
        {
            "version": 1,
            "all": [
                {
                    "column_id": str(uuid4()),
                    "operator": "is_null",
                    "value": {"source": "literal", "value": None},
                }
            ],
        },
    ],
)
def test_malformed_unknown_and_client_context_filters_are_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        RowFilterDSL.model_validate(payload)


def test_unauthorized_and_non_filterable_columns_are_rejected() -> None:
    schema = effective_schema()
    country = schema.tables[0].columns[1].metadata
    with pytest.raises(InvalidRowFilterError):
        validate_row_filter(dsl(uuid4()), columns=[country], explicit_permissions=[])


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT c.id FROM business.customers c",
        "SELECT c.id FROM business.customers c WHERE c.country = 'France' OR 1 = 1",
        "WITH x AS (SELECT id FROM business.customers) SELECT id FROM x",
        "SELECT id FROM (SELECT id FROM business.customers) x",
        "SELECT id FROM business.customers UNION SELECT id FROM business.customers",
        "SELECT a.id FROM business.customers a LEFT JOIN business.customers b ON b.id = a.id",
        "SELECT b.id FROM business.customers a RIGHT JOIN business.customers b ON b.id = a.id",
    ],
)
def test_every_table_occurrence_is_wrapped_with_mandatory_parameterized_filter(
    sql: str,
) -> None:
    base = effective_schema()
    country = base.tables[0].columns[1].metadata
    filter_value = {
        "version": 1,
        "all": [
            {
                "column_id": str(country.id),
                "operator": "eq",
                "value": {"source": "literal", "value": "Egypt"},
            }
        ],
    }
    allowed = effective_schema(row_filters=(filter_value,))
    # The helper creates fresh UUIDs, so bind the filter to its own country column.
    own_country = allowed.tables[0].columns[1].metadata
    allowed_filter = {
        "version": 1,
        "all": [{**filter_value["all"][0], "column_id": str(own_country.id)}],
    }
    allowed = type(allowed)(
        allowed.connection_id,
        (
            type(allowed.tables[0])(
                allowed.tables[0].metadata,
                allowed.tables[0].schema,
                allowed.tables[0].columns,
                (allowed_filter,),
            ),
        ),
    )
    rewritten = QueryRewriter().rewrite(
        parse_one(sql, read="postgres"),
        allowed,
        context=RuntimeFilterContext(uuid4(), uuid4()),
    )
    occurrence_count = sql.casefold().count("business.customers")
    assert rewritten.sql.count("_authorized_") >= occurrence_count
    assert "Egypt" not in rewritten.sql
    assert len(rewritten.parameters) == occurrence_count
    assert all(value == "Egypt" for value in rewritten.parameters.values())
