from __future__ import annotations

import datetime as dt
import decimal

from app.services.sql_utils import (
    classify_engine,
    row_to_jsonable,
    split_sql_statements,
    statement_type,
)


def test_split_respects_literals_and_comments() -> None:
    sql = """
    -- first statement
    SELECT 'a;b' AS value;
    /* block ; comment */
    SELECT 2 AS value;
    SELECT 'it''s fine; really' AS quoted;
    """
    statements = split_sql_statements(sql)
    assert len(statements) == 3
    assert "SELECT 'a;b'" in statements[0]
    assert "SELECT 2" in statements[1]
    assert "it''s fine; really" in statements[2]


def test_statement_type_skips_leading_comments() -> None:
    assert statement_type("-- note\n/* more */ select 1") == "SELECT"
    assert statement_type("CREATE TABLE t (id INT)") == "CREATE"


def test_classify_engine() -> None:
    assert classify_engine("SELECT * FROM local_iceberg.demo.sales") == "iceberg"
    assert classify_engine("CREATE TABLE x (id INT) USING delta") == "delta"
    assert classify_engine("SELECT * FROM spark_catalog.demo.t") == "delta"
    assert classify_engine("SELECT * FROM t", "local_iceberg") == "iceberg"
    assert classify_engine("SELECT 1", "spark_catalog") == "delta"


def test_row_to_jsonable() -> None:
    row = {
        "amount": decimal.Decimal("12.50"),
        "created": dt.datetime(2026, 1, 1, 10, 30),
        "nan": float("nan"),
        "nested": [decimal.Decimal("1.25")],
        "binary": b"abc",
    }
    encoded = row_to_jsonable(row)
    assert encoded["amount"] == "12.50"
    assert encoded["created"] == "2026-01-01T10:30:00"
    assert encoded["nan"] is None
    assert encoded["nested"] == ["1.25"]
    assert encoded["binary"] == "YWJj"
