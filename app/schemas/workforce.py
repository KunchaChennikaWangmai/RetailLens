"""
Retail Lens — Workforce API Response Schemas
"""

from typing import Optional
from pydantic import BaseModel


class EmployeeRecord(BaseModel):
    employee_name: str
    shifts_worked: int
    scheduled_hours: float
    actual_hours: Optional[float] = None
    total_wages_inr: float
    average_hours_per_shift: float
    check_in_count: int
    late_check_in_count: int
    early_departure_count: int
    overtime_shift_count: int


class WorkforceResponse(BaseModel):
    """Response for GET /api/employees/summary."""
    start_date: str
    end_date: str
    total_labour_cost: float
    total_shifts: int
    employees: list[EmployeeRecord]
