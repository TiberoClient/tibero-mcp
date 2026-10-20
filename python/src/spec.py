"""Export the server's MCP surface as the shared spec consumed by the Java server.

    python -m src.spec > ../spec/tools.json

The Java implementation registers its tools from this file, and the tests of both
implementations compare their live tools/list against it, so the two servers expose
exactly the same names, descriptions, annotations and input/output schemas.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from . import __version__
from .mcp.server import INSTRUCTIONS, mcp


def build_spec() -> dict[str, Any]:
    tools = asyncio.run(mcp.list_tools())
    return {
        "server": {
            "name": "tibero-mcp-server",
            "title": "Tibero Database",
            "version": __version__,
            "instructions": INSTRUCTIONS,
        },
        "tools": [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools],
    }


def render_spec() -> str:
    return json.dumps(build_spec(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render_spec())
