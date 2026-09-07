"""
Milestone 21 — Analytics Page Tests (deterministic, no servers).

  1. Analytics.tsx exists and is registered in App.tsx.
  2. Exactly the four preset analyses required by the roadmap.
  3. Only ONE chart is rendered at a time (single ResponsiveContainer).
  4. Uses existing structured APIs (no new backend, no AI).
  5. No predictive analytics / AI interpretation.
  6. Loading / error / empty states.

Usage:
    python tests/test_m21_analytics_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


REQUIRED_PRESETS = [
    "Sales Trend — 30 Days",
    "Sales Trend — 90 Days",
    "Top Products by Revenue",
    "Gross Profit by Category",
]


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    ana_path = root / "frontend/src/Analytics.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M21] CHECK {n}: {desc}...")
        if condition:
            print(f"[M21] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M21] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Analytics.tsx exists", ana_path.exists(), "frontend/src/Analytics.tsx missing")
    if not ana_path.exists():
        sys.exit(1)
    ana = ana_path.read_text()

    check(1, "Analytics registered in App.tsx", 'currentView === "analytics"' in app_tsx and "<Analytics />" in app_tsx,
          "App.tsx does not render Analytics")

    for label in REQUIRED_PRESETS:
        check(2, f"preset: {label}", label in ana, f"preset {label!r} missing")
    check(2, "no extra presets", ana.count('id: "') == 4, f"expected 4 presets")

    check(3, "one chart container only", ana.count("<ResponsiveContainer") == 1,
          "more than one chart rendered at a time")

    check(4, "uses fetchSalesTrend", "fetchSalesTrend" in ana, "structured sales-trend API not used")
    check(4, "uses fetchProfitability", "fetchProfitability" in ana, "structured profitability API not used")
    check(4, "no direct AI calls", "sendChatMessage" not in ana and "/chat" not in ana,
          "analytics page must not call AI")

    check(5, "no predictive analytics", "predict" not in ana.lower() and "forecast" not in ana.lower(),
          "predictive/forecast features detected")

    check(6, "loading state", "loading-spinner" in ana, "loading state missing")
    check(6, "error state", "error-box" in ana, "error state missing")
    check(6, "empty state", "No data for this analysis" in ana, "empty state missing")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M21] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M21] RESULT: PASS - Analytics page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()