"""
Retail Lens — Milestone 1 Smoke Test

Verifies that:
  1. GEMINI_API_KEY is present in the environment.
  2. The ADK Runner can send a message to root_agent.
  3. Gemini 3.6 Flash returns a non-empty response.

Run:
    python tests/test_milestone1.py

No additional dependencies beyond requirements.txt.
"""

import asyncio
import os
import sys

# Make sure the project root is on sys.path when this file is run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

load_dotenv()

_APP_NAME = "retail_lens_smoke"
_USER_ID = "smoke_user"
_SESSION_ID = "smoke_session"
_MESSAGE = "Say hello and confirm that you are the Retail Lens orchestrator."


async def _smoke() -> str:
    """Run a single turn against root_agent and return the reply text."""
    from app.agents.orchestrator import root_agent  # imported here to keep path clean

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=_APP_NAME,
        user_id=_USER_ID,
        session_id=_SESSION_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=_SESSION_ID,
        new_message=Content(parts=[Part(text=_MESSAGE)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    return final_text


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[smoke] SKIP — GEMINI_API_KEY not set. Add it to .env and retry.")
        sys.exit(0)

    print("[smoke] Sending message to root_agent…")
    try:
        response = asyncio.run(_smoke())
    except Exception as exc:  # noqa: BLE001
        print(f"[smoke] FAIL — {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "[smoke] Check that GEMINI_API_KEY is valid and "
            "gemini-3.6-flash is accessible on your account.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not response.strip():
        print("[smoke] FAIL — empty response from Gemini.", file=sys.stderr)
        sys.exit(1)

    print(f"[smoke] PASS — response received ({len(response)} chars)")
    print(f"[smoke] Response preview: {response[:120].strip()}…")


if __name__ == "__main__":
    main()
