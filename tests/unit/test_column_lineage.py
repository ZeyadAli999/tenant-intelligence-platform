"""Provenance-aware, output-position masking security tests."""

from dataclasses import replace

import pytest
import sqlglot

from services.database.column_lineage import ColumnLineageAnalyzer
from services.database.query_validator import QueryValidator
from services.database.result_masking import ResultMasker
from tests.unit.phase3b_helpers import effective_schema

ADVERSARIAL_QUERIES = (
    "SELECT tax_identifier AS public_value FROM business.customers",
    (
        "WITH x AS (SELECT tax_identifier AS hidden_name FROM business.customers) "
        "SELECT hidden_name FROM x"
    ),
    (
        "WITH x AS (SELECT tax_identifier AS first_name FROM business.customers), "
        "y AS (SELECT first_name AS second_name FROM x) SELECT second_name FROM y"
    ),
    (
        "SELECT renamed_value FROM (SELECT tax_identifier AS renamed_value "
        "FROM business.customers) q"
    ),
    (
        "SELECT combined FROM (SELECT tax_identifier || '-suffix' AS combined "
        "FROM business.customers) q"
    ),
    (
        "WITH x AS (SELECT COALESCE(tax_identifier, '') AS exposed "
        "FROM business.customers) SELECT exposed FROM x"
    ),
    (
        "WITH x AS (SELECT tax_identifier AS value FROM business.customers) "
        "SELECT value FROM x UNION ALL SELECT value FROM x"
    ),
    (
        "WITH x AS (SELECT CASE WHEN tax_identifier IS NULL THEN '' "
        "ELSE tax_identifier END AS transformed FROM business.customers) "
        "SELECT transformed FROM x"
    ),
    (
        "SELECT nested_again FROM (SELECT nested_once AS nested_again FROM "
        "(SELECT tax_identifier AS nested_once FROM business.customers) a) b"
    ),
    "SELECT CAST(tax_identifier AS TEXT) AS cast_value FROM business.customers",
    "SELECT LOWER(tax_identifier) AS lowered FROM business.customers",
)


@pytest.mark.parametrize("sql", ADVERSARIAL_QUERIES)
def test_sensitive_lineage_survives_alias_expression_and_derived_scopes(
    sql: str,
) -> None:
    allowed = effective_schema(hidden_sensitive=False)
    expression = sqlglot.parse_one(sql, read="postgres")
    lineage = ColumnLineageAnalyzer(allowed).analyze(expression)
    assert lineage.masking_plan == ("redact",)
    assert {source.qualified_name for source in lineage.outputs[0].sources} == {
        "business.customers.tax_identifier"
    }


def test_aggregate_lineage_uses_sensitive_source_policy() -> None:
    allowed = effective_schema(hidden_sensitive=False)
    table = allowed.tables[0]
    columns = tuple(
        replace(column, aggregatable=True)
        if column.metadata.column_name == "tax_identifier"
        else column
        for column in table.columns
    )
    allowed = replace(allowed, tables=(replace(table, columns=columns),))
    sql = "SELECT MAX(tax_identifier) AS maximum_tax FROM business.customers"
    result = QueryValidator().validate(sql, allowed)
    assert result.accepted, result.errors
    assert ColumnLineageAnalyzer(allowed).analyze(result.expression).masking_plan == (
        "redact",
    )


def test_case_is_a_supported_expression_not_an_unknown_function() -> None:
    allowed = effective_schema(hidden_sensitive=False)
    result = QueryValidator().validate(
        "SELECT CASE WHEN tax_identifier IS NULL THEN '' "
        "ELSE tax_identifier END AS transformed FROM business.customers",
        allowed,
    )
    assert result.accepted, result.errors
    assert ColumnLineageAnalyzer(allowed).analyze(result.expression).masking_plan == (
        "redact",
    )


def test_union_merges_lineage_by_position_and_strongest_mask_wins() -> None:
    allowed = effective_schema(hidden_sensitive=False)
    table = allowed.tables[0]
    columns = tuple(
        replace(column, mask_type="partial")
        if column.metadata.column_name == "country"
        else column
        for column in table.columns
    )
    allowed = replace(allowed, tables=(replace(table, columns=columns),))
    union = sqlglot.parse_one(
        "SELECT country AS value FROM business.customers "
        "UNION ALL SELECT tax_identifier AS value FROM business.customers",
        read="postgres",
    )
    combined = sqlglot.parse_one(
        "SELECT country || tax_identifier AS combined FROM business.customers",
        read="postgres",
    )
    assert ColumnLineageAnalyzer(allowed).analyze(union).masking_plan == ("redact",)
    assert ColumnLineageAnalyzer(allowed).analyze(combined).masking_plan == ("redact",)


def test_non_sensitive_derived_output_remains_unmasked() -> None:
    allowed = effective_schema(hidden_sensitive=False)
    expression = sqlglot.parse_one(
        "WITH x AS (SELECT UPPER(country) AS region FROM business.customers) "
        "SELECT region FROM x",
        read="postgres",
    )
    lineage = ColumnLineageAnalyzer(allowed).analyze(expression)
    assert lineage.masking_plan == (None,)
    masker = ResultMasker("m" * 32, max_cell_length=100, max_result_bytes=1000)
    rows, _ = masker.mask_rows(("region",), ({"region": "EGYPT"},), (None,))
    assert rows == [{"region": "EGYPT"}]


def test_unresolved_derived_provenance_fails_closed() -> None:
    result = QueryValidator().validate(
        "WITH x AS (SELECT id AS value FROM business.customers) "
        "SELECT value FROM x a JOIN x b ON a.value = b.value",
        effective_schema(),
    )
    assert result.accepted is False
    assert "LINEAGE_UNRESOLVED" in {error.code for error in result.errors}


def test_duplicate_final_output_names_are_rejected_before_execution() -> None:
    result = QueryValidator().validate(
        "SELECT a.id, b.id FROM business.customers a "
        "JOIN business.customers b ON a.id = b.id",
        effective_schema(),
    )
    assert result.accepted is False
    assert "DUPLICATE_OUTPUT_COLUMN" in {error.code for error in result.errors}
    masker = ResultMasker("m" * 32, max_cell_length=100, max_result_bytes=1000)
    with pytest.raises(ValueError, match="Unsafe result-column metadata"):
        masker.mask_rows(("id", "id"), ({"id": 1},), (None, None))


def test_result_masker_applies_plan_by_output_position_not_source_name() -> None:
    masker = ResultMasker("m" * 32, max_cell_length=100, max_result_bytes=1000)
    rows, truncated = masker.mask_rows(
        ("leaked_value", "country"),
        ({"leaked_value": "EG-SECRET-001", "country": "Egypt"},),
        ("redact", None),
    )
    assert rows == [{"leaked_value": "***", "country": "Egypt"}]
    assert truncated is False
