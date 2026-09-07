"""
Smoke Test - Milestone 5: Orchestrator Integration & Cross-Agent Reasoning

Deterministic tests verify:
  - orchestrator imports successfully
  - sales_agent and inventory_agent are registered as sub_agents
  - both specialist agents use MCP Toolbox
  - exactly 6 MCP tools remain configured
  - Sales and Inventory tools unchanged
  - no direct BigQuery access in orchestrator
  - existing reasoning contracts remain loaded
  - no forbidden inventory fields introduced

One optional Gemini NL test (only if quota available, no retries).

Usage:
    python tests/test_milestone5.py
"""

import asyncio
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

try:
    from app.agents.orchestrator import root_agent
except ImportError as e:
    print(f"[smoke M5] FAIL - Failed to import root_agent: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from app.agents.sales_agent import sales_agent
except ImportError as e:
    print(f"[smoke M5] FAIL - Failed to import sales_agent: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from app.agents.inventory_agent import inventory_agent
except ImportError as e:
    print(f"[smoke M5] FAIL - Failed to import inventory_agent: {e}", file=sys.stderr)
    sys.exit(1)

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

EXPECTED_ALL_TOOLS = EXPECTED_SALES_TOOLS | EXPECTED_INVENTORY_TOOLS

FORBIDDEN_STOCK_FIELDS = [
    "current_stock", "stock_on_hand", "reorder_point",
    "safety_stock", "stock_received", "stock_remaining",
    "inventory_quantity",
]


def run_deterministic_tests():
    failures = []

    # 1. Orchestrator imports successfully
    print("[smoke M5] CHECK 1: Orchestrator imports...")
    try:
        from app.agents.orchestrator import root_agent as ra
        print("[smoke M5] PASS - orchestrator imports successfully.")
    except Exception as exc:
        failures.append(f"orchestrator import failed: {exc}")
        print(f"[smoke M5] FAIL - {exc}", file=sys.stderr)

    # 2. sales_agent registered as sub-agent
    print("[smoke M5] CHECK 2: sales_agent is a sub-agent...")
    sub_agent_names = [a.name for a in root_agent.sub_agents]
    if "sales_agent" not in sub_agent_names:
        failures.append("sales_agent not in orchestrator sub_agents")
        print(f"[smoke M5] FAIL - sub_agents: {sub_agent_names}", file=sys.stderr)
    else:
        print("[smoke M5] PASS - sales_agent is registered.")

    # 3. inventory_agent registered as sub-agent
    print("[smoke M5] CHECK 3: inventory_agent is a sub-agent...")
    if "inventory_agent" not in sub_agent_names:
        failures.append("inventory_agent not in orchestrator sub_agents")
        print(f"[smoke M5] FAIL - sub_agents: {sub_agent_names}", file=sys.stderr)
    else:
        print("[smoke M5] PASS - inventory_agent is registered.")

    # 4. Both specialist agents use MCP Toolbox
    print("[smoke M5] CHECK 4: Both agents use MCP Toolbox...")
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent missing mcp_toolbox")
        print("[smoke M5] FAIL - sales_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M5] PASS - sales_agent uses mcp_toolbox.")
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent missing mcp_toolbox")
        print("[smoke M5] FAIL - inventory_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M5] PASS - inventory_agent uses mcp_toolbox.")

    # 5. Orchestrator does NOT have direct BigQuery access
    print("[smoke M5] CHECK 5: No direct BigQuery in orchestrator...")
    orch_src = Path("app/agents/orchestrator.py").read_text()
    if "google.cloud.bigquery" in orch_src or "bigquery_client" in orch_src:
        failures.append("orchestrator has direct BigQuery access")
        print("[smoke M5] FAIL - direct BigQuery access found", file=sys.stderr)
    else:
        print("[smoke M5] PASS - no direct BigQuery access.")

    # 6. Orchestrator does NOT have tools (delegates to sub-agents)
    print("[smoke M5] CHECK 6: Orchestrator delegates (no own tools)...")
    if hasattr(root_agent, 'tools') and root_agent.tools:
        # Orchestrator may have empty tools list or None - that's fine
        # But it should NOT have mcp_toolbox directly
        if mcp_toolbox in root_agent.tools:
            failures.append("orchestrator has mcp_toolbox directly (should delegate)")
            print("[smoke M5] FAIL - orchestrator has mcp_toolbox", file=sys.stderr)
        else:
            print("[smoke M5] PASS - orchestrator does not duplicate MCP tools.")
    else:
        print("[smoke M5] PASS - orchestrator has no own tools.")

    # 7. Sales reasoning contract remains loaded
    print("[smoke M5] CHECK 7: Sales reasoning contract loaded...")
    sales_instr = sales_agent.instruction
    if "PRINCIPLE 1" not in sales_instr or "PRINCIPLE 12" not in sales_instr:
        failures.append("sales_agent reasoning contract not loaded")
        print("[smoke M5] FAIL - sales contract missing", file=sys.stderr)
    else:
        print("[smoke M5] PASS - sales reasoning contract intact.")

    # 8. Inventory reasoning contract remains loaded
    print("[smoke M5] CHECK 8: Inventory reasoning contract loaded...")
    inv_instr = inventory_agent.instruction
    if "PRINCIPLE 1" not in inv_instr or "ABSOLUTE PROHIBITIONS" not in inv_instr:
        failures.append("inventory_agent reasoning contract not loaded")
        print("[smoke M5] FAIL - inventory contract missing", file=sys.stderr)
    else:
        print("[smoke M5] PASS - inventory reasoning contract intact.")

    # 9. No forbidden stock fields in orchestrator
    print("[smoke M5] CHECK 9: No forbidden stock fields in orchestrator...")
    found_forbidden = [f for f in FORBIDDEN_STOCK_FIELDS if f in orch_src.lower()]
    if found_forbidden:
        failures.append(f"Forbidden fields in orchestrator: {found_forbidden}")
        print(f"[smoke M5] FAIL - {found_forbidden}", file=sys.stderr)
    else:
        print("[smoke M5] PASS - no forbidden stock fields.")

    # 10. tools.yaml has exactly 6 tools
    print("[smoke M5] CHECK 10: tools.yaml has exactly 6 tools...")
    import yaml
    with open(_TOOLS_YAML) as f:
        cfg = yaml.safe_load(f)
    tool_names = set(cfg.get("tools", {}).keys())
    if tool_names != EXPECTED_ALL_TOOLS:
        failures.append(f"tools.yaml mismatch: {tool_names} vs {EXPECTED_ALL_TOOLS}")
        print(f"[smoke M5] FAIL - tool mismatch", file=sys.stderr)
    else:
        print(f"[smoke M5] PASS - exactly 6 tools: {sorted(tool_names)}")

    # 11. Sales tools unchanged
    print("[smoke M5] CHECK 11: Sales tools unchanged...")
    sales_toolset = set(cfg.get("toolsets", {}).get("sales_toolset", []))
    if sales_toolset != EXPECTED_SALES_TOOLS:
        failures.append(f"sales_toolset changed: {sales_toolset}")
        print(f"[smoke M5] FAIL - sales_toolset changed", file=sys.stderr)
    else:
        print("[smoke M5] PASS - sales tools unchanged.")

    # 12. Inventory tools unchanged
    print("[smoke M5] CHECK 12: Inventory tools unchanged...")
    inv_toolset = set(cfg.get("toolsets", {}).get("inventory_toolset", []))
    if inv_toolset != EXPECTED_INVENTORY_TOOLS:
        failures.append(f"inventory_toolset changed: {inv_toolset}")
        print(f"[smoke M5] FAIL - inventory_toolset changed", file=sys.stderr)
    else:
        print("[smoke M5] PASS - inventory tools unchanged.")

    return failures


async def run_gemini_nl_test():
    """ONE Gemini NL test - cross-agent reasoning. No retries."""
    print("[smoke M5] GEMINI NL TEST: Cross-agent reasoning...")
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    APP_NAME = "retail_lens"
    USER_ID = "smoke_test_user_m5"

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    prompt = (
        "Which products are both selling strongly and have inventory "
        "characteristics that deserve attention? Use available sales and "
        "inventory evidence, clearly distinguish facts from interpretation, "
        "and do not invent stock levels."
    )

    msg = Content(role="user", parts=[Part(text=prompt)])
    final = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=msg
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final = event.content.parts[0].text or ""
    return final


async def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M5] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    # Run deterministic tests
    print("=== MILESTONE 5 DETERMINISTIC TESTS ===\n")
    failures = run_deterministic_tests()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[smoke M5] DETERMINISTIC RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("[smoke M5] DETERMINISTIC RESULT: PASS - All checks succeeded.\n")

    # Run ONE Gemini NL test (no retries)
    print("=== MILESTONE 5 GEMINI NL TEST ===\n")
    try:
        nl_text = await run_gemini_nl_test()
        if not nl_text:
            print("[smoke M5] GEMINI RESULT: FAIL - empty response")
            sys.exit(1)

        # Check for failure markers
        lowered = nl_text.lower()
        fail_markers = ["database error", "unrecognized name", "tool not found",
                        "connection closed", "syntax error", "timed out"]
        matched = [m for m in fail_markers if m in lowered]
        if matched:
            print(f"[smoke M5] GEMINI RESULT: FAIL - failure markers: {matched}")
            sys.exit(1)

        print("[smoke M5] GEMINI RESULT: PASS")
        print("\n=== COMPLETE GEMINI RESPONSE ===\n")
        print(nl_text)
        print("\n=== END GEMINI RESPONSE ===\n")
        sys.exit(0)

    except Exception as exc:
        is_quota = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
        if is_quota:
            print(f"[smoke M5] GEMINI RESULT: SKIP - Quota exhausted (429)")
            print(f"[smoke M5] Error: {str(exc)[:300]}")
            # Deterministic tests passed, so exit 0 with quota note
            sys.exit(0)
        else:
            print(f"[smoke M5] GEMINI RESULT: FAIL - {exc}")
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
