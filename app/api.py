"""
Retail Lens — Minimal HTTP API

Exposes the ADK root_agent as a simple REST API compatible with Web UIs.

Also exposes deterministic structured REST endpoints (Milestone 15) that
serve real BigQuery data to the dashboard pages.  These go straight to
BigQuery — no ADK, no MCP, no Gemini.
"""

import asyncio
import sys
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any, Optional

import os
import time
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.agents.orchestrator import root_agent
from app.tools import (
    customer_tools,
    insight_tools,
    inventory_tools,
    sales_tools,
    workforce_tools,
)
from app.tools.query_runner import cache_stats
from app.schemas.customer import CustomerBehaviorResponse, CustomerRecord
from app.schemas.inventory import (
    ProfitabilityItem,
    ProfitabilityResponse,
    ReplenishmentRiskResponse,
    RiskItem,
    StockItem,
    StockResponse,
    SupplyItem,
    SupplyResponse,
)
from app.schemas.sales import DailySummary, DailySummaryResponse, SalesTrendResponse, TrendDay
from app.schemas.insight import DailyAdviceResponse
from app.schemas.workforce import EmployeeRecord, WorkforceResponse

app = FastAPI(title="Retail Lens API", version="0.1.0")

# Hard cap on a single chat request so a stuck Gemini/ADK call cannot hang
# the browser forever.  Override with CHAT_TIMEOUT_SECONDS in the environment.
CHAT_TIMEOUT_SECONDS = int(os.getenv("CHAT_TIMEOUT_SECONDS", "120"))

# Substrings in Gemini/ADK error text that indicate the model is busy,
# overloaded or quota-exhausted — surfaced to users as HTTP 503.
_GEMINI_BUSY_MARKERS = ("503", "UNAVAILABLE", "overloaded", "RESOURCE_EXHAUSTED", "quota")

# Local CORS setup for Vite frontend port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level singleton: reuse session service and runner across requests
# to avoid per-request object construction overhead.
_session_service = InMemorySessionService()
_runner = None

def _get_runner():
    """Lazy-initialize the Runner singleton."""
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=root_agent,
            app_name="retail_lens_local",
            session_service=_session_service,
        )
    return _runner

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str


@app.get("/api/health")
def health():
    """Liveness probe: process is up and basic configuration is present."""
    return {
        "status": "ok",
        "app": "Retail Lens API",
        "project_configured": bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
        "chat_timeout_seconds": CHAT_TIMEOUT_SECONDS,
        "cache": cache_stats(),
        "time": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Structured REST endpoints (Milestone 15)
#
# Frontend → FastAPI → query layer → BigQuery.  No AI involved.
# Date windows are anchored to the latest date that actually has data so
# the demo dataset (which lags the wall clock) still renders honestly.
# ---------------------------------------------------------------------------

def _clean_row(row: Any) -> dict:
    """Convert BigQuery DATE/TIMESTAMP/TIME values to ISO strings."""
    return {
        k: (v.isoformat() if isinstance(v, (date, datetime, dt_time)) else v)
        for k, v in dict(row).items()
    }


def _window(end_iso: str, days: int) -> tuple[str, str]:
    """Return (start_iso, end_iso) covering *days* inclusive days ending at end_iso."""
    end = date.fromisoformat(end_iso)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end_iso


@app.get("/api/home/summary", response_model=DailySummaryResponse)
def home_summary(date: Optional[date] = None):
    """Store-level sales totals for one day.

    No `date` param → the most recent day that has sales data (labelled
    "Today" from the shopkeeper's point of view).  With `date=YYYY-MM-DD`
    → that exact day, with an honest message when it has no data.
    """
    try:
        if date is not None:
            label = date.isoformat()
            rows = sales_tools.query_daily_summary(label)
            if not rows:
                return DailySummaryResponse(
                    date_label=label,
                    summary=None,
                    message=f"No sales recorded for {label}.",
                )
            return DailySummaryResponse(date_label=label, summary=DailySummary(**_clean_row(rows[0])))

        latest = sales_tools.query_latest_sales_date()
        if latest is None:
            return DailySummaryResponse(
                date_label="Today", summary=None, message="No sales data available yet."
            )
        rows = sales_tools.query_daily_summary(latest)
        if not rows:
            return DailySummaryResponse(
                date_label="Today",
                summary=None,
                message=f"No sales recorded for {latest}.",
            )
        return DailySummaryResponse(date_label="Today", summary=DailySummary(**_clean_row(rows[0])))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/home/sales-trend", response_model=SalesTrendResponse)
def home_sales_trend(days: int = Query(30, ge=1, le=365)):
    """Daily revenue/bills/units over the last *days* of available data."""
    try:
        end = sales_tools.query_latest_sales_date()
        if end is None:
            today = date.today()
            return SalesTrendResponse(start_date=today, end_date=today, trend=[])
        start, end = _window(end, days)
        rows = sales_tools.query_sales_trend(start, end)
        return SalesTrendResponse(
            start_date=start,
            end_date=end,
            trend=[TrendDay(**_clean_row(r)) for r in rows],
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/home/advice", response_model=DailyAdviceResponse)
def home_advice():
    """One data-grounded advice note for the Dashboard.

    Deterministic (no AI): scores the most interesting findings for the
    latest business day and rotates through the top ones every 6 hours.
    """
    try:
        return insight_tools.get_advice_for_now()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Insight generation failed: {exc}") from exc


@app.get("/api/inventory/replenishment-risk", response_model=ReplenishmentRiskResponse)
def inventory_replenishment_risk(days: int = Query(30, ge=1, le=365)):
    """Replenishment evidence: stock, incoming supply and recent demand."""
    try:
        end = sales_tools.query_latest_sales_date()
        if end is None:
            today = date.today()
            return ReplenishmentRiskResponse(start_date=today, end_date=today, products=[], below_reorder_count=0)
        start, end = _window(end, days)
        rows = inventory_tools.query_replenishment_risk(start, end)
        products = [RiskItem(**_clean_row(r)) for r in rows]
        below_reorder_count = sum(
            1
            for p in products
            if p.stock_on_hand is not None
            and p.reorder_level is not None
            and p.stock_on_hand < p.reorder_level
        )
        return ReplenishmentRiskResponse(
            start_date=start, end_date=end, products=products, below_reorder_count=below_reorder_count
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/inventory/stock", response_model=StockResponse)
def inventory_stock():
    """Current stock on hand for every tracked product."""
    try:
        rows = inventory_tools.query_stock_levels()
        products = [StockItem(**_clean_row(r)) for r in rows]
        below_reorder_count = sum(
            1 for p in products if p.stock_on_hand < p.reorder_level
        )
        return StockResponse(
            products=products, total_products=len(products), below_reorder_count=below_reorder_count
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/inventory/supply", response_model=SupplyResponse)
def inventory_supply():
    """Incoming supply orders and expected deliveries."""
    try:
        rows = inventory_tools.query_supply_status()
        return SupplyResponse(products=[SupplyItem(**_clean_row(r)) for r in rows])
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/employees/summary", response_model=WorkforceResponse)
def employees_summary(days: int = Query(30, ge=1, le=365)):
    """Per-employee attendance and wage summary over the last *days* of shifts."""
    try:
        end = workforce_tools.query_latest_shift_date()
        if end is None:
            today = date.today()
            return WorkforceResponse(
                start_date=today.isoformat(), end_date=today.isoformat(),
                total_labour_cost=0.0, total_shifts=0, employees=[],
            )
        start, end = _window(end, days)
        rows = workforce_tools.query_workforce_summary(start, end)
        employees = [EmployeeRecord(**_clean_row(r)) for r in rows]
        return WorkforceResponse(
            start_date=start,
            end_date=end,
            total_labour_cost=round(sum(e.total_wages_inr for e in employees), 2),
            total_shifts=sum(e.shifts_worked for e in employees),
            employees=employees,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/customers/behavior", response_model=CustomerBehaviorResponse)
def customers_behavior(days: int = Query(30, ge=1, le=365)):
    """Customer spending and visit behaviour over the last *days* of bills."""
    try:
        end = customer_tools.query_latest_bill_date()
        if end is None:
            today = date.today()
            return CustomerBehaviorResponse(
                start_date=today.isoformat(), end_date=today.isoformat(),
                total_customers=0, repeat_customers=0, total_bills=0,
                average_bill_value=0.0, customers=[],
            )
        start, end = _window(end, days)
        rows = customer_tools.query_customer_behavior(start, end)
        customers = [CustomerRecord(**_clean_row(r)) for r in rows]
        total_bills = sum(c.bill_count for c in customers)
        total_spend = sum(c.total_spend for c in customers)
        return CustomerBehaviorResponse(
            start_date=start,
            end_date=end,
            total_customers=len(customers),
            repeat_customers=sum(1 for c in customers if c.bill_count > 1),
            total_bills=total_bills,
            average_bill_value=round(total_spend / total_bills, 2) if total_bills else 0.0,
            customers=customers,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc


@app.get("/api/profitability/products", response_model=ProfitabilityResponse)
def profitability_products(days: int = Query(30, ge=1, le=365)):
    """Gross profit (revenue minus COGS) by product over the last *days* of sales.

    Gross profit only — operating expenses are not part of this dataset.
    """
    try:
        end = sales_tools.query_latest_sales_date()
        if end is None:
            today = date.today()
            return ProfitabilityResponse(
                start_date=today, end_date=today, total_revenue=0.0,
                total_cogs=0.0, gross_profit=0.0, gross_margin_pct=0.0, products=[],
            )
        start, end = _window(end, days)
        rows = inventory_tools.query_product_profitability(start, end)
        products = [ProfitabilityItem(**_clean_row(r)) for r in rows]
        total_revenue = round(sum(p.revenue for p in products), 2)
        total_cogs = round(sum(p.cost_of_goods_sold for p in products), 2)
        gross_profit = round(total_revenue - total_cogs, 2)
        gross_margin_pct = round(gross_profit / total_revenue * 100, 2) if total_revenue else 0.0
        return ProfitabilityResponse(
            start_date=start,
            end_date=end,
            total_revenue=total_revenue,
            total_cogs=total_cogs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            products=products,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery query failed: {exc}") from exc

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    perf_start = time.perf_counter()
    print(f"[PERF] API start")
    
    user_id = "local_web_user"
    app_name = "retail_lens_local"
    
    perf_session_start = time.perf_counter()
    session = await _session_service.create_session(
        app_name=app_name,
        user_id=user_id,
    )
    perf_session_end = time.perf_counter()
    print(f"[PERF] Session created: {perf_session_end - perf_session_start:.3f}s")
    
    runner = _get_runner()
    
    msg_content = Content(role="user", parts=[Part(text=request.message)])
    
    perf_adk_start = time.perf_counter()
    print(f"[PERF] ADK invocation start")
    
    final_text = ""

    async def _collect_response() -> str:
        text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=msg_content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    text = event.content.parts[0].text or ""
        return text

    try:
        final_text = await asyncio.wait_for(
            _collect_response(), timeout=CHAT_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=(
                "The AI agent took too long to respond "
                f"(over {CHAT_TIMEOUT_SECONDS}s). Please try again."
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        if any(marker in err_text for marker in _GEMINI_BUSY_MARKERS):
            raise HTTPException(
                status_code=503,
                detail=(
                    "The AI service (Gemini) is temporarily busy or unavailable. "
                    "Please try again in a moment."
                ),
            ) from exc
        print(f"[CHAT ERROR] {type(exc).__name__}: {err_text}", file=sys.stderr)
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI agent could not complete your request. "
                "Please try again, or rephrase your question."
            ),
        ) from exc

    perf_adk_end = time.perf_counter()
    print(f"[PERF] ADK completed: {perf_adk_end - perf_adk_start:.3f}s")
    
    perf_end = time.perf_counter()
    total_time = perf_end - perf_start
    print(f"[PERF] API response: {total_time:.3f}s total")
    
    return {"response": final_text}
