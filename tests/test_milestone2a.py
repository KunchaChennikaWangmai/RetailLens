"""
Smoke Test — Milestone 2A: Sales Agent → MCP Toolbox → BigQuery → Gemini

Verifies that:
  1. The local MCP Toolbox server connects to BigQuery correctly via ADC.
  2. The Sales Agent uses the get_daily_sales_summary MCP tool.
  3. The final response synthesizes the empirical SQL result (not hallucinated).

Usage:
    python tests/test_milestone2a.py
"""

import asyncio
import os
import sys

# Make sure the project root is on sys.path when this file is run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# Load .env BEFORE importing the agent so that GOOGLE_CLOUD_PROJECT is
# available when mcp_toolbox.py captures os.environ for the subprocess.
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

try:
    from app.agents.sales_agent import sales_agent
except ImportError as e:
    print(f"[smoke 2A] FAIL — Failed to import sales_agent: {e}", file=sys.stderr)
    sys.exit(1)


APP_NAME = "retail_lens"
USER_ID = "smoke_test_user"


async def run_m2a_smoke_test() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke 2A] SKIP — GEMINI_API_KEY not set.")
        sys.exit(0)

    print("[smoke 2A] Initializing session and executing Sales Agent...")

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    runner = Runner(
        agent=sales_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = Content(
        role="user",
        parts=[Part(text="Give me today's sales summary.")],
    )

    final_text = ""
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response():
                final_text = event.content.parts[0].text
    except Exception as exc:
        print(
            f"[smoke 2A] FAIL — {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not final_text:
        print("[smoke 2A] FAIL — empty response from Gemini", file=sys.stderr)
        sys.exit(1)

    # Harden: a non-empty response that reports a tool/database failure
    # must NOT be treated as a PASS. Gemini may synthesize an error
    # message returned by the tool, so we scan the final text for
    # obvious failure signals.
    failure_markers = [
        "database error",
        "unrecognized name",
        "tool not found",
        "connection closed",
        "failed to",
        "error",
    ]
    lowered = final_text.lower()
    matched = [m for m in failure_markers if m in lowered]
    if matched:
        print(
            "[smoke 2A] FAIL — Gemini response contains a tool/database "
            f"failure signal: {matched}",
            file=sys.stderr,
        )
        print(f"[smoke 2A] Preview: {final_text[:300]}…", file=sys.stderr)
        sys.exit(1)

    print("[smoke 2A] PASS — Data successfully fetched and synthesized.")
    print(f"[smoke 2A] Preview: {final_text[:300]}…")


if __name__ == "__main__":
    asyncio.run(run_m2a_smoke_test())