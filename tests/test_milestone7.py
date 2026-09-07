"""
Smoke Test - Milestone 7: Synthetic Operational Data Population

Deterministic tests verify:
  1. Workforce timestamps exist and are populated
  2. Workforce timestamps are valid (checkout > checkin, date = shift_date)
  3. inventory_stock has exactly one row per product
  4. inventory_stock has no orphan products
  5. inventory_stock has no duplicates
  6. Low-stock scenarios exist
  7. inventory_supply has exactly one row per product
  8. inventory_supply has no orphan products
  9. Supplier information exists
  10. Lead times are valid
  11. Incoming quantities are valid
  12. Delivery dates are consistent
  13. get_current_stock_levels works
  14. get_current_supply_status works
  15. get_product_profitability still works
  16. All existing Sales tools remain available
  17. All existing Inventory tools remain available
  18. Agents import successfully
  19. Orchestrator imports successfully
  20. No direct BigQuery access in agents

Usage:
    python tests/test_milestone7.py
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
    print(f"[smoke M7] FAIL - import: {e}", file=sys.stderr)
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


async def run_m7_smoke_test():
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M7] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    from google.cloud import bigquery
    bq = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    ds = "retail_lens_patchamomma"

    # ------------------------------------------------------------------
    # 1. Workforce timestamps exist and are populated
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 1: Workforce timestamps populated...")
    q = bq.query(f"""
        SELECT COUNTIF(check_in_timestamp IS NOT NULL) AS checkin_count,
               COUNTIF(check_out_timestamp IS NOT NULL) AS checkout_count,
               COUNT(*) AS total
        FROM `{ds}.workforce_shifts`
    """)
    for r in q:
        if r.checkin_count != r.total or r.checkout_count != r.total:
            failures.append(f"Workforce timestamps not fully populated: checkin={r.checkin_count}/{r.total}, checkout={r.checkout_count}/{r.total}")
            print(f"[smoke M7] FAIL - checkin={r.checkin_count}/{r.total}", file=sys.stderr)
        else:
            print(f"[smoke M7] PASS - All {r.total} shifts have timestamps.")

    # ------------------------------------------------------------------
    # 2. Workforce timestamps are valid
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 2: Workforce timestamps valid...")
    q2 = bq.query(f"""
        SELECT COUNTIF(check_out_timestamp > check_in_timestamp) AS valid_order,
               COUNTIF(DATE(check_in_timestamp) = shift_date) AS checkin_date_match,
               COUNTIF(DATE(check_out_timestamp) = shift_date) AS checkout_date_match,
               COUNT(*) AS total
        FROM `{ds}.workforce_shifts`
    """)
    for r in q2:
        if r.valid_order != r.total:
            failures.append(f"Invalid timestamp order: {r.valid_order}/{r.total}")
        if r.checkin_date_match != r.total:
            failures.append(f"Checkin date mismatch: {r.checkin_date_match}/{r.total}")
        if r.checkout_date_match != r.total:
            failures.append(f"Checkout date mismatch: {r.checkout_date_match}/{r.total}")
        if r.valid_order == r.total and r.checkin_date_match == r.total and r.checkout_date_match == r.total:
            print(f"[smoke M7] PASS - All timestamps valid (order, dates match).")
        else:
            print(f"[smoke M7] FAIL - Timestamp validation failed", file=sys.stderr)

    # ------------------------------------------------------------------
    # 3-5. inventory_stock: one row per product, no orphans, no duplicates
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 3-5: inventory_stock integrity...")
    q3 = bq.query(f"""
        SELECT
          (SELECT COUNT(*) FROM `{ds}.inventory_metadata`) AS metadata_count,
          (SELECT COUNT(*) FROM `{ds}.inventory_stock`) AS stock_count,
          (SELECT COUNT(DISTINCT product_id) FROM `{ds}.inventory_stock`) AS distinct_products,
          (SELECT COUNT(*) FROM `{ds}.inventory_stock` s
           WHERE NOT EXISTS (SELECT 1 FROM `{ds}.inventory_metadata` i WHERE i.prod_id = s.product_id)) AS orphans,
          (SELECT COUNTIF(stock_on_hand IS NULL) FROM `{ds}.inventory_stock`) AS null_stock,
          (SELECT COUNTIF(reorder_level IS NULL) FROM `{ds}.inventory_stock`) AS null_reorder
    """)
    for r in q3:
        if r.stock_count != r.metadata_count:
            failures.append(f"Stock count mismatch: {r.stock_count} vs {r.metadata_count} products")
        if r.distinct_products != r.stock_count:
            failures.append(f"Duplicate product_ids in stock: {r.distinct_products} distinct vs {r.stock_count} total")
        if r.orphans > 0:
            failures.append(f"Orphan products in stock: {r.orphans}")
        if r.null_stock > 0:
            failures.append(f"NULL stock values: {r.null_stock}")
        if r.null_reorder > 0:
            failures.append(f"NULL reorder values: {r.null_reorder}")
        if r.stock_count == r.metadata_count and r.distinct_products == r.stock_count and r.orphans == 0:
            print(f"[smoke M7] PASS - {r.stock_count} stock rows, no orphans, no duplicates.")

    # ------------------------------------------------------------------
    # 6. Low-stock scenarios exist
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 6: Low-stock scenarios exist...")
    q4 = bq.query(f"""
        SELECT COUNTIF(stock_on_hand < reorder_level) AS below_reorder,
               COUNTIF(stock_on_hand < reorder_level * 0.3) AS critical
        FROM `{ds}.inventory_stock`
    """)
    for r in q4:
        if r.below_reorder == 0:
            failures.append("No products below reorder level")
        if r.critical == 0:
            failures.append("No critically low stock products")
        if r.below_reorder > 0 and r.critical > 0:
            print(f"[smoke M7] PASS - {r.below_reorder} below reorder, {r.critical} critical.")

    # ------------------------------------------------------------------
    # 7-8. inventory_supply: one row per product, no orphans
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 7-8: inventory_supply integrity...")
    q5 = bq.query(f"""
        SELECT
          (SELECT COUNT(*) FROM `{ds}.inventory_supply`) AS supply_count,
          (SELECT COUNT(DISTINCT product_id) FROM `{ds}.inventory_supply`) AS distinct_products,
          (SELECT COUNT(*) FROM `{ds}.inventory_supply` s
           WHERE NOT EXISTS (SELECT 1 FROM `{ds}.inventory_metadata` i WHERE i.prod_id = s.product_id)) AS orphans
    """)
    for r in q5:
        if r.supply_count != r.distinct_products:
            failures.append(f"Duplicate product_ids in supply")
        if r.orphans > 0:
            failures.append(f"Orphan products in supply: {r.orphans}")
        if r.supply_count == r.distinct_products and r.orphans == 0:
            print(f"[smoke M7] PASS - {r.supply_count} supply rows, no orphans, no duplicates.")

    # ------------------------------------------------------------------
    # 9. Supplier information exists
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 9: Supplier information exists...")
    q6 = bq.query(f"SELECT COUNT(DISTINCT supplier_id) AS supplier_count FROM `{ds}.inventory_supply`")
    for r in q6:
        if r.supplier_count < 2:
            failures.append(f"Only {r.supplier_count} suppliers")
        else:
            print(f"[smoke M7] PASS - {r.supplier_count} suppliers.")

    # ------------------------------------------------------------------
    # 10. Lead times are valid
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 10: Lead times valid...")
    q7 = bq.query(f"SELECT MIN(supplier_lead_time_days) AS min_lt, MAX(supplier_lead_time_days) AS max_lt, COUNTIF(supplier_lead_time_days IS NULL) AS null_lt FROM `{ds}.inventory_supply`")
    for r in q7:
        if r.null_lt > 0:
            failures.append(f"NULL lead times: {r.null_lt}")
        if r.min_lt < 1 or r.max_lt > 30:
            failures.append(f"Lead time out of range: {r.min_lt}-{r.max_lt}")
        if r.null_lt == 0 and r.min_lt >= 1:
            print(f"[smoke M7] PASS - Lead times {r.min_lt}-{r.max_lt} days.")

    # ------------------------------------------------------------------
    # 11-12. Incoming quantities and delivery dates consistent
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 11-12: Incoming qty and delivery dates consistent...")
    q8 = bq.query(f"""
        SELECT COUNTIF(incoming_quantity > 0 AND expected_delivery_date IS NULL) AS bad_delivery,
               COUNTIF(incoming_quantity = 0 AND expected_delivery_date IS NOT NULL) AS bad_null,
               COUNTIF(incoming_quantity < 0) AS negative_qty,
               COUNTIF(incoming_quantity > 0) AS has_incoming
        FROM `{ds}.inventory_supply`
    """)
    for r in q8:
        if r.bad_delivery > 0:
            failures.append(f"Incoming qty > 0 but no delivery date: {r.bad_delivery}")
        if r.bad_null > 0:
            failures.append(f"No incoming qty but has delivery date: {r.bad_null}")
        if r.negative_qty > 0:
            failures.append(f"Negative incoming quantities: {r.negative_qty}")
        if r.bad_delivery == 0 and r.bad_null == 0 and r.negative_qty == 0:
            print(f"[smoke M7] PASS - {r.has_incoming} products with incoming, all consistent.")

    # ------------------------------------------------------------------
    # 13-15. MCP tools work
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 13-15: MCP tools work...")
    sp = StdioServerParameters(
        command="npx",
        args=["-y", "@toolbox-sdk/server", "--config", _TOOLS_YAML, "--stdio"],
        env=dict(os.environ),
    )
    cp = StdioConnectionParams(server_params=sp, timeout=120.0)
    toolset = McpToolset(connection_params=cp)
    tools = await toolset.get_tools()
    found_names = {t.name for t in tools}

    # Check all tools present
    missing = EXPECTED_ALL_TOOLS - found_names
    if missing:
        failures.append(f"Missing MCP tools: {missing}")
        print(f"[smoke M7] FAIL - Missing: {missing}", file=sys.stderr)
    else:
        print(f"[smoke M7] PASS - All {len(found_names)} MCP tools present.")

    # Test stock levels tool
    try:
        t_stock = next(x for x in tools if x.name == "get_current_stock_levels")
        r_stock = await t_stock.run_async(args={}, tool_context=None)
        f_stock = _check_tool_result(r_stock, "get_current_stock_levels")
        if f_stock:
            failures.extend(f_stock)
            print(f"[smoke M7] FAIL - {f_stock[0]}", file=sys.stderr)
        else:
            content = r_stock.get("content", [])
            print(f"[smoke M7] PASS - get_current_stock_levels returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"stock tool failed: {exc}")
        print(f"[smoke M7] FAIL - {exc}", file=sys.stderr)

    # Test supply status tool
    try:
        t_supply = next(x for x in tools if x.name == "get_current_supply_status")
        r_supply = await t_supply.run_async(args={}, tool_context=None)
        f_supply = _check_tool_result(r_supply, "get_current_supply_status")
        if f_supply:
            failures.extend(f_supply)
            print(f"[smoke M7] FAIL - {f_supply[0]}", file=sys.stderr)
        else:
            content = r_supply.get("content", [])
            print(f"[smoke M7] PASS - get_current_supply_status returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"supply tool failed: {exc}")
        print(f"[smoke M7] FAIL - {exc}", file=sys.stderr)

    # Test profitability tool
    try:
        t_profit = next(x for x in tools if x.name == "get_product_profitability")
        r_profit = await t_profit.run_async(args={"start_date": "2026-08-01", "end_date": "2026-08-28"}, tool_context=None)
        f_profit = _check_tool_result(r_profit, "get_product_profitability")
        if f_profit:
            failures.extend(f_profit)
            print(f"[smoke M7] FAIL - {f_profit[0]}", file=sys.stderr)
        else:
            content = r_profit.get("content", [])
            print(f"[smoke M7] PASS - get_product_profitability returned {len(content)} rows.")
    except Exception as exc:
        failures.append(f"profitability tool failed: {exc}")
        print(f"[smoke M7] FAIL - {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 16-20. Agents and architecture
    # ------------------------------------------------------------------
    print("[smoke M7] CHECK 16-20: Agents and architecture...")
    if mcp_toolbox not in sales_agent.tools:
        failures.append("sales_agent missing mcp_toolbox")
    else:
        print("[smoke M7] PASS - sales_agent uses mcp_toolbox.")
    if mcp_toolbox not in inventory_agent.tools:
        failures.append("inventory_agent missing mcp_toolbox")
    else:
        print("[smoke M7] PASS - inventory_agent uses mcp_toolbox.")

    for name, path in [("sales_agent", "app/agents/sales_agent.py"),
                        ("inventory_agent", "app/agents/inventory_agent.py"),
                        ("orchestrator", "app/agents/orchestrator.py")]:
        src = Path(path).read_text()
        if "google.cloud.bigquery" in src or "bigquery_client" in src:
            failures.append(f"{name} has direct BigQuery access")
            print(f"[smoke M7] FAIL - {name} has direct BigQuery", file=sys.stderr)
        else:
            print(f"[smoke M7] PASS - {name} has no direct BigQuery.")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke M7] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M7] RESULT: PASS - All Milestone 7 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m7_smoke_test())
