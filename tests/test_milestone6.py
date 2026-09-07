"""
Smoke Test - Milestone 6: Data Integrity & Operational Data Foundation

Deterministic tests verify:
  1. Existing Sales tools still work (4 tools)
  2. Existing Inventory tools still work (2 original + 2 new = 4)
  3. New profitability tool works against BigQuery
  4. New stock tool works (returns empty - no fabricated data)
  5. Workforce timestamp columns exist
  6. Workforce timestamps are NULL (no legitimate source)
  7. Customer bill join status (fixed or blocked)
  8. No fabricated stock data
  9. All agents import successfully
  10. No direct BigQuery access in agents

Usage:
    python tests/test_milestone6.py
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
    print(f"[smoke M6] FAIL - import: {e}", file=sys.stderr)
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

EXPECTED_ALL_TOOLS = EXPECTED_SALES_TOOLS | EXPECTED_INVENTORY_TOOLS


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


async def run_m6_smoke_test():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M6] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    # ------------------------------------------------------------------
    # 1. MCP Toolbox starts and lists all 8 tools
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 1: MCP Toolbox lists all 8 tools...")
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
            print(f"[smoke M6] FAIL - Missing: {missing}", file=sys.stderr)
        else:
            print(f"[smoke M6] PASS - {len(found_names)} tools: {sorted(found_names)}")

        # Verify Sales tools unchanged
        sales_missing = EXPECTED_SALES_TOOLS - found_names
        if sales_missing:
            failures.append(f"Sales tools missing: {sales_missing}")
        else:
            print("[smoke M6] PASS - All 4 Sales tools present.")

        # Verify Inventory tools (now 4)
        inv_missing = EXPECTED_INVENTORY_TOOLS - found_names
        if inv_missing:
            failures.append(f"Inventory tools missing: {inv_missing}")
        else:
            print("[smoke M6] PASS - All 4 Inventory tools present.")
    except Exception:
        print("[smoke M6] FAIL - MCP Toolbox failed to start.", file=sys.stderr)
        traceback.print_exc()
        failures.append("MCP Toolbox failed to start")

    # ------------------------------------------------------------------
    # 2. Profitability tool queries BigQuery
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 2: get_product_profitability queries BigQuery...")
    try:
        t = next(x for x in tools if x.name == "get_product_profitability")
        r = await t.run_async(args={"start_date": "2026-08-01", "end_date": "2026-08-28"}, tool_context=None)
        f = _check_tool_result(r, "get_product_profitability")
        if f:
            failures.extend(f)
            print(f"[smoke M6] FAIL - {f[0]}", file=sys.stderr)
        else:
            content = r.get("content", [])
            print(f"[smoke M6] PASS - get_product_profitability returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"profitability tool failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 3. Stock tool queries BigQuery (should return empty - no fabricated data)
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 3: get_current_stock_levels queries BigQuery...")
    try:
        t2 = next(x for x in tools if x.name == "get_current_stock_levels")
        r2 = await t2.run_async(args={}, tool_context=None)
        f2 = _check_tool_result(r2, "get_current_stock_levels")
        if f2:
            failures.extend(f2)
            print(f"[smoke M6] FAIL - {f2[0]}", file=sys.stderr)
        else:
            content = r2.get("content", [])
            print(f"[smoke M6] PASS - get_current_stock_levels returned {len(content)} rows (empty = no fabricated data).")
    except Exception as exc:
        failures.append(f"stock tool failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 4. Workforce timestamp columns exist
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 4: Workforce timestamp columns exist...")
    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
        q = bq.query("""
            SELECT column_name FROM `retail_lens_patchamomma.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name = 'workforce_shifts' ORDER BY ordinal_position
        """)
        cols = [r.column_name for r in q]
        if "check_in_timestamp" not in cols or "check_out_timestamp" not in cols:
            failures.append(f"Missing workforce timestamp columns. Found: {cols}")
            print(f"[smoke M6] FAIL - Missing columns. Found: {cols}", file=sys.stderr)
        else:
            print(f"[smoke M6] PASS - check_in_timestamp and check_out_timestamp exist.")
    except Exception as exc:
        failures.append(f"Workforce column check failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 5. Workforce timestamps are NULL (no legitimate source)
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 5: Workforce timestamps are NULL...")
    try:
        q2 = bq.query("""
            SELECT COUNTIF(check_in_timestamp IS NOT NULL) AS has_checkin,
                   COUNTIF(check_out_timestamp IS NOT NULL) AS has_checkout,
                   COUNT(*) AS total
            FROM `retail_lens_patchamomma.workforce_shifts`
        """)
        for r in q2:
            if r.has_checkin > 0 or r.has_checkout > 0:
                failures.append(f"Timestamps populated without legitimate source: checkin={r.has_checkin}, checkout={r.has_checkout}")
                print(f"[smoke M6] FAIL - Timestamps populated: checkin={r.has_checkin}", file=sys.stderr)
            else:
                print(f"[smoke M6] PASS - All timestamps NULL (total={r.total}). No fabricated data.")
    except Exception as exc:
        failures.append(f"Workforce timestamp check failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 6. Customer bill join status
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 6: Customer bill join status...")
    try:
        q3 = bq.query("""
            SELECT COUNT(DISTINCT c.bill_number) AS total_customer_bills,
                   COUNT(DISTINCT CASE WHEN s.bill_number IS NOT NULL THEN c.bill_number END) AS matched_bills
            FROM `retail_lens_patchamomma.customer_bills` c
            LEFT JOIN `retail_lens_patchamomma.sales_transactions` s ON s.bill_number = c.bill_number
        """)
        for r in q3:
            if r.matched_bills > 0:
                print(f"[smoke M6] PASS - Customer bill join works: {r.matched_bills}/{r.total_customer_bills} matched.")
            else:
                failures.append("Customer bill join still broken: 0 matched")
                print(f"[smoke M6] FAIL - 0 matched bills", file=sys.stderr)
    except Exception as exc:
        failures.append(f"Customer join check failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 7. No fabricated stock data
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 7: No fabricated stock data...")
    try:
        q4 = bq.query("SELECT COUNT(*) AS cnt FROM `retail_lens_patchamomma.inventory_stock`")
        for r in q4:
            if r.cnt > 0:
                failures.append(f"inventory_stock has {r.cnt} rows - should be empty (no legitimate source)")
                print(f"[smoke M6] FAIL - {r.cnt} rows in inventory_stock", file=sys.stderr)
            else:
                print(f"[smoke M6] PASS - inventory_stock is empty (no fabricated data).")
    except Exception as exc:
        failures.append(f"Stock table check failed: {exc}")
        print(f"[smoke M6] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 8. All agents import and use MCP Toolbox
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 8: Agents import and use MCP Toolbox...")
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent missing mcp_toolbox")
        print("[smoke M6] FAIL - sales_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M6] PASS - sales_agent uses mcp_toolbox.")
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent missing mcp_toolbox")
        print("[smoke M6] FAIL - inventory_agent missing mcp_toolbox", file=sys.stderr)
    else:
        print("[smoke M6] PASS - inventory_agent uses mcp_toolbox.")

    # ------------------------------------------------------------------
    # 9. No direct BigQuery access in agents
    # ------------------------------------------------------------------
    print("[smoke M6] CHECK 9: No direct BigQuery in agents...")
    for name, path in [("sales_agent", "app/agents/sales_agent.py"),
                        ("inventory_agent", "app/agents/inventory_agent.py"),
                        ("orchestrator", "app/agents/orchestrator.py")]:
        src = Path(path).read_text()
        if "google.cloud.bigquery" in src or "bigquery_client" in src:
            failures.append(f"{name} has direct BigQuery access")
            print(f"[smoke M6] FAIL - {name} has direct BigQuery", file=sys.stderr)
        else:
            print(f"[smoke M6] PASS - {name} has no direct BigQuery.")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke M6] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M6] RESULT: PASS - All Milestone 6 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m6_smoke_test())
