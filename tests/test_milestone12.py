"""Milestone 12: Replenishment Risk Evidence Tool - Deterministic tests."""
import asyncio, os, sys, json, traceback
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv; load_dotenv()
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
try:
    from app.agents.orchestrator import root_agent
except ImportError as e:
    print(f"[smoke M12] FAIL - import: {e}", file=sys.stderr); sys.exit(1)
from app.agents.sales_agent import sales_agent
from app.agents.inventory_agent import inventory_agent
from app.tools.mcp_toolbox import mcp_toolbox
_TOOLS_YAML = str(Path(__file__).parent.parent / "tools.yaml")
EXPECTED_ALL = {"get_daily_sales_summary","get_daily_product_movement","get_sales_trends","get_product_behavior_profile","get_product_inventory_profile","get_inventory_category_profile","get_product_profitability","get_current_stock_levels","get_current_supply_status","get_workforce_summary","get_customer_behavior_profile","get_replenishment_risk"}
def _check(r, n):
    f=[]
    if isinstance(r,dict) and "error" in r and "content" not in r: f.append(f"{n}: {r['error']}"); return f
    if r.get("isError",False) if isinstance(r,dict) else True:
        c=r.get("content",[]) if isinstance(r,dict) else []
        t=" ".join(p.get("text","") for p in c if isinstance(p,dict))
        f.append(f"{n} error: {t[:300]}"); return f
    if not (r.get("content",[]) if isinstance(r,dict) else []): f.append(f"{n}: empty")
    return f
async def main():
    if not os.getenv("GEMINI_API_KEY"): print("[smoke M12] SKIP"); sys.exit(0)
    failures=[]
    print("[smoke M12] CHECK 1-3: MCP Toolbox starts with 12 tools...")
    sp=StdioServerParameters(command="npx",args=["-y","@toolbox-sdk/server","--config",_TOOLS_YAML,"--stdio"],env=dict(os.environ))
    cp=StdioConnectionParams(server_params=sp,timeout=120.0)
    ts=McpToolset(connection_params=cp)
    tools=await ts.get_tools()
    found={t.name for t in tools}
    missing=EXPECTED_ALL-found
    if missing: failures.append(f"Missing: {missing}"); print(f"[smoke M12] FAIL - {missing}",file=sys.stderr)
    else: print(f"[smoke M12] PASS - {len(found)} tools")
    if "get_replenishment_risk" not in found: failures.append("replenishment tool missing")
    else: print("[smoke M12] PASS - replenishment tool exists")
    print("[smoke M12] CHECK 4-5: Tool queries BigQuery...")
    try:
        t=next(x for x in tools if x.name=="get_replenishment_risk")
        r=await t.run_async(args={"start_date":"2026-08-01","end_date":"2026-08-28"},tool_context=None)
        f=_check(r,"get_replenishment_risk")
        if f: failures.extend(f); print(f"[smoke M12] FAIL - {f[0]}",file=sys.stderr)
        else:
            content=r.get("content",[])
            print(f"[smoke M12] PASS - returned {len(content)} rows")
            data=[]
            for item in content:
                if isinstance(item,dict) and "text" in item:
                    try: data.append(json.loads(item["text"]))
                    except: pass
            print("[smoke M12] CHECK 6-10: Data validity...")
            for d in data:
                if d.get("stock_on_hand") is None: failures.append(f"NULL stock: {d.get('product_id')}")
                if d.get("reorder_level") is None: failures.append(f"NULL reorder: {d.get('product_id')}")
                if d.get("average_daily_demand") is not None and d.get("average_daily_demand")<0: failures.append(f"Neg demand: {d.get('product_id')}")
                if d.get("incoming_quantity") is not None and d.get("incoming_quantity")<0: failures.append(f"Neg incoming: {d.get('product_id')}")
                if not d.get("product_id"): failures.append("Missing product_id")
            if not failures: print(f"[smoke M12] PASS - {len(data)} products, all valid")
    except Exception as exc:
        failures.append(f"Tool failed: {exc}"); print(f"[smoke M12] FAIL - {exc}",file=sys.stderr)
    print("[smoke M12] CHECK 11-13: Agents...")
    for n,p in [("sales_agent","app/agents/sales_agent.py"),("inventory_agent","app/agents/inventory_agent.py"),("orchestrator","app/agents/orchestrator.py")]:
        s=Path(p).read_text()
        if "google.cloud.bigquery" in s: failures.append(f"{n} has BQ")
    if mcp_toolbox not in sales_agent.tools: failures.append("sales missing toolbox")
    if mcp_toolbox not in inventory_agent.tools: failures.append("inventory missing toolbox")
    if not any("BQ" in f or "missing toolbox" in f for f in failures): print("[smoke M12] PASS - agents OK")
    print(f"\n{'='*60}")
    if failures:
        print(f"[smoke M12] RESULT: FAIL - {len(failures)}"); [print(f"  - {f}") for f in failures]; sys.exit(1)
    else: print("[smoke M12] RESULT: PASS"); sys.exit(0)
if __name__=="__main__": asyncio.run(main())