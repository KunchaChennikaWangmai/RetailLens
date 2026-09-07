"""
Standalone test — verify MCP Toolbox server lists tools over stdio.

Run from the project root:
    python test_mcp_fetch.py

Expected output:
    SUCCESS! Tools found:
    - get_daily_sales_summary
"""

import asyncio
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

_TOOLS_YAML = str(Path(__file__).parent / "tools.yaml")


async def test_mcp() -> None:
    print("Initializing McpToolset...")
    sp = StdioServerParameters(
        command="npx",
        args=["-y", "@toolbox-sdk/server", "--config", _TOOLS_YAML, "--stdio"],
        env=dict(os.environ),
    )
    connection_params = StdioConnectionParams(server_params=sp)
    toolset = McpToolset(connection_params=connection_params)

    print("Fetching tools...")
    try:
        tools = await toolset.get_tools()
        print("SUCCESS! Tools found:")
        for t in tools:
            print("-", t.name)
    except Exception:
        print("FAILED to fetch tools:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp())
