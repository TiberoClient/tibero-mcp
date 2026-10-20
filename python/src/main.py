"""Main entry point for Tibero MCP Server."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    os.environ["PYTHONIOENCODING"] = "utf-8"

# Load environment variables
config_path = Path(__file__).parent.parent / "mcp.cfg"
if config_path.exists():
    load_dotenv(config_path)
else:
    logger.warning(f"mcp.cfg file not found at {config_path}. Using environment variables.")


def setup_logging():
    """Configure logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )


def validate_environment():
    """Validate required environment variables."""
    required_vars = [
        "TIBERO_HOST",
        "TIBERO_DATABASE",
        "TIBERO_USER",
        "TIBERO_PASSWORD",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your mcp.cfg file or environment.")
        sys.exit(1)


async def run_stdio_server():
    """Run the server over stdio (local clients such as Cursor or Claude Desktop)."""
    from .mcp.server import mcp
    
    logger.info("Starting Tibero MCP Server as stdio server")
    logger.info("Server will communicate via stdin/stdout")
    
    await mcp.run_stdio_async()


def _api_keys() -> list[str]:
    return [key.strip() for key in os.getenv("MCP_API_KEYS", "").split(",") if key.strip()]


def build_http_app():
    """Build the ASGI app: Streamable HTTP endpoint behind key auth and a redacting access log."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from mcp.server.transport_security import TransportSecuritySettings

    from .mcp.auth import ApiKeyMiddleware, RequestLogMiddleware
    from .mcp.server import mcp

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    allowed_hosts = [host.strip() for host in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if host.strip()]
    transport_security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts)
        if allowed_hosts
        else TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )

    # Stateless + JSON responses: every POST is self-contained, so the server works
    # behind reverse proxies and restarts without clients losing a session.
    app = mcp.streamable_http_app(
        streamable_http_path=os.getenv("MCP_HTTP_PATH", "/mcp"),
        stateless_http=True,
        json_response=True,
        transport_security=transport_security,
    )

    keys = _api_keys()
    if keys:
        app = ApiKeyMiddleware(app, keys)
    return RequestLogMiddleware(app, keys)


async def run_http_server():
    """Run the Streamable HTTP server."""
    import uvicorn

    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))

    if not _api_keys():
        if host not in ("127.0.0.1", "localhost", "::1") and os.getenv("MCP_ALLOW_ANONYMOUS", "").lower() != "true":
            logger.error(
                "MCP_API_KEYS is empty while listening on a non-loopback address. "
                "Set MCP_API_KEYS, or MCP_ALLOW_ANONYMOUS=true to run without authentication."
            )
            sys.exit(1)
        logger.warning("Running without API key authentication")

    logger.info(f"Starting Tibero MCP Server (Streamable HTTP) on {host}:{port}{os.getenv('MCP_HTTP_PATH', '/mcp')}")

    # uvicorn's own access log prints raw paths, which may carry the API key.
    config = uvicorn.Config(
        build_http_app(),
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
    server = uvicorn.Server(config)
    await server.serve()


def main():
    """Main entry point using FastMCP."""
    setup_logging()
    validate_environment()
    
    # Determine transport mode from environment or default to http
    transport = os.getenv("MCP_TRANSPORT", "http").lower()
    
    if transport in ("http", "streamable-http"):
        asyncio.run(run_http_server())
    else:
        asyncio.run(run_stdio_server())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
