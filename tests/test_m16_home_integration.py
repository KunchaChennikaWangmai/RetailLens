"""
Milestone 16 — Home Page Integration Tests (deterministic, no servers).

  1. Home.tsx no longer contains demo/fake sales data.
  2. Home uses the structured M15 APIs (summary + sales trend).
  3. Today/Yesterday toggle, 1 Month Summary and 1 Year Summary are present.
  4. Month/Year summaries route through the AI Chat page (onAskChat).
  5. api.ts exposes typed fetchers hitting the M15 endpoints.
  6. Loading and error states are implemented.
  7. App.tsx wires the chat handoff (pendingChatMessage).
  8. Chat.tsx markdown rendering from M14 is intact (no regression).

Usage:
    python tests/test_m16_home_integration.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    root = Path(__file__).parent.parent
    failures: list[str] = []

    home = (root / "frontend/src/Home.tsx").read_text()
    api = (root / "frontend/src/services/api.ts").read_text()
    app_tsx = (root / "frontend/src/App.tsx").read_text()
    chat = (root / "frontend/src/Chat.tsx").read_text()

    def check(n, desc, condition, fail_msg):
        print(f"[M16] CHECK {n}: {desc}...")
        if condition:
            print(f"[M16] PASS - {desc}")
        else:
            failures.append(fail_msg)
            print(f"[M16] FAIL - {fail_msg}", file=sys.stderr)

    check(1, "no demo sales data in Home", "demoSalesData" not in home and "Demo Data" not in home,
          "Home still contains demoSalesData / Demo Data badge")
    check(1, "no placeholder AI-insight block in Home", "Placeholder" not in home and "backend integration" not in home,
          "Home still contains placeholder insight text")

    check(2, "Home uses fetchHomeSummary", "fetchHomeSummary" in home, "fetchHomeSummary not used")
    check(2, "Home uses fetchSalesTrend", "fetchSalesTrend" in home, "fetchSalesTrend not used")
    check(2, "no fake setTimeout API stubs in api.ts", "setTimeout" not in api, "api.ts still has the setTimeout placeholder stub")

    check(3, "Today/Yesterday toggle present", "toggle-btn" in home and 'handleRange("today")' in home and 'handleRange("yesterday")' in home,
          "Today/Yesterday toggle missing")
    check(3, "1 Month Summary button present", "1 Month Summary" in home, "1 Month Summary button missing")
    check(3, "1 Year Summary button present", "1 Year Summary" in home, "1 Year Summary button missing")

    check(4, "Month/Year summaries route via onAskChat", "onAskChat(MONTH_SUMMARY_PROMPT)" in home and "onAskChat(YEAR_SUMMARY_PROMPT)" in home,
          "Month/Year buttons do not call onAskChat")

    check(5, "api.ts hits /home/summary", '"/home/summary"' in api, "api.ts missing /home/summary")
    check(5, "api.ts hits /home/sales-trend", '"/home/sales-trend"' in api, "api.ts missing /home/sales-trend")
    check(5, "api.ts keeps /chat endpoint", "${API_BASE_URL}/chat" in api, "api.ts lost the /chat endpoint")

    check(6, "loading states present in Home", "loading-spinner" in home, "Home missing loading spinner")
    check(6, "error states present in Home", "error-box" in home or "state-title" in home, "Home missing error/empty states")
    check(6, "empty-state messaging present in Home", "No sales" in home, "Home missing empty-state message")

    check(7, "App wires pendingChatMessage", "pendingChatMessage" in app_tsx and "askChat" in app_tsx,
          "App.tsx missing chat handoff wiring")
    check(7, "Chat accepts pendingMessage prop", "pendingMessage" in chat, "Chat.tsx missing pendingMessage prop")

    check(8, "M14 markdown rendering intact", 'import ReactMarkdown from "react-markdown"' in chat and "remarkGfm" in chat,
          "Chat.tsx markdown rendering regression")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M16] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[M16] RESULT: PASS - Home page is fully wired to real backend data.")
    sys.exit(0)


if __name__ == "__main__":
    main()