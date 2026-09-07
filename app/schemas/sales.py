"""
Retail Lens — Sales API Response Schemas

Pydantic models for the structured sales REST endpoints.
Used by FastAPI for response validation and automatic OpenAPI docs.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel


class DailySummary(BaseModel):
    """Response for GET /api/home/summary — one day's store-level totals."""
    sales_date: date
    total_bills: int
    transaction_lines: int
    total_units_sold: int
    total_revenue: float
    average_bill_value: float


class DailySummaryResponse(BaseModel):
    """Envelope for /api/home/summary."""
    date_label: str          # "Today" or "Yesterday"
    summary: Optional[DailySummary] = None
    message: Optional[str] = None  # set when no data found for the date


class TrendDay(BaseModel):
    """One day's data in the sales trend series."""
    sales_date: date
    bills: int
    units_sold: int
    revenue: float


class SalesTrendResponse(BaseModel):
    """Response for GET /api/home/sales-trend."""
    start_date: date
    end_date: date
    trend: list[TrendDay]
