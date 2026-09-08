"""
Retail Lens — Customer Agent

Milestone 11: loads the reasoning contract from
app/prompts/customer_agent.txt and exposes the MCP Toolbox
customer behavior tool.
"""

import os

from pathlib import Path

from google.adk import Agent
from app.tools.mcp_toolbox import mcp_toolbox

_PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "customer_agent.txt"
_CUSTOMER_AGENT_INSTRUCTION = _PROMPT_PATH.read_text(encoding="utf-8")

customer_agent = Agent(
    name="customer_agent",
    model=os.getenv("RETAIL_LENS_MODEL", "gemini-3.6-flash"),
    description="Answers customer behavior, spending, and frequency queries using BigQuery data via MCP Toolbox.",
    instruction=_CUSTOMER_AGENT_INSTRUCTION,
    tools=[mcp_toolbox],
)