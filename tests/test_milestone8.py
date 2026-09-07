"""
Smoke Test - Milestone 8: Workforce Analytical Evidence Tool

Deterministic tests verify:
  1. MCP Toolbox starts
  2. get_workforce_summary is available
  3. Existing 9 tools remain available
  4. Tool queries BigQuery successfully
  5. Returned data is non-empty for August 2026
  6. Employee count is correct (2 employees)
  7. Wage calculations are numeric and non-negative
  8. Actual hours are valid
  9. Attendance metrics are internally consistent
  10. No direct BigQuery access in agents
  11. Sales and Inventory agents still import
  12. Orchestrator still imports

Usage:
    python tests/test_milestone8.py
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
    from app.agents.orchestrator import root_agent
except ImportError as e:
    print(f"[smoke M8] FAIL - import: {e}", file=sys.stderr)
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


def _check_tool_result(result, tool_name):
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


async def run_m8_smoke_test():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M8] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    # ------------------------------------------------------------------
    # 1-3. MCP Toolbox starts, all 10 tools available
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 1-3: MCP Toolbox starts with all 10 tools...")
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
            failures.append(f"Missing tools: {missing}")
            print(f"[smoke M8] FAIL - Missing: {missing}", file=sys.stderr)
        else:
            print(f"[smoke M8] PASS - {len(found_names)} tools: {sorted(found_names)}")

        # Verify existing 9 tools
        existing_9 = EXPECTED_SALES_TOOLS | EXPECTED_INVENTORY_TOOLS
        existing_missing = existing_9 - found_names
        if existing_missing:
            failures.append(f"Existing tools missing: {existing_missing}")
            print(f"[smoke M8] FAIL - Existing tools missing", file=sys.stderr)
        else:
            print("[smoke M8] PASS - All 9 existing tools remain available.")

        # Verify workforce tool
        if "get_workforce_summary" not in found_names:
            failures.append("get_workforce_summary not found")
            print("[smoke M8] FAIL - get_workforce_summary missing", file=sys.stderr)
        else:
            print("[smoke M8] PASS - get_workforce_summary available.")
    except Exception:
        print("[smoke M8] FAIL - MCP Toolbox failed to start.", file=sys.stderr)
        traceback.print_exc()
        failures.append("MCP Toolbox failed to start")

    # ------------------------------------------------------------------
    # 4-5. Tool queries BigQuery, non-empty for August 2026
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 4-5: Tool queries BigQuery, non-empty...")
    try:
        t = next(x for x in tools if x.name == "get_workforce_summary")
        r = await t.run_async(args={"start_date": "2026-08-01", "end_date": "2026-08-31"}, tool_context=None)
        f = _check_tool_result(r, "get_workforce_summary")
        if f:
            failures.extend(f)
            print(f"[smoke M8] FAIL - {f[0]}", file=sys.stderr)
        else:
            content = r.get("content", [])
            if not content:
                failures.append("get_workforce_summary returned empty results")
                print("[smoke M8] FAIL - empty results", file=sys.stderr)
            else:
                print(f"[smoke M8] PASS - get_workforce_summary returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"Tool execution failed: {exc}")
        print(f"[smoke M8] FAIL - {exc}", file=sys.stderr)
        traceback.print_exc()

    # Parse the results for further checks
    import json
    employee_data = []
    if r and not _check_tool_result(r, ""):
        for item in r.get("content", []):
            if isinstance(item, dict) and "text" in item:
                try:
                    employee_data.append(json.loads(item["text"]))
                except (json.JSONDecodeError, KeyError):
                    pass

    # ------------------------------------------------------------------
    # 6. Employee count is correct (2 employees)
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 6: Employee count correct...")
    if len(employee_data) != 2:
        failures.append(f"Expected 2 employees, got {len(employee_data)}")
        print(f"[smoke M8] FAIL - Expected 2, got {len(employee_data)}", file=sys.stderr)
    else:
        print(f"[smoke M8] PASS - {len(employee_data)} employees returned.")

    # ------------------------------------------------------------------
    # 7. Wage calculations are numeric and non-negative
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 7: Wages numeric and non-negative...")
    for emp in employee_data:
        wages = emp.get("total_wages_inr")
        if wages is None or wages < 0:
            failures.append(f"{emp.get('employee_name')}: invalid wages={wages}")
            print(f"[smoke M8] FAIL - {emp.get('employee_name')}: wages={wages}", file=sys.stderr)
    if not any(f for f in failures if "wages" in str(f).lower()):
        print("[smoke M8] PASS - All wages numeric and non-negative.")

    # ------------------------------------------------------------------
    # 8. Actual hours are valid
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 8: Actual hours valid...")
    for emp in employee_data:
        actual = emp.get("actual_hours")
        if actual is not None and actual < 0:
            failures.append(f"{emp.get('employee_name')}: negative actual_hours={actual}")
            print(f"[smoke M8] FAIL - {emp.get('employee_name')}: actual={actual}", file=sys.stderr)
    if not any(f for f in failures if "actual" in str(f).lower()):
        print("[smoke M8] PASS - All actual hours valid.")

    # ------------------------------------------------------------------
    # 9. Attendance metrics internally consistent
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 9: Attendance metrics consistent...")
    for emp in employee_data:
        shifts = emp.get("shifts_worked", 0)
        checkins = emp.get("check_in_count", 0)
        late = emp.get("late_check_in_count", 0)
        early = emp.get("early_departure_count", 0)
        overtime = emp.get("overtime_shift_count", 0)
        # check_in_count <= shifts_worked
        if checkins > shifts:
            failures.append(f"{emp.get('employee_name')}: checkins={checkins} > shifts={shifts}")
        # late <= checkins
        if late > checkins:
            failures.append(f"{emp.get('employee_name')}: late={late} > checkins={checkins}")
        # early <= checkins (can't leave early if you didn't check in)
        if early > checkins:
            failures.append(f"{emp.get('employee_name')}: early={early} > checkins={checkins}")
        # overtime <= shifts
        if overtime > shifts:
            failures.append(f"{emp.get('employee_name')}: overtime={overtime} > shifts={shifts}")
    if not any(f for f in failures if "checkins" in str(f).lower() or "late" in str(f).lower() or "early" in str(f).lower() or "overtime" in str(f).lower()):
        print("[smoke M8] PASS - Attendance metrics internally consistent.")
    else:
        for f in failures:
            if "checkins" in f or "late" in f or "early" in f or "overtime" in f:
                print(f"[smoke M8] FAIL - {f}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 10. No direct BigQuery access in agents
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 10: No direct BigQuery in agents...")
    for name, path in [("sales_agent", "app/agents/sales_agent.py"),
                        ("inventory_agent", "app/agents/inventory_agent.py"),
                        ("orchestrator", "app/agents/orchestrator.py")]:
        src = Path(path).read_text()
        if "google.cloud.bigquery" in src or "bigquery_client" in src:
            failures.append(f"{name} has direct BigQuery access")
            print(f"[smoke M8] FAIL - {name} has direct BigQuery", file=sys.stderr)
        else:
            print(f"[smoke M8] PASS - {name} has no direct BigQuery.")

    # ------------------------------------------------------------------
    # 11-12. Agents and orchestrator import
    # ------------------------------------------------------------------
    print("[smoke M8] CHECK 11-12: Agents import...")
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent missing mcp_toolbox")
        print("[smoke M8] FAIL - sales_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M8] PASS - sales_agent imports and uses mcp_toolbox.")
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent missing mcp_toolbox")
        print("[smoke M8] FAIL - inventory_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M8] PASS - inventory_agent imports and uses mcp_toolbox.")
    print("[smoke M8] PASS - orchestrator imports successfully.")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke M8] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M8] RESULT: PASS - All Milestone 8 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m8_smoke_test())
