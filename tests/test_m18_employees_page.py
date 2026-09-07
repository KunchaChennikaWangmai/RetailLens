"""
Milestone 18 — Employees Page Tests (deterministic, no servers).

  1. Employees.tsx exists and is registered in App.tsx.
  2. Date range selector (7 / 30 / 90 days) drives refetch.
  3. KPIs: total labour cost, total shifts, scheduled hours, actual hours.
  4. Employee table: wages, late check-ins, early departures, overtime.
  5. Data limitations stated honestly (no fabricated precision).
  6. No unnecessary charts.
  7. Loading / error / empty states.

Usage:
    python tests/test_m18_employees_page.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    emp_path = root / "frontend/src/Employees.tsx"
    app_tsx = (root / "frontend/src/App.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M18] CHECK {n}: {desc}...")
        if condition:
            print(f"[M18] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M18] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "Employees.tsx exists", emp_path.exists(), "frontend/src/Employees.tsx missing")
    if not emp_path.exists():
        sys.exit(1)
    emp = emp_path.read_text()

    check(1, "Employees registered in App.tsx", 'currentView === "employees"' in app_tsx and "<Employees />" in app_tsx,
          "App.tsx does not render Employees")

    check(2, "date range selector", "Last 7 Days" in emp and "Last 30 Days" in emp and "Last 90 Days" in emp,
          "range selector options missing")
    check(2, "range change refetches", "useEffect" in emp and "[days]" in emp, "range change does not refetch")

    check(3, "KPI: total labour cost", "Total Labour Cost" in emp, "labour-cost KPI missing")
    check(3, "KPI: total shifts", "Total Shifts" in emp, "shifts KPI missing")
    check(3, "KPI: scheduled hours", "Scheduled Hours" in emp, "scheduled-hours KPI missing")
    check(3, "KPI: actual hours", "Actual Hours" in emp, "actual-hours KPI missing")

    check(4, "table shows wages", "Wages" in emp, "wages column missing")
    check(4, "table shows late check-ins", "Late In" in emp and "late_check_in_count" in emp, "late check-in column missing")
    check(4, "table shows early departures", "Early Out" in emp and "early_departure_count" in emp, "early-departure column missing")
    check(4, "table shows overtime", "Overtime" in emp and "overtime_shift_count" in emp, "overtime column missing")

    check(5, "data limitations stated", "About this data" in emp and "note-list" in emp,
          "data limitation notes missing")
    check(5, "honest missing-actual-hours handling", '"—"' in emp, "missing actual hours not handled")

    check(6, "no charts on employees page", "recharts" not in emp and "ResponsiveContainer" not in emp,
          "Employees page should not include charts")

    check(7, "loading state", "loading-spinner" in emp, "loading state missing")
    check(7, "error state", "error-box" in emp, "error state missing")
    check(7, "empty state", "No shifts recorded" in emp, "empty state missing")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M18] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M18] RESULT: PASS - Employees page complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()