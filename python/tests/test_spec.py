"""The committed shared spec must match what this server actually exposes."""

import asyncio
import json
from pathlib import Path

from src.mcp import server
from src.spec import render_spec

SPEC_PATH = Path(__file__).parents[2] / "spec" / "tools.json"


def test_spec_file_is_current():
    assert SPEC_PATH.read_text(encoding="utf-8") == render_spec(), "run: python -m src.spec > ../spec/tools.json"


def test_read_only_keeps_exactly_read_only_tools(monkeypatch):
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    expected = [tool["name"] for tool in spec["tools"] if tool["annotations"].get("readOnlyHint") is True]
    removed = []
    monkeypatch.setattr(server.mcp, "remove_tool", removed.append)
    server.apply_read_only(True)
    remaining = [t.name for t in asyncio.run(server.mcp.list_tools()) if t.name not in removed]
    assert remaining == expected
    assert removed == ["execute_dml"]
