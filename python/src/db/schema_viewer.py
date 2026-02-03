"""Database schema information viewer module."""

from __future__ import annotations

from typing import Any
import jaydebeapi
from loguru import logger

from .query_executor import execute_select_query_and_fetch_results


def get_schema_info(
    connection: jaydebeapi.Connection,
    schema_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get schema information for the database including tables and views with comments.

    Args:
        connection: Database connection
        schema_name: Optional schema name to filter results

    Returns:
        List of schema information dictionaries with OBJECT_TYPE (TABLE/VIEW) and COMMENTS
    """
    if schema_name:
        query = """
            SELECT 
                t.OWNER as SCHEMA_NAME,
                t.TABLE_NAME as OBJECT_NAME,
                'TABLE' as OBJECT_TYPE,
                t.TABLESPACE_NAME,
                t.NUM_ROWS,
                t.LAST_ANALYZED,
                tc.COMMENTS
            FROM ALL_TABLES t
            LEFT JOIN ALL_TAB_COMMENTS tc 
                ON t.OWNER = tc.OWNER 
                AND t.TABLE_NAME = tc.TABLE_NAME 
                AND tc.TABLE_TYPE = 'TABLE'
            WHERE t.OWNER = UPPER(?)
            
            UNION ALL
            
            SELECT 
                v.OWNER as SCHEMA_NAME,
                v.VIEW_NAME as OBJECT_NAME,
                'VIEW' as OBJECT_TYPE,
                NULL as TABLESPACE_NAME,
                NULL as NUM_ROWS,
                NULL as LAST_ANALYZED,
                vc.COMMENTS
            FROM ALL_VIEWS v
            LEFT JOIN ALL_TAB_COMMENTS vc 
                ON v.OWNER = vc.OWNER 
                AND v.VIEW_NAME = vc.TABLE_NAME 
                AND vc.TABLE_TYPE = 'VIEW'
            WHERE v.OWNER = UPPER(?)
            
            ORDER BY SCHEMA_NAME, OBJECT_TYPE, OBJECT_NAME
        """
        return execute_select_query_and_fetch_results(connection, query, [schema_name, schema_name])
    else:
        query = """
            SELECT 
                t.OWNER as SCHEMA_NAME,
                t.TABLE_NAME as OBJECT_NAME,
                'TABLE' as OBJECT_TYPE,
                t.TABLESPACE_NAME,
                t.NUM_ROWS,
                t.LAST_ANALYZED,
                tc.COMMENTS
            FROM ALL_TABLES t
            LEFT JOIN ALL_TAB_COMMENTS tc 
                ON t.OWNER = tc.OWNER 
                AND t.TABLE_NAME = tc.TABLE_NAME 
                AND tc.TABLE_TYPE = 'TABLE'
            
            UNION ALL
            
            SELECT 
                v.OWNER as SCHEMA_NAME,
                v.VIEW_NAME as OBJECT_NAME,
                'VIEW' as OBJECT_TYPE,
                NULL as TABLESPACE_NAME,
                NULL as NUM_ROWS,
                NULL as LAST_ANALYZED,
                vc.COMMENTS
            FROM ALL_VIEWS v
            LEFT JOIN ALL_TAB_COMMENTS vc 
                ON v.OWNER = vc.OWNER 
                AND v.VIEW_NAME = vc.TABLE_NAME 
                AND vc.TABLE_TYPE = 'VIEW'
            
            ORDER BY SCHEMA_NAME, OBJECT_TYPE, OBJECT_NAME
        """
        return execute_select_query_and_fetch_results(connection, query)


def get_table_columns(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Get column information for a specific table or view with comments.

    Args:
        connection: Database connection
        schema_name: Schema name
        table_name: Table or view name

    Returns:
        List of column information dictionaries including COMMENTS
    """
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
        WHERE c.OWNER = UPPER(?)
          AND c.TABLE_NAME = ?
        ORDER BY c.COLUMN_ID
    """
    return execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])


def get_table_constraints(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Get constraint information for a specific table.

    Args:
        connection: Database connection
        schema_name: Schema name
        table_name: Table name

    Returns:
        List of constraint information dictionaries
    """
    query = """
        SELECT 
            CONSTRAINT_NAME,
            CONSTRAINT_TYPE,
            SEARCH_CONDITION,
            STATUS,
            VALIDATED
        FROM ALL_CONSTRAINTS
        WHERE OWNER = UPPER(?)
          AND TABLE_NAME = ?
        ORDER BY CONSTRAINT_NAME
    """
    return execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])


def get_table_indexes(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Get index information for a specific table.

    Args:
        connection: Database connection
        schema_name: Schema name
        table_name: Table name

    Returns:
        List of index information dictionaries
    """
    query = """
        SELECT 
            INDEX_NAME,
            INDEX_TYPE,
            UNIQUENESS,
            STATUS,
            TABLESPACE_NAME
        FROM ALL_INDEXES
        WHERE OWNER = UPPER(?)
          AND TABLE_NAME = ?
        ORDER BY INDEX_NAME
    """
    return execute_select_query_and_fetch_results(connection, query, [schema_name, table_name])

