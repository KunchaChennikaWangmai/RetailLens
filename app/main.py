"""
Retail Lens — Application Entry Point

Milestone 1: verifies that the local machine can reach Gemini via ADK.
Sends a single test message to the root orchestrator agent and prints
the response.  No sub-agents, no MCP Toolbox, no BigQuery.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.agents.orchestrator import root_agent

load_dotenv()

_TEST_MESSAGE = (
    "Say hello and confirm that you are the Retail Lens orchestrator."
)
_APP_NAME = "retail_lens"
_USER_ID = "milestone1_user"
_SESSION_ID = "milestone1_session"


async def _run_agent(message: str) -> str:
    """Send *message* to root_agent and return the final response text."""
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

    user_content = Content(parts=[Part(text=message)])
    final_text = ""

    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=_SESSION_ID,
        new_message=user_content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    return final_text


def main() -> None:
    """Milestone 1 entry point — proves Gemini API connectivity."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Set GEMINI_API_KEY=<your-key> inside .env\n"
            "  3. Re-run."
        )

    print("Retail Lens initialised.")
    print(f"Root agent: {root_agent.name}")
    print("Sending test message to Gemini…")
    print("─" * 45)

    try:
        response = asyncio.run(_run_agent(_TEST_MESSAGE))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Gemini API call failed — {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "Check that GEMINI_API_KEY is valid and that gemini-3.6-flash "
            "is accessible on your account.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Agent: {response}")
    print("─" * 45)
    print("Milestone 1 complete. Gemini API connectivity verified. ✓")


if __name__ == "__main__":
    main()
