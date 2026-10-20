"""Database schema information viewer module."""

from __future__ import annotations

import os
from typing import Any

import jaydebeapi

from .query_executor import execute_select_query_and_fetch_results

# Dictionary owners that are never user data. Listing them by default floods the
# model with thousands of catalog objects before it finds the application tables.
SYSTEM_SCHEMAS = tuple(
    name.strip().upper()
    for name in os.getenv("TIBERO_SYSTEM_SCHEMAS", "SYS,SYSCAT,SYSGIS,SYSBACKUP,LBACSYS,OUTLN,PUBLIC,TIBERO,TIBERO1").split(",")
    if name.strip()
)

_OBJECTS_QUERY = """
    SELECT
        t.OWNER AS SCHEMA_NAME,
        t.TABLE_NAME AS OBJECT_NAME,
        'TABLE' AS OBJECT_TYPE,
        t.NUM_ROWS,
        t.LAST_ANALYZED,
        tc.COMMENTS
    FROM ALL_TABLES t
    LEFT JOIN ALL_TAB_COMMENTS tc
        ON t.OWNER = tc.OWNER
        AND t.TABLE_NAME = tc.TABLE_NAME
    WHERE {table_filter}

    UNION ALL

    SELECT
        v.OWNER AS SCHEMA_NAME,
        v.VIEW_NAME AS OBJECT_NAME,
        'VIEW' AS OBJECT_TYPE,
        NULL AS NUM_ROWS,
        NULL AS LAST_ANALYZED,
        vc.COMMENTS
    FROM ALL_VIEWS v
    LEFT JOIN ALL_TAB_COMMENTS vc
        ON v.OWNER = vc.OWNER
        AND v.VIEW_NAME = vc.TABLE_NAME
    WHERE {view_filter}

    ORDER BY 1, 3, 2
"""


def get_schema_info(
    connection: jaydebeapi.Connection,
    schema_name: str | None = None,
) -> list[dict[str, Any]]:
    """List tables and views with comments, for one schema or all non-system schemas."""
    if schema_name:
        query = _OBJECTS_QUERY.format(table_filter="t.OWNER = UPPER(?)", view_filter="v.OWNER = UPPER(?)")
        return execute_select_query_and_fetch_results(connection, query, [schema_name, schema_name])
    placeholders = ", ".join("?" for _ in SYSTEM_SCHEMAS)
    query = _OBJECTS_QUERY.format(
        table_filter=f"t.OWNER NOT IN ({placeholders})",
        view_filter=f"v.OWNER NOT IN ({placeholders})",
    )
    return execute_select_query_and_fetch_results(connection, query, [*SYSTEM_SCHEMAS, *SYSTEM_SCHEMAS])


def resolve_object(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> dict[str, Any] | None:
    """Find a table or view, trying the exact name first and then its upper-case form.

    Unquoted identifiers are stored upper-case, so a model that writes ``orders``
    usually means ``ORDERS``; a quoted mixed-case name still matches exactly.
    """
    query = """
        SELECT o.OWNER, o.OBJECT_NAME, o.OBJECT_TYPE, c.COMMENTS
        FROM ALL_OBJECTS o
        LEFT JOIN ALL_TAB_COMMENTS c
            ON o.OWNER = c.OWNER AND o.OBJECT_NAME = c.TABLE_NAME
        WHERE o.OWNER = UPPER(?)
          AND o.OBJECT_NAME = ?
          AND o.OBJECT_TYPE IN ('TABLE', 'VIEW')
    """
    for candidate in dict.fromkeys((table_name, table_name.upper())):
        rows = execute_select_query_and_fetch_results(connection, query, [schema_name, candidate])
        if rows:
            return rows[0]
    return None


def get_table_columns(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """Column definitions with comments, in column order."""
    query = """
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.DATA_LENGTH,
            c.DATA_PRECISION,
            c.DATA_SCALE,
            c.NULLABLE,
            c.DATA_DEFAULT,
            c.COLUMN_ID,
            cc.COMMENTS
        FROM ALL_TAB_COLUMNS c
        LEFT JOIN ALL_COL_COMMENTS cc
            ON c.OWNER = cc.OWNER
            AND c.TABLE_NAME = cc.TABLE_NAME
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.OWNER = ?
          AND c.TABLE_NAME = ?
        ORDER BY c.COLUMN_ID
    """
    return execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])


def get_table_constraints(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """Constraints with their columns and, for foreign keys, the referenced table.

    Foreign keys are what lets a model write correct joins, so the referenced
    owner/table/columns are resolved here instead of leaving a bare constraint name.
    """
    query = """
        SELECT
            c.CONSTRAINT_NAME,
            c.CONSTRAINT_TYPE,
            c.SEARCH_CONDITION,
            c.STATUS,
            cc.COLUMN_NAME,
            cc.POSITION,
            r.OWNER AS R_OWNER,
            r.TABLE_NAME AS R_TABLE_NAME,
            rc.COLUMN_NAME AS R_COLUMN_NAME
        FROM ALL_CONSTRAINTS c
        LEFT JOIN ALL_CONS_COLUMNS cc
            ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
        LEFT JOIN ALL_CONSTRAINTS r
            ON c.R_OWNER = r.OWNER AND c.R_CONSTRAINT_NAME = r.CONSTRAINT_NAME
        LEFT JOIN ALL_CONS_COLUMNS rc
            ON r.OWNER = rc.OWNER AND r.CONSTRAINT_NAME = rc.CONSTRAINT_NAME AND rc.POSITION = cc.POSITION
        WHERE c.OWNER = ?
          AND c.TABLE_NAME = ?
        ORDER BY c.CONSTRAINT_NAME, cc.POSITION
    """
    rows = execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])
    constraints: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = constraints.setdefault(
            row["CONSTRAINT_NAME"],
            {
                "CONSTRAINT_NAME": row["CONSTRAINT_NAME"],
                "CONSTRAINT_TYPE": row["CONSTRAINT_TYPE"],
                "SEARCH_CONDITION": row["SEARCH_CONDITION"],
                "STATUS": row["STATUS"],
                "COLUMNS": [],
            },
        )
        if row["COLUMN_NAME"] is not None:
            entry["COLUMNS"].append(row["COLUMN_NAME"])
        if row["R_TABLE_NAME"] is not None:
            ref = entry.setdefault(
                "REFERENCES", {"OWNER": row["R_OWNER"], "TABLE_NAME": row["R_TABLE_NAME"], "COLUMNS": []}
            )
            if row["R_COLUMN_NAME"] is not None:
                ref["COLUMNS"].append(row["R_COLUMN_NAME"])
    return list(constraints.values())


def get_table_indexes(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """Indexes with their columns in key order."""
    query = """
        SELECT
            i.INDEX_NAME,
            i.INDEX_TYPE,
            i.UNIQUENESS,
            i.STATUS,
            ic.COLUMN_NAME,
            ic.COLUMN_POSITION
        FROM ALL_INDEXES i
        LEFT JOIN ALL_IND_COLUMNS ic
            ON i.OWNER = ic.INDEX_OWNER AND i.INDEX_NAME = ic.INDEX_NAME
        WHERE i.TABLE_OWNER = ?
          AND i.TABLE_NAME = ?
        ORDER BY i.INDEX_NAME, ic.COLUMN_POSITION
    """
    rows = execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])
    indexes: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = indexes.setdefault(
            row["INDEX_NAME"],
            {
                "INDEX_NAME": row["INDEX_NAME"],
                "INDEX_TYPE": row["INDEX_TYPE"],
                "UNIQUENESS": row["UNIQUENESS"],
                "STATUS": row["STATUS"],
                "COLUMNS": [],
            },
        )
        if row["COLUMN_NAME"] is not None:
            entry["COLUMNS"].append(row["COLUMN_NAME"])
    return list(indexes.values())
