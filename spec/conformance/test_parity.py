"""Python and Java servers must be functionally identical.

Both servers are started over stdio and driven by the same MCP client:

- always: server identity, instructions, and tools/list (full and read-only) are
  compared with each other and with spec/tools.json; statement checks that fail
  before touching the database must return the same errors.
- with a database (TIBERO_HOST/TIBERO_DATABASE/TIBERO_USER/TIBERO_PASSWORD set and
  PARITY_LIVE=1): a battery of real calls whose structured results and error texts
  must match exactly.

Run from the repository root after ``./gradlew shadowJar`` in java/:

    python/.venv/bin/python -m pytest spec/conformance -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import pytest
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "spec" / "tools.json").read_text(encoding="utf-8"))
JAVA_JAR = ROOT / "java" / "build" / "libs" / f"tibero-mcp-server-{SPEC['server']['version']}.jar"
LIVE = os.getenv("PARITY_LIVE") == "1"

DB_ENV = {
    name: os.getenv(name, default)
    for name, default in (
        ("TIBERO_HOST", "127.0.0.1"),
        ("TIBERO_PORT", "8629"),
        ("TIBERO_DATABASE", "tibero"),
        ("TIBERO_USER", "parity"),
        ("TIBERO_PASSWORD", "parity"),
    )
}


def _servers(read_only: bool) -> dict[str, StdioServerParameters]:
    base = {"PATH": os.environ.get("PATH", ""), **DB_ENV, "MCP_TRANSPORT": "stdio", "LOG_LEVEL": "WARNING"}
    if read_only:
        base["MCP_READ_ONLY"] = "true"
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        base["JAVA_HOME"] = java_home
    return {
        "python": StdioServerParameters(
            command=sys.executable, args=["-m", "src.main"], cwd=str(ROOT / "python"), env=base
        ),
        # An empty MCP_CONFIG_FILE path keeps the Java server from reading a local mcp.cfg.
        "java": StdioServerParameters(
            command="java", args=["-jar", str(JAVA_JAR)], cwd=str(ROOT), env={**base, "MCP_CONFIG_FILE": "/nonexistent"}
        ),
    }


def _run(coro):
    return asyncio.run(coro)


async def _with_both(read_only: bool, action):
    if not JAVA_JAR.exists():
        pytest.fail(f"{JAVA_JAR} not built; run ./gradlew shadowJar in java/")
    results: dict[str, Any] = {}
    async with AsyncExitStack() as stack:
        for name, params in _servers(read_only).items():
            client = await stack.enter_async_context(Client(params, read_timeout_seconds=60))
            results[name] = await action(client)
    return results


def _dump(model: Any) -> Any:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


# ----- surface -----


@pytest.mark.parametrize("read_only", [False, True])
def test_tools_list_identical_and_matches_spec(read_only):
    async def tools(client):
        return [_dump(tool) for tool in (await client.list_tools()).tools]

    results = _run(_with_both(read_only, tools))
    expected = [t for t in SPEC["tools"] if not read_only or t["annotations"].get("readOnlyHint") is True]
    assert results["python"] == expected
    assert results["java"] == expected
    if read_only:
        assert "execute_dml" not in [t["name"] for t in results["java"]]


def test_server_identity_and_instructions():
    async def identity(client):
        info = client.server_info
        return {
            "name": info.name,
            "title": info.title,
            "version": info.version,
            "instructions": client.instructions,
            "tools_capability": client.server_capabilities.tools is not None,
        }

    results = _run(_with_both(False, identity))
    assert results["python"] == results["java"]
    assert results["java"]["version"] == SPEC["server"]["version"]
    assert results["java"]["instructions"] == SPEC["server"]["instructions"]


# Rejected before any connection is made, so these hold without a database.
OFFLINE_CALLS = [
    ("execute_query", {"query": "DELETE FROM t"}),
    ("execute_query", {"query": " ; "}),
    ("execute_dml", {"query": "DROP TABLE t"}),
    ("execute_dml", {"query": "SELECT 1 FROM dual"}),
    ("explain_plan", {"query": ";"}),
]

# Rejected by input-schema validation; messages differ by SDK, so only isError is compared.
INVALID_INPUTS = [
    ("execute_query", {}),
    ("execute_query", {"query": "SELECT 1 FROM dual", "max_rows": 0}),
    ("execute_query", {"query": "SELECT 1 FROM dual", "max_rows": 5001}),
    ("sample_table", {"schema_name": "S", "table_name": "T", "limit": 1001}),
    ("get_table_info", {"schema_name": "S"}),
]


def _result(result) -> dict[str, Any]:
    return {
        "is_error": bool(result.is_error),
        "structured": result.structured_content,
        "text": [json.loads(c.text) if not result.is_error else c.text for c in result.content if c.type == "text"],
    }


@pytest.mark.parametrize("name, args", OFFLINE_CALLS)
def test_offline_rejections_identical(name, args):
    async def call(client):
        return _result(await client.call_tool(name, args))

    results = _run(_with_both(False, call))
    assert results["python"]["is_error"] and results["python"] == results["java"]


@pytest.mark.parametrize("name, args", INVALID_INPUTS)
def test_invalid_inputs_rejected_by_both(name, args):
    async def call(client):
        return bool((await client.call_tool(name, args)).is_error)

    assert _run(_with_both(False, call)) == {"python": True, "java": True}


# ----- live database -----

LIVE_CALLS = [
    ("get_schema", {}),
    ("get_schema", {"schema_name": "singstat"}),
    ("get_schema", {"schema_name": "NO_SUCH_SCHEMA"}),
    ("get_table_info", {"schema_name": "MANUFACTURING", "table_name": "mfg_work_order"}),
    ("get_table_info", {"schema_name": "SINGSTAT", "table_name": "SG_MARKET_COUNTRY"}),
    ("get_table_info", {"schema_name": "SINGSTAT", "table_name": "NO_SUCH_TABLE"}),
    ("sample_table", {"schema_name": "WORLDBANK", "table_name": "wdi_country", "limit": 3}),
    ("sample_table", {"schema_name": "MANUFACTURING", "table_name": "MFG_WORK_ORDER", "limit": 5}),
    ("execute_query", {"query": "SELECT * FROM SINGSTAT.SG_MARKET_COUNTRY ORDER BY 1;"}),
    ("execute_query", {"query": "SELECT * FROM SINGSTAT.SG_MARKET_COUNTRY ORDER BY 1", "max_rows": 5}),
    (
        "execute_query",
        {
            "query": (
                "SELECT 1 AS A, 1 AS A, 1.5 AS FRAC, 0.1 AS TENTH, 123456789012345678901234567890 AS BIG, "
                "9007199254740992 AS EDGE, -42 AS NEG, NULL AS NOTHING, 'héllo 😀' AS UNI, "
                "TO_DATE('2026-10-20 13:14:15', 'YYYY-MM-DD HH24:MI:SS') AS D, "
                "TO_TIMESTAMP('2026-10-20 13:14:15.123456', 'YYYY-MM-DD HH24:MI:SS.FF6') AS TS, "
                "TO_TIMESTAMP('2026-10-20 00:00:00', 'YYYY-MM-DD HH24:MI:SS') AS TS0, "
                "TO_CLOB(RPAD('x', 4100, 'x')) AS LONGTEXT, HEXTORAW('00FF10') AS RAWV FROM DUAL"
            )
        },
    ),
    ("execute_query", {"query": "WITH t AS (SELECT LEVEL AS N FROM DUAL CONNECT BY LEVEL <= 12) SELECT * FROM t", "max_rows": 10}),
    ("execute_query", {"query": "SELECT nope FROM SINGSTAT.SG_MARKET_COUNTRY"}),
    ("execute_query", {"query": "SELECT * FROM MANUFACTURING.MFG_WORK_ORDER WHERE ROWNUM <= 20"}),
    ("explain_plan", {"query": "SELECT * FROM SINGSTAT.SG_MARKET_COUNTRY WHERE ROWNUM < 5"}),
    ("explain_plan", {"query": "SELECT COUNT(*) FROM MANUFACTURING.MFG_WORK_ORDER WHERE WORK_ORDER_CODE = 'X'"}),
    ("explain_plan", {"query": "SELECT nope FROM DUAL"}),
    ("execute_dml", {"query": "DELETE FROM SINGSTAT.SG_MARKET_COUNTRY WHERE 1 = 0", "dry_run": True}),
]


@pytest.mark.skipif(not LIVE, reason="set PARITY_LIVE=1 and TIBERO_* to compare against a database")
@pytest.mark.parametrize("name, args", LIVE_CALLS, ids=[f"{n}-{i}" for i, (n, _) in enumerate(LIVE_CALLS)])
def test_live_results_identical(name, args):
    async def call(client):
        return _result(await client.call_tool(name, args))

    results = _run(_with_both(False, call))
    assert results["python"] == results["java"], json.dumps(results, ensure_ascii=False, indent=1)[:4000]


@pytest.mark.parametrize("implementation", ["python", "java"])
def test_stdio_stdout_carries_only_protocol(implementation):
    """Any log line on stdout corrupts the stdio stream (a client may skip it silently)."""
    import subprocess

    params = _servers(False)[implementation]
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "parity", "version": "0"}},
    }
    completed = subprocess.run(
        [params.command, *params.args],
        cwd=params.cwd,
        env=params.env,
        input=json.dumps(initialize) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert lines, completed.stderr[-2000:]
    for line in lines:
        assert json.loads(line).get("jsonrpc") == "2.0", line[:200]


# ----- HTTP transport and authentication -----

HTTP_KEY = "parity-" + "k" * 40


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def http_servers():
    """Both servers over Streamable HTTP with the same key, read-only, on loopback ports."""
    import subprocess
    import time
    import urllib.request

    procs, urls = [], {}
    try:
        for name, params in _servers(True).items():
            port = _free_port()
            env = {**params.env, "MCP_TRANSPORT": "http", "MCP_SERVER_HOST": "127.0.0.1", "MCP_SERVER_PORT": str(port), "MCP_API_KEYS": f"other-key,{HTTP_KEY}"}
            procs.append(subprocess.Popen([params.command, *params.args], cwd=params.cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            urls[name] = f"http://127.0.0.1:{port}"
        for url in urls.values():
            for _ in range(120):
                try:
                    urllib.request.urlopen(url + "/healthz", timeout=1)
                    break
                except Exception:
                    time.sleep(0.25)
            else:
                pytest.fail(f"{url} did not start")
        yield urls
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=20)


def _post(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode()
    try:
        payload = json.loads(text)
    except ValueError:
        payload = text
    if isinstance(payload, dict) and "result" in payload:
        payload = sorted(tool["name"] for tool in payload["result"]["tools"])
    return status, payload


AUTH_CASES = {
    "bearer": ("/mcp", {"Authorization": f"Bearer {HTTP_KEY}"}),
    "bearer-lowercase-scheme": ("/mcp", {"Authorization": f"bearer {HTTP_KEY}"}),
    "x-api-key": ("/mcp", {"X-API-Key": HTTP_KEY}),
    "path-key": (f"/{HTTP_KEY}/mcp", {}),
    "second-key": ("/mcp", {"Authorization": "Bearer other-key"}),
    "no-key": ("/mcp", {}),
    "wrong-key": ("/mcp", {"Authorization": "Bearer nope"}),
    "wrong-path-key": ("/nope/mcp", {}),
    "basic-scheme": ("/mcp", {"Authorization": f"Basic {HTTP_KEY}"}),
}


@pytest.mark.parametrize("case", AUTH_CASES)
def test_http_auth_identical(http_servers, case):
    path, headers = AUTH_CASES[case]
    results = {name: _post(url + path, headers) for name, url in http_servers.items()}
    assert results["python"] == results["java"]
    status, payload = results["java"]
    if case in ("bearer", "bearer-lowercase-scheme", "x-api-key", "path-key", "second-key"):
        assert status == 200 and "execute_dml" not in payload
    else:
        assert status == 401 and payload == {"error": "unauthorized", "error_description": "Missing or invalid API key"}


def test_http_health_identical(http_servers):
    import urllib.request

    bodies = {}
    for name, url in http_servers.items():
        with urllib.request.urlopen(url + "/healthz", timeout=5) as response:
            bodies[name] = (response.status, json.loads(response.read()))
    assert bodies["python"] == bodies["java"] == (200, {"status": "ok"})


def test_http_tools_list_via_client_identical(http_servers):
    async def tools(url):
        async with Client(f"{url}/{HTTP_KEY}/mcp") as client:
            return [_dump(tool) for tool in (await client.list_tools()).tools]

    results = {name: _run(tools(url)) for name, url in http_servers.items()}
    expected = [t for t in SPEC["tools"] if t["annotations"].get("readOnlyHint") is True]
    assert results["python"] == results["java"] == expected


@pytest.mark.parametrize("implementation", ["python", "java"])
def test_refuses_public_listen_without_keys(implementation):
    import subprocess

    params = _servers(False)[implementation]
    env = {**params.env, "MCP_TRANSPORT": "http", "MCP_SERVER_HOST": "0.0.0.0", "MCP_SERVER_PORT": str(_free_port())}
    completed = subprocess.run([params.command, *params.args], cwd=params.cwd, env=env, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 1
    assert "MCP_API_KEYS is empty" in completed.stderr
