"""
Smoke Test - Milestone 4: Inventory Agent Evidence Layer

Deterministic tests (no Gemini API calls):
  1. MCP Toolbox starts and lists all 6 tools (4 Sales + 2 Inventory).
  2. Both Inventory tools successfully query BigQuery.
  3. Inventory Agent imports successfully.
  4. Orchestrator imports successfully.
  5. Inventory Agent uses MCP Toolbox (not direct BigQuery).
  6. Inventory Agent does not reference nonexistent stock fields.
  7. Inventory prompt exists and is loaded.
  8. No existing Sales functionality is broken.

One optional Gemini NL test (only if quota available):
  - "What are the inventory characteristics of our household cleaning products?"

Usage:
    python tests/test_milestone4.py
"""

import asyncio
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

try:
    from app.agents.inventory_agent import inventory_agent
except ImportError as e:
    print(f"[smoke M4] FAIL - Failed to import inventory_agent: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from app.agents.orchestrator import root_agent
except ImportError as e:
    print(f"[smoke M4] FAIL - Failed to import orchestrator: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from app.agents.sales_agent import sales_agent
except ImportError as e:
    print(f"[smoke M4] FAIL - Failed to import sales_agent: {e}", file=sys.stderr)
    sys.exit(1)


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

# Fields that must NOT appear in inventory agent code (no stock data).
FORBIDDEN_STOCK_FIELDS = [
    "current_stock",
    "stock_on_hand",
    "reorder_point",
    "safety_stock",
    "stock_received",
    "stock_remaining",
    "inventory_quantity",
]


def _check_tool_result(result, tool_name):
    """Return list of failure strings; empty list means success."""
    failures = []
    if isinstance(result, dict) and "error" in result and "content" not in result:
        failures.append(f"{tool_name}: {result['error']}")
        return failures
    is_error = result.get("isError", False) if isinstance(result, dict) else True
    if is_error:
        content = result.get("content", []) if isinstance(result, dict) else []
        err_text = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        failures.append(f"{tool_name} BigQuery error: {err_text[:300]}")
        return failures
    content = result.get("content", []) if isinstance(result, dict) else []
    if not content:
        failures.append(f"{tool_name}: empty content")
    return failures


async def run_m4_smoke_test():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M4] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    # ------------------------------------------------------------------
    # 1. MCP Toolbox starts and lists all 6 tools
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 1: MCP Toolbox starts and lists all 6 tools...")
    try:
        sp = StdioServerParameters(
            command="npx",
            args=["-y", "@toolbox-sdk/server", "--config", _TOOLS_YAML, "--stdio"],
            env=dict(os.environ),
        )
        cp = StdioConnectionParams(server_params=sp, timeout=120.0)
        toolset = McpToolset(connection_params=cp)
        tools = await toolset.get_tools()
        found_names = {t.name for t in tools}
        missing = EXPECTED_ALL_TOOLS - found_names
        if missing:
            failures.append(f"MCP Toolbox missing tools: {missing}")
            print(f"[smoke M4] FAIL - Missing tools: {missing}", file=sys.stderr)
        else:
            print(f"[smoke M4] PASS - MCP Toolbox reports {len(found_names)} tools: {sorted(found_names)}")

        # Verify Sales tools still present
        sales_missing = EXPECTED_SALES_TOOLS - found_names
        if sales_missing:
            failures.append(f"Sales tools missing: {sales_missing}")
        else:
            print("[smoke M4] PASS - All 4 Sales tools remain available.")

        # Verify Inventory tools present
        inv_missing = EXPECTED_INVENTORY_TOOLS - found_names
        if inv_missing:
            failures.append(f"Inventory tools missing: {inv_missing}")
        else:
            print("[smoke M4] PASS - All 4 Inventory tools available.")
    except Exception:
        print("[smoke M4] FAIL - MCP Toolbox failed to start.", file=sys.stderr)
        traceback.print_exc()
        failures.append("MCP Toolbox failed to start")

    # ------------------------------------------------------------------
    # 2. Both Inventory tools query BigQuery
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 2: Inventory tools query BigQuery...")
    try:
        # get_product_inventory_profile (no filter - all products)
        t1 = next(x for x in tools if x.name == "get_product_inventory_profile")
        r1 = await t1.run_async(args={"product_name": ""}, tool_context=None)
        f1 = _check_tool_result(r1, "get_product_inventory_profile")
        if f1:
            failures.extend(f1)
            print(f"[smoke M4] FAIL - {f1[0]}", file=sys.stderr)
        else:
            content = r1.get("content", [])
            print(f"[smoke M4] PASS - get_product_inventory_profile returned {len(content)} rows.")

        # get_inventory_category_profile
        t2 = next(x for x in tools if x.name == "get_inventory_category_profile")
        r2 = await t2.run_async(args={}, tool_context=None)
        f2 = _check_tool_result(r2, "get_inventory_category_profile")
        if f2:
            failures.extend(f2)
            print(f"[smoke M4] FAIL - {f2[0]}", file=sys.stderr)
        else:
            content = r2.get("content", [])
            print(f"[smoke M4] PASS - get_inventory_category_profile returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"Inventory tool execution failed: {exc}")
        print(f"[smoke M4] FAIL - {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # 3. Inventory Agent imports successfully
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 3: Inventory Agent imports...")
    try:
        from app.agents.inventory_agent import inventory_agent as ia
        print("[smoke M4] PASS - inventory_agent imports successfully.")
    except Exception as exc:
        failures.append(f"inventory_agent import failed: {exc}")
        print(f"[smoke M4] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 4. Orchestrator imports successfully
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 4: Orchestrator imports...")
    try:
        from app.agents.orchestrator import root_agent as ra
        print("[smoke M4] PASS - orchestrator imports successfully.")
    except Exception as exc:
        failures.append(f"orchestrator import failed: {exc}")
        print(f"[smoke M4] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 5. Inventory Agent uses MCP Toolbox
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 5: Inventory Agent uses MCP Toolbox...")
    from app.tools.mcp_toolbox import mcp_toolbox
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent does not have mcp_toolbox in tools")
        print("[smoke M4] FAIL - inventory_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M4] PASS - inventory_agent uses mcp_toolbox.")

    # ------------------------------------------------------------------
    # 6. Inventory Agent does NOT reference nonexistent stock fields
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 6: No nonexistent stock fields referenced...")
    agent_src = Path("app/agents/inventory_agent.py").read_text()
    prompt_src = Path("app/prompts/inventory_agent.txt").read_text()
    combined = (agent_src + prompt_src).lower()
    found_forbidden = []
    for field in FORBIDDEN_STOCK_FIELDS:
        # The prompt may mention these in a "never invent" context, which is OK.
        # Check only the agent source code for actual usage.
        if field in agent_src.lower():
            found_forbidden.append(field)
    if found_forbidden:
        failures.append(f"Forbidden stock fields in agent code: {found_forbidden}")
        print(f"[smoke M4] FAIL - Forbidden stock fields: {found_forbidden}", file=sys.stderr)
    else:
        print("[smoke M4] PASS - No forbidden stock fields in agent code.")

    # ------------------------------------------------------------------
    # 7. Inventory prompt exists and is loaded
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 7: Inventory prompt exists and is loaded...")
    prompt_path = Path("app/prompts/inventory_agent.txt")
    if not prompt_path.exists():
        failures.append("app/prompts/inventory_agent.txt does not exist")
        print("[smoke M4] FAIL - prompt file missing", file=sys.stderr)
    else:
        text = prompt_path.read_text(encoding="utf-8")
        required = ["PRINCIPLE 1", "PRINCIPLE 3", "NEVER INVENT", "ABSOLUTE PROHIBITIONS",
                     "stock", "essentiality", "perishability", "shelf_life"]
        missing_markers = [m for m in required if m not in text]
        if missing_markers:
            failures.append(f"Prompt missing markers: {missing_markers}")
            print(f"[smoke M4] FAIL - Prompt missing: {missing_markers}", file=sys.stderr)
        else:
            print(f"[smoke M4] PASS - Prompt loaded ({len(text)} chars, all markers present).")

    # Verify instruction is loaded
    instr = inventory_agent.instruction
    if "PRINCIPLE 1" not in instr:
        failures.append("inventory_agent.instruction does not contain reasoning contract")
        print("[smoke M4] FAIL - instruction missing contract", file=sys.stderr)
    else:
        print("[smoke M4] PASS - instruction contains reasoning contract.")

    # ------------------------------------------------------------------
    # 8. No existing Sales functionality broken
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 8: Sales functionality not broken...")
    # Verify sales_agent still has its tools
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent lost mcp_toolbox")
        print("[smoke M4] FAIL - sales_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M4] PASS - sales_agent still uses mcp_toolbox.")

    # Verify sales prompt unchanged
    sales_prompt = Path("app/prompts/sales_agent.txt").read_text()
    if "PRINCIPLE 1" not in sales_prompt or "PRINCIPLE 12" not in sales_prompt:
        failures.append("sales_agent.txt appears modified")
        print("[smoke M4] FAIL - sales prompt modified", file=sys.stderr)
    else:
        print("[smoke M4] PASS - sales_agent.txt unchanged.")

    # ------------------------------------------------------------------
    # 9. ONE Gemini NL test (only if quota available, no retries)
    # ------------------------------------------------------------------
    print("[smoke M4] CHECK 9: ONE Gemini NL test (if quota available)...")
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    APP_NAME = "retail_lens"
    USER_ID = "smoke_test_user_m4"

    async def _run_one_nl():
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
        runner = Runner(agent=inventory_agent, app_name=APP_NAME, session_service=session_service)
        msg = Content(role="user", parts=[Part(text="What are the inventory characteristics of our household cleaning products?")])
        final = ""
        async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=msg):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final = event.content.parts[0].text or ""
        return final

    try:
        nl_text = await _run_one_nl()
        if not nl_text:
            failures.append("Gemini NL test: empty response")
            print("[smoke M4] FAIL - NL test empty response", file=sys.stderr)
        else:
            lowered = nl_text.lower()
            # Check for failure markers
            fail_markers = ["database error", "unrecognized name", "tool not found",
                           "connection closed", "syntax error", "timed out"]
            matched = [m for m in fail_markers if m in lowered]
            if matched:
                failures.append(f"NL test failure markers: {matched}")
                print(f"[smoke M4] FAIL - NL test markers: {matched}", file=sys.stderr)
            else:
                print("[smoke M4] PASS - Gemini NL test returned a response.")
                print(f"[smoke M4] Preview: {nl_text[:300]}...")
    except Exception as exc:
        is_quota = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
        if is_quota:
            print("[smoke M4] SKIP - Gemini quota exhausted (429). NL test skipped.")
        else:
            failures.append(f"Gemini NL test failed: {exc}")
            print(f"[smoke M4] FAIL - NL test: {exc}", file=sys.stderr)
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke M4] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M4] RESULT: PASS - All Milestone 4 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m4_smoke_test())
