"""
Retail Lens — Sales Query Functions

Direct BigQuery query functions used by the structured REST endpoints.
SQL mirrors the tools.yaml definitions exactly — no business classification
is encoded here; that is left to the AI agents.

These functions do NOT go through ADK / MCP / Gemini.
"""

from app.tools.query_runner import run_query

# ---------------------------------------------------------------------------
# SQL constants — ported verbatim from tools.yaml
# ---------------------------------------------------------------------------

_SQL_DAILY_SUMMARY = """
SELECT
  DATE(time_stamp) AS sales_date,
  COUNT(DISTINCT bill_number) AS total_bills,
  COUNT(transaction_id) AS transaction_lines,
  SUM(quantity) AS total_units_sold,
  SUM(total_price) AS total_revenue,
  SUM(total_price) / COUNT(DISTINCT bill_number) AS average_bill_value
FROM `retail_lens_patchamomma.sales_transactions`
WHERE DATE(time_stamp) = DATE(@target_date)
GROUP BY 1
LIMIT 1
"""

_SQL_SALES_TREND = """
SELECT
  DATE(time_stamp) AS sales_date,
  COUNT(DISTINCT bill_number) AS bills,
  SUM(quantity) AS units_sold,
  SUM(total_price) AS revenue
FROM `retail_lens_patchamomma.sales_transactions`
WHERE DATE(time_stamp) BETWEEN DATE(@start_date) AND DATE(@end_date)
GROUP BY 1
ORDER BY 1 ASC
"""

_SQL_LATEST_SALES_DATE = """
SELECT MAX(DATE(time_stamp)) AS latest_date
FROM `retail_lens_patchamomma.sales_transactions`
"""


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_daily_summary(target_date: str) -> list[dict]:
    """Return sales summary for a single date (YYYY-MM-DD).

    Returns a list with 0 or 1 row dict containing:
      sales_date, total_bills, transaction_lines, total_units_sold,
      total_revenue, average_bill_value
    """
    return run_query(_SQL_DAILY_SUMMARY, {"target_date": target_date})


def query_sales_trend(start_date: str, end_date: str) -> list[dict]:
    """Return daily sales aggregates over a date range (inclusive).

    Each row: sales_date, bills, units_sold, revenue
    Ordered by date ascending — ready for Recharts LineChart.
    """
    return run_query(_SQL_SALES_TREND, {"start_date": start_date, "end_date": end_date})


def query_latest_sales_date() -> str | None:
    """Return the most recent date (YYYY-MM-DD) that has sales data.

    Used to anchor date windows to real data instead of the wall clock,
    since the demo dataset may lag behind the current date.
    Returns None when the table is empty.
    """
    rows = run_query(_SQL_LATEST_SALES_DATE)
    if not rows or rows[0].get("latest_date") is None:
        return None
    latest = rows[0]["latest_date"]
    return latest.isoformat() if hasattr(latest, "isoformat") else str(latest)
