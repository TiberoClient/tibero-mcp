# Tibero MCP Server (Java)

Java implementation of the Tibero MCP server, built on the official MCP Java SDK
(`io.modelcontextprotocol.sdk:mcp` 2.1.0) with Jetty 12 and HikariCP. It is **functionally identical
to the Python implementation** (`../python`): tool names, descriptions, annotations and input/output
schemas come from the shared `spec/tools.json`, and settings, authentication, error texts and value
conversion are the same. See [../spec/README.md](../spec/README.md).

## Tools

| Tool | Kind | Description |
|---|---|---|
| `execute_query` | read | SELECT / WITH only; `max_rows` (default 200, max 5000), `truncated` when more rows existed |
| `execute_dml` | write (destructive) | One INSERT/UPDATE/DELETE/MERGE in its own transaction; DDL rejected; `dry_run` rolls back |
| `get_schema` | read | Tables and views with comments and row statistics (system schemas excluded by default) |
| `get_table_info` | read | Columns, PK/FK (with referenced table/columns), UNIQUE/CHECK, index columns |
| `explain_plan` | read | Plan from `PLAN_TABLE`, created and read in one transaction, then rolled back |
| `sample_table` | read | First n rows (default 10, max 1000) |

`MCP_READ_ONLY=true` leaves `execute_dml` unregistered.

## Build and run

```bash
cd java
./gradlew shadowJar   # build/libs/tibero-mcp-server-<version>.jar (self-contained)
./gradlew test
MCP_TRANSPORT=stdio TIBERO_HOST=… TIBERO_DATABASE=… TIBERO_USER=… TIBERO_PASSWORD=… \
  java -jar build/libs/tibero-mcp-server-0.2.0.jar
```

Docker, from the repository root: `docker build -f java/Dockerfile -t tibero-mcp-java .`

Requires JDK 17+ to build and Java 17+ to run; the JDBC driver `com.tmaxtibero:tbjdbc17:7.2.6` is bundled.

## Configuration

Environment variables, or `mcp.cfg` (KEY=VALUE) in the working directory (`MCP_CONFIG_FILE` to override);
the environment wins. The variables are the same as the Python server's — see `../python/mcp.cfg.example`.
Since 0.2.0 the default transport is `http`; set `MCP_TRANSPORT=stdio` for stdio clients.
Logs go to stderr only.

## Authentication (HTTP)

Send one of `MCP_API_KEYS` as `Authorization: Bearer <key>`, `X-API-Key: <key>`, or path `/<key>/mcp`.
Without keys the server refuses to listen on a non-loopback address unless `MCP_ALLOW_ANONYMOUS=true`.
`/healthz` is the only unauthenticated path.

## References

- [Tibero JDBC Developer Guide](https://docs.tmaxtibero.com/tibero/topics/development/jdbc-developers-guide/introduction-to-tibero-jdbc)
- [MCP Java SDK](https://github.com/modelcontextprotocol/java-sdk)
