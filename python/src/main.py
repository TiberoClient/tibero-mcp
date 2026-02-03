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
    """Run FastMCP server as stdio server (for Cursor)."""
    from .mcp.server import mcp
    
    logger.info("Starting Tibero MCP Server as stdio server")
    logger.info("Server will communicate via stdin/stdout")
    
    # Use FastMCP's stdio server method (recommended for Cursor)
    await mcp.run_stdio_async()


async def run_http_server():
    """
    Run FastMCP server as Streamable HTTP server.
    
    Reference: https://pypi.org/project/mcp/#streamable-http-transport
    """
    from .mcp.server import mcp
    import uvicorn
    
    # Get server configuration
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))
    
    logger.info(f"Starting Tibero MCP Server as Streamable HTTP server on {host}:{port}")
    logger.info(f"Server will be accessible at: http://{host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp")
    
    # Get Streamable HTTP app from FastMCP
    # This returns a Starlette ASGI app that handles MCP protocol
    app = mcp.streamable_http_app()
    
    # Run with uvicorn
    # The app handles all MCP protocol endpoints including /mcp
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


def main():
    """Main entry point using FastMCP."""
    setup_logging()
    validate_environment()
    
    # Determine transport mode from environment or default to http
    transport = os.getenv("MCP_TRANSPORT", "http").lower()
    
    if transport == "http" or transport == "sse":
        # Run HTTP server
        asyncio.run(run_http_server())
    else:
        # Run stdio server (default, recommended for Cursor)
        asyncio.run(run_stdio_server())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
