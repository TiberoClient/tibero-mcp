# Shared specification (Python ⇄ Java)

The Python (`python/`) and Java (`java/`) servers must stay functionally identical.
This directory is the contract between them.

| File | Role |
|---|---|
| `tools.json` | Server identity, instructions, and every tool's name, title, description, annotations, input and output schema. Generated from the Python server (`cd python && python -m src.spec > ../spec/tools.json`); the Java server registers its tools from it. |
| `conformance/cases.json` | Test vectors for SQL guards, identifier quoting, label de-duplication, number conversion, truncation and flag parsing. Both unit-test suites read it. |
| `conformance/test_parity.py` | Starts both servers and compares them: tools/list (full and `MCP_READ_ONLY`), identity, rejections, input validation, stdio stream purity, HTTP authentication, and — with a database — the exact results of a battery of real calls. |

## Changing behaviour

1. Change the Python server; if a tool's surface changed, regenerate `tools.json`.
2. Make the same change in Java.
3. Add vectors to `cases.json` or calls to `test_parity.py` that pin the change.
4. Run everything:

```bash
(cd python && .venv/bin/python -m pytest tests)                 # also fails if tools.json is stale
(cd java && ./gradlew test shadowJar)
python/.venv/bin/python -m pytest spec/conformance              # surface, errors, auth
PARITY_LIVE=1 TIBERO_HOST=… TIBERO_DATABASE=… TIBERO_USER=… TIBERO_PASSWORD=… \
  python/.venv/bin/python -m pytest spec/conformance            # + real database results
```

## Value rules

Rows are read straight from the JDBC `ResultSet` (by `java.sql.Types`), not through driver-specific
object mapping, and become JSON as follows:

| Column type | JSON |
|---|---|
| `NUMERIC`, `DECIMAL`, `TINYINT`, `SMALLINT`, `INTEGER`, `BIGINT` | integral → integer if `|v| ≤ 2^53−1`, otherwise a string of digits; fractional → double |
| `FLOAT`, `REAL`, `DOUBLE` | double |
| `BIT`, `BOOLEAN` | boolean |
| `DATE`, `TIMESTAMP`, `TIMESTAMP WITH TIME ZONE` | `"YYYY-MM-DD HH:MM:SS"` plus `.ffffff` when microseconds ≠ 0 (Tibero `DATE` carries a time) |
| `TIME` | `"HH:MM:SS"` |
| `BINARY`, `VARBINARY`, `LONGVARBINARY`, `BLOB` | `"base64:…"` |
| everything else (`CHAR`, `VARCHAR`, `CLOB`, …) | string |
| SQL `NULL` | `null` |

Strings longer than `TIBERO_MAX_CELL_CHARS` code points are cut and suffixed `...[truncated N chars]`.
Duplicate column labels are renamed `ID`, `ID_2`, `ID_3`, … so no column is lost.

## Error texts

Tool failures are `isError` results with text `Error executing tool <name>: <message>`, where the
message is the guard's own text or `Database error: <java exception toString()>`. Input-schema
violations are `isError` in both, but their wording comes from each SDK and is not compared.

## Known, accepted differences

- Protocol version: the Python SDK speaks up to `2026-07-28`, the Java SDK up to `2025-11-25`;
  clients negotiate. Tool behaviour does not depend on it.
- Unknown tool names: Python returns an `isError` result, Java a JSON-RPC error.
- HTTP edge cases outside MCP (e.g. a POST without `Accept: text/event-stream`) are answered by each SDK.
