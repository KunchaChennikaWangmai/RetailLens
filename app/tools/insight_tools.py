"""
Retail Lens — Daily Advice Engine

Builds ONE data-grounded piece of advice for the Dashboard from the same
BigQuery data the structured pages use.  Deterministic — no ADK / MCP /
Gemini — so it is fast, free and cannot hallucinate.

How rotation works:
  - The day is split into four 6-hour blocks (00-06, 06-12, 12-18, 18-24,
    server-local time).
  - The engine gathers the latest business day's facts (revenue vs recent
    average, basket size, stock alerts, top product) and scores candidate
    insights.
  - The top 4 candidates are rotated across the 4 blocks (with a per-day
    offset), so the note changes every 6 hours but stays stable within a
    block.
"""

from datetime import date, datetime, timedelta

from app.schemas.insight import AdviceCard, DailyAdviceResponse
from app.tools import inventory_tools, sales_tools

_BLOCKS_PER_DAY = 4
_HOURS_PER_BLOCK = 24 // _BLOCKS_PER_DAY  # 6-hour blocks: 00-06, 06-12, 12-18, 18-24

# In-process cache keyed by (local date, block).  The underlying demo data is
# static within a day, so caching per half-day block is safe and keeps repeat
# dashboard loads instant.  In production, entries would carry a short TTL.
_CACHE: dict[tuple[str, int], DailyAdviceResponse] = {}


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------

def _inr(value) -> str:
    """Format a number as ₹ with Indian digit grouping (e.g. ₹10,82,996)."""
    n = round(float(value))
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"₹{sign}{s}"


# ---------------------------------------------------------------------------
# Context gathering (I/O) — composes EXISTING query functions, no new SQL
# ---------------------------------------------------------------------------

def gather_context() -> dict:
    """Collect the facts the advice engine needs, via existing query tools.

    Returns a dict with keys: latest_date, today, prev, trend, profitability,
    risk — or {"latest_date": None} when there is no sales data at all.
    """
    latest = sales_tools.query_latest_sales_date()
    if latest is None:
        return {"latest_date": None}

    latest_d = date.fromisoformat(latest)
    prev_d = latest_d - timedelta(days=1)
    window_start = latest_d - timedelta(days=6)

    today_rows = sales_tools.query_daily_summary(latest)
    prev_rows = sales_tools.query_daily_summary(prev_d.isoformat())
    trend_rows = sales_tools.query_sales_trend(window_start.isoformat(), latest)
    prof_rows = inventory_tools.query_product_profitability(latest, latest)
    risk_rows = inventory_tools.query_replenishment_risk(
        (latest_d - timedelta(days=29)).isoformat(), latest
    )

    return {
        "latest_date": latest,
        "today": today_rows[0] if today_rows else None,
        "prev": prev_rows[0] if prev_rows else None,
        "trend": trend_rows,
        "profitability": prof_rows,
        "risk": risk_rows,
    }


# ---------------------------------------------------------------------------
# Rule engine (pure functions — unit-testable without BigQuery)
# ---------------------------------------------------------------------------

def build_candidates(ctx: dict) -> list[dict]:
    """Turn a context dict into scored candidate insights.

    Each candidate is a dict with keys: headline, detail, category, tone,
    score (higher = more interesting).  Pure function — no I/O.
    """
    candidates: list[dict] = []
    latest = ctx.get("latest_date")
    today = ctx.get("today")
    prev = ctx.get("prev")
    trend = ctx.get("trend") or []

    if today:
        # 1. Revenue vs the trailing 7-day average (excluding the day itself).
        prior = [r for r in trend if str(r.get("sales_date")) != latest]
        if len(prior) >= 3:
            avg7 = sum(float(r.get("revenue") or 0) for r in prior) / len(prior)
            revenue = float(today.get("total_revenue") or 0)
            if avg7 > 0:
                pct = (revenue - avg7) / avg7 * 100
                if pct >= 10:
                    candidates.append({
                        "headline": "Strong sales day",
                        "detail": (
                            f"Revenue was {pct:.0f}% above your recent daily average "
                            f"({_inr(revenue)} vs {_inr(avg7)}). Keep the momentum — "
                            f"make sure your best sellers are still in stock."
                        ),
                        "category": "sales",
                        "tone": "positive",
                        "score": min(5.0, 1.5 + pct / 20),
                    })
                elif pct <= -10:
                    candidates.append({
                        "headline": "Softer sales day",
                        "detail": (
                            f"Revenue came in {abs(pct):.0f}% below your recent daily "
                            f"average ({_inr(revenue)} vs {_inr(avg7)}). Worth checking "
                            f"whether stock-outs or slow categories played a part."
                        ),
                        "category": "sales",
                        "tone": "warning",
                        "score": min(5.0, 1.5 + abs(pct) / 20),
                    })

        # 2. Average bill value vs the previous business day.
        if prev and float(prev.get("average_bill_value") or 0) > 0:
            abv_now = float(today.get("average_bill_value") or 0)
            abv_prev = float(prev["average_bill_value"])
            pct = (abv_now - abv_prev) / abv_prev * 100
            if abs(pct) >= 10:
                up = pct > 0
                candidates.append({
                    "headline": "Bigger baskets than yesterday"
                    if up
                    else "Smaller baskets than yesterday",
                    "detail": (
                        f"Average bill value was {_inr(abv_now)} vs {_inr(abv_prev)} "
                        f"yesterday ({pct:+.0f}%)."
                        + (
                            " Nice — customers are buying more per visit."
                            if up
                            else " Customers are spending less per visit."
                        )
                    ),
                    "category": "sales",
                    "tone": "positive" if up else "neutral",
                    "score": 1.5,
                })

    # 3. Inventory urgency — products below their reorder level.
    risk = ctx.get("risk") or []
    below = [
        r
        for r in risk
        if r.get("stock_on_hand") is not None
        and r.get("reorder_level") is not None
        and r["stock_on_hand"] < r["reorder_level"]
    ]
    if below:

        def _urgency(r: dict):
            cov = r.get("stock_coverage_days")
            tier = r.get("essentiality_tier") if r.get("essentiality_tier") is not None else 9
            return (cov if cov is not None else 9999, tier)

        urgent = sorted(below, key=_urgency)[0]
        cov = urgent.get("stock_coverage_days")
        name = urgent.get("product_name") or urgent.get("product_id") or "a product"
        cover_txt = (
            f"about {cov} days of stock left"
            if cov is not None
            else "no recent sales to estimate cover"
        )
        score = 4.0 if (cov is not None and cov <= 3) or urgent.get("essentiality_tier") == 1 else 2.5
        candidates.append({
            "headline": f"{len(below)} product{'s' if len(below) != 1 else ''} below reorder level",
            "detail": (
                f"Most urgent: {name} — {cover_txt} "
                f"({urgent.get('stock_on_hand')} on hand vs reorder level "
                f"{urgent.get('reorder_level')}). Raise a purchase order soon."
            ),
            "category": "inventory",
            "tone": "warning",
            "score": score,
        })

    # 4. Top product of the day by revenue.
    prof = ctx.get("profitability") or []
    if prof:
        top = max(prof, key=lambda r: float(r.get("revenue") or 0))
        rev = float(top.get("revenue") or 0)
        if rev > 0 and top.get("product_name"):
            candidates.append({
                "headline": "Top earner of the day",
                "detail": (
                    f"{top['product_name']} led revenue with {_inr(rev)} from "
                    f"{top.get('units_sold') or 0} units sold."
                ),
                "category": "products",
                "tone": "positive",
                "score": 1.0,
            })

    # Calm fallback — always available so the box can rotate in a quiet note.
    candidates.append({
        "headline": "A steady day",
        "detail": (
            "No unusual patterns in sales. A good moment to review incoming "
            "deliveries and plan tomorrow's top-ups."
        ),
        "category": "sales",
        "tone": "neutral",
        "score": 0.75,
    })
    return candidates


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Most interesting first, capped at one candidate per 6-hour block (4)."""
    return sorted(candidates, key=lambda c: (-c["score"], c["headline"]))[:_BLOCKS_PER_DAY]


def select_candidate(ranked: list[dict], block_index: int, day_seed: int) -> dict:
    """Deterministically pick one candidate for a given block and day.

    day_seed is usually the business date's ordinal, so the rotation starts
    at a different candidate each day.
    """
    return ranked[(block_index + day_seed) % len(ranked)]


def _next_block_time(now: datetime | None = None) -> str:
    """Local time (HH:MM) at which the advice will next rotate."""
    now = now or datetime.now()
    end_hour = ((now.hour // _HOURS_PER_BLOCK) + 1) * _HOURS_PER_BLOCK % 24
    return f"{end_hour:02d}:00"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def build_daily_advice(block_index: int, context: dict | None = None) -> DailyAdviceResponse:
    """Build the advice response for a specific block.

    `context` is injectable for unit testing; by default it is gathered
    from BigQuery via the existing query tools.
    """
    ctx = context if context is not None else gather_context()
    latest = ctx.get("latest_date")

    if not latest or not ctx.get("today"):
        return DailyAdviceResponse(
            business_date=latest,
            block_index=block_index,
            next_update=_next_block_time(),
            advice=None,
            message=(
                "No sales data available yet — daily advice will appear once "
                "sales are recorded."
            ),
        )

    ranked = rank_candidates(build_candidates(ctx))
    day_seed = date.fromisoformat(latest).toordinal()
    chosen = select_candidate(ranked, block_index, day_seed)

    return DailyAdviceResponse(
        business_date=latest,
        block_index=block_index,
        next_update=_next_block_time(),
        advice=AdviceCard(
            headline=chosen["headline"],
            detail=chosen["detail"],
            category=chosen["category"],
            tone=chosen["tone"],
        ),
        message=None,
    )


def get_advice_for_now(now: datetime | None = None) -> DailyAdviceResponse:
    """Advice for the current 6-hour block, cached per (local date, block)."""
    now = now or datetime.now()
    block = now.hour // _HOURS_PER_BLOCK
    key = (now.date().isoformat(), block)
    if key not in _CACHE:
        _CACHE[key] = build_daily_advice(block)
    return _CACHE[key]


