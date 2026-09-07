"""
Milestone 22 — Data Page Tests (deterministic, no servers).

  1. Data.tsx exists and is registered in App.tsx.
  2. Pipeline diagram: POS/ERP → Data Pipeline → BigQuery → MCP Toolbox
     → AI Agents → Retail Lens.
  3. All existing tables explained.
  4. Distinguishes realistic demo data vs synthetic demo data, and
     describes production ingestion.
  5. Static page — no backend calls.

Usage:
    python tests/test_m22_data_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


REQUIRED_STEPS = ["POS / ERP", "Data Pipeline", "BigQuery", "MCP Toolbox", "AI Agents", "Retail Lens"]
REQUIRED_TABLES = [
    "sales_transactions",
    "customer_bills",
    "inventory_stock",
    "inventory_supply",
    "inventory_metadata",
    "workforce_shifts",
]


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    data_path = root / "frontend/src/Data.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M22] CHECK {n}: {desc}...")
        if condition:
            print(f"[M22] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M22] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Data.tsx exists", data_path.exists(), "frontend/src/Data.tsx missing")
    if not data_path.exists():
        sys.exit(1)
    data = data_path.read_text()

    check(1, "Data registered in App.tsx", 'currentView === "data"' in app_tsx and "<Data />" in app_tsx,
          "App.tsx does not render Data")

    for step in REQUIRED_STEPS:
        check(2, f"pipeline step: {step}", step in data, f"pipeline step {step!r} missing")

    for table in REQUIRED_TABLES:
        check(3, f"table explained: {table}", table in data, f"table {table!r} not explained")

    check(4, "realistic demo data distinguished", "Realistic demo data" in data,
          "realistic demo data explanation missing")
    check(4, "synthetic demo data distinguished", "Synthetic demo data" in data,
          "synthetic demo data explanation missing")
    check(4, "production ingestion explained", "In production" in data or "In a live deployment" in data,
          "production ingestion explanation missing")

    check(5, "static page (no API calls)", "fetch" not in data.replace(".fetch(", "").replace("fetchStock", ""),
          "Data page should be static")
    check(5, "no charts on data page", "ResponsiveContainer" not in data, "Data page should not have charts")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M22] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M22] RESULT: PASS - Data page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()