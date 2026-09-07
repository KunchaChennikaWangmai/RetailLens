"""
Retail Lens — Workforce Query Functions

Direct BigQuery query functions used by the structured REST endpoints.
SQL mirrors the tools.yaml get_workforce_summary definition exactly.

These functions do NOT go through ADK / MCP / Gemini.
"""

from app.tools.query_runner import run_query

_SQL_WORKFORCE_SUMMARY = """
WITH shift_parsed AS (
  SELECT
    shift_id,
    shift_date,
    employee_name,
    hours_worked,
    hourly_wage_inr,
    shift_timing,
    check_in_timestamp,
    check_out_timestamp,
    CASE
      WHEN shift_timing LIKE 'Morning%' THEN TIME(9, 0, 0)
      WHEN shift_timing LIKE 'Evening%' THEN TIME(17, 0, 0)
      ELSE TIME(9, 0, 0)
    END AS scheduled_start_time,
    CASE
      WHEN shift_timing LIKE 'Morning%' THEN TIME(17, 0, 0)
      WHEN shift_timing LIKE 'Evening%' THEN TIME(22, 0, 0)
      ELSE TIME(17, 0, 0)
    END AS scheduled_end_time,
    CASE
      WHEN check_in_timestamp IS NOT NULL AND check_out_timestamp IS NOT NULL
      THEN ROUND(DATETIME_DIFF(check_out_timestamp, check_in_timestamp, MINUTE) / 60.0, 2)
      ELSE NULL
    END AS actual_hours,
    CASE
      WHEN shift_timing LIKE 'Morning%' THEN 8.0
      WHEN shift_timing LIKE 'Evening%' THEN 5.0
      ELSE CAST(hours_worked AS FLOAT64)
    END AS scheduled_duration_hours
  FROM `retail_lens_patchamomma.workforce_shifts`
  WHERE shift_date BETWEEN DATE(@start_date) AND DATE(@end_date)
),
shift_with_flags AS (
  SELECT
    *,
    CASE
      WHEN check_in_timestamp IS NOT NULL
        AND TIME(check_in_timestamp) > TIME_ADD(scheduled_start_time, INTERVAL 5 MINUTE)
      THEN 1 ELSE 0
    END AS is_late,
    CASE
      WHEN check_out_timestamp IS NOT NULL
        AND TIME(check_out_timestamp) < TIME_SUB(scheduled_end_time, INTERVAL 5 MINUTE)
      THEN 1 ELSE 0
    END AS is_early_departure,
    CASE
      WHEN actual_hours IS NOT NULL
        AND actual_hours > scheduled_duration_hours + 0.25
      THEN 1 ELSE 0
    END AS is_overtime
  FROM shift_parsed
)
SELECT
  employee_name,
  COUNT(*) AS shifts_worked,
  SUM(hours_worked) AS scheduled_hours,
  ROUND(SUM(actual_hours), 2) AS actual_hours,
  ROUND(SUM(hours_worked * hourly_wage_inr), 2) AS total_wages_inr,
  ROUND(SAFE_DIVIDE(SUM(hours_worked), COUNT(*)), 2) AS average_hours_per_shift,
  COUNTIF(check_in_timestamp IS NOT NULL) AS check_in_count,
  SUM(is_late) AS late_check_in_count,
  SUM(is_early_departure) AS early_departure_count,
  SUM(is_overtime) AS overtime_shift_count
FROM shift_with_flags
GROUP BY employee_name
ORDER BY total_wages_inr DESC
"""

_SQL_LATEST_SHIFT_DATE = """
SELECT MAX(shift_date) AS latest_date
FROM `retail_lens_patchamomma.workforce_shifts`
"""


def query_workforce_summary(start_date: str, end_date: str) -> list[dict]:
    """Return per-employee workforce summary over a date range.

    Each row: employee_name, shifts_worked, scheduled_hours, actual_hours,
              total_wages_inr, average_hours_per_shift, check_in_count,
              late_check_in_count, early_departure_count, overtime_shift_count
    """
    return run_query(_SQL_WORKFORCE_SUMMARY, {"start_date": start_date, "end_date": end_date})


def query_latest_shift_date() -> str | None:
    """Return the most recent shift date (YYYY-MM-DD), or None if no data."""
    rows = run_query(_SQL_LATEST_SHIFT_DATE)
    if not rows or rows[0].get("latest_date") is None:
        return None
    latest = rows[0]["latest_date"]
    return latest.isoformat() if hasattr(latest, "isoformat") else str(latest)
