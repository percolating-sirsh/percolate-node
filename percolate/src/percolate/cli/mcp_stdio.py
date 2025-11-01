#!/usr/bin/env python3
"""Run MCP server in stdio mode for Claude Desktop."""

import sys
from percolate.mcplib.server import create_mcp_server


def main():
    """Run MCP server in stdio mode."""
    mcp = create_mcp_server()
    # FastMCP.run() runs in stdio mode by default
    mcp.run()


if __name__ == "__main__":
    main()
