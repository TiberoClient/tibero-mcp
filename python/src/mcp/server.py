"""MCP server implementation for Tibero database using FastMCP.

This MCP (Model Context Protocol) server provides tools for interacting with Tibero DBMS.
It enables AI assistants to query, analyze, and manage Tibero databases through a standardized
protocol interface.

**Key Features:**
- Execute SELECT queries and DML statements (INSERT, UPDATE, DELETE)
- Retrieve schema and table information with detailed metadata
- Analyze SQL execution plans without executing queries
- Sample table data for quick inspection
- Automatic transaction management for data safety

**Best Practices:**
- Always use explain_plan before executing queries or DML statements to validate SQL syntax
  and verify that the statement matches your intended logic
- Use double quotes for case-sensitive table/column names (e.g., "atom", "Country")
- Check table structure with get_table_info before writing complex queries

This module defines MCP tools using @mcp.tool() decorators.
All business logic is implemented in this module.
"""

from __future__ import annotations

import json
from typing import Any
from loguru import logger

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    logger.error("MCP SDK not available. Please install with: pip install 'mcp[cli]>=1.21.1'")
    raise

from ..db import (
    get_connection,
    execute_select_query_and_fetch_results,
    execute_dml_statement_with_transaction_management,
    get_execution_plan,
    sample_table_rows,
    get_schema_info,
    get_table_columns,
    get_table_constraints,
    get_table_indexes,
)


# Create FastMCP server instance
# This server provides database tools for Tibero DBMS including query execution,
# schema inspection, execution plan analysis, and data sampling.
# Before executing queries or DML statements, it's recommended to use explain_plan
# to validate SQL syntax and verify intended logic.
mcp = FastMCP("tibero-mcp-server")


@mcp.tool()
async def execute_query_jsonl(query: str) -> str:
    """
    Execute a SELECT query on the Tibero database and return results.
    
    **IMPORTANT: Before executing a query, it is strongly recommended to first use the 
    explain_plan tool to validate the SQL syntax and verify that the query matches your 
    intended logic. This helps catch errors and semantic issues before actual execution.**
    
    This tool is designed for SELECT queries that return result sets.
    It executes the query and returns all rows in JSONL format (one JSON object per line).
    
    Note: Table, view, and column names are case-sensitive. If they were created with
    quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use
    double quotes around the names in your SQL query to preserve case sensitivity.
    Example: SELECT * FROM "atom" WHERE "atom_id" = '123'
    
    Args:
        query: SELECT SQL query to execute (use double quotes for case-sensitive identifiers)
        
    Returns:
        JSONL string where:
        - First line contains metadata: {"success": true, "row_count": N}
        - Subsequent lines contain data rows (each row is a dictionary with column names as keys)
        - Rows are separated by newline characters
        - On error, returns a single line with success: false, error message, and row_count: 0
    """
    logger.info(f"Executing SELECT query: {query[:100]}...")
    try:
        connection = get_connection()
        try:
            results = execute_select_query_and_fetch_results(connection, query)
            # First line: metadata with success and row_count
            jsonl_lines = []
            metadata = {
                "success": True,
                "row_count": len(results),
            }
            jsonl_lines.append(json.dumps(metadata, ensure_ascii=False))
            
            # Write each row as a separate JSON object (JSONL format)
            for row in results:
                jsonl_lines.append(json.dumps(row, ensure_ascii=False))
            return "\n".join(jsonl_lines) + "\n"
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"SELECT query execution failed: {e}")
        # On error, return error info as JSONL
        error_row = {
            "success": False,
            "error": str(e),
            "query": query,
        }
        return json.dumps(error_row, ensure_ascii=False) + "\n"


@mcp.tool()
async def execute_query_md(query: str) -> str:
    """
    Execute a SELECT query on the Tibero database and return results as a Markdown table.
    
    **IMPORTANT: Before executing a query, it is strongly recommended to first use the 
    explain_plan tool to validate the SQL syntax and verify that the query matches your 
    intended logic. This helps catch errors and semantic issues before actual execution.**
    
    This tool is designed for SELECT queries that return result sets.
    It executes the query and returns all rows as a Markdown-formatted table.
    
    Note: Table, view, and column names are case-sensitive. If they were created with
    quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use
    double quotes around the names in your SQL query to preserve case sensitivity.
    Example: SELECT * FROM "atom" WHERE "atom_id" = '123'
    
    Args:
        query: SELECT SQL query to execute (use double quotes for case-sensitive identifiers)
        
    Returns:
        Markdown table string with:
        - Header row with column names
        - Separator row
        - Data rows with values
        - On error, returns error message in Markdown format
    """
    logger.info(f"Executing SELECT query (MD format): {query[:100]}...")
    try:
        connection = get_connection()
        try:
            results = execute_select_query_and_fetch_results(connection, query)
            
            if not results:
                return "**Query executed successfully.**\n\n*No rows returned.*\n"
            
            # Get column names from first row
            columns = list(results[0].keys())
            
            # Build header row
            md_lines = []
            header = "| " + " | ".join(escape_markdown(str(col)) for col in columns) + " |"
            md_lines.append(header)
            
            # Build separator row
            separator = "|" + "|".join("---" for _ in columns) + "|"
            md_lines.append(separator)
            
            # Build data rows
            for row in results:
                row_values = []
                for col in columns:
                    value = row.get(col)
                    cell_value = "" if value is None else escape_markdown(str(value))
                    row_values.append(cell_value)
                data_row = "| " + " | ".join(row_values) + " |"
                md_lines.append(data_row)
            
            return "\n".join(md_lines) + "\n"
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"SELECT query execution failed: {e}")
        return f"**Error executing query:**\n\n```\n{str(e)}\n```\n"


def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown table."""
    if not text:
        return ""
    # Escape pipe characters and newlines for Markdown table
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _convert_execution_plan_to_markdown(plan: list[dict[str, Any]]) -> str:
    """
    Convert execution plan data to Markdown format.
    
    This is an internal helper function used only by the explain_plan tool.

    Args:
        plan: List of dictionaries representing execution plan rows

    Returns:
        Markdown formatted string
    """
    if not plan:
        return "**Execution plan is empty.**\n"

    md_lines = []
    in_table = False
    table_rows = []
    header_line = None

    for row in plan:
        column_value = row.get("COLUMN_VALUE")
        if column_value is None:
            continue

        line = str(column_value).strip()

        # Skip empty lines
        if not line:
            if in_table and table_rows:
                # Flush table
                md_lines.append(_build_markdown_table(header_line, table_rows))
                table_rows = []
                in_table = False
            md_lines.append("")
            continue

        # Check if this is a table header line (contains "|" and "Operation")
        if "|" in line and "Operation" in line:
            in_table = True
            header_line = line
            table_rows = []
            continue

        # Check if this is a separator line
        if in_table and line.replace("|", "").replace("-", "").strip() == "":
            continue

        # Check if this is a table data row
        if in_table and "|" in line and line.replace("|", "").replace("-", "").strip() != "":
            table_rows.append(line)
            continue

        # If we were in a table and hit a non-table line, flush the table
        if in_table and "|" not in line:
            md_lines.append(_build_markdown_table(header_line, table_rows))
            table_rows = []
            in_table = False

        # Regular text line
        if line.startswith("Note") or line.startswith("---"):
            md_lines.append(line)
        elif "SQL" in line and ":" in line:
            # SQL section - format as bold
            md_lines.append(f"**{line}**")
            md_lines.append("")
        elif line:
            md_lines.append(line)

    # Flush any remaining table
    if in_table and table_rows:
        md_lines.append(_build_markdown_table(header_line, table_rows))

    return "\n".join(md_lines) + "\n"


def _build_markdown_table(header_line: str | None, data_rows: list[str]) -> str:
    """Build a Markdown table from parsed table rows."""
    if not header_line or not data_rows:
        return ""

    table_lines = []

    # Parse header
    header_cells = _parse_table_row(header_line)
    table_lines.append("| " + " | ".join(header_cells) + " |")

    # Build separator
    table_lines.append("|" + "|".join([" --- "] * len(header_cells)) + "|")

    # Add data rows
    for row in data_rows:
        cells = _parse_table_row(row)
        # Pad or truncate cells to match header length
        while len(cells) < len(header_cells):
            cells.append("")
        cells = cells[:len(header_cells)]
        table_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(table_lines)


def _parse_table_row(row: str) -> list[str]:
    """Parse a table row string into individual cells."""
    cleaned = row.strip()
    if cleaned.startswith("|"):
        cleaned = cleaned[1:]
    if cleaned.endswith("|"):
        cleaned = cleaned[:-1]
    parts = cleaned.split("|")
    return [part.strip() for part in parts]


@mcp.tool()
async def execute_dml(
    query: str,
    auto_commit: bool = True,
) -> str:
    """
    Execute a DML statement (INSERT, UPDATE, DELETE) on the Tibero database.
    
    **IMPORTANT: Before executing a DML statement, it is strongly recommended to first use 
    the explain_plan tool to validate the SQL syntax and verify that the statement matches 
    your intended logic. This helps catch errors and prevent unintended data modifications 
    before actual execution.**
    
    This tool is specifically designed for Data Manipulation Language statements
    and returns the number of affected rows. The transaction is automatically
    committed on success (unless auto_commit is False) and rolled back on error.
    
    Note: Table, view, and column names are case-sensitive. If they were created with
    quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use
    double quotes around the names in your SQL statement to preserve case sensitivity.
    Example: INSERT INTO "atom" ("atom_id", "molecule_id") VALUES ('123', '456')
    
    Args:
        query: DML statement to execute (INSERT, UPDATE, DELETE) (use double quotes for case-sensitive identifiers)
        auto_commit: Whether to automatically commit the transaction (default: True)
        
    Returns:
        JSON string with execution result containing:
        - success: Whether the DML statement executed successfully
        - rowcount: Number of rows affected by the statement
    """
    logger.info(f"Executing DML statement: {query[:100]}...")
    try:
        connection = get_connection()
        try:
            result = execute_dml_statement_with_transaction_management(
                connection, query, auto_commit
            )
            result["success"] = True
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"DML statement execution failed: {e}")
        result = {
            "success": False,
            "error": str(e),
            "query": query,
        }
        if auto_commit is not None:
            result["auto_commit"] = auto_commit
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_schema(schema_name: str | None = None) -> str:
    """
    Get schema information for the database including tables and views with comments.
    
    Note: Table and view names returned in OBJECT_NAME are case-sensitive as defined
    in the schema. If a table/view was created with quoted identifiers (e.g., "atom",
    "Country", "Player_Attributes"), the OBJECT_NAME will reflect the exact case.
    When using these names in other tools, use the exact case as shown in OBJECT_NAME.
    
    Args:
        schema_name: Optional schema name to filter results
        
    Returns:
        JSON string with schema information (tables and views) including:
        - SCHEMA_NAME: Schema/owner name
        - OBJECT_NAME: Table or view name (case-sensitive, exact case as in schema)
        - OBJECT_TYPE: 'TABLE' or 'VIEW'
        - TABLESPACE_NAME: Tablespace name (for tables only)
        - NUM_ROWS: Number of rows (for tables only)
        - LAST_ANALYZED: Last analyzed date (for tables only)
        - COMMENTS: Comment text for the table or view
    """
    logger.info(f"Getting schema info for: {schema_name or 'all'}")
    try:
        connection = get_connection()
        try:
            schema_info = get_schema_info(connection, schema_name)
            result = {
                "success": True,
                "schema": schema_info,
                "count": len(schema_info),
            }
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        result = {
            "success": False,
            "error": str(e),
        }
        if schema_name is not None:
            result["schema_name"] = schema_name
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_table_info(schema_name: str, table_name: str) -> str:
    """
    Get detailed information about a specific table or view.
    
    This tool works for both tables and views. For views, constraints and indexes
    will typically be empty arrays.
    
    Note: Table and view names are case-sensitive. If the table/view name was created
    with quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must
    use the exact case as defined in the schema. Use double quotes around the name
    if it contains mixed case or special characters.
    
    Args:
        schema_name: Schema name
        table_name: Table or view name (case-sensitive, use exact case as in schema)
        
    Returns:
        JSON string with table/view details containing:
        - success: Whether the operation was successful
        - schema_name: Schema name
        - table_name: Table or view name
        - columns: Array of column information (including COMMENTS for each column)
        - constraints: Array of constraint information (empty for views)
        - indexes: Array of index information (empty for views)
        - error: Error message if operation failed
    """
    logger.info(f"Getting table info for: {schema_name}.{table_name}")
    try:
        connection = get_connection()
        try:
            columns = get_table_columns(connection, schema_name, table_name)
            # Constraints and indexes may not exist for views, but the queries should still work
            constraints = get_table_constraints(connection, schema_name, table_name)
            indexes = get_table_indexes(connection, schema_name, table_name)
            result = {
                "success": True,
                "schema_name": schema_name,
                "table_name": table_name,
                "columns": columns,
                "constraints": constraints,
                "indexes": indexes,
            }
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"Failed to get table info: {e}")
        result = {
            "success": False,
            "error": str(e),
            "schema_name": schema_name,
            "table_name": table_name,
        }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def explain_plan(query: str) -> str:
    """
    Get execution plan for a SQL query without actually executing it.
    
    This tool analyzes the execution plan of a SQL statement (SELECT, INSERT, UPDATE, DELETE, etc.)
    without actually executing the query. It validates whether the SQL is executable and returns
    the execution plan in Markdown format. If the SQL is not valid, it returns an error message.
    
    Note: Table, view, and column names are case-sensitive. If they were created with
    quoted identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use
    double quotes around the names in your SQL query to preserve case sensitivity.
    Example: EXPLAIN PLAN FOR SELECT * FROM "atom" WHERE "atom_id" = '123'
    
    Args:
        query: SQL query string to analyze (SELECT, INSERT, UPDATE, DELETE, etc.) (use double quotes for case-sensitive identifiers)
        
    Returns:
        Markdown string with execution plan formatted as a table, including:
        - SQL ID, execution statistics
        - Execution plan tree with operations, costs, and cardinality
        - Notes and additional information
        - Error message in Markdown format if SQL is invalid or plan generation failed
    """
    logger.info(f"Getting execution plan for: {query[:100]}...")
    try:
        connection = get_connection()
        try:
            plan = get_execution_plan(connection, query)
            markdown = _convert_execution_plan_to_markdown(plan)
            return markdown
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"Failed to get execution plan: {e}")
        return f"**Error generating execution plan:**\n\n```\n{str(e)}\n```\n\n**Query:**\n```sql\n{query}\n```\n"


@mcp.tool()
async def sample_table(schema_name: str, table_name: str, limit: int = 10) -> str:
    """
    Sample n rows from a specific table.
    
    This tool retrieves a sample of rows from a table without loading all data.
    It's useful for quickly inspecting table contents and structure.
    
    Note: Table names are case-sensitive. If the table name was created with quoted
    identifiers (e.g., "atom", "Country", "Player_Attributes"), you must use the exact
    case as defined in the schema. Use double quotes around the name if it contains
    mixed case or special characters.
    
    Args:
        schema_name: Schema name (owner) of the table
        table_name: Name of the table to sample (case-sensitive, use exact case as in schema)
        limit: Number of rows to sample (default: 10, maximum: 1000)
        
    Returns:
        JSON string with sample result containing:
        - success: Whether the sampling was successful
        - schema_name: Schema name
        - table_name: Table name
        - rows: Array of sampled rows (each row is a dictionary with column names as keys)
        - row_count: Number of rows returned
        - limit: Requested limit
        - error: Error message if sampling failed
    """
    logger.info(f"Sampling {limit} rows from {schema_name}.{table_name}")
    try:
        connection = get_connection()
        try:
            rows = sample_table_rows(connection, schema_name, table_name, limit)
            result = {
                "success": True,
                "schema_name": schema_name,
                "table_name": table_name,
                "rows": rows,
                "row_count": len(rows),
                "limit": limit,
                "error": None,
            }
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"Failed to sample table: {e}")
        result = {
            "success": False,
            "error": str(e),
            "schema_name": schema_name,
            "table_name": table_name,
        }
        if limit != 10:  # Only include if not default value
            result["limit"] = limit
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_server() -> FastMCP:
    """
    Get the configured FastMCP server instance.
    
    This function returns the Tibero MCP server instance that provides database tools
    for query execution, schema inspection, execution plan analysis, and data sampling.
    
    The server includes the following tools:
    - execute_query: Execute SELECT queries
    - execute_dml: Execute INSERT, UPDATE, DELETE statements
    - get_schema: Retrieve schema information
    - get_table_info: Get detailed table/view information
    - explain_plan: Analyze SQL execution plans
    - sample_table: Sample rows from tables
    
    Returns:
        FastMCP server instance configured for Tibero database operations
    """
    return mcp
