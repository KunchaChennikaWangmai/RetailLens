"""
Query-cache regression tests (query_runner hardening).

Covers, without touching BigQuery (run_query's execution backend is
monkeypatched):
  1. Cache HIT: identical SQL+params execute the backend once.
  2. Param sensitivity: different params are distinct cache entries.
  3. TTL expiry: entries older than the TTL are re-fetched.
  4. Disable flag: QUERY_CACHE_TTL_SECONDS=0 bypasses the cache entirely.
  5. Copy-on-hit: mutating a returned list/row cannot poison the cache.
  6. Expired-entry pruning: inserting an entry purges expired ones.
  7. Capacity cap: the cache never exceeds QUERY_CACHE_MAX_ENTRIES.
  8. cache_stats() exposes counters for /api/health.
  9. LIVE: /api/health reports the cache section (when credentials exist).

Usage:
    python tests/test_cache.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.tools import query_runner as qr  # noqa: E402

SAVED: dict = {}


def _setup():
    """Snapshot module globals and reset counters for an isolated test."""
    SAVED.update(
        ttl=qr._CACHE_TTL,
        max_entries=qr._CACHE_MAX_ENTRIES,
        execute=qr._execute,
        cache_items=dict(qr._cache),
        stats=dict(qr._stats),
    )
    qr._cache.clear()
    for k in list(qr._stats):
        qr._stats[k] = 0


def _teardown():
    qr._CACHE_TTL = SAVED["ttl"]
    qr._CACHE_MAX_ENTRIES = SAVED["max_entries"]
    qr._execute = SAVED["execute"]
    qr._cache.clear()
    qr._cache.update(SAVED["cache_items"])
    qr._stats.clear()
    qr._stats.update(SAVED["stats"])


class FakeExec:
    """Stands in for _execute, counting calls and returning fresh rows."""

    def __init__(self, rows=None):
        self.calls = 0
        self.rows = rows if rows is not None else [{"n": 1}]

    def __call__(self, sql, params=None):
        self.calls += 1
        return [dict(r) for r in self.rows]


SQL = "SELECT 1 AS n -- cache-test"


def test_hit():
    qr._CACHE_TTL = 300
    fake = FakeExec()
    qr._execute = fake
    a = qr.run_query(SQL, {"d": "2026-08-31"})
    b = qr.run_query(SQL, {"d": "2026-08-31"})
    assert fake.calls == 1, f"expected 1 backend call, got {fake.calls}"
    assert a == b == [{"n": 1}]
    assert qr._stats["hits"] == 1 and qr._stats["misses"] == 1


def test_param_sensitivity():
    qr._CACHE_TTL = 300
    fake = FakeExec()
    qr._execute = fake
    qr.run_query(SQL, {"d": "2026-08-30"})
    qr.run_query(SQL, {"d": "2026-08-31"})
    qr.run_query(SQL, {"d": "2026-08-30"})  # hit — same params as call 1
    assert fake.calls == 2, f"expected 2 backend calls, got {fake.calls}"
    assert qr._stats["hits"] == 1


def test_expiry():
    qr._CACHE_TTL = 1  # seconds; keeps the test fast
    fake = FakeExec()
    qr._execute = fake
    qr.run_query(SQL)
    qr.run_query(SQL)
    assert fake.calls == 1
    time.sleep(1.05)
    qr.run_query(SQL)
    assert fake.calls == 2, "expired entry was served instead of re-fetched"


def test_disabled():
    qr._CACHE_TTL = 0
    fake = FakeExec()
    qr._execute = fake
    before = dict(qr._stats)
    qr.run_query(SQL)
    qr.run_query(SQL)
    assert fake.calls == 2, "disabled cache must always execute"
    assert dict(qr._stats) == before, "stats must not move while disabled"
    assert len(qr._cache) == 0, "disabled cache must not store entries"


def test_copy_on_hit():
    qr._CACHE_TTL = 300
    fake = FakeExec(rows=[{"n": 1, "name": "x"}])
    qr._execute = fake
    a = qr.run_query(SQL)
    a[0]["name"] = "MUTATED"
    a.append({"n": 2})
    b = qr.run_query(SQL)
    assert b == [{"n": 1, "name": "x"}], f"cache was poisoned: {b}"
    assert fake.calls == 1


def test_prune_expired():
    # TTL stays constant here (as in production, where it is read once from
    # env at startup): an expired entry must be purged when the next insert
    # happens.
    qr._CACHE_TTL = 1
    fake = FakeExec()
    qr._execute = fake
    qr.run_query(SQL)  # entry A — expires after 1s
    time.sleep(1.05)
    qr.run_query(SQL + " -- fresh")  # entry B; insert purges expired A
    assert qr._stats["evicted_expired"] >= 1, "expired entries not pruned"
    assert len(qr._cache) == 1, f"expected 1 entry after prune, got {len(qr._cache)}"


def test_capacity_cap():
    qr._CACHE_TTL = 300
    qr._CACHE_MAX_ENTRIES = 2
    fake = FakeExec()
    qr._execute = fake
    for i in range(4):
        qr.run_query(f"{SQL} -- {i}")
    assert len(qr._cache) <= 2, f"cache grew to {len(qr._cache)} entries"
    assert qr._stats["evicted_capacity"] >= 1, "capacity eviction not recorded"


def test_stats_shape():
    qr._CACHE_TTL = 300
    fake = FakeExec()
    qr._execute = fake
    qr.run_query(SQL)
    s = qr.cache_stats()
    for key in ("enabled", "ttl_seconds", "max_entries", "entries",
                "hits", "misses", "evicted_expired", "evicted_capacity"):
        assert key in s, f"cache_stats missing key {key}"
    assert s["enabled"] is True and s["entries"] == 1


def live_checks() -> list[str]:
    failures: list[str] = []
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        print("[CACHE] LIVE: SKIP - GOOGLE_CLOUD_PROJECT not set")
        return failures
    from fastapi.testclient import TestClient

    from app.api import app

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/api/home/summary")
    client.get("/api/home/summary")  # second call should hit the cache
    h = client.get("/api/health").json()
    cache = h.get("cache")
    if not isinstance(cache, dict) or "hits" not in cache:
        failures.append(f"/api/health missing cache section: {h}")
    elif cache["hits"] < 1 or cache["entries"] < 1:
        failures.append(f"cache stats look wrong after two identical calls: {cache}")
    else:
        print(f"[CACHE] PASS - /api/health reports {cache}")
    return failures


def main():
    tests = [
        test_hit,
        test_param_sensitivity,
        test_expiry,
        test_disabled,
        test_copy_on_hit,
        test_prune_expired,
        test_capacity_cap,
        test_stats_shape,
    ]
    print("=== QUERY CACHE TESTS (no BigQuery needed) ===\n")
    failures: list[str] = []
    for fn in tests:
        _setup()
        try:
            fn()
            print(f"[CACHE] PASS - {fn.__name__}")
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
            print(f"[CACHE] FAIL - {fn.__name__}: {exc}", file=sys.stderr)
        finally:
            _teardown()

    print("\n=== QUERY CACHE LIVE VALIDATION ===\n")
    failures += live_checks()

    print(f"\n{'=' * 60}")
    if failures:
        print(f"[CACHE] RESULT: FAIL - {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("[CACHE] RESULT: PASS - query cache hardening verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()

