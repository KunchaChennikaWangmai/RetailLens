"""
Retail Lens — MCP Toolbox Integration

Connects the Sales Agent to the MCP Toolbox for Databases server (npm package
@toolbox-sdk/server) running in stdio mode, configured by tools.yaml.

The server is spawned as a subprocess by ADK's McpToolset using the
StdioConnectionParams transport.  The full current environment is forwarded
so that GOOGLE_CLOUD_PROJECT and Application Default Credentials are available
to the subprocess, which needs them to expand tools.yaml and query BigQuery.
"""
import os
from pathlib import Path

from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Absolute path to tools.yaml so the subprocess can find it regardless of CWD.
_TOOLS_YAML = str(Path(__file__).parents[2] / "tools.yaml")

server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@toolbox-sdk/server", "--config", _TOOLS_YAML, "--stdio"],
    # Forward the full environment so the subprocess inherits GOOGLE_CLOUD_PROJECT
    # and Application Default Credentials needed to connect to BigQuery.
    env=dict(os.environ),
)

# The default 5s timeout is too short for the Milestone 2B analytical
# queries (product movement, behaviour profile) which join multiple CTEs
# against BigQuery. 120s gives complex queries room to complete.
connection_params = StdioConnectionParams(server_params=server_params, timeout=120.0)

# McpToolset spawns the server, lists its tools, and proxies every tool call.
mcp_toolbox = McpToolset(connection_params=connection_params)
