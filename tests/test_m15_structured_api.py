"""
Milestone 15 — Structured REST API Tests

Deterministic checks (always run):
  1. app.api imports and /api/chat is untouched (POST).
  2. All 8 structured GET endpoints are registered.
  3. Query-layer functions exist for every endpoint.
  4. Tools SQL mirrors tools.yaml business definitions (key markers present).

Live validation (runs when BigQuery credentials are available):
  5. Every endpoint returns HTTP 200 against real BigQuery data.
  6. Endpoint envelopes match direct query-layer results (same SQL path).

Usage:
    python tests/test_m15_structured_api.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


STRUCTURED_ENDPOINTS = [
    "/api/home/summary",
    "/api/home/sales-trend",
    "/api/inventory/replenishment-risk",
    "/api/inventory/stock",
    "/api/inventory/supply",
    "/api/employees/summary",
    "/api/customers/behavior",
    "/api/profitability/products",
]

SQL_MARKERS = {
    "app/tools/sales_tools.py": [
        "retail_lens_patchamomma.sales_transactions",
        "COUNT(DISTINCT bill_number) AS total_bills",
        "SUM(total_price) / COUNT(DISTINCT bill_number) AS average_bill_value",
        "SUM(quantity) AS units_sold",
        "SUM(total_price) AS revenue",
    ],
    "app/tools/inventory_tools.py": [
        "retail_lens_patchamomma.inventory_stock",
        "retail_lens_patchamomma.inventory_supply",
        "retail_lens_patchamomma.inventory_metadata",
        "stock_coverage_days",
        "days_until_expected_delivery",
        "SUM(s.quantity * i.cost), 2) AS cost_of_goods_sold",
        "SUM(s.total_price) - SUM(s.quantity * i.cost), 2) AS gross_profit",
        "gross_margin_pct",
    ],
    "app/tools/workforce_tools.py": [
        "retail_lens_patchamomma.workforce_shifts",
        "SUM(hours_worked * hourly_wage_inr), 2) AS total_wages_inr",
        "late_check_in_count",
        "early_departure_count",
        "overtime_shift_count",
    ],
    "app/tools/customer_tools.py": [
        "retail_lens_patchamomma.customer_bills",
        "ON s.bill_number = c.bill_number",
        "purchase_frequency_pct",
        "ORDER BY total_spend DESC",
    ],
}


def static_checks() -> list[str]:
    """Checks 1-4: wiring and business-logic fidelity. Returns failures."""
    failures: list[str] = []

    print("[M15] CHECK 1: app.api imports, /api/chat untouched...")
    try:
        from app.api import app  # noqa: E402
    except Exception as exc:  # noqa: BLE001
        failures.append(f"app.api import failed: {exc}")
        print("[M15] FAIL - app.api import failed", file=sys.stderr)
        return failures
    print("[M15] PASS - app.api imports")

    routes = {(r.path, tuple(sorted(getattr(r, "methods", []) or []))) for r in app.routes}
    if ("/api/chat", ("POST",)) not in routes:
        failures.append("/api/chat POST route missing — chat was modified!")
        print("[M15] FAIL - /api/chat POST missing", file=sys.stderr)
    else:
        print("[M15] PASS - /api/chat still POST")

    print("[M15] CHECK 2: all 8 structured GET endpoints registered...")
    for path in STRUCTURED_ENDPOINTS:
        if not any(p == path and "GET" in m for p, m in routes):
            failures.append(f"missing GET {path}")
            print(f"[M15] FAIL - GET {path} missing", file=sys.stderr)
    if not failures:
        print("[M15] PASS - all 8 structured endpoints registered")

    print("[M15] CHECK 3: query-layer functions exist...")
    from app.tools import customer_tools, inventory_tools, sales_tools, workforce_tools  # noqa: E402

    required = [
        (sales_tools, "query_daily_summary"),
        (sales_tools, "query_sales_trend"),
        (sales_tools, "query_latest_sales_date"),
        (inventory_tools, "query_stock_levels"),
        (inventory_tools, "query_supply_status"),
        (inventory_tools, "query_replenishment_risk"),
        (inventory_tools, "query_product_profitability"),
        (workforce_tools, "query_workforce_summary"),
        (workforce_tools, "query_latest_shift_date"),
        (customer_tools, "query_customer_behavior"),
        (customer_tools, "query_latest_bill_date"),
    ]
    for mod, fn in required:
        if not hasattr(mod, fn):
            failures.append(f"{mod.__name__}.{fn} missing")
            print(f"[M15] FAIL - {mod.__name__}.{fn} missing", file=sys.stderr)
    if not any("missing" in f for f in failures):
        print("[M15] PASS - all query-layer functions present")

    print("[M15] CHECK 4: tools SQL mirrors tools.yaml definitions...")
    from pathlib import Path  # noqa: E402

    root = Path(__file__).parent.parent
    for rel, markers in SQL_MARKERS.items():
        src = (root / rel).read_text()
        for marker in markers:
            if marker not in src:
                failures.append(f"{rel} missing SQL marker: {marker!r}")
                print(f"[M15] FAIL - {rel} missing {marker!r}", file=sys.stderr)
    if not any("SQL marker" in f for f in failures):
        print("[M15] PASS - SQL mirrors tools.yaml business logic")

    return failures


def live_checks() -> list[str]:
    """Checks 5-6: hit the real BigQuery-backed endpoints. Returns failures."""
    failures: list[str] = []
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        print("[M15] LIVE: SKIP - GOOGLE_CLOUD_PROJECT not set")
        return failures

    try:
        from fastapi.testclient import TestClient

        from app.api import app
    except Exception as exc:  # noqa: BLE001
        print(f"[M15] LIVE: SKIP - TestClient unavailable ({exc})")
        return failures

    print("[M15] LIVE CHECK 5: all endpoints return 200 on real data...")
    client = TestClient(app, raise_server_exceptions=False)
    payloads: dict[str, dict] = {}
    for path in STRUCTURED_ENDPOINTS:
        resp = client.get(path, params={"days": 30} if "days" in path or path.endswith(("summary", "products")) else None)
        if resp.status_code != 200:
            failures.append(f"GET {path} -> {resp.status_code}: {resp.text[:200]}")
            print(f"[M15] FAIL - GET {path} -> {resp.status_code}", file=sys.stderr)
            continue
        payloads[path] = resp.json()
        print(f"[M15] PASS - GET {path} -> 200")

    # Param validation: days=0 must be rejected (422), not silently accepted.
    resp = client.get("/api/home/sales-trend", params={"days": 0})
    if resp.status_code != 422:
        failures.append(f"days=0 not rejected (got {resp.status_code})")
        print("[M15] FAIL - days=0 not rejected", file=sys.stderr)
    else:
        print("[M15] PASS - days=0 rejected with 422")

    print("[M15] LIVE CHECK 6: envelope numbers match direct query layer...")
    from app.tools import customer_tools, inventory_tools, sales_tools, workforce_tools  # noqa: E402

    def approx(a, b, tol=0.05):
        return a is not None and b is not None and abs(float(a) - float(b)) <= tol

    # Home summary vs direct query
    if "/api/home/summary" in payloads:
        body = payloads["/api/home/summary"]
        latest = sales_tools.query_latest_sales_date()
        direct = sales_tools.query_daily_summary(latest)[0] if latest else None
        if direct is None:
            if body.get("summary") is not None:
                failures.append("summary mismatch: expected empty")
        else:
            s = body.get("summary") or {}
            if not approx(s.get("total_revenue"), direct["total_revenue"]):
                failures.append("summary total_revenue mismatch")
            if s.get("total_bills") != direct["total_bills"]:
                failures.append("summary total_bills mismatch")
            if not failures or all("mismatch" not in f for f in failures):
                print(f"[M15] PASS - summary matches direct query ({latest})")

    # Sales trend window vs direct query
    if "/api/home/sales-trend" in payloads:
        body = payloads["/api/home/sales-trend"]
        direct = sales_tools.query_sales_trend(body["start_date"], body["end_date"])
        if len(body["trend"]) != len(direct):
            failures.append(f"trend length mismatch: api={len(body['trend'])} direct={len(direct)}")
        elif body["trend"]:
            api_rev = sum(d["revenue"] for d in body["trend"])
            dir_rev = sum(float(d["revenue"]) for d in direct)
            if not approx(api_rev, dir_rev):
                failures.append("trend revenue mismatch")
        if not any("trend" in f for f in failures):
            print(f"[M15] PASS - trend matches ({len(body['trend'])} days: {body['start_date']}..{body['end_date']})")

    # Stock counts vs direct query
    if "/api/inventory/stock" in payloads:
        body = payloads["/api/inventory/stock"]
        direct = inventory_tools.query_stock_levels()
        if body["total_products"] != len(direct):
            failures.append("stock total_products mismatch")
        below = sum(1 for r in direct if r["stock_on_hand"] < r["reorder_level"])
        if body["below_reorder_count"] != below:
            failures.append(f"stock below_reorder mismatch: api={body['below_reorder_count']} direct={below}")
        if not any("stock" in f for f in failures):
            print(f"[M15] PASS - stock matches ({body['total_products']} products, {body['below_reorder_count']} below reorder)")

    # Supply vs direct query
    if "/api/inventory/supply" in payloads:
        body = payloads["/api/inventory/supply"]
        direct = inventory_tools.query_supply_status()
        if len(body["products"]) != len(direct):
            failures.append("supply count mismatch")
        else:
            print(f"[M15] PASS - supply matches ({len(body['products'])} rows)")

    # Replenishment risk vs direct query
    if "/api/inventory/replenishment-risk" in payloads:
        body = payloads["/api/inventory/replenishment-risk"]
        direct = inventory_tools.query_replenishment_risk(body["start_date"], body["end_date"])
        if len(body["products"]) != len(direct):
            failures.append("risk product count mismatch")
        else:
            print(f"[M15] PASS - replenishment risk matches ({len(body['products'])} rows)")

    # Employees vs direct query
    if "/api/employees/summary" in payloads:
        body = payloads["/api/employees/summary"]
        direct = workforce_tools.query_workforce_summary(body["start_date"], body["end_date"])
        if body["total_shifts"] != sum(r["shifts_worked"] for r in direct):
            failures.append("employees total_shifts mismatch")
        elif not approx(body["total_labour_cost"], sum(float(r["total_wages_inr"]) for r in direct)):
            failures.append("employees total_labour_cost mismatch")
        else:
            print(
                f"[M15] PASS - employees matches ({len(body['employees'])} employees, "
                f"₹{body['total_labour_cost']}, {body['total_shifts']} shifts)"
            )

    # Customers vs direct query
    if "/api/customers/behavior" in payloads:
        body = payloads["/api/customers/behavior"]
        direct = customer_tools.query_customer_behavior(body["start_date"], body["end_date"])
        ids = [c["customer_id"] for c in body["customers"]]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            failures.append(f"customers contains duplicate customer_id rows: {dupes[:5]}")
            print("[M15] FAIL - duplicate customer_id rows in /api/customers/behavior", file=sys.stderr)
        else:
            print("[M15] PASS - one row per customer (no duplicate ids)")
        if body["total_customers"] != len(direct):
            failures.append("customers total mismatch")
        elif body["total_bills"] != sum(r["bill_count"] for r in direct):
            failures.append("customers total_bills mismatch")
        else:
            print(
                f"[M15] PASS - customers matches ({body['total_customers']} customers, "
                f"{body['repeat_customers']} repeat, {body['total_bills']} bills)"
            )

    # Profitability vs direct query
    if "/api/profitability/products" in payloads:
        body = payloads["/api/profitability/products"]
        direct = inventory_tools.query_product_profitability(body["start_date"], body["end_date"])
        if len(body["products"]) != len(direct):
            failures.append("profitability product count mismatch")
        elif not approx(body["total_revenue"], sum(float(r["revenue"]) for r in direct)):
            failures.append("profitability revenue mismatch")
        elif not approx(body["gross_profit"], body["total_revenue"] - body["total_cogs"]):
            failures.append("profitability gross_profit != revenue - cogs")
        else:
            print(
                f"[M15] PASS - profitability matches (revenue ₹{body['total_revenue']}, "
                f"gross profit ₹{body['gross_profit']}, margin {body['gross_margin_pct']}%)"
            )

    return failures


def main():
    print("=== MILESTONE 15 DETERMINISTIC TESTS ===\n")
    failures = static_checks()

    print("\n=== MILESTONE 15 LIVE BIGQUERY VALIDATION ===\n")
    failures += live_checks()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M15] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M15] RESULT: PASS - Milestone 15 complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()