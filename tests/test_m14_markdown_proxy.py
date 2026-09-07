"""
Smoke Test - Milestone 14: Markdown Rendering & Vite Proxy Configuration

Deterministic tests (no Gemini API calls, no server startup):
  1. react-markdown is imported in Chat.tsx
  2. remark-gfm is imported in Chat.tsx
  3. ReactMarkdown component is used for AI messages
  4. Vite proxy configuration is present in vite.config.ts
  5. Proxy target is correctly set to http://localhost:8000
  6. Markdown-related CSS styles are present in styles.css
  7. Chat message markdown classes are properly styled

Usage:
    python tests/test_m14_markdown_proxy.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_deterministic_tests():
    """Verify markdown and proxy configuration without running servers."""
    failures = []

    # Check 1: react-markdown imported
    print("[M14] CHECK 1: react-markdown imported in Chat.tsx...")
    chat_src = Path("frontend/src/Chat.tsx").read_text()
    if 'import ReactMarkdown from "react-markdown"' not in chat_src:
        failures.append("react-markdown not imported")
        print("[M14] FAIL - react-markdown not imported", file=sys.stderr)
    else:
        print("[M14] PASS - react-markdown imported")

    # Check 2: remark-gfm imported
    print("[M14] CHECK 2: remark-gfm imported in Chat.tsx...")
    if 'import remarkGfm from "remark-gfm"' not in chat_src:
        failures.append("remark-gfm not imported")
        print("[M14] FAIL - remark-gfm not imported", file=sys.stderr)
    else:
        print("[M14] PASS - remark-gfm imported")

    # Check 3: ReactMarkdown component used
    print("[M14] CHECK 3: ReactMarkdown used for AI messages...")
    if "<ReactMarkdown remarkPlugins={[remarkGfm]}>" not in chat_src:
        failures.append("ReactMarkdown component not used")
        print("[M14] FAIL - ReactMarkdown not used", file=sys.stderr)
    else:
        print("[M14] PASS - ReactMarkdown component used")

    # Check 4: Vite proxy config exists
    print("[M14] CHECK 4: Vite proxy configuration present...")
    vite_src = Path("frontend/vite.config.ts").read_text()
    if 'proxy: {' not in vite_src or '"/api": {' not in vite_src:
        failures.append("Vite proxy not configured")
        print("[M14] FAIL - Vite proxy not configured", file=sys.stderr)
    else:
        print("[M14] PASS - Vite proxy configured")

    # Check 5: Proxy target is correct
    print("[M14] CHECK 5: Proxy target set to localhost:8000...")
    if 'target: "http://localhost:8000"' not in vite_src:
        failures.append("Proxy target incorrect")
        print("[M14] FAIL - Proxy target incorrect", file=sys.stderr)
    else:
        print("[M14] PASS - Proxy target correct")

    # Check 6: changeOrigin is set
    print("[M14] CHECK 6: changeOrigin flag set...")
    if 'changeOrigin: true' not in vite_src:
        failures.append("changeOrigin not set")
        print("[M14] FAIL - changeOrigin not set", file=sys.stderr)
    else:
        print("[M14] PASS - changeOrigin set")

    # Check 7: Markdown CSS for chat messages
    print("[M14] CHECK 7: Markdown CSS styles in styles.css...")
    styles_src = Path("frontend/src/styles.css").read_text()
    required_css_selectors = [
        ".chat-msg h1",
        ".chat-msg table",
        ".chat-msg code",
        ".chat-msg pre",
        ".chat-msg ul,\n.chat-msg ol",
    ]
    for selector in required_css_selectors:
        if selector not in styles_src:
            failures.append(f"CSS selector '{selector}' not found")
            print(f"[M14] FAIL - CSS '{selector}' missing", file=sys.stderr)
    if not any("CSS selector" in f for f in failures):
        print("[M14] PASS - All markdown CSS styles present")

    # Check 8: Table styling
    print("[M14] CHECK 8: Table styling in chat messages...")
    if ".chat-msg table th" not in styles_src or ".chat-msg table td" not in styles_src:
        failures.append("Table styling incomplete")
        print("[M14] FAIL - Table styling incomplete", file=sys.stderr)
    else:
        print("[M14] PASS - Table styling complete")

    # Check 9: Code/pre block styling
    print("[M14] CHECK 9: Code block styling...")
    if ".chat-msg pre" not in styles_src or ".chat-msg pre code" not in styles_src:
        failures.append("Code block styling incomplete")
        print("[M14] FAIL - Code block styling incomplete", file=sys.stderr)
    else:
        print("[M14] PASS - Code block styling complete")

    # Check 10: AI vs user message handling
    print("[M14] CHECK 10: AI messages use ReactMarkdown, user messages don't...")
    if 'msg.role === "user" ? (' not in chat_src:
        failures.append("Message role check not implemented")
        print("[M14] FAIL - Message role check missing", file=sys.stderr)
    else:
        print("[M14] PASS - Message role check implemented")

    return failures


def main():
    print("=== MILESTONE 14 DETERMINISTIC TESTS ===\n")
    failures = run_deterministic_tests()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[M14] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("[M14] RESULT: PASS - All Milestone 14 checks succeeded.")
        print("\nMarkdown rendering is now enabled in Chat.tsx.")
        print("Vite proxy is configured: /api → http://localhost:8000")
        print("To test in development:")
        print("  1. cd frontend")
        print("  2. npm run dev")
        print("  3. In another terminal: uvicorn app.api:app --host 127.0.0.1 --port 8000")
        print("  4. Navigate to http://localhost:5173")
        print("  5. Click 'AI Chat' and send a question")
        print("  6. Verify markdown renders correctly (bold, tables, lists, code blocks)")
        sys.exit(0)


if __name__ == "__main__":
    main()
