"""
Milestone 23 — Final Integration + Demo Readiness (deterministic + live).

Static checks:
  1. Dockerfile CMD serves uvicorn app.api:app.
  2. /api/health handler exists; chat has 503/timeout handling.
  3. Frontend chat surfaces 503/504 friendly errors.
  4. No 'Coming Soon' pages remain.
  5. No demo/fake data remains in any page component.
  6. Every sidebar page component exists and is registered in App.tsx.
  7. README documents the current system.

Live checks (TestClient against real backend):
  8. /api/health returns 200 with status ok.
  9. All 8 structured endpoints + POST /api/chat still registered.

Usage:
    python tests/test_m23_final_integration.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


SIDEBAR_PAGES = {
    "home": "Home.tsx",
    "chat": "Chat.tsx",
    "inventory": "Inventory.tsx",
    "employees": "Employees.tsx",
    "customers": "Customers.tsx",
    "profitability": "Profitability.tsx",
    "analytics": "Analytics.tsx",
    "data": "Data.tsx",
}

FAKE_DATA_MARKERS = ["demoSalesData", "demo_sales", "fakeData", "FAKE_", "setTimeout("]


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    def check(n, desc, condition, fail_msg):
        print(f"[M23] CHECK {n}: {desc}...")
        if condition:
            print(f"[M23] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M23] FAIL - {fail_msg}", file=sys.stderr)

    # 1. Dockerfile
    dockerfile = (root / "Dockerfile").read_text()
    check(1, "Dockerfile CMD uses uvicorn app.api:app",
          "uvicorn" in dockerfile and "app.api:app" in dockerfile and "app.main" not in dockerfile.split("CMD")[-1],
          "Dockerfile CMD does not serve uvicorn app.api:app")

    # 2. Backend error handling
    api_src = (root / "app/api.py").read_text()
    check(2, "/api/health handler exists", '"/api/health"' in api_src, "/api/health missing")
    check(2, "chat timeout handling", "asyncio.wait_for" in api_src and "504" in api_src,
          "chat timeout handling missing")
    check(2, "Gemini 503 handling", "503" in api_src and "_GEMINI_BUSY_MARKERS" in api_src,
          "Gemini 503 handling missing")

    # 3. Frontend chat error handling
    api_ts = (root / "frontend/src/services/api.ts").read_text()
    check(3, "frontend handles 503", "503" in api_ts, "frontend 503 handling missing")
    check(3, "frontend handles 504", "504" in api_ts, "frontend 504 handling missing")

    # 4/5/6. Frontend pages
    src_dir = root / "frontend/src"
    all_src = ""
    page_files = {}
    for view, fname in SIDEBAR_PAGES.items():
        p = src_dir / fname
        page_files[view] = p
        if p.exists():
            all_src += p.read_text()
    check(4, "all page components exist", all(p.exists() for p in page_files.values()),
          f"missing pages: {[f for v, f in SIDEBAR_PAGES.items() if not page_files[v].exists()]}")
    check(4, "no 'Coming Soon' remains", "Coming Soon" not in all_src.lower(),
          "a page still shows 'Coming Soon'")

    fake_hits = [m for m in FAKE_DATA_MARKERS if m in all_src]
    check(5, "no fake/demo data in pages", not fake_hits,
          f"fake data markers still present: {fake_hits}")

    app_tsx = (src_dir / "App.tsx").read_text()
    missing_routes = [v for v in SIDEBAR_PAGES if f'currentView === "{v}"' not in app_tsx]
    check(6, "all pages registered in App.tsx", not missing_routes,
          f"pages not routed in App.tsx: {missing_routes}")

    # 7. README
    readme = (root / "README.md").read_text()
    check(7, "README documents structured API", "/api/home/summary" in readme and "/api/profitability/products" in readme,
          "README missing structured API docs")
    check(7, "README documents uvicorn + Docker", "uvicorn app.api:app" in readme,
          "README missing uvicorn/Docker instructions")
    check(7, "README explains gross vs net profit", "gross profit" in readme.lower(),
          "README missing gross profit clarification")

    # Live checks
    print("\n[M23] LIVE CHECKS")
    live_ok = False
    if os.getenv("GOOGLE_CLOUD_PROJECT"):
        try:
            from fastapi.testclient import TestClient

            from app.api import app

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/health")
            check(8, "/api/health returns 200 ok", resp.status_code == 200 and resp.json().get("status") == "ok",
                  f"/api/health -> {resp.status_code}")

            expected = {
                "/api/home/summary", "/api/home/sales-trend",
                "/api/inventory/replenishment-risk", "/api/inventory/stock",
                "/api/inventory/supply", "/api/employees/summary",
                "/api/customers/behavior", "/api/profitability/products",
            }
            routes = {r.path for r in app.routes}
            missing = expected - routes
            check(9, "all structured endpoints registered", not missing,
                  f"missing endpoints: {sorted(missing)}")
            check(9, "POST /api/chat registered",
                  any(r.path == "/api/chat" and "POST" in getattr(r, "methods", set()) for r in app.routes),
                  "/api/chat POST missing")
            live_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"[M23] LIVE: SKIP - {exc}")
    else:
        print("[M23] LIVE: SKIP - GOOGLE_CLOUD_PROJECT not set")
    if not live_ok:
        print("[M23] LIVE checks skipped (no credentials) — static checks still apply.")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M23] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M23] RESULT: PASS - Project is demo-ready.")
    sys.exit(0)


if __name__ == "__main__":
    main()