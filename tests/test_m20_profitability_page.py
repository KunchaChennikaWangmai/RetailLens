"""
Milestone 20 — Profitability Page Tests (deterministic, no servers).

  1. Profitability.tsx exists and is registered in App.tsx.
  2. The exact gross-vs-net-profit disclaimer is displayed prominently.
  3. KPIs: Revenue, COGS, Gross Profit, Gross Margin.
  4. Product profitability table + category summary.
  5. Exactly one chart (top products by gross profit).
  6. The word "net profit" only appears in the disclaimer context.
  7. Loading / error / empty states.

Usage:
    python tests/test_m20_profitability_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


DISCLAIMER = (
    "These figures show gross profit — revenue minus cost of goods sold. Operating "
    "expenses such as rent, utilities, and labour are not included. Net profit data "
    "is not available in this system."
)


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    prof_path = root / "frontend/src/Profitability.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M20] CHECK {n}: {desc}...")
        if condition:
            print(f"[M20] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M20] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Profitability.tsx exists", prof_path.exists(), "frontend/src/Profitability.tsx missing")
    if not prof_path.exists():
        sys.exit(1)
    prof = prof_path.read_text()
    # JSX inserts newlines/indentation inside text nodes; normalize for matching.
    prof_norm = " ".join(prof.split())

    check(1, "Profitability registered in App.tsx", 'currentView === "profitability"' in app_tsx and "<Profitability />" in app_tsx,
          "App.tsx does not render Profitability")

    check(2, "exact gross-profit disclaimer present", DISCLAIMER in prof_norm,
          "required disclaimer text missing or altered")
    check(2, "disclaimer is prominent (near top, not buried)",
          prof.find("disclaimer-box") < prof.find("metric-grid"),
          "disclaimer does not appear before the KPI grid")

    check(3, "KPI: revenue", ">Revenue<" in prof, "revenue KPI missing")
    check(3, "KPI: COGS", "Cost of Goods Sold" in prof, "COGS KPI missing")
    check(3, "KPI: gross profit", "Gross Profit" in prof, "gross profit KPI missing")
    check(3, "KPI: gross margin", "Gross Margin" in prof, "gross margin KPI missing")

    check(4, "product profitability table", "Product Profitability" in prof, "product table missing")
    check(4, "category summary", "Category Summary" in prof, "category summary missing")
    check(4, "table columns complete",
          all(c in prof for c in ["Units Sold", "Revenue", "COGS", "Gross Profit", "Margin"]),
          "product table missing required columns")

    chart_count = prof.count("<ResponsiveContainer")
    check(5, "exactly one chart", chart_count == 1, f"expected 1 chart, found {chart_count}")
    check(5, "chart is top products by gross profit", 'dataKey="gross_profit"' in prof,
          "chart does not plot gross profit")

    check(6, "no KPI/heading labelled 'Net Profit'",
          ">Net Profit<" not in prof and "Net Profit:" not in prof,
          "a KPI/heading labels gross profit as net profit")
    check(6, "'net profit' mentioned only to disclaim it",
          "net profit data" in prof_norm.lower() and "not net profit" in prof_norm.lower(),
          "unexpected net profit usage")

    check(7, "loading state", "loading-spinner" in prof, "loading state missing")
    check(7, "error state", "error-box" in prof, "error state missing")
    check(7, "empty state", "No sales in this period" in prof, "empty state missing")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M20] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M20] RESULT: PASS - Profitability page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()