"""SQL query execution module."""

from __future__ import annotations

import base64
import os
import re
from decimal import Decimal
from typing import Any

import jaydebeapi
from loguru import logger

# Every statement gets a server-side timeout so a runaway query from a remote
# client cannot hold a session (and a worker thread) indefinitely.
QUERY_TIMEOUT_SECONDS = int(os.getenv("TIBERO_QUERY_TIMEOUT", "60"))
# A single huge LOB/VARCHAR cell can blow a model's context on its own.
MAX_CELL_CHARS = int(os.getenv("TIBERO_MAX_CELL_CHARS", "4000"))

_LEADING_NOISE = re.compile(r"^(\s+|--[^\n]*\n?|/\*.*?\*/|\()+", re.DOTALL)
_SELECT_KEYWORDS = ("SELECT", "WITH")
_DML_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "MERGE")


class _TimedCursor(jaydebeapi.Cursor):
    """Cursor that applies a query timeout and row cap before each execute.

    JayDeBeApi prepares the statement and calls ``_set_stmt_parms`` right before
    ``execute()``, which is the only point where the JDBC statement is reachable.
    """

    def __init__(self, connection: jaydebeapi.Connection, max_rows: int = 0):
        super().__init__(connection, connection._converters)
        self._max_rows = max_rows

    def _set_stmt_parms(self, prep_stmt: Any, parameters: Any) -> None:
        prep_stmt.setQueryTimeout(QUERY_TIMEOUT_SECONDS)
        if self._max_rows:
            prep_stmt.setMaxRows(self._max_rows)
        super()._set_stmt_parms(prep_stmt, parameters)


def normalize_statement(query: str) -> str:
    """Strip whitespace and a trailing semicolon, which the JDBC driver rejects."""
    statement = query.strip()
    while statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if not statement:
        raise ValueError("SQL statement is empty.")
    return statement


def leading_keyword(statement: str) -> str:
    """Return the first SQL keyword, skipping comments and opening parentheses."""
    body = _LEADING_NOISE.sub("", statement)
    match = re.match(r"[A-Za-z]+", body)
    return match.group(0).upper() if match else ""


def ensure_select(statement: str) -> None:
    if leading_keyword(statement) not in _SELECT_KEYWORDS:
        raise ValueError("Only SELECT (or WITH ... SELECT) statements are allowed here. Use execute_dml for INSERT/UPDATE/DELETE/MERGE.")


def ensure_dml(statement: str) -> None:
    if leading_keyword(statement) not in _DML_KEYWORDS:
        raise ValueError("Only INSERT, UPDATE, DELETE or MERGE statements are allowed. DDL and other statements are rejected.")


def quote_identifier(name: str) -> str:
    """Quote an identifier exactly as stored in the dictionary."""
    return '"' + name.replace('"', '""') + '"'


# java.sql.Types codes. The value rules below are the shared contract with the Java
# implementation (see spec/README.md), so both servers return identical JSON.
_NUMERIC_TYPES = {2, 3, -6, 5, 4, -5}
_FLOAT_TYPES = {6, 7, 8}
_BOOLEAN_TYPES = {-7, 16}
_TIMESTAMP_TYPES = {91, 93, 2014}
_TIME_TYPES = {92, 2013}
_BINARY_TYPES = {-2, -3, -4, 2004}
_MAX_SAFE_INTEGER = 2**53 - 1


def to_json_value(value: Any) -> Any:
    """Convert a Python-side value into the shared JSON form (used for already-converted values)."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return decimal_to_json(value)
    if isinstance(value, (bytes, bytearray)):
        return truncate("base64:" + base64.b64encode(bytes(value)).decode("ascii"))
    return truncate(str(value))


def decimal_to_json(value: Decimal) -> Any:
    """Integral values become JSON integers while exactly representable, larger ones strings; fractions doubles."""
    # normalize() would round to the context precision (28 digits); these are exact.
    if value == value.to_integral_value():
        integral = int(value)
        return integral if abs(integral) <= _MAX_SAFE_INTEGER else str(integral)
    return float(value)


def truncate(text: str) -> str:
    """Cap a text cell at MAX_CELL_CHARS code points."""
    if len(text) <= MAX_CELL_CHARS:
        return text
    return text[:MAX_CELL_CHARS] + f"...[truncated {len(text) - MAX_CELL_CHARS} chars]"


def _format_timestamp(timestamp: Any) -> str:
    local = timestamp.toLocalDateTime()
    text = (
        f"{local.getYear():04d}-{local.getMonthValue():02d}-{local.getDayOfMonth():02d} "
        f"{local.getHour():02d}:{local.getMinute():02d}:{local.getSecond():02d}"
    )
    micros = int(local.getNano()) // 1000
    return f"{text}.{micros:06d}" if micros else text


def _read_value(rs: Any, col: int, sql_type: int) -> Any:
    """Read one JDBC column into the shared JSON form."""
    if sql_type in _BOOLEAN_TYPES:
        value = rs.getBoolean(col)
        return None if rs.wasNull() else bool(value)
    if sql_type in _NUMERIC_TYPES:
        value = rs.getBigDecimal(col)
        return None if value is None else decimal_to_json(Decimal(str(value.toPlainString())))
    if sql_type in _FLOAT_TYPES:
        value = rs.getDouble(col)
        return None if rs.wasNull() else float(value)
    if sql_type in _TIMESTAMP_TYPES:
        value = rs.getTimestamp(col)
        return None if value is None else _format_timestamp(value)
    if sql_type in _TIME_TYPES:
        value = rs.getTime(col)
        return None if value is None else str(value.toString())
    if sql_type in _BINARY_TYPES:
        value = rs.getBytes(col)
        return None if value is None else truncate("base64:" + base64.b64encode(bytes(value)).decode("ascii"))
    value = rs.getString(col)
    return None if value is None else truncate(str(value))


def unique_labels(labels: list[str]) -> list[str]:
    """Make column labels unique (ID, ID_2, ...) so rows keyed by label lose no column."""
    used: set[str] = set()
    result = []
    for label in labels:
        name, suffix = label, 1
        while name in used:
            suffix += 1
            name = f"{label}_{suffix}"
        used.add(name)
        result.append(name)
    return result


def _fetch_dicts(cursor: jaydebeapi.Cursor, limit: int | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    """Read rows straight from the JDBC ResultSet with the shared value rules.

    JayDeBeApi's own converters drop the time of DATE values, print LOBs as Java
    object names and overflow large integers, so they are bypassed.
    """
    meta, rs = cursor._meta, cursor._rs
    if meta is None or rs is None:
        return [], []
    count = int(meta.getColumnCount())
    columns = unique_labels([str(meta.getColumnLabel(i)) for i in range(1, count + 1)])
    types = [int(meta.getColumnType(i)) for i in range(1, count + 1)]
    rows: list[dict[str, Any]] = []
    while (limit is None or len(rows) < limit) and rs.next():
        rows.append({columns[i]: _read_value(rs, i + 1, types[i]) for i in range(count)})
    return columns, rows


def execute_select_query_and_fetch_results(
    connection: jaydebeapi.Connection,
    query: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a dictionary/metadata SELECT and return every row as a dictionary."""
    cursor = _TimedCursor(connection)
    try:
        cursor.execute(query, params or None)
        return _fetch_dicts(cursor)[1]
    finally:
        cursor.close()


def run_select(
    connection: jaydebeapi.Connection,
    query: str,
    max_rows: int,
) -> dict[str, Any]:
    """Execute a user SELECT, returning at most ``max_rows`` rows.

    One extra row is requested so the caller can tell a full page from a truncated one.
    """
    statement = normalize_statement(query)
    ensure_select(statement)
    cursor = _TimedCursor(connection, max_rows=max_rows + 1)
    try:
        cursor.execute(statement)
        columns, rows = _fetch_dicts(cursor, max_rows + 1)
    finally:
        cursor.close()
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    logger.info(f"SELECT returned {len(rows)} rows (truncated={truncated})")
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}


def execute_dml_statement_with_transaction_management(
    connection: jaydebeapi.Connection,
    query: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute one DML statement in its own transaction.

    The statement is committed on success, or rolled back when ``dry_run`` is set
    (useful to see how many rows would change). Any failure rolls back.
    """
    statement = normalize_statement(query)
    ensure_dml(statement)
    connection.jconn.setAutoCommit(False)
    cursor = _TimedCursor(connection)
    try:
        cursor.execute(statement)
        rowcount = cursor.rowcount
        if dry_run:
            connection.rollback()
        else:
            connection.commit()
        logger.info(f"DML affected {rowcount} rows (committed={not dry_run})")
        return {"rowcount": rowcount, "committed": not dry_run}
    except Exception:
        try:
            connection.rollback()
        except Exception as rollback_error:
            logger.warning(f"Failed to rollback transaction: {rollback_error}")
        raise
    finally:
        cursor.close()


def get_execution_plan(
    connection: jaydebeapi.Connection,
    query: str,
) -> list[dict[str, Any]]:
    """Return the optimizer plan for a statement without executing it.

    Tibero has no DBMS_XPLAN, so the plan is read from PLAN_TABLE. ``EXPLAIN PLAN``
    writes rows there; preparing and reading in one uncommitted transaction and
    rolling back keeps concurrent callers' plans apart and leaves nothing behind.
    ``EXPLAIN PLAN`` returns no result set, so it must not be fetched.
    """
    statement = normalize_statement(query)
    connection.jconn.setAutoCommit(False)
    cursor = _TimedCursor(connection)
    try:
        cursor.execute(f"EXPLAIN PLAN FOR {statement}")
        cursor.execute(
            """
            SELECT ID, PARENT_ID, DEPTH, OPERATION, OBJECT_OWNER, OBJECT_NAME,
                   COST, CARDINALITY, ACCESS_PREDICATES, FILTER_PREDICATES
            FROM PLAN_TABLE
            ORDER BY ID
            """
        )
        return _fetch_dicts(cursor)[1]
    finally:
        cursor.close()
        try:
            connection.rollback()
        except Exception as rollback_error:
            logger.warning(f"Failed to rollback explain plan: {rollback_error}")


def sample_table_rows(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the first ``limit`` rows of a table (1..1000)."""
    limit = max(1, min(limit, 1000))
    query = f"SELECT * FROM {quote_identifier(schema_name)}.{quote_identifier(table_name)} WHERE ROWNUM <= {limit}"
    cursor = _TimedCursor(connection, max_rows=limit)
    try:
        cursor.execute(query)
        return _fetch_dicts(cursor, limit)[1]
    finally:
        cursor.close()
