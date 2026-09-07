"""
Retail Lens — Inventory Agent

Milestone 4: loads the reasoning contract from
app/prompts/inventory_agent.txt and exposes the two MCP Toolbox
inventory evidence tools.
"""

from pathlib import Path

from google.adk import Agent
from app.tools.mcp_toolbox import mcp_toolbox

# Load the reasoning contract from the prompt file.
_PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "inventory_agent.txt"
_INVENTORY_AGENT_INSTRUCTION = _PROMPT_PATH.read_text(encoding="utf-8")

inventory_agent = Agent(
    name="inventory_agent",
    model="gemini-3.6-flash",
    description="Answers inventory and product-context queries using BigQuery data via MCP Toolbox.",
    instruction=_INVENTORY_AGENT_INSTRUCTION,
    tools=[mcp_toolbox],
)
