"""
Retail Lens — Inventory Query Functions

Direct BigQuery query functions used by the structured REST endpoints.
SQL mirrors the tools.yaml definitions exactly.

These functions do NOT go through ADK / MCP / Gemini.
"""

from app.tools.query_runner import run_query

# ---------------------------------------------------------------------------
# SQL constants — ported verbatim from tools.yaml
# ---------------------------------------------------------------------------

_SQL_STOCK_LEVELS = """
SELECT
  st.product_id,
  i.prod_name AS product_name,
  i.category,
  st.stock_on_hand,
  st.reorder_level,
  st.last_updated
FROM `retail_lens_patchamomma.inventory_stock` st
LEFT JOIN `retail_lens_patchamomma.inventory_metadata` i
  ON i.prod_id = st.product_id
ORDER BY i.category, i.prod_name
"""

_SQL_SUPPLY_STATUS = """
SELECT
  sup.product_id,
  i.prod_name AS product_name,
  i.category,
  sup.supplier_id,
  sup.supplier_lead_time_days,
  sup.incoming_quantity,
  sup.expected_delivery_date,
  sup.last_updated
FROM `retail_lens_patchamomma.inventory_supply` sup
LEFT JOIN `retail_lens_patchamomma.inventory_metadata` i
  ON i.prod_id = sup.product_id
ORDER BY i.category, i.prod_name
"""

_SQL_REPLENISHMENT_RISK = """
WITH demand AS (
  SELECT
    s.product_id,
    SUM(s.quantity) AS units_sold_in_period
  FROM `retail_lens_patchamomma.sales_transactions` s
  WHERE DATE(s.time_stamp) BETWEEN DATE(@start_date) AND DATE(@end_date)
  GROUP BY s.product_id
),
period_days AS (
  SELECT DATE_DIFF(DATE(@end_date), DATE(@start_date), DAY) + 1 AS days
)
SELECT
  i.prod_id AS product_id,
  i.prod_name AS product_name,
  i.category,
  i.essentiality_tier,
  i.perishability_class,
  i.shelf_life_days,
  st.stock_on_hand,
  st.reorder_level,
  sup.incoming_quantity,
  sup.expected_delivery_date,
  sup.supplier_id,
  sup.supplier_lead_time_days,
  COALESCE(d.units_sold_in_period, 0) AS units_sold_in_period,
  ROUND(SAFE_DIVIDE(COALESCE(d.units_sold_in_period, 0), (SELECT days FROM period_days)), 2) AS average_daily_demand,
  CASE
    WHEN COALESCE(d.units_sold_in_period, 0) > 0 AND st.stock_on_hand IS NOT NULL
    THEN ROUND(st.stock_on_hand / SAFE_DIVIDE(d.units_sold_in_period, (SELECT days FROM period_days)), 1)
    ELSE NULL
  END AS stock_coverage_days,
  CASE
    WHEN sup.expected_delivery_date IS NOT NULL
    THEN DATE_DIFF(sup.expected_delivery_date, DATE(@end_date), DAY)
    ELSE NULL
  END AS days_until_expected_delivery
FROM `retail_lens_patchamomma.inventory_metadata` i
LEFT JOIN `retail_lens_patchamomma.inventory_stock` st ON st.product_id = i.prod_id
LEFT JOIN `retail_lens_patchamomma.inventory_supply` sup ON sup.product_id = i.prod_id
LEFT JOIN demand d ON d.product_id = i.prod_id
ORDER BY
  CASE WHEN st.stock_on_hand < st.reorder_level THEN 0 ELSE 1 END,
  i.essentiality_tier DESC,
  average_daily_demand DESC
"""

_SQL_PROFITABILITY = """
SELECT
  s.product_id,
  ANY_VALUE(s.product_name) AS product_name,
  ANY_VALUE(i.category) AS category,
  SUM(s.quantity) AS units_sold,
  ROUND(SUM(s.total_price), 2) AS revenue,
  ROUND(SUM(s.quantity * i.cost), 2) AS cost_of_goods_sold,
  ROUND(SUM(s.total_price) - SUM(s.quantity * i.cost), 2) AS gross_profit,
  ROUND(
    SAFE_DIVIDE(
      SUM(s.total_price) - SUM(s.quantity * i.cost),
      SUM(s.total_price)
    ) * 100, 2
  ) AS gross_margin_pct
FROM `retail_lens_patchamomma.sales_transactions` s
JOIN `retail_lens_patchamomma.inventory_metadata` i
  ON i.prod_id = s.product_id
WHERE DATE(s.time_stamp) BETWEEN DATE(@start_date) AND DATE(@end_date)
GROUP BY s.product_id
ORDER BY gross_profit DESC
"""


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_stock_levels() -> list[dict]:
    """Return current stock levels for all products.

    Each row: product_id, product_name, category, stock_on_hand,
              reorder_level, last_updated
    """
    return run_query(_SQL_STOCK_LEVELS)


def query_supply_status() -> list[dict]:
    """Return current supply/incoming orders for all products.

    Each row: product_id, product_name, category, supplier_id,
              supplier_lead_time_days, incoming_quantity,
              expected_delivery_date, last_updated
    """
    return run_query(_SQL_SUPPLY_STATUS)


def query_replenishment_risk(start_date: str, end_date: str) -> list[dict]:
    """Return replenishment risk evidence for all products.

    Combines stock levels, supply data, and recent demand to compute
    stock_coverage_days and days_until_expected_delivery.

    Each row: product_id, product_name, category, essentiality_tier,
              perishability_class, shelf_life_days, stock_on_hand,
              reorder_level, incoming_quantity, expected_delivery_date,
              supplier_id, supplier_lead_time_days, units_sold_in_period,
              average_daily_demand, stock_coverage_days,
              days_until_expected_delivery
    """
    return run_query(_SQL_REPLENISHMENT_RISK, {"start_date": start_date, "end_date": end_date})


def query_product_profitability(start_date: str, end_date: str) -> list[dict]:
    """Return gross profit and margin for each product over a date range.

    Each row: product_id, product_name, category, units_sold, revenue,
              cost_of_goods_sold, gross_profit, gross_margin_pct

    NOTE: gross profit only — operating expenses are not in the data.
    """
    return run_query(_SQL_PROFITABILITY, {"start_date": start_date, "end_date": end_date})
