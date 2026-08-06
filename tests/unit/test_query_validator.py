"""Adversarial SQLGlot validation tests."""

import pytest

from app.config import Settings
from services.database.query_validator import QueryValidator
from tests.unit.phase3b_helpers import effective_schema


def codes(sql: str, **schema_options: object) -> set[str]:
    return {
        item.code
        for item in QueryValidator()
        .validate(sql, effective_schema(**schema_options))
        .errors
    }


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id, country FROM business.customers WHERE country = 'Egypt'",
        "SELECT c.id FROM business.customers AS c WHERE c.country = 'Egypt'",
        "WITH visible AS (SELECT id FROM business.customers) SELECT id FROM visible",
        "SELECT id FROM (SELECT id FROM business.customers) AS visible",
        "SELECT id FROM business.customers UNION SELECT id FROM business.customers",
        "SELECT a.id FROM business.customers a JOIN business.customers b ON b.id = a.id",
    ],
)
def test_permitted_select_shapes_are_accepted(sql: str) -> None:
    result = QueryValidator().validate(sql, effective_schema())
    assert result.accepted is True, result.errors


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT id FROM business.orders", "TABLE_NOT_ALLOWED"),
        ("SELECT tax_identifier FROM business.customers", "COLUMN_NOT_ALLOWED"),
        ("SELECT * FROM business.customers", "STAR_BLOCKED"),
        ("DELETE FROM business.customers", "READ_ONLY_REQUIRED"),
        (
            "SELECT id FROM business.customers; SELECT id FROM business.customers",
            "MULTIPLE_STATEMENTS",
        ),
        ("SELECT id /* hidden */ FROM business.customers", "COMMENTS_BLOCKED"),
        ("SELECT id INTO stolen FROM business.customers", "BLOCKED_OPERATION"),
        ("EXPLAIN ANALYZE SELECT id FROM business.customers", "READ_ONLY_REQUIRED"),
        ("SELECT id FROM business.customers FOR UPDATE", "BLOCKED_OPERATION"),
        ("SELECT oid FROM pg_catalog.pg_class", "SYSTEM_SCHEMA_BLOCKED"),
        ("SELECT pg_sleep(1) FROM business.customers", "FUNCTION_BLOCKED"),
    ],
)
def test_unsafe_sql_is_rejected(sql: str, expected: str) -> None:
    assert expected in codes(sql)


def test_filter_and_aggregate_capabilities_are_independent() -> None:
    assert "COLUMN_NOT_FILTERABLE" in codes(
        "SELECT country FROM business.customers WHERE country = 'Egypt'",
        filter_country=False,
    )
    assert "COLUMN_NOT_AGGREGATABLE" in codes(
        "SELECT SUM(id) FROM business.customers",
        aggregate_id=False,
    )


def test_complexity_limits_are_enforced() -> None:
    settings = Settings(
        safe_query_max_joins=0,
        safe_query_max_ctes=0,
        safe_query_max_subquery_depth=0,
        safe_query_max_selected_columns=1,
    )
    validator = QueryValidator(settings)
    result = validator.validate(
        "WITH x AS (SELECT id FROM business.customers) "
        "SELECT a.id, b.country FROM business.customers a "
        "JOIN business.customers b ON b.id = a.id",
        effective_schema(),
    )
    assert {item.code for item in result.errors} >= {
        "TOO_MANY_JOINS",
        "TOO_MANY_CTES",
        "TOO_MANY_COLUMNS",
    }
