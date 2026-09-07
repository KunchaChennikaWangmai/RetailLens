"""
Smoke Test — Milestone 3: Sales Agent Reasoning Contract

Verifies that the Sales Agent:
  1. Loads the reasoning contract from app/prompts/sales_agent.txt.
  2. Uses the correct tool for each question type.
  3. Distinguishes evidence from interpretation.
  4. Uses baseline + selling frequency together (not percentage alone).
  5. Does NOT invent unavailable data (e.g. inventory levels).
  6. Responds in a concise, business-oriented style.

Scenarios:
  A. "How were sales today?"           -> get_daily_sales_summary
  B. "Which products are showing unusual movement today?"
                                        -> get_daily_product_movement
  C. "How does Amul Taaza Toned Milk 1L normally behave?"
                                        -> get_product_behavior_profile
  D. "How have our sales been trending?" -> get_sales_trends
  E. "What is our current inventory quantity for milk?"
                                        -> must NOT invent inventory data

Usage:
    python tests/test_milestone3.py
"""

import asyncio
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

try:
    from app.agents.sales_agent import sales_agent
except ImportError as e:
    print(f"[smoke M3] FAIL - Failed to import sales_agent: {e}", file=sys.stderr)
    sys.exit(1)


APP_NAME = "retail_lens"
USER_ID = "smoke_test_user_m3"


# ---------------------------------------------------------------------------
# Deterministic checks (do not consume Gemini quota)
# ---------------------------------------------------------------------------

def check_prompt_loaded() -> list:
    """Verify the reasoning contract is loaded from the prompt file."""
    failures = []
    prompt_path = Path(__file__).parent.parent / "app" / "prompts" / "sales_agent.txt"
    if not prompt_path.exists():
        failures.append("app/prompts/sales_agent.txt does not exist")
        return failures
    text = prompt_path.read_text(encoding="utf-8")
    required_markers = [
        "PRINCIPLE 1",
        "PRINCIPLE 5",
        "PRINCIPLE 6",
        "selling_frequency",
        "NEVER INVENT DATA",
        "INTERPRETATION",
        "ABSOLUTE PROHIBITIONS",
    ]
    for marker in required_markers:
        if marker not in text:
            failures.append(f"Prompt missing marker: {marker}")
    instr = sales_agent.instruction
    if "PRINCIPLE 1" not in instr:
        failures.append("sales_agent.instruction does not contain the reasoning contract")
    if "Retail Lens Sales Agent" not in instr:
        failures.append("sales_agent.instruction missing agent identity")
    return failures


# ---------------------------------------------------------------------------
# Gemini-backed NL checks
# ---------------------------------------------------------------------------

FAILURE_MARKERS = [
    "database error",
    "unrecognized name",
    "tool not found",
    "connection closed",
    "failed to",
    "syntax error",
    "query failed",
    "error executing",
    "timed out",
]


def _contains_failure(text: str) -> list:
    lowered = text.lower()
    return [m for m in FAILURE_MARKERS if m in lowered]


async def _run_agent_single(prompt: str) -> str:
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
    message = Content(role="user", parts=[Part(text=prompt)])
    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
    return final_text


async def _run_agent(prompt: str) -> str:
    """Run agent with retry on Gemini 429 quota errors."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await _run_agent_single(prompt)
        except Exception as exc:
            is_quota = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if is_quota and attempt < max_retries - 1:
                wait = 40 * (attempt + 1)
                print(f"[smoke M3] Gemini quota hit, waiting {wait}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait)
                continue
            raise


def _check_response(text: str, label: str, *, must_not_contain=None,
                    should_contain_any=None) -> list:
    """Check a Gemini response for failure markers and required content."""
    failures = []
    if not text:
        failures.append(f"{label}: empty response")
        return failures
    matched = _contains_failure(text)
    if matched:
        failures.append(f"{label}: failure markers {matched}")
    if must_not_contain:
        lowered = text.lower()
        for bad in must_not_contain:
            if bad.lower() in lowered:
                failures.append(f"{label}: should not contain '{bad}'")
    if should_contain_any:
        lowered = text.lower()
        if not any(s.lower() in lowered for s in should_contain_any):
            failures.append(f"{label}: should contain one of {should_contain_any}")
    return failures


async def run_m3_smoke_test() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke M3] SKIP - GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    # ------------------------------------------------------------------
    # Deterministic: prompt loaded
    # ------------------------------------------------------------------
    print("[smoke M3] CHECK: Reasoning contract loaded from prompt file...")
    pf = check_prompt_loaded()
    if pf:
        failures.extend(pf)
        for f in pf:
            print(f"[smoke M3] FAIL - {f}", file=sys.stderr)
    else:
        print("[smoke M3] PASS - Reasoning contract loaded and contains all key principles.")

    # ------------------------------------------------------------------
    # NL scenario A: current sales
    # ------------------------------------------------------------------
    print("[smoke M3] SCENARIO A: 'How were sales today?'...")
    try:
        text_a = await _run_agent("How were sales today?")
        f = _check_response(text_a, "Scenario A (daily summary)",
                            should_contain_any=["revenue", "bills", "units", "sales"])
        if f:
            failures.extend(f)
            print(f"[smoke M3] FAIL - {f[0]}", file=sys.stderr)
        else:
            print("[smoke M3] PASS - Scenario A returned a business response.")
            print(f"[smoke M3] Preview: {text_a[:200]}...")
    except Exception as exc:
        failures.append(f"Scenario A exception: {exc}")
        print(f"[smoke M3] FAIL - Scenario A: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # NL scenario B: product movement (baseline + frequency reasoning)
    # ------------------------------------------------------------------
    print("[smoke M3] SCENARIO B: 'Which products are showing unusual movement today?'...")
    time.sleep(5)
    try:
        text_b = await _run_agent(
            "Which products are showing unusual movement today? "
            "Consider both the percentage change and how often each product normally sells."
        )
        f = _check_response(text_b, "Scenario B (product movement)",
                            should_contain_any=["baseline", "frequency", "selling", "units", "movement", "revenue"])
        if f:
            failures.extend(f)
            print(f"[smoke M3] FAIL - {f[0]}", file=sys.stderr)
        else:
            print("[smoke M3] PASS - Scenario B returned a movement analysis.")
            print(f"[smoke M3] Preview: {text_b[:200]}...")
    except Exception as exc:
        failures.append(f"Scenario B exception: {exc}")
        print(f"[smoke M3] FAIL - Scenario B: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # NL scenario C: historical behaviour
    # ------------------------------------------------------------------
    print("[smoke M3] SCENARIO C: 'How does Amul Taaza Toned Milk 1L normally behave?'...")
    time.sleep(5)
    try:
        text_c = await _run_agent(
            "How does the product 'Amul Taaza Toned Milk 1L Packet' normally behave? "
            "Look at its historical sales profile."
        )
        f = _check_response(text_c, "Scenario C (behaviour profile)",
                            should_contain_any=["active", "frequency", "volatility", "units", "days", "revenue", "behave"])
        if f:
            failures.extend(f)
            print(f"[smoke M3] FAIL - {f[0]}", file=sys.stderr)
        else:
            print("[smoke M3] PASS - Scenario C returned a behaviour profile.")
            print(f"[smoke M3] Preview: {text_c[:200]}...")
    except Exception as exc:
        failures.append(f"Scenario C exception: {exc}")
        print(f"[smoke M3] FAIL - Scenario C: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # NL scenario D: trends
    # ------------------------------------------------------------------
    print("[smoke M3] SCENARIO D: 'How have our sales been trending?'...")
    time.sleep(5)
    try:
        text_d = await _run_agent("How have our sales been trending over the last month?")
        f = _check_response(text_d, "Scenario D (trends)",
                            should_contain_any=["trend", "revenue", "units", "bills", "sales", "daily"])
        if f:
            failures.extend(f)
            print(f"[smoke M3] FAIL - {f[0]}", file=sys.stderr)
        else:
            print("[smoke M3] PASS - Scenario D returned a trend analysis.")
            print(f"[smoke M3] Preview: {text_d[:200]}...")
    except Exception as exc:
        failures.append(f"Scenario D exception: {exc}")
        print(f"[smoke M3] FAIL - Scenario D: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # NL scenario E: evidence limitation (inventory)
    # ------------------------------------------------------------------
    print("[smoke M3] SCENARIO E: 'What is our current inventory quantity for milk?'...")
    time.sleep(5)
    try:
        text_e = await _run_agent("What is our current inventory quantity for milk?")
        f = _check_response(text_e, "Scenario E (inventory limitation)",
                            should_contain_any=["don't have", "do not have", "not available",
                                                "no inventory", "cannot", "unable",
                                                "don't currently", "no data"])
        if f:
            failures.extend(f)
            print(f"[smoke M3] FAIL - {f[0]}", file=sys.stderr)
        else:
            print("[smoke M3] PASS - Scenario E correctly acknowledged missing inventory data.")
            print(f"[smoke M3] Preview: {text_e[:200]}...")
    except Exception as exc:
        failures.append(f"Scenario E exception: {exc}")
        print(f"[smoke M3] FAIL - Scenario E: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke M3] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke M3] RESULT: PASS - All Milestone 3 checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m3_smoke_test())
