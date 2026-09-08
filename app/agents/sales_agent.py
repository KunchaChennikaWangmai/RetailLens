"""
Retail Lens — Sales Agent

Milestone 3: loads the reasoning contract from app/prompts/sales_agent.txt
and exposes the four MCP Toolbox analytical tools.
"""

import os

from pathlib import Path

from google.adk import Agent
from app.tools.mcp_toolbox import mcp_toolbox

# Load the reasoning contract from the prompt file so the full instruction
# is maintained outside of Python source.
_PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "sales_agent.txt"
_SALES_AGENT_INSTRUCTION = _PROMPT_PATH.read_text(encoding="utf-8")

sales_agent = Agent(
    name="sales_agent",
    model=os.getenv("RETAIL_LENS_MODEL", "gemini-3.6-flash"),
    description="Answers sales-related queries using BigQuery data via MCP Toolbox.",
    instruction=_SALES_AGENT_INSTRUCTION,
    tools=[mcp_toolbox],
)