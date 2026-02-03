"""SQL query execution module."""

from __future__ import annotations

from typing import Any
import jaydebeapi
from loguru import logger


def execute_select_query_and_fetch_results(
    connection: jaydebeapi.Connection,
    query: str,
    params: list[Any] | None = None,
    fetch_all: bool = True,
) -> list[dict[str, Any]]:
    """
    Execute a SELECT SQL query and fetch all results as a list of dictionaries.

    This function is designed specifically for SELECT queries that return result sets.
    It executes the query, fetches all rows, and converts them to a list of dictionaries
    where each dictionary represents a row with column names as keys.

    Args:
        connection: Database connection object
        query: SELECT SQL query string
        params: Optional list of parameters for parameterized queries
        fetch_all: Whether to fetch all results (default: True)

    Returns:
        List of dictionaries representing query results, where each dictionary
        contains column names as keys and row values as values

    Raises:
        Exception: If query execution fails
    """
    cursor = None
    try:
        cursor = connection.cursor()
        logger.debug(f"Executing query: {query[:100]}...")

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch_all:
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch all rows
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                results.append(row_dict)
            
            logger.info(f"Query executed successfully. Rows returned: {len(results)}")
            return results
        else:
            # Return empty list if not fetching all
            return []

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise
    finally:
        if cursor:
            cursor.close()


def execute_dml_statement_with_transaction_management(
    connection: jaydebeapi.Connection,
    query: str,
    auto_commit: bool = True,
) -> dict[str, Any]:
    """
    Execute a DML statement (INSERT, UPDATE, DELETE) with transaction management.

    This function executes Data Manipulation Language statements and handles
    transaction management automatically. On success, it commits the transaction
    (if auto_commit is enabled). On failure, it rolls back the transaction to
    maintain data consistency.

    Args:
        connection: Database connection object
        query: DML statement string (INSERT, UPDATE, DELETE)
        auto_commit: Whether to automatically commit the transaction on success (default: True)

    Returns:
        Dictionary with execution result containing:
        - success: Boolean indicating whether execution was successful
        - rowcount: Number of rows affected by the DML statement

    Raises:
        Exception: If DML execution fails (transaction is rolled back automatically)
    """
    cursor = None
    try:
        cursor = connection.cursor()
        logger.debug(f"Executing DML: {query[:100]}...")

        cursor.execute(query)

        rowcount = cursor.rowcount
        logger.info(f"DML executed successfully. Rows affected: {rowcount}")

        # Commit transaction if auto_commit is enabled
        if auto_commit:
            connection.commit()
            logger.debug("Transaction committed")

        return {
            "success": True,
            "rowcount": rowcount,
        }

    except Exception as e:
        logger.error(f"DML execution failed: {e}")
        # Rollback transaction on error
        try:
            connection.rollback()
            logger.debug("Transaction rolled back due to error")
        except Exception as rollback_error:
            logger.warning(f"Failed to rollback transaction: {rollback_error}")
        raise
    finally:
        if cursor:
            cursor.close()


def get_execution_plan(
    connection: jaydebeapi.Connection,
    query: str,
) -> list[dict[str, Any]]:
    """
    Get execution plan for a SQL query without actually executing it.

    This function uses EXPLAIN PLAN to analyze the execution plan of a SQL statement.
    It validates whether the SQL is executable and returns the execution plan.
    If the SQL is not valid, it raises an exception.

    Args:
        connection: Database connection object
        query: SQL query string (SELECT, INSERT, UPDATE, DELETE, etc.)

    Returns:
        List of dictionaries representing the execution plan rows

    Raises:
        Exception: If SQL is invalid or plan generation failed
    """
    cursor = None
    try:
        cursor = connection.cursor()
        logger.debug(f"Getting execution plan for: {query[:100]}...")

        # Create the execution plan
        explain_query = f"EXPLAIN PLAN FOR {query}"
        cursor.execute(explain_query)

        # Get execution plan using DBMS_XPLAN.DISPLAY
        plan_query = "SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY)"
        cursor.execute(plan_query)
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        
        execution_plan = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            execution_plan.append(row_dict)
        
        logger.info(f"Execution plan generated successfully. Plan rows: {len(execution_plan)}")
        
        return execution_plan

    except Exception as e:
        logger.error(f"Failed to get execution plan: {e}")
        raise
    finally:
        if cursor:
            cursor.close()


def sample_table_rows(
    connection: jaydebeapi.Connection,
    schema_name: str,
    table_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Sample n rows from a specific table.

    This function retrieves a sample of rows from a table without loading all data.
    It uses ROWNUM to limit the number of rows returned.

    Args:
        connection: Database connection object
        schema_name: Schema name
        table_name: Table name
        limit: Number of rows to sample (default: 10, max: 1000)

    Returns:
        List of sampled rows (each row is a dictionary with column names as keys)

    Raises:
        Exception: If sampling fails
    """
    # Limit the maximum number of rows to prevent excessive data transfer
    if limit > 1000:
        limit = 1000
        logger.warning(f"Limit exceeded maximum (1000), using 1000 instead")
    
    if limit < 1:
        limit = 1
        logger.warning(f"Limit must be at least 1, using 1 instead")
    
    cursor = None
    try:
        cursor = connection.cursor()
        logger.debug(f"Sampling {limit} rows from {schema_name}.{table_name}")
        
        # Build query with schema qualification
        if schema_name:
            qualified_table = f'"{schema_name}"."{table_name}"'
        else:
            qualified_table = f'"{table_name}"'
        
        # Use ROWNUM for Tibero/Oracle compatibility
        query = f"""
            SELECT * FROM {qualified_table}
            WHERE ROWNUM <= {limit}
        """
        
        cursor.execute(query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        results = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            results.append(row_dict)
        
        logger.info(f"Successfully sampled {len(results)} rows from {schema_name}.{table_name}")
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to sample rows from {schema_name}.{table_name}: {e}")
        raise
    finally:
        if cursor:
            cursor.close()

