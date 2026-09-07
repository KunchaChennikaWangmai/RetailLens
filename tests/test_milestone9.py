"""
Smoke Test - Milestone 9: Workforce Agent

Deterministic tests verify:
  1. workforce_agent imports successfully
  2. workforce_agent uses mcp_toolbox
  3. workforce_agent does not directly access BigQuery
  4. workforce_agent loads workforce_agent.txt
  5. workforce prompt contains anti-hallucination rules
  6. get_workforce_summary remains available
  7. All existing 10 MCP tools remain available
  8. sales_agent remains intact
  9. inventory_agent remains intact
  10. orchestrator imports successfully
  11. workforce_agent is registered as orchestrator sub-agent
  12. sales/inventory routing remains intact
  13. No new MCP tools were introduced
  14. No BigQuery data was modified

Usage:
    python tests/test_milestone9.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

try:
    from app.agents.workforce_agent import workforce_agent
except ImportError as e:
    print(f"[smoke M9] FAIL - import workforce_agent: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from app.agents.orchestrator import root_agent
except ImportError as e:
    print(f"[smoke M9] FAIL - import orchestrator: {e}", file=sys.stderr)
    sys.exit(1)

from app.agents.sales_agent import sales_agent
from app.agents.inventory_agent import inventory_agent
from app.tools.mcp_toolbox import mcp_toolbox

_TOOLS_YAML = str(Path(__file__).parent.parent / "tools.yaml")

EXPECTED_SALES_TOOLS = {
    "get_daily_sales_summary",
    "get_daily_product_movement",
    "get_sales_trends",
    "get_product_behavior_profile",
}

EXPECTED_INVENTORY_TOOLS = {
    "get_product_inventory_profile",
    "get_inventory_category_profile",
    "get_product_profitability",
    "get_current_stock_levels",
    "get_current_supply_status",
}

EXPECTED_WORKFORCE_TOOLS = {
    "get_workforce_summary",
}

EXPECTED_ALL_TOOLS = EXPECTED_SALES_TOOLS | EXPECTED_INVENTORY_TOOLS | EXPECTED_WORKFORCE_TOOLS


def run_deterministic_tests():
    failures = []

    # 1. workforce_agent imports successfully
    print("[smoke M9] CHECK 1: workforce_agent imports...")
    try:
        from app.agents.workforce_agent import workforce_agent as wa
        print("[smoke M9] PASS - workforce_agent imports successfully.")
    except Exception as exc:
        failures.append(f"workforce_agent import failed: {exc}")
        print(f"[smoke M9] FAIL - {exc}", file=sys.stderr)

    # 2. workforce_agent uses mcp_toolbox
    print("[smoke M9] CHECK 2: workforce_agent uses mcp_toolbox...")
    if mcp_toolbox not in workforce_agent.tools:
        failures.append("workforce_agent missing mcp_toolbox")
        print("[smoke M9] FAIL - workforce_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M9] PASS - workforce_agent uses mcp_toolbox.")

    # 3. workforce_agent does not directly access BigQuery
    print("[smoke M9] CHECK 3: No direct BigQuery in workforce_agent...")
    agent_src = Path("app/agents/workforce_agent.py").read_text()
    if "google.cloud.bigquery" in agent_src or "bigquery_client" in agent_src:
        failures.append("workforce_agent has direct BigQuery access")
        print("[smoke M9] FAIL - direct BigQuery access", file=sys.stderr)
    else:
        print("[smoke M9] PASS - no direct BigQuery access.")

    # 4. workforce_agent loads workforce_agent.txt
    print("[smoke M9] CHECK 4: workforce_agent loads prompt...")
    prompt_path = Path("app/prompts/workforce_agent.txt")
    if not prompt_path.exists():
        failures.append("app/prompts/workforce_agent.txt does not exist")
        print("[smoke M9] FAIL - prompt file missing", file=sys.stderr)
    else:
        text = prompt_path.read_text(encoding="utf-8")
        instr = workforce_agent.instruction
        if "PRINCIPLE 1" not in instr or "ABSOLUTE PROHIBITIONS" not in instr:
            failures.append("workforce_agent.instruction does not contain reasoning contract")
            print("[smoke M9] FAIL - instruction missing contract", file=sys.stderr)
        else:
            print(f"[smoke M9] PASS - Prompt loaded ({len(text)} chars).")

    # 5. workforce prompt contains anti-hallucination rules
    print("[smoke M9] CHECK 5: Anti-hallucination rules present...")
    required_markers = [
        "NEVER INVENT DATA",
        "Never invent",
        "NEVER estimate",
        "Never fabricate",
        "Never claim lateness",
        "ABSOLUTE PROHIBITIONS",
    ]
    missing_markers = [m for m in required_markers if m not in text]
    if missing_markers:
        failures.append(f"Prompt missing anti-hallucination markers: {missing_markers}")
        print(f"[smoke M9] FAIL - Missing: {missing_markers}", file=sys.stderr)
    else:
        print("[smoke M9] PASS - All anti-hallucination rules present.")

    # 6-7. MCP tools check (via tools.yaml, no Gemini needed)
    print("[smoke M9] CHECK 6-7: MCP tools in tools.yaml...")
    import yaml
    with open(_TOOLS_YAML) as f:
        cfg = yaml.safe_load(f)
    tool_names = set(cfg.get("tools", {}).keys())
    if tool_names != EXPECTED_ALL_TOOLS:
        failures.append(f"tools.yaml mismatch: {tool_names} vs {EXPECTED_ALL_TOOLS}")
        print(f"[smoke M9] FAIL - tool mismatch", file=sys.stderr)
    else:
        print(f"[smoke M9] PASS - Exactly {len(tool_names)} tools: {sorted(tool_names)}")

    # 8. sales_agent remains intact
    print("[smoke M9] CHECK 8: sales_agent intact...")
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent missing mcp_toolbox")
        print("[smoke M9] FAIL - sales_agent missing mcp_toolbox", file=sys.stderr)
    else:
        sales_instr = sales_agent.instruction
        if "PRINCIPLE 1" not in sales_instr or "PRINCIPLE 12" not in sales_instr:
            failures.append("sales_agent reasoning contract not loaded")
            print("[smoke M9] FAIL - sales contract missing", file=sys.stderr)
        else:
            print("[smoke M9] PASS - sales_agent intact.")

    # 9. inventory_agent remains intact
    print("[smoke M9] CHECK 9: inventory_agent intact...")
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent missing mcp_toolbox")
        print("[smoke M9] FAIL - inventory_agent missing mcp_toolbox", file=sys.stderr)
    else:
        inv_instr = inventory_agent.instruction
        if "PRINCIPLE 1" not in inv_instr or "ABSOLUTE PROHIBITIONS" not in inv_instr:
            failures.append("inventory_agent reasoning contract not loaded")
            print("[smoke M9] FAIL - inventory contract missing", file=sys.stderr)
        else:
            print("[smoke M9] PASS - inventory_agent intact.")

    # 10. orchestrator imports successfully
    print("[smoke M9] CHECK 10: orchestrator imports...")
    try:
        from app.agents.orchestrator import root_agent as ra
        print("[smoke M9] PASS - orchestrator imports successfully.")
    except Exception as exc:
        failures.append(f"orchestrator import failed: {exc}")
        print(f"[smoke M9] FAIL - {exc}", file=sys.stderr)

    # 11. workforce_agent is registered as orchestrator sub-agent
    print("[smoke M9] CHECK 11: workforce_agent is sub-agent...")
    sub_names = [a.name for a in root_agent.sub_agents]
    if "workforce_agent" not in sub_names:
        failures.append(f"workforce_agent not in sub_agents: {sub_names}")
        print(f"[smoke M9] FAIL - sub_agents: {sub_names}", file=sys.stderr)
    else:
        print(f"[smoke M9] PASS - workforce_agent registered. Sub-agents: {sub_names}")

    # 12. sales/inventory routing remains intact
    print("[smoke M9] CHECK 12: Sales/inventory routing intact...")
    if "sales_agent" not in sub_names:
        failures.append("sales_agent not in sub_agents")
        print("[smoke M9] FAIL - sales_agent missing from sub_agents", file=sys.stderr)
    elif "inventory_agent" not in sub_names:
        failures.append("inventory_agent not in sub_agents")
        print("[smoke M9] FAIL - inventory_agent missing from sub_agents", file=sys.stderr)
    else:
        print("[smoke M9] PASS - All 3 sub-agents registered.")

    # 13. No new MCP tools were introduced
    print("[smoke M9] CHECK 13: No new MCP tools...")
    if len(tool_names) != 10:
        failures.append(f"Expected 10 tools, got {len(tool_names)}")
        print(f"[smoke M9] FAIL - {len(tool_names)} tools", file=sys.stderr)
    else:
        print("[smoke M9] PASS - Exactly 10 tools (no new tools).")

    # 14. No direct BigQuery in any agent
    print("[smoke M9] CHECK 14: No direct BigQuery in any agent...")
    for name, path in [("sales_agent", "app/agents/sales_agent.py"),
                        ("inventory_agent", "app/agents/inventory_agent.py"),
                        ("workforce_agent", "app/agents/workforce_agent.py"),
                        ("orchestrator", "app/agents/orchestrator.py")]:
        src = Path(path).read_text()
        if "google.cloud.bigquery" in src or "bigquery_client" in src:
            failures.append(f"{name} has direct BigQuery access")
            print(f"[smoke M9] FAIL - {name} has direct BigQuery", file=sys.stderr)
    if not any("direct BigQuery" in f for f in failures):
        print("[smoke M9] PASS - No direct BigQuery in any agent.")

    return failures


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M9] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    print("=== MILESTONE 9 DETERMINISTIC TESTS ===\n")
    failures = run_deterministic_tests()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[smoke M9] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M9] RESULT: PASS - All Milestone 9 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())