"""Milestone 11: Customer Agent - Deterministic tests."""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv; load_dotenv()
try:
    from app.agents.customer_agent import customer_agent
except ImportError as e:
    print(f"[smoke M11] FAIL - import: {e}", file=sys.stderr); sys.exit(1)
from app.agents.sales_agent import sales_agent
from app.agents.inventory_agent import inventory_agent
from app.agents.workforce_agent import workforce_agent
from app.agents.orchestrator import root_agent
from app.tools.mcp_toolbox import mcp_toolbox
_TOOLS_YAML = str(Path(__file__).parent.parent / "tools.yaml")
EXPECTED_ALL = {"get_daily_sales_summary","get_daily_product_movement","get_sales_trends","get_product_behavior_profile","get_product_inventory_profile","get_inventory_category_profile","get_product_profitability","get_current_stock_levels","get_current_supply_status","get_workforce_summary","get_customer_behavior_profile","get_replenishment_risk"}
async def main():
    if not os.getenv("GEMINI_API_KEY"): print("[smoke M11] SKIP"); sys.exit(0)
    failures=[]
    print("[smoke M11] CHECK 1-3: customer_agent imports, uses toolbox, no BQ...")
    if mcp_toolbox not in customer_agent.tools: failures.append("customer_agent missing toolbox")
    else: print("[smoke M11] PASS - uses toolbox")
    s=Path("app/agents/customer_agent.py").read_text()
    if "google.cloud.bigquery" in s: failures.append("customer_agent has BQ")
    else: print("[smoke M11] PASS - no BQ")
    print("[smoke M11] CHECK 4-5: prompt loaded, anti-hallucination...")
    p=Path("app/prompts/customer_agent.txt")
    if not p.exists(): failures.append("prompt missing")
    else:
        t=p.read_text(encoding="utf-8")
        instr=customer_agent.instruction
        if "PRINCIPLE 1" not in instr: failures.append("instruction missing contract")
        else: print("[smoke M11] PASS - prompt loaded")
        for m in ["NEVER INVENT","Never fabricate","ABSOLUTE PROHIBITIONS"]:
            if m not in t: failures.append(f"Missing: {m}")
        if not any("Missing" in f for f in failures): print("[smoke M11] PASS - anti-hallucination OK")
    print("[smoke M11] CHECK 6-7: tools.yaml has 11 tools...")
    import yaml
    with open(_TOOLS_YAML) as f: cfg=yaml.safe_load(f)
    tn=set(cfg.get("tools",{}).keys())
    if tn!=EXPECTED_ALL: failures.append(f"tool mismatch: {tn}")
    else: print(f"[smoke M11] PASS - {len(tn)} tools")
    print("[smoke M11] CHECK 8-10: other agents intact...")
    for a,n in [(sales_agent,"sales"),(inventory_agent,"inventory"),(workforce_agent,"workforce")]:
        if mcp_toolbox not in a.tools: failures.append(f"{n} missing toolbox")
    if not any("missing toolbox" in f for f in failures): print("[smoke M11] PASS - all agents intact")
    print("[smoke M11] CHECK 11-12: orchestrator + sub-agent...")
    sub=[a.name for a in root_agent.sub_agents]
    if "customer_agent" not in sub: failures.append("customer_agent not sub-agent")
    elif "sales_agent" not in sub or "inventory_agent" not in sub or "workforce_agent" not in sub: failures.append("routing broken")
    else: print(f"[smoke M11] PASS - 4 sub-agents: {sub}")
    print("[smoke M11] CHECK 13-14: tool count + no BQ in agents...")
    if len(tn)!=12: failures.append(f"Expected 11, got {len(tn)}")
    else: print("[smoke M11] PASS - exactly 12 tools")
    for n,p in [("sales_agent","app/agents/sales_agent.py"),("inventory_agent","app/agents/inventory_agent.py"),("workforce_agent","app/agents/workforce_agent.py"),("customer_agent","app/agents/customer_agent.py"),("orchestrator","app/agents/orchestrator.py")]:
        if "google.cloud.bigquery" in Path(p).read_text(): failures.append(f"{n} has BQ")
    if not any("has BQ" in f for f in failures): print("[smoke M11] PASS - no BQ in agents")
    print(f"\n{'='*60}")
    if failures:
        print(f"[smoke M11] RESULT: FAIL - {len(failures)}"); [print(f"  - {f}") for f in failures]; sys.exit(1)
    else: print("[smoke M11] RESULT: PASS"); sys.exit(0)
if __name__=="__main__": asyncio.run(main())