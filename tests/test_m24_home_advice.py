"""
Milestone 24 — Dashboard Daily Advice Tests

Deterministic checks (always run):
  1. Backend/frontend wiring: /api/home/advice endpoint, AdviceCard on Home,
     fetchHomeAdvice in api.ts, .advice-box CSS.
  2. Rule-engine unit tests on synthetic context (no BigQuery):
     - strong/soft revenue candidates carry the right numbers
     - inventory urgency picks the most urgent below-reorder product
     - no "None"/"nan" leaks into any candidate text
     - Indian ₹ grouping helper
     - ranking caps at 4 and is score-ordered
     - selection is stable within a block, distinct across the 4 blocks
     - honest empty state when there is no data

Live validation (runs when BigQuery credentials are available):
  3. GET /api/home/advice returns 200; business_date matches the query
     layer; two calls in the same block are identical; text is clean.

Usage:
    python tests/test_m24_home_advice.py
"""

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


def _ctx(**overrides):
    """Synthetic context for pure rule-engine tests (no BigQuery)."""
    ctx = {
        "latest_date": "2026-08-31",
        "today": {
            "sales_date": date(2026, 8, 31),
            "total_bills": 26,
            "transaction_lines": 123,
            "total_units_sold": 165,
            "total_revenue": 10000.0,
            "average_bill_value": 384.62,
        },
        "prev": {
            "sales_date": date(2026, 8, 30),
            "total_bills": 30,
            "transaction_lines": 130,
            "total_units_sold": 150,
            "total_revenue": 7000.0,
            "average_bill_value": 233.33,
        },
        "trend": [
            {"sales_date": date(2026, 8, d), "bills": 30, "units_sold": 150, "revenue": 7000.0}
            for d in range(25, 31)
        ]
        + [
            {"sales_date": date(2026, 8, 31), "bills": 26, "units_sold": 165, "revenue": 10000.0}
        ],
        "profitability": [
            {
                "product_id": "P1",
                "product_name": "Amul Butter 500g",
                "category": "Dairy",
                "units_sold": 12,
                "revenue": 3000.0,
                "cost_of_goods_sold": 2100.0,
                "gross_profit": 900.0,
                "gross_margin_pct": 30.0,
            }
        ],
        "risk": [
            {
                "product_id": "P2",
                "product_name": "Milk 1L",
                "category": "Dairy",
                "essentiality_tier": 1,
                "stock_on_hand": 5,
                "reorder_level": 40,
                "stock_coverage_days": 2,
            }
        ],
    }
    ctx.update(overrides)
    return ctx


def static_checks() -> list[str]:
    """Wiring checks 1. Returns failures."""
    from pathlib import Path

    root = Path(__file__).parent.parent
    failures: list[str] = []

    def check(desc, cond, msg):
        print(f"[M24] CHECK: {desc}...")
        if cond:
            print(f"[M24] PASS - {desc}")
        else:
            failures.append(msg)
            print(f"[M24] FAIL - {msg}", file=sys.stderr)

    api_py = (root / "app/api.py").read_text()
    check("endpoint registered", '"/api/home/advice"' in api_py, "/api/home/advice missing in api.py")

    from app.tools import insight_tools  # noqa: E402

    for fn in ["gather_context", "build_candidates", "rank_candidates",
               "select_candidate", "build_daily_advice", "get_advice_for_now"]:
        check(f"engine function {fn}", hasattr(insight_tools, fn), f"insight_tools.{fn} missing")

    home = (root / "frontend/src/Home.tsx").read_text()
    check("AdviceCard rendered on Home", "AdviceCard from" in home and "<AdviceCard" in home,
          "Home.tsx does not render AdviceCard")
    api_ts = (root / "frontend/src/services/api.ts").read_text()
    check("fetchHomeAdvice in api.ts", "fetchHomeAdvice" in api_ts and '"/home/advice"' in api_ts,
          "api.ts missing fetchHomeAdvice / /home/advice")
    check("AdviceCard component exists", (root / "frontend/src/AdviceCard.tsx").exists(),
          "frontend/src/AdviceCard.tsx missing")
    css = (root / "frontend/src/styles.css").read_text()
    check("advice-box CSS present", ".advice-box" in css, "styles.css missing .advice-box")

    return failures


def unit_checks() -> list[str]:
    """Pure rule-engine checks on synthetic context (no BigQuery)."""
    from app.tools import insight_tools as it

    failures: list[str] = []

    def check(desc, cond, msg):
        print(f"[M24] UNIT: {desc}...")
        if cond:
            print(f"[M24] PASS - {desc}")
        else:
            failures.append(msg)
            print(f"[M24] FAIL - {msg}", file=sys.stderr)

    # ₹ Indian grouping
    check("inr grouping 1082996", it._inr(1082996) == "₹10,82,996", f"_inr wrong: {it._inr(1082996)}")
    check("inr grouping 24182", it._inr(24182) == "₹24,182", f"_inr wrong: {it._inr(24182)}")

    # Strong revenue day: 10000 vs 7000 avg => +43%
    cands = it.build_candidates(_ctx())
    strong = next((c for c in cands if c["headline"] == "Strong sales day"), None)
    check("strong candidate present", strong is not None, "Strong sales day candidate missing on +43% day")
    if strong:
        check("strong detail has 43%", "43%" in strong["detail"], "strong detail missing 43%")
        check("strong detail has ₹10,000", "₹10,000" in strong["detail"], "strong detail missing ₹10,000")

    # Soft revenue day: 5000 vs 7000 avg => -29%
    base_today = _ctx()["today"]
    down = _ctx(today={**base_today, "total_revenue": 5000.0, "average_bill_value": 192.31})
    soft = next((c for c in it.build_candidates(down) if c["headline"] == "Softer sales day"), None)
    check("soft candidate present", soft is not None, "Softer sales day candidate missing on -29% day")
    if soft:
        check("soft detail has 29%", "29%" in soft["detail"], "soft detail missing 29%")
        check("soft tone is warning", soft["tone"] == "warning", "soft tone not warning")

    # Inventory urgency
    inv = next((c for c in cands if c["category"] == "inventory"), None)
    check("inventory candidate present", inv is not None, "inventory candidate missing")
    if inv:
        check("inventory count 1", "1 product below reorder level" in inv["headline"],
              f"inventory headline wrong: {inv['headline']}")
        check("inventory names urgent item", "Milk 1L" in inv["detail"] and "2 days" in inv["detail"],
              "inventory detail missing urgent product/coverage")

    # Text hygiene — no None/nan leaks in any candidate
    dirty = [c["headline"] + c["detail"] for c in cands
             if "None" in c["headline"] + c["detail"] or "nan" in c["headline"] + c["detail"]]
    check("no None/nan in candidate text", not dirty, f"leaked text: {dirty}")

    # Ranking: capped at 4, score-descending
    ranked = it.rank_candidates(cands)
    check("ranked capped at 4", len(ranked) <= 4, f"ranked len {len(ranked)} > 4")
    check("ranked score-ordered", all(
        ranked[i]["score"] >= ranked[i + 1]["score"] for i in range(len(ranked) - 1)
    ), "ranked not score-ordered")

    # Selection: stable within a block, distinct across the 4 blocks
    seed = date(2026, 8, 31).toordinal()
    picked = [it.select_candidate(ranked, b, seed)["headline"] for b in range(4)]
    check("4 distinct headlines across blocks", len(set(picked)) == 4, f"blocks repeat: {picked}")
    check("selection deterministic", it.select_candidate(ranked, 2, seed)["headline"] == picked[2],
          "same block+seed gave different results")

    # Full build with injected context
    resp = it.build_daily_advice(1, _ctx())
    check("build_daily_advice returns advice", resp.advice is not None, "advice missing in response")
    check("business_date anchored", str(resp.business_date) == "2026-08-31", "business_date wrong")
    check("next_update is HH:MM", re.fullmatch(r"\d{2}:\d{2}", resp.next_update) is not None,
          f"next_update bad: {resp.next_update}")

    # Honest empty state
    empty = it.build_daily_advice(0, {"latest_date": None})
    check("empty state honest", empty.advice is None and empty.message is not None,
          "no-data response should carry message and no advice")

    # 6-hour block boundaries (the rotation must happen every 6 hours)
    from datetime import datetime

    check("block at 05:59 is 0", it.get_advice_for_now(datetime(2026, 1, 1, 5, 59)).block_index == 0,
          "05:59 should be block 0")
    check("block at 06:00 is 1", it.get_advice_for_now(datetime(2026, 1, 1, 6, 0)).block_index == 1,
          "06:00 should be block 1")
    check("block at 20:00 is 3", it.get_advice_for_now(datetime(2026, 1, 1, 20, 0)).block_index == 3,
          "20:00 should be block 3 (block_index must stay 0-3)")
    check("next update after 13:00 is 18:00", it._next_block_time(datetime(2026, 1, 1, 13, 0)) == "18:00",
          "13:00 should promise next tip at 18:00")
    check("next update after 20:00 is 00:00", it._next_block_time(datetime(2026, 1, 1, 20, 0)) == "00:00",
          "20:00 should promise next tip at 00:00")

    return failures


def live_checks() -> list[str]:
    """Live BigQuery-backed checks via TestClient."""
    failures: list[str] = []
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        print("[M24] LIVE: SKIP - GOOGLE_CLOUD_PROJECT not set")
        return failures

    from fastapi.testclient import TestClient

    from app.api import app
    from app.tools import sales_tools

    client = TestClient(app, raise_server_exceptions=False)
    print("[M24] LIVE CHECK: GET /api/home/advice ...")
    r1 = client.get("/api/home/advice")
    if r1.status_code != 200:
        failures.append(f"GET /api/home/advice -> {r1.status_code}: {r1.text[:200]}")
        print(f"[M24] FAIL - advice endpoint {r1.status_code}", file=sys.stderr)
        return failures
    body = r1.json()
    print("[M24] PASS - advice endpoint 200")

    latest = sales_tools.query_latest_sales_date()
    if latest:
        if str(body.get("business_date")) != latest:
            failures.append(f"business_date {body.get('business_date')} != latest {latest}")
        else:
            print(f"[M24] PASS - business_date anchored to {latest}")

    r2 = client.get("/api/home/advice")
    if r2.json() != body:
        failures.append("two calls in the same block differ")
    else:
        print("[M24] PASS - stable within the 6-hour block")

    adv = body.get("advice")
    if adv:
        valid = adv["category"] in {"sales", "inventory", "products"} and adv["tone"] in {
            "positive", "neutral", "warning"
        }
        clean = "None" not in adv["headline"] + adv["detail"] and "nan" not in adv["headline"] + adv["detail"]
        if not (valid and clean):
            failures.append(f"advice card invalid: {adv}")
        else:
            print(f"[M24] PASS - advice card valid: {adv['headline']}")
        print(f"[M24] INFO - detail: {adv['detail']}")
    elif not body.get("message"):
        failures.append("response has neither advice nor message")

    r_sum = client.get("/api/home/summary")
    if r_sum.status_code != 200:
        failures.append(f"/api/home/summary regression -> {r_sum.status_code}")
    else:
        print("[M24] PASS - /api/home/summary still 200 (no regression)")

    return failures


def main():
    print("=== MILESTONE 24 DETERMINISTIC TESTS ===\n")
    failures = static_checks()

    print("\n=== MILESTONE 24 RULE-ENGINE UNIT TESTS ===\n")
    failures += unit_checks()

    print("\n=== MILESTONE 24 LIVE BIGQUERY VALIDATION ===\n")
    failures += live_checks()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M24] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M24] RESULT: PASS - Dashboard daily advice complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()


