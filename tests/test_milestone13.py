"""Milestone 13: Inventory Agent Replenishment Support - Deterministic tests."""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv; load_dotenv()
try:
    from app.agents.inventory_agent import inventory_agent
except ImportError as e:
    print(f"[smoke M13] FAIL - import: {e}", file=sys.stderr); sys.exit(1)
from app.agents.sales_agent import sales_agent
from app.agents.workforce_agent import workforce_agent
from app.agents.customer_agent import customer_agent
from app.agents.orchestrator import root_agent
from app.tools.mcp_toolbox import mcp_toolbox
_TOOLS_YAML = str(Path(__file__).parent.parent / "tools.yaml")
EXPECTED_ALL = {"get_daily_sales_summary","get_daily_product_movement","get_sales_trends","get_product_behavior_profile","get_product_inventory_profile","get_inventory_category_profile","get_product_profitability","get_current_stock_levels","get_current_supply_status","get_workforce_summary","get_customer_behavior_profile","get_replenishment_risk"}
async def main():
    if not os.getenv("GEMINI_API_KEY"): print("[smoke M13] SKIP"); sys.exit(0)
    failures=[]
    print("[smoke M13] CHECK 1-2: Inventory agent imports, prompt loads...")
    if mcp_toolbox not in inventory_agent.tools: failures.append("inventory missing toolbox")
    else: print("[smoke M13] PASS - uses toolbox")
    instr=inventory_agent.instruction
    if "PRINCIPLE 1" not in instr: failures.append("instruction missing contract")
    else: print("[smoke M13] PASS - prompt loads")
    print("[smoke M13] CHECK 3: Replenishment reasoning markers...")
    for m in ["REPLENISHMENT REASONING","get_replenishment_risk","reorder quantity","replenishment priority","six MCP tools"]:
        if m not in instr: failures.append(f"Missing marker: {m}")
    if not any("Missing marker" in f for f in failures): print("[smoke M13] PASS - replenishment markers present")
    print("[smoke M13] CHECK 4-5: Tool available, agent uses toolbox...")
    import yaml
    with open(_TOOLS_YAML) as f: cfg=yaml.safe_load(f)
    tn=set(cfg.get("tools",{}).keys())
    if "get_replenishment_risk" not in tn: failures.append("replenishment tool not in tools.yaml")
    else: print("[smoke M13] PASS - tool in tools.yaml")
    print("[smoke M13] CHECK 6: No direct BQ...")
    s=Path("app/agents/inventory_agent.py").read_text()
    if "google.cloud.bigquery" in s: failures.append("inventory has BQ")
    else: print("[smoke M13] PASS - no BQ")
    print("[smoke M13] CHECK 7-8: Other agents intact...")
    for a,n in [(sales_agent,"sales"),(workforce_agent,"workforce"),(customer_agent,"customer")]:
        if mcp_toolbox not in a.tools: failures.append(f"{n} missing toolbox")
    sub=[a.name for a in root_agent.sub_agents]
    if len(sub)!=4: failures.append(f"Expected 4 sub-agents, got {len(sub)}: {sub}")
    if not any("missing toolbox" in f for f in failures): print(f"[smoke M13] PASS - all agents intact, {len(sub)} sub-agents")
    print("[smoke M13] CHECK 9-10: Customer agent intact, 12 tools...")
    if "customer_agent" not in sub: failures.append("customer_agent not in sub_agents")
    if len(tn)!=12: failures.append(f"Expected 12 tools, got {len(tn)}")
    else: print("[smoke M13] PASS - exactly 12 tools")
    print(f"\n{'='*60}")
    if failures:
        print(f"[smoke M13] RESULT: FAIL - {len(failures)}"); [print(f"  - {f}") for f in failures]; sys.exit(1)
    else: print("[smoke M13] RESULT: PASS"); sys.exit(0)
if __name__=="__main__": asyncio.run(main())