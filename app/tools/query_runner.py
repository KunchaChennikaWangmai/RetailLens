"""
Retail Lens — BigQuery Query Runner

Thin helper that executes a parameterised BigQuery SQL string and returns
results as a list of plain dicts.  All structured REST endpoints use this
instead of writing boilerplate client code each time.

No ADK, no MCP, no Gemini involved — pure deterministic BigQuery access.

Includes a small in-process TTL cache so repeat page visits (and multiple
users) do not re-run identical BigQuery queries on every click.  Cached
values are identical to live results within the TTL window; set
QUERY_CACHE_TTL_SECONDS=0 to disable.
"""

import os
import threading
import time
from typing import Any

from google.cloud import bigquery

from app.tools.bigquery_client import get_client

PROJECT = None  # resolved lazily from env via get_client()

_CACHE_TTL = int(os.getenv("QUERY_CACHE_TTL_SECONDS", "300"))
_CACHE_MAX_ENTRIES = max(1, int(os.getenv("QUERY_CACHE_MAX_ENTRIES", "256")))
_cache: dict[tuple[str, tuple[tuple[str, Any], ...]], tuple[float, list[dict]]] = {}
_lock = threading.Lock()  # FastAPI sync endpoints run in a threadpool

# Observability counters, surfaced via GET /api/health → "cache".
_stats = {"hits": 0, "misses": 0, "evicted_expired": 0, "evicted_capacity": 0}


def run_query(sql: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Execute *sql* against BigQuery and return rows as a list of dicts.

    Args:
        sql:    A BigQuery Standard SQL string.  Named parameters must use
                the @name syntax and be supplied in *params*.
        params: Optional mapping of parameter name → value.  Scalar values
                are automatically wrapped in the correct bigquery.ScalarQueryParameter
                type (string, int, float, date).  Pass None for no params.

    Returns:
        A list of row dicts with column names as keys.
        Returns an empty list if the query returns no rows.
    """
    cache_key = (sql, tuple(sorted((params or {}).items())))
    use_cache = _CACHE_TTL > 0

    if use_cache:
        with _lock:
            hit = _cache.get(cache_key)
            if hit is not None and (time.monotonic() - hit[0]) < _CACHE_TTL:
                _stats["hits"] += 1
                # Defensive copies: a caller mutating a returned row (in-place
                # sort, .pop(), key overwrite) must not poison the cache for
                # every other caller.
                return [dict(row) for row in hit[1]]
            _stats["misses"] += 1

    result = _execute(sql, params)

    if use_cache:
        _store(cache_key, result)

    # Always return copies — including on the fill path — so the cache keeps
    # a pristine snapshot of the query result.
    return [dict(row) for row in result]


def _execute(sql: str, params: dict[str, Any] | None) -> list[dict]:
    """Run the query against BigQuery (no caching). Returns fresh row dicts."""
    client = get_client()

    bq_params: list[bigquery.ScalarQueryParameter] = []
    for name, value in (params or {}).items():
        if isinstance(value, str):
            bq_params.append(
                bigquery.ScalarQueryParameter(name, "STRING", value)
            )
        elif isinstance(value, int):
            bq_params.append(
                bigquery.ScalarQueryParameter(name, "INT64", value)
            )
        elif isinstance(value, float):
            bq_params.append(
                bigquery.ScalarQueryParameter(name, "FLOAT64", value)
            )
        else:
            # Fallback: stringify
            bq_params.append(
                bigquery.ScalarQueryParameter(name, "STRING", str(value))
            )

    job_config = bigquery.QueryJobConfig(query_parameters=bq_params)
    query_job = client.query(sql, job_config=job_config)
    rows = query_job.result()

    return [dict(row) for row in rows]


def _store(cache_key, rows: list[dict]) -> None:
    """Insert *rows* into the cache, pruning expired/oldest entries first."""
    now = time.monotonic()
    with _lock:
        # Opportunistic prune: drop expired entries so the cache cannot grow
        # without bound over a long-running process.
        expired = [k for k, (ts, _) in _cache.items() if (now - ts) >= _CACHE_TTL]
        for k in expired:
            del _cache[k]
        if expired:
            _stats["evicted_expired"] += len(expired)
        # Hard capacity cap: evict oldest entries until there is room.
        while len(_cache) >= _CACHE_MAX_ENTRIES:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            del _cache[oldest]
            _stats["evicted_capacity"] += 1
        _cache[cache_key] = (now, rows)


def cache_stats() -> dict:
    """Snapshot of cache counters for GET /api/health."""
    with _lock:
        return {
            "enabled": _CACHE_TTL > 0,
            "ttl_seconds": _CACHE_TTL,
            "max_entries": _CACHE_MAX_ENTRIES,
            "entries": len(_cache),
            **_stats,
        }
