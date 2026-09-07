"""
Retail Lens — Inventory API Response Schemas

Pydantic models for the structured inventory and profitability REST endpoints.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Stock levels
# ---------------------------------------------------------------------------

class StockItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    category: Optional[str] = None
    stock_on_hand: int
    reorder_level: int
    last_updated: Optional[str] = None   # serialised as ISO string


class StockResponse(BaseModel):
    """Response for GET /api/inventory/stock."""
    products: list[StockItem]
    total_products: int
    below_reorder_count: int


# ---------------------------------------------------------------------------
# Supply status
# ---------------------------------------------------------------------------

class SupplyItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    category: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_lead_time_days: Optional[int] = None
    incoming_quantity: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    last_updated: Optional[str] = None


class SupplyResponse(BaseModel):
    """Response for GET /api/inventory/supply."""
    products: list[SupplyItem]


# ---------------------------------------------------------------------------
# Replenishment risk
# ---------------------------------------------------------------------------

class RiskItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    category: Optional[str] = None
    essentiality_tier: Optional[int] = None
    perishability_class: Optional[str] = None
    shelf_life_days: Optional[int] = None
    stock_on_hand: Optional[int] = None
    reorder_level: Optional[int] = None
    incoming_quantity: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    supplier_id: Optional[str] = None
    supplier_lead_time_days: Optional[int] = None
    units_sold_in_period: int
    average_daily_demand: Optional[float] = None
    stock_coverage_days: Optional[float] = None
    days_until_expected_delivery: Optional[int] = None


class ReplenishmentRiskResponse(BaseModel):
    """Response for GET /api/inventory/replenishment-risk."""
    start_date: date
    end_date: date
    products: list[RiskItem]
    below_reorder_count: int


# ---------------------------------------------------------------------------
# Profitability
# ---------------------------------------------------------------------------

class ProfitabilityItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    category: Optional[str] = None
    units_sold: int
    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin_pct: Optional[float] = None


class ProfitabilityResponse(BaseModel):
    """Response for GET /api/profitability/products."""
    start_date: date
    end_date: date
    total_revenue: float
    total_cogs: float
    gross_profit: float
    gross_margin_pct: float
    products: list[ProfitabilityItem]
