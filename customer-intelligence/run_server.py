"""
Standalone runner for AI4Search MCP Server.

Usage:
    python run_server.py

This directly starts the MCP server on stdio transport without needing the `mcp` CLI.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from search_mcp.server import main

if __name__ == "__main__":
    main()
