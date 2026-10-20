# Tibero MCP Server (Python)

Python implementation of the Tibero MCP server on the MCP Python SDK 2.x (`MCPServer`). It is
**functionally identical to the Java implementation** (`../java`); the tool surface is exported to
`../spec/tools.json` (`python -m src.spec > ../spec/tools.json`) and both servers are tested against it.
See [../spec/README.md](../spec/README.md). The Korean [README.md](README.md) has the full guide.

## Tools

| Tool | Kind | Description |
|---|---|---|
| `execute_query` | read | SELECT / WITH only; `max_rows` (default 200, max 5000), `truncated` when more rows existed |
| `execute_dml` | write (destructive) | One INSERT/UPDATE/DELETE/MERGE in its own transaction; DDL rejected; `dry_run` rolls back |
| `get_schema` | read | Tables and views with comments and row statistics (system schemas excluded by default) |
| `get_table_info` | read | Columns, PK/FK (with referenced table/columns), UNIQUE/CHECK, index columns |
| `explain_plan` | read | Plan from `PLAN_TABLE`, created and read in one transaction, then rolled back |
| `sample_table` | read | First n rows (default 10, max 1000) |

Every tool declares MCP annotations and an output schema and returns `structuredContent`; database
errors come back as `isError` results carrying the Tibero message. `MCP_READ_ONLY=true` leaves
`execute_dml` unregistered.

## Setup

```bash
pip install -r requirements.txt
curl -o lib/tbjdbc17-7.2.6.jar https://repo1.maven.org/maven2/com/tmaxtibero/tbjdbc17/7.2.6/tbjdbc17-7.2.6.jar
cp mcp.cfg.example mcp.cfg   # fill in the connection; environment variables win
python -m src.main
```

Requires Python 3.12+ and Java 17+ (for the JDBC driver). Docker: `docker build -t tibero-mcp .`
(the driver is downloaded and checksum-verified during the build).

## Transport and authentication

`MCP_TRANSPORT=http` (default; stateless Streamable HTTP with JSON responses at `MCP_HTTP_PATH`, `/mcp`)
or `stdio`. Over HTTP, send one of `MCP_API_KEYS` as `Authorization: Bearer <key>`, `X-API-Key: <key>`,
or path `/<key>/mcp`. Without keys the server refuses to listen on a non-loopback address unless
`MCP_ALLOW_ANONYMOUS=true`. `/healthz` is unauthenticated. Access logs redact path keys.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests                      # unit tests (shared vectors) + spec drift check
pytest ../spec/conformance        # Python ⇄ Java parity (build the Java jar first)
```
