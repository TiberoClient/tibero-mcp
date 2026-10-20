import datetime as dt
from decimal import Decimal

import pytest

from src.db.query_executor import (
    ensure_dml,
    ensure_select,
    leading_keyword,
    normalize_statement,
    quote_identifier,
    to_json_value,
)


@pytest.mark.parametrize(
    "sql, keyword",
    [
        ("select 1 from dual", "SELECT"),
        ("  -- note\n/* block */ (SELECT 1 FROM dual)", "SELECT"),
        ("WITH t AS (SELECT 1 x FROM dual) SELECT * FROM t", "WITH"),
        ("delete from t", "DELETE"),
        ("", ""),
    ],
)
def test_leading_keyword(sql, keyword):
    assert leading_keyword(sql) == keyword


def test_normalize_strips_trailing_semicolons():
    assert normalize_statement("  SELECT 1 FROM dual ;; ") == "SELECT 1 FROM dual"


def test_normalize_rejects_empty():
    with pytest.raises(ValueError):
        normalize_statement(" ; ")


@pytest.mark.parametrize("sql", ["DELETE FROM t", "DROP TABLE t", "BEGIN NULL; END", "/* x */ UPDATE t SET a = 1"])
def test_select_guard_rejects_non_select(sql):
    with pytest.raises(ValueError):
        ensure_select(sql)


@pytest.mark.parametrize("sql", ["DROP TABLE t", "TRUNCATE TABLE t", "SELECT 1 FROM dual", "GRANT SELECT ON t TO u"])
def test_dml_guard_rejects_non_dml(sql):
    with pytest.raises(ValueError):
        ensure_dml(sql)


@pytest.mark.parametrize("sql", ["INSERT INTO t VALUES (1)", "update t set a = 1", "MERGE INTO t USING s ON (1=1) WHEN MATCHED THEN UPDATE SET a = 1"])
def test_dml_guard_accepts_dml(sql):
    ensure_dml(sql)


def test_quote_identifier_escapes_quotes():
    assert quote_identifier('a"b') == '"a""b"'


def test_to_json_value():
    assert to_json_value(Decimal("42")) == 42
    assert to_json_value(Decimal("1.5")) == 1.5
    assert to_json_value(Decimal("123456789012345678901234567890")) == "123456789012345678901234567890"
    assert to_json_value(dt.date(2026, 1, 2)) == "2026-01-02"
    assert to_json_value(b"\x00\x01") == "base64:AAE="
    assert to_json_value("x" * 5000).endswith("[truncated 1000 chars]")
