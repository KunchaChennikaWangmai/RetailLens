"""
Retail Lens — Workforce Agent

Milestone 9: loads the reasoning contract from
app/prompts/workforce_agent.txt and exposes the MCP Toolbox
workforce evidence tool.
"""

import os

from pathlib import Path

from google.adk import Agent
from app.tools.mcp_toolbox import mcp_toolbox

_PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "workforce_agent.txt"
_WORKFORCE_AGENT_INSTRUCTION = _PROMPT_PATH.read_text(encoding="utf-8")

workforce_agent = Agent(
    name="workforce_agent",
    model=os.getenv("RETAIL_LENS_MODEL", "gemini-3.6-flash"),
    description="Answers workforce, attendance, and labour-cost queries using BigQuery data via MCP Toolbox.",
    instruction=_WORKFORCE_AGENT_INSTRUCTION,
    tools=[mcp_toolbox],
)