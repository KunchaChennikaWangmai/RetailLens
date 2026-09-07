"""
Retail Lens — Customer API Response Schemas
"""

from typing import Optional
from pydantic import BaseModel


class CustomerRecord(BaseModel):
    customer_id: str
    customer_name: str
    bill_count: int
    total_spend: float
    average_bill_value: float
    total_units: int
    first_purchase_date: Optional[str] = None
    last_purchase_date: Optional[str] = None
    active_purchase_days: int
    purchase_frequency_pct: Optional[float] = None


class CustomerBehaviorResponse(BaseModel):
    """Response for GET /api/customers/behavior."""
    start_date: str
    end_date: str
    total_customers: int
    repeat_customers: int      # bill_count > 1
    total_bills: int
    average_bill_value: float
    customers: list[CustomerRecord]
