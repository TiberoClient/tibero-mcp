"""MCP server implementation for Tibero database.

Tools are declared with MCP tool annotations (read-only / destructive / idempotent /
open-world hints) and typed return models, so clients receive both an
``outputSchema`` and ``structuredContent`` in addition to the JSON text block.

Database calls go through blocking JDBC, so every tool hands its work to a worker
thread instead of stalling the event loop that serves other clients.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

import anyio
from loguru import logger
from pydantic import BaseModel, Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from .. import __version__
from ..db import (
    execute_dml_statement_with_transaction_management,
    get_connection,
    get_execution_plan,
    get_schema_info,
    get_table_columns,
    get_table_constraints,
    get_table_indexes,
    resolve_object,
    run_select,
    sample_table_rows,
)

INSTRUCTIONS = """\
Tools for a Tibero (Oracle-compatible) relational database.

Recommended workflow:
1. get_schema to find tables and views (optionally for one schema).
2. get_table_info for columns, comments, primary/foreign keys and indexes before writing joins.
3. sample_table to see real values, then execute_query for the actual question.
4. explain_plan to validate a statement without running it.

SQL dialect is Oracle-compatible: use ROWNUM or FETCH FIRST n ROWS ONLY to limit rows,
NVL/DECODE/TO_CHAR/TO_DATE, and qualify tables as SCHEMA.TABLE. Unquoted identifiers are
upper-case; only quote names that were created mixed-case. Do not end statements with ';'.
"""

mcp = MCPServer(
    name="tibero-mcp-server",
    title="Tibero Database",
    version=__version__,
    instructions=INSTRUCTIONS,
)

READ_ONLY = dict(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

T = TypeVar("T")


class QueryResult(BaseModel):
    columns: list[str] = Field(description="Column names in select-list order")
    rows: list[dict[str, Any]] = Field(description="One object per row, keyed by column name")
    row_count: int = Field(description="Number of rows returned")
    truncated: bool = Field(description="True when more rows existed than max_rows; narrow or aggregate the query")


class DmlResult(BaseModel):
    rowcount: int = Field(description="Rows inserted, updated or deleted")
    committed: bool = Field(description="False when dry_run rolled the change back")


class SchemaObject(BaseModel):
    schema_name: str
    object_name: str = Field(description="Exact dictionary name (case-sensitive)")
    object_type: str = Field(description="TABLE or VIEW")
    num_rows: int | None = Field(None, description="Row count from the last statistics run, if any")
    last_analyzed: str | None = None
    comments: str | None = None


class SchemaResult(BaseModel):
    objects: list[SchemaObject]
    count: int


class TableInfo(BaseModel):
    schema_name: str
    table_name: str
    object_type: str = Field(description="TABLE or VIEW")
    comments: str | None = None
    columns: list[dict[str, Any]]
    constraints: list[dict[str, Any]] = Field(description="PK (P), FK (R, with REFERENCES), unique (U) and check (C) constraints")
    indexes: list[dict[str, Any]]


class PlanStep(BaseModel):
    id: int
    parent_id: int | None = None
    depth: int | None = None
    operation: str | None = None
    object_owner: str | None = None
    object_name: str | None = None
    cost: float | None = None
    cardinality: float | None = None
    access_predicates: str | None = None
    filter_predicates: str | None = None


class ExplainResult(BaseModel):
    steps: list[PlanStep]
    total_cost: float | None = Field(None, description="Cost of the root step")
    plan_text: str = Field(description="Indented plan tree for reading")


async def _with_connection(work: Callable[[Any], T]) -> T:
    """Run ``work(connection)`` on a worker thread with a fresh connection.

    Database errors are surfaced as ToolError so the model sees the Tibero message
    (e.g. JDBC-8026 invalid identifier) and can correct its SQL.
    """

    def run() -> T:
        connection = get_connection()
        try:
            return work(connection)
        finally:
            connection.close()

    try:
        return await anyio.to_thread.run_sync(run)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        logger.warning(f"Database call failed: {message}")
        raise ToolError(f"Database error: {message}") from exc


@mcp.tool(title="Run SELECT query", annotations=ToolAnnotations(title="Run SELECT query", **READ_ONLY))
async def execute_query(
    query: str = Field(description="A single SELECT or WITH ... SELECT statement, without a trailing ';'"),
    max_rows: int = Field(200, ge=1, le=5000, description="Maximum rows to return"),
) -> QueryResult:
    """Run a read-only SELECT statement and return its rows.

    Only SELECT/WITH statements are accepted; use execute_dml for data changes.
    If the result is truncated, aggregate or filter in SQL rather than raising max_rows.
    """
    logger.info(f"execute_query: {query[:200]}")
    return QueryResult(**await _with_connection(lambda conn: run_select(conn, query, max_rows)))


@mcp.tool(
    title="Run INSERT/UPDATE/DELETE",
    annotations=ToolAnnotations(
        title="Run INSERT/UPDATE/DELETE",
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
        open_world_hint=False,
    ),
)
async def execute_dml(
    query: str = Field(description="One INSERT, UPDATE, DELETE or MERGE statement, without a trailing ';'"),
    dry_run: bool = Field(False, description="Execute and report the affected row count, then roll back"),
) -> DmlResult:
    """Execute one DML statement in its own transaction and commit it.

    DDL (CREATE/DROP/ALTER/TRUNCATE...) is rejected. Run with dry_run=true first when
    the statement could touch many rows. Writes succeed only where the connected
    database account has privileges.
    """
    logger.info(f"execute_dml (dry_run={dry_run}): {query[:200]}")
    return DmlResult(
        **await _with_connection(
            lambda conn: execute_dml_statement_with_transaction_management(conn, query, dry_run)
        )
    )


@mcp.tool(title="List tables and views", annotations=ToolAnnotations(title="List tables and views", **READ_ONLY))
async def get_schema(
    schema_name: str | None = Field(None, description="Schema (owner) to list; omit for every non-system schema"),
) -> SchemaResult:
    """List tables and views visible to this account, with comments and row-count statistics."""
    rows = await _with_connection(lambda conn: get_schema_info(conn, schema_name))
    objects = [
        SchemaObject(
            schema_name=row["SCHEMA_NAME"],
            object_name=row["OBJECT_NAME"],
            object_type=row["OBJECT_TYPE"],
            num_rows=row["NUM_ROWS"],
            last_analyzed=row["LAST_ANALYZED"],
            comments=row["COMMENTS"],
        )
        for row in rows
    ]
    return SchemaResult(objects=objects, count=len(objects))


@mcp.tool(title="Describe table or view", annotations=ToolAnnotations(title="Describe table or view", **READ_ONLY))
async def get_table_info(
    schema_name: str = Field(description="Schema (owner) name"),
    table_name: str = Field(description="Table or view name; an unquoted name is also tried upper-case"),
) -> TableInfo:
    """Describe a table or view: columns with comments, constraints (including foreign-key targets) and indexes."""

    def work(conn: Any) -> TableInfo:
        found = resolve_object(conn, schema_name, table_name)
        if found is None:
            raise ValueError(f"{schema_name}.{table_name} does not exist or is not visible to this account.")
        owner, name = found["OWNER"], found["OBJECT_NAME"]
        return TableInfo(
            schema_name=owner,
            table_name=name,
            object_type=found["OBJECT_TYPE"],
            comments=found["COMMENTS"],
            columns=get_table_columns(conn, owner, name),
            constraints=get_table_constraints(conn, owner, name),
            indexes=get_table_indexes(conn, owner, name),
        )

    return await _with_connection(work)


def _plan_text(steps: list[PlanStep]) -> str:
    lines = []
    for step in steps:
        target = ".".join(part for part in (step.object_owner, step.object_name) if part)
        detail = f" {target}" if target else ""
        stats = f" (cost={step.cost}, rows={step.cardinality})" if step.cost is not None else ""
        lines.append(f"{'  ' * (step.depth or 0)}{step.id} {step.operation}{detail}{stats}")
        for label, predicate in (("access", step.access_predicates), ("filter", step.filter_predicates)):
            if predicate:
                lines.append(f"{'  ' * ((step.depth or 0) + 1)}{label}: {predicate}")
    return "\n".join(lines)


@mcp.tool(title="Explain SQL plan", annotations=ToolAnnotations(title="Explain SQL plan", **READ_ONLY))
async def explain_plan(
    query: str = Field(description="SELECT or DML statement to analyze; it is not executed"),
) -> ExplainResult:
    """Show the optimizer's execution plan for a statement without running it.

    Also a cheap way to validate SQL: invalid identifiers or syntax come back as errors.
    """
    logger.info(f"explain_plan: {query[:200]}")
    rows = await _with_connection(lambda conn: get_execution_plan(conn, query))
    steps = [PlanStep(**{key.lower(): value for key, value in row.items()}) for row in rows]
    if not steps:
        raise ToolError("The database produced no plan rows for this statement.")
    return ExplainResult(steps=steps, total_cost=steps[0].cost, plan_text=_plan_text(steps))


@mcp.tool(title="Sample table rows", annotations=ToolAnnotations(title="Sample table rows", **READ_ONLY))
async def sample_table(
    schema_name: str = Field(description="Schema (owner) name"),
    table_name: str = Field(description="Table or view name; an unquoted name is also tried upper-case"),
    limit: int = Field(10, ge=1, le=1000, description="Number of rows"),
) -> QueryResult:
    """Return the first rows of a table or view to see real values and formats."""

    def work(conn: Any) -> QueryResult:
        found = resolve_object(conn, schema_name, table_name)
        if found is None:
            raise ValueError(f"{schema_name}.{table_name} does not exist or is not visible to this account.")
        rows = sample_table_rows(conn, found["OWNER"], found["OBJECT_NAME"], limit)
        columns = list(rows[0].keys()) if rows else [c["COLUMN_NAME"] for c in get_table_columns(conn, found["OWNER"], found["OBJECT_NAME"])]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=False)

    return await _with_connection(work)


def get_server() -> MCPServer:
    """Return the configured Tibero MCP server instance."""
    return mcp
