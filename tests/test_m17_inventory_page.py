"""
Milestone 17 — Inventory Page Tests (deterministic, no servers).

  1. Inventory.tsx exists and is registered in App.tsx (no Coming Soon).
  2. Uses the structured M15 APIs (replenishment-risk, stock, supply).
  3. Required KPIs: products tracked, below reorder, incoming supply,
     next expected delivery.
  4. Required tables: needs-attention, current stock, incoming supply.
  5. Status indicators: Low Stock / Monitor / OK.
  6. No unnecessary inventory charts (no recharts on this page).
  7. Loading / error / empty states present.

Usage:
    python tests/test_m17_inventory_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    inv_path = root / "frontend/src/Inventory.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M17] CHECK {n}: {desc}...")
        if condition:
            print(f"[M17] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M17] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Inventory.tsx exists", inv_path.exists(), "frontend/src/Inventory.tsx missing")
    if not inv_path.exists():
        print(f"\n[M17] RESULT: FAIL", file=sys.stderr)
        sys.exit(1)
    inv = inv_path.read_text()

    check(1, "Inventory registered in App.tsx", 'currentView === "inventory"' in app_tsx and "Inventory" in app_tsx,
          "App.tsx does not render Inventory")
    check(1, "no Inventory Coming Soon placeholder", "Inventory — Coming Soon" not in app_tsx,
          "Inventory Coming Soon placeholder still present")

    check(2, "uses fetchReplenishmentRisk", "fetchReplenishmentRisk" in inv, "replenishment-risk API not used")
    check(2, "uses fetchStock", "fetchStock" in inv, "stock API not used")
    check(2, "uses fetchSupply", "fetchSupply" in inv, "supply API not used")

    check(3, "KPI: products tracked", "Products Tracked" in inv, "products-tracked KPI missing")
    check(3, "KPI: below reorder level", "Below Reorder Level" in inv, "below-reorder KPI missing")
    check(3, "KPI: incoming supply", "With Incoming Supply" in inv, "incoming-supply KPI missing")
    check(3, "KPI: next expected delivery", "Next Expected Delivery" in inv, "next-delivery KPI missing")

    check(4, "needs-attention table", "Needs Attention First" in inv, "needs-attention table missing")
    check(4, "current stock table", "Current Stock" in inv, "current-stock table missing")
    check(4, "incoming supply table", "Incoming Supply" in inv, "incoming-supply table missing")

    check(5, "Low Stock indicator", '"low"' in inv and "Low Stock" in inv, "Low Stock status missing")
    check(5, "Monitor indicator", "Monitor" in inv, "Monitor status missing")
    check(5, "OK indicator", 'ok: "OK"' in inv, "OK status missing")

    check(6, "no charts on inventory page", "recharts" not in inv and "ResponsiveContainer" not in inv,
          "Inventory page should not include charts")

    check(7, "loading state", "loading-spinner" in inv, "loading state missing")
    check(7, "error state", "error-box" in inv, "error state missing")
    check(7, "empty states", "state-box" in inv and ("No stock records" in inv or "No incoming supply" in inv),
          "empty states missing")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M17] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M17] RESULT: PASS - Inventory page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()