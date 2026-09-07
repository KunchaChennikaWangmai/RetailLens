"""
Retail Lens — Customer Query Functions

Direct BigQuery query functions used by the structured REST endpoints.
SQL mirrors the tools.yaml get_customer_behavior_profile definition exactly.

These functions do NOT go through ADK / MCP / Gemini.
"""

from app.tools.query_runner import run_query

_SQL_CUSTOMER_BEHAVIOR = """
WITH customer_sales AS (
  SELECT
    c.customer_id,
    ANY_VALUE(c.customer_name) AS customer_name,
    c.bill_number,
    c.bill_date,
    SUM(s.quantity) AS units,
    SUM(s.total_price) AS spend
  FROM `retail_lens_patchamomma.customer_bills` c
  INNER JOIN `retail_lens_patchamomma.sales_transactions` s
    ON s.bill_number = c.bill_number
  WHERE c.bill_date BETWEEN DATE(@start_date) AND DATE(@end_date)
  GROUP BY c.customer_id, c.bill_number, c.bill_date
),
customer_agg AS (
  SELECT
    customer_id,
    ANY_VALUE(customer_name) AS customer_name,
    COUNT(DISTINCT bill_number) AS bill_count,
    ROUND(SUM(spend), 2) AS total_spend,
    ROUND(SAFE_DIVIDE(SUM(spend), COUNT(DISTINCT bill_number)), 2) AS average_bill_value,
    SUM(units) AS total_units,
    MIN(bill_date) AS first_purchase_date,
    MAX(bill_date) AS last_purchase_date,
    COUNT(DISTINCT bill_date) AS active_purchase_days
  FROM customer_sales
  GROUP BY customer_id
)
SELECT
  customer_id,
  customer_name,
  bill_count,
  total_spend,
  average_bill_value,
  total_units,
  first_purchase_date,
  last_purchase_date,
  active_purchase_days,
  ROUND(SAFE_DIVIDE(active_purchase_days, DATE_DIFF(DATE(@end_date), DATE(@start_date), DAY) + 1) * 100, 2) AS purchase_frequency_pct
FROM customer_agg
ORDER BY total_spend DESC
"""

_SQL_LATEST_BILL_DATE = """
SELECT MAX(bill_date) AS latest_date
FROM `retail_lens_patchamomma.customer_bills`
"""


def query_customer_behavior(start_date: str, end_date: str) -> list[dict]:
    """Return per-customer behavior profile over a date range.

    Each row: customer_id, customer_name, bill_count, total_spend,
              average_bill_value, total_units, first_purchase_date,
              last_purchase_date, active_purchase_days, purchase_frequency_pct

    Ordered by total_spend descending (highest-value customers first).
    Only includes customers whose bills join to sales_transactions.
    """
    return run_query(_SQL_CUSTOMER_BEHAVIOR, {"start_date": start_date, "end_date": end_date})


def query_latest_bill_date() -> str | None:
    """Return the most recent bill date (YYYY-MM-DD), or None if no data."""
    rows = run_query(_SQL_LATEST_BILL_DATE)
    if not rows or rows[0].get("latest_date") is None:
        return None
    latest = rows[0]["latest_date"]
    return latest.isoformat() if hasattr(latest, "isoformat") else str(latest)
