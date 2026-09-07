"""
Milestone 19 — Customers Page Tests (deterministic, no servers).

  1. Customers.tsx exists and is registered in App.tsx.
  2. Date range selector drives refetch.
  3. KPIs: unique customers, total bills, average bill value, repeat customers.
  4. Ranked top-customer table with all required columns.
  5. No invented data: no preferences / CLV / segmentation claims.
  6. Purchase frequency note matches backend definition (share of days).
  7. Loading / error / empty states.

Usage:
    python tests/test_m19_customers_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    cust_path = root / "frontend/src/Customers.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M19] CHECK {n}: {desc}...")
        if condition:
            print(f"[M19] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M19] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Customers.tsx exists", cust_path.exists(), "frontend/src/Customers.tsx missing")
    if not cust_path.exists():
        sys.exit(1)
    cust = cust_path.read_text()

    check(1, "Customers registered in App.tsx", 'currentView === "customers"' in app_tsx and "<Customers />" in app_tsx,
          "App.tsx does not render Customers")

    check(2, "date range selector", "Last 7 Days" in cust and "Last 90 Days" in cust, "range selector missing")
    check(2, "range change refetches", "useEffect" in cust and "[days]" in cust, "range change does not refetch")

    check(3, "KPI: unique customers", "Unique Customers" in cust, "unique-customers KPI missing")
    check(3, "KPI: total bills", "Total Bills" in cust, "total-bills KPI missing")
    check(3, "KPI: average bill value", "Average Bill Value" in cust, "average-bill KPI missing")
    check(3, "KPI: repeat customers", "Repeat Customers" in cust, "repeat-customers KPI missing")

    for col in ["Rank", "Customer", "Visits", "Total Spend", "Avg / Visit", "Last Visit", "Purchase Frequency"]:
        check(4, f"column: {col}", col in cust, f"table column {col!r} missing")

    check(5, "explicit limitation note", "does not track customer preferences" in cust,
          "missing honest data-limitation note")
    check(6, "frequency note matches backend (share of days)",
          "share of days in the period" in cust, "purchase frequency definition does not match backend")

    check(7, "loading state", "loading-spinner" in cust, "loading state missing")
    check(7, "error state", "error-box" in cust, "error state missing")
    check(7, "empty state", "No customer activity" in cust, "empty state missing")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M19] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M19] RESULT: PASS - Customers page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()