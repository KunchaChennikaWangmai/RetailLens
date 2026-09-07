"""
Smoke Test — Milestone 2B: Sales Analytical Evidence Layer

Verifies that:
  1. Existing get_daily_sales_summary still works (regression).
  2. MCP Toolbox starts successfully.
  3. MCP Toolbox reports all four expected tools.
  4. get_daily_product_movement successfully queries BigQuery.
  5. get_sales_trends successfully queries BigQuery.
  6. get_product_behavior_profile successfully queries BigQuery.
  7. Sales Agent can invoke the new tools (natural-language tests).
  8. A database/tool failure results in test failure (hardened pattern).

Usage:
    python tests/test_milestone2b.py
"""

import asyncio
import os
import time
import sys
import traceback
from pathlib import Path

# Make sure the project root is on sys.path when this file is run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# Load .env BEFORE importing the agent so that GOOGLE_CLOUD_PROJECT is
# available when mcp_toolbox.py captures os.environ for the subprocess.
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

try:
    from app.agents.sales_agent import sales_agent
except ImportError as e:
    print(f"[smoke 2B] FAIL — Failed to import sales_agent: {e}", file=sys.stderr)
    sys.exit(1)


APP_NAME = "retail_lens"
USER_ID = "smoke_test_user_2b"

_TOOLS_YAML = str(Path(__file__).parent.parent / "tools.yaml")

EXPECTED_TOOLS = {
    "get_daily_sales_summary",
    "get_daily_product_movement",
    "get_sales_trends",
    "get_product_behavior_profile",
}

# Valid date range based on the live BigQuery data (2026-05-01 .. 2026-08-31).
TARGET_DATE = "2026-08-28"
RANGE_START = "2026-08-01"
RANGE_END = "2026-08-28"

# Failure signals that, if present in a Gemini response, indicate a tool /
# database failure rather than a successful synthesis. Reused from the
# Milestone 2A hardening pattern.
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


# A single shared toolset is reused for all direct tool invocations to
# avoid spawning multiple npx subprocesses. The default 5s timeout is too
# short for session creation + complex BigQuery analytical queries, so we
# raise it to 120s.
_MCP_TIMEOUT = 120.0
_shared_toolset = None
_shared_tools = None


async def _get_shared_toolset():
    """Lazily create and cache a single McpToolset + its tools dict."""
    global _shared_toolset, _shared_tools
    if _shared_tools is None:
        sp = StdioServerParameters(
            command="npx",
            args=["-y", "@toolbox-sdk/server", "--config", _TOOLS_YAML, "--stdio"],
            env=dict(os.environ),
        )
        connection_params = StdioConnectionParams(
            server_params=sp, timeout=_MCP_TIMEOUT
        )
        _shared_toolset = McpToolset(connection_params=connection_params)
        tools = await _shared_toolset.get_tools()
        _shared_tools = {t.name: t for t in tools}
    return _shared_toolset, _shared_tools


async def _get_mcp_tools() -> dict:
    """Spin up the MCP Toolbox server and return {name: tool} dict."""
    _, tools_map = await _get_shared_toolset()
    return tools_map


async def _invoke_tool(tool_name: str, **kwargs) -> dict:
    """Invoke an MCP tool by name with keyword arguments and return result."""
    _, tools_map = await _get_shared_toolset()
    t = tools_map.get(tool_name)
    if t is None:
        raise RuntimeError(f"Tool {tool_name} not found in MCP Toolbox")
    result = await t.run_async(args=kwargs, tool_context=None)
    return result


def _check_tool_result(result: dict, tool_name: str) -> list:
    """Return list of failure strings; empty list means success."""
    failures = []
    # Timeout / MCP-level error: result is {'error': '...'}
    if isinstance(result, dict) and "error" in result and "content" not in result:
        failures.append(f"{tool_name}: {result['error']}")
        return failures
    # BigQuery-level error: result is {'content': [{'text': 'error ...'}],
    # 'isError': True}
    is_error = result.get("isError", False)
    if is_error:
        content = result.get("content", [])
        err_text = " ".join(
            p.get("text", "") for p in content if isinstance(p, dict)
        )
        failures.append(f"{tool_name} BigQuery error: {err_text[:300]}")
        return failures
    # Ensure there is actual content
    content = result.get("content", [])
    if not content:
        failures.append(f"{tool_name}: empty content in result")
    return failures


async def _run_agent_single(prompt: str) -> str:
    """Run the Sales Agent with a natural-language prompt; return final text."""
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
    """Run the Sales Agent with retry on Gemini 429 quota errors.

    The free-tier Gemini API has a low daily quota. On 429
    RESOURCE_EXHAUSTED we wait and retry a few times before giving up.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await _run_agent_single(prompt)
        except Exception as exc:
            is_quota = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if is_quota and attempt < max_retries - 1:
                wait = 40 * (attempt + 1)
                print(f"[smoke 2B] Gemini quota hit, waiting {wait}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait)
                continue
            raise


async def run_m2b_smoke_test() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        print("[smoke 2B] SKIP — GEMINI_API_KEY not set.")
        sys.exit(0)

    failures = []

    # ------------------------------------------------------------------
    # STEP 2 & 3: MCP Toolbox starts + reports all four tools.
    # ------------------------------------------------------------------
    print("[smoke 2B] STEP 2-3: Starting MCP Toolbox and listing tools...")
    try:
        tools_map = await _get_mcp_tools()
    except Exception:
        print("[smoke 2B] FAIL — MCP Toolbox failed to start.", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    found_names = set(tools_map.keys())
    missing = EXPECTED_TOOLS - found_names
    if missing:
        failures.append(f"MCP Toolbox missing tools: {missing}")
        print(f"[smoke 2B] FAIL — Missing tools: {missing}", file=sys.stderr)
    else:
        print(f"[smoke 2B] PASS — MCP Toolbox reports {len(found_names)} tools: "
              f"{sorted(found_names)}")

    # ------------------------------------------------------------------
    # STEP 4: get_daily_product_movement queries BigQuery directly.
    # ------------------------------------------------------------------
    print("[smoke 2B] STEP 4: Invoking get_daily_product_movement directly...")
    try:
        movement_result = await _invoke_tool(
            "get_daily_product_movement",
            target_date=TARGET_DATE,
        )
        f = _check_tool_result(movement_result, "get_daily_product_movement")
        if f:
            failures.extend(f)
            print(f"[smoke 2B] FAIL — {f[0]}", file=sys.stderr)
        else:
            print("[smoke 2B] PASS — get_daily_product_movement returned data.")
    except Exception as exc:
        failures.append(f"get_daily_product_movement exception: {exc}")
        print(f"[smoke 2B] FAIL — get_daily_product_movement: {exc}",
              file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # STEP 5: get_sales_trends queries BigQuery directly.
    # ------------------------------------------------------------------
    print("[smoke 2B] STEP 5: Invoking get_sales_trends directly...")
    try:
        trends_result = await _invoke_tool(
            "get_sales_trends",
            start_date=RANGE_START,
            end_date=RANGE_END,
        )
        f = _check_tool_result(trends_result, "get_sales_trends")
        if f:
            failures.extend(f)
            print(f"[smoke 2B] FAIL — {f[0]}", file=sys.stderr)
        else:
            print("[smoke 2B] PASS — get_sales_trends returned data.")
    except Exception as exc:
        failures.append(f"get_sales_trends exception: {exc}")
        print(f"[smoke 2B] FAIL — get_sales_trends: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # STEP 6: get_product_behavior_profile queries BigQuery directly.
    # ------------------------------------------------------------------
    print("[smoke 2B] STEP 6: Invoking get_product_behavior_profile directly...")
    try:
        profile_result = await _invoke_tool(
            "get_product_behavior_profile",
            start_date=RANGE_START,
            end_date=RANGE_END,
        )
        f = _check_tool_result(profile_result, "get_product_behavior_profile")
        if f:
            failures.extend(f)
            print(f"[smoke 2B] FAIL — {f[0]}", file=sys.stderr)
        else:
            print("[smoke 2B] PASS — get_product_behavior_profile returned data.")
    except Exception as exc:
        failures.append(f"get_product_behavior_profile exception: {exc}")
        print(f"[smoke 2B] FAIL — get_product_behavior_profile: {exc}",
              file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # STEP 7,8,9,10: Natural-language agent invocations for each new tool.
    # ------------------------------------------------------------------
    nl_tests = [
        (
            "STEP 8 (NL)",
            f"Show me the daily product movement for {TARGET_DATE} — "
            "which products moved compared to their 7-day baseline?",
        ),
        (
            "STEP 9 (NL)",
            f"Give me the sales trends from {RANGE_START} to {RANGE_END}.",
        ),
        (
            "STEP 10 (NL)",
            f"Show me the product behavior profile for all products from "
            f"{RANGE_START} to {RANGE_END}.",
        ),
    ]
    for label, prompt in nl_tests:
        print(f"[smoke 2B] {label}: Running Sales Agent...")
        if label != "STEP 8 (NL)":
            # Pace requests to avoid Gemini free-tier rate limits.
            print("[smoke 2B] Pausing 5s between agent calls...")
            time.sleep(5)
        try:
            final_text = await _run_agent(prompt)
        except Exception as exc:
            failures.append(f"{label} agent run failed: {exc}")
            print(f"[smoke 2B] FAIL — {label}: {exc}", file=sys.stderr)
            traceback.print_exc()
            continue

        if not final_text:
            failures.append(f"{label} empty response")
            print(f"[smoke 2B] FAIL — {label} empty response", file=sys.stderr)
            continue

        matched = _contains_failure(final_text)
        if matched:
            failures.append(f"{label} failure markers: {matched}")
            print(
                f"[smoke 2B] FAIL — {label} contains failure signal: {matched}",
                file=sys.stderr,
            )
            print(f"[smoke 2B] Preview: {final_text[:300]}…", file=sys.stderr)
        else:
            print(f"[smoke 2B] PASS — {label} synthesized a response.")
            print(f"[smoke 2B] Preview: {final_text[:200]}…")

    # ------------------------------------------------------------------
    # STEP 1 (regression): existing get_daily_sales_summary still works.
    # ------------------------------------------------------------------
    print("[smoke 2B] STEP 1 (regression): get_daily_sales_summary via agent...")
    print("[smoke 2B] Pausing 5s before regression test...")
    time.sleep(5)
    try:
        reg_text = await _run_agent("Give me today's sales summary.")
        if not reg_text:
            failures.append("regression get_daily_sales_summary empty response")
            print("[smoke 2B] FAIL — regression empty response", file=sys.stderr)
        else:
            matched = _contains_failure(reg_text)
            if matched:
                failures.append(
                    f"regression get_daily_sales_summary failure: {matched}"
                )
                print(
                    f"[smoke 2B] FAIL — regression failure signal: {matched}",
                    file=sys.stderr,
                )
            else:
                print("[smoke 2B] PASS — regression get_daily_sales_summary OK.")
    except Exception as exc:
        failures.append(f"regression get_daily_sales_summary failed: {exc}")
        print(f"[smoke 2B] FAIL — regression: {exc}", file=sys.stderr)
        traceback.print_exc()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"[smoke 2B] RESULT: FAIL — {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[smoke 2B] RESULT: PASS — All Milestone 2B checks succeeded.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_m2b_smoke_test())
