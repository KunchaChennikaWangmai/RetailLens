"""
Retail Lens — Daily Advice API Response Schemas

Pydantic models for GET /api/home/advice — the Dashboard "Advice of the
Day" note. Generated deterministically by app/tools/insight_tools.py
(no ADK / MCP / Gemini involved).
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel


class AdviceCard(BaseModel):
    """One advice note shown on the Dashboard."""

    headline: str
    detail: str
    category: str  # "sales" | "inventory" | "products"
    tone: str  # "positive" | "neutral" | "warning"


class DailyAdviceResponse(BaseModel):
    """Envelope for GET /api/home/advice."""

    business_date: Optional[date] = None  # latest business day with data
    block_index: int  # 0-3 — which 6-hour block of the day this advice belongs to
    next_update: str  # "HH:MM" local time when the advice will rotate
    advice: Optional[AdviceCard] = None
    message: Optional[str] = None  # honest note when there is no data
