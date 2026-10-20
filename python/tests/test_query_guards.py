"""SQL guard and value rules, driven by the vectors shared with the Java tests."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.db.query_executor import (
    MAX_CELL_CHARS,
    decimal_to_json,
    ensure_dml,
    ensure_select,
    leading_keyword,
    normalize_statement,
    quote_identifier,
    truncate,
    unique_labels,
)
from src.main import env_flag

CASES = json.loads((Path(__file__).parents[2] / "spec" / "conformance" / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sql, keyword", CASES["leading_keyword"])
def test_leading_keyword(sql, keyword):
    assert leading_keyword(sql) == keyword


@pytest.mark.parametrize("sql, expected", CASES["normalize"])
def test_normalize(sql, expected):
    assert normalize_statement(sql) == expected


@pytest.mark.parametrize("sql", CASES["normalize_rejects"])
def test_normalize_rejects(sql):
    with pytest.raises(ValueError):
        normalize_statement(sql)


@pytest.mark.parametrize("sql", CASES["select_rejects"])
def test_select_rejects(sql):
    with pytest.raises(ValueError):
        ensure_select(sql)


@pytest.mark.parametrize("sql", CASES["select_accepts"])
def test_select_accepts(sql):
    ensure_select(sql)


@pytest.mark.parametrize("sql", CASES["dml_rejects"])
def test_dml_rejects(sql):
    with pytest.raises(ValueError):
        ensure_dml(sql)


@pytest.mark.parametrize("sql", CASES["dml_accepts"])
def test_dml_accepts(sql):
    ensure_dml(sql)


@pytest.mark.parametrize("name, expected", CASES["quote_identifier"])
def test_quote_identifier(name, expected):
    assert quote_identifier(name) == expected


@pytest.mark.parametrize("labels, expected", CASES["unique_labels"])
def test_unique_labels(labels, expected):
    assert unique_labels(labels) == expected


@pytest.mark.parametrize("text, expected", CASES["decimal"])
def test_decimal_to_json(text, expected):
    result = decimal_to_json(Decimal(text))
    assert result == expected and type(result) is type(expected)


def _expand(spec):
    return spec["repeat"] * spec["count"] + spec.get("suffix", "")


@pytest.mark.parametrize("given, expected", CASES["truncate"]["cases"])
def test_truncate(given, expected):
    assert MAX_CELL_CHARS == CASES["truncate"]["max_chars"]
    assert truncate(_expand(given)) == _expand(expected)


@pytest.mark.parametrize("value, expected", CASES["env_flag"])
def test_env_flag(value, expected, monkeypatch):
    monkeypatch.setenv("SOME_FLAG", value)
    assert env_flag("SOME_FLAG") is expected
