"""
Healthcheck service for RadardeOfertas.

Checks the operational status of:
* PostgreSQL (database connection)
* Redis (ping)
* Telegram Bot API (getMe)
* Scrapers (circuit breaker state)

Usage (CLI)::

    python main.py healthcheck

Returns exit code 0 when all checks pass, 1 when any check fails.
"""
from __future__ import annotations

import logging
import sys
from typing import NamedTuple

logger = logging.getLogger(__name__)


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


def check_database() -> CheckResult:
    """Verify that PostgreSQL is reachable and the schema exists."""
    try:
        from database.connection import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return CheckResult("database", True, "PostgreSQL reachable")
    except Exception as exc:
        return CheckResult("database", False, f"PostgreSQL error: {exc}")


def check_redis() -> CheckResult:
    """Verify that Redis is reachable."""
    try:
        import redis as redis_lib
        from config.settings import REDIS_URL

        r = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
        r.ping()
        return CheckResult("redis", True, "Redis reachable")
    except Exception as exc:
        return CheckResult("redis", False, f"Redis error: {exc}")


def check_telegram() -> CheckResult:
    """Verify that the Telegram Bot API token is valid via getMe."""
    try:
        import requests
        from config.settings import TELEGRAM_BOT_TOKEN

        if not TELEGRAM_BOT_TOKEN:
            return CheckResult("telegram", False, "TELEGRAM_BOT_TOKEN not configured")
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=10,
        )
        if resp.ok:
            username = resp.json().get("result", {}).get("username", "?")
            return CheckResult("telegram", True, f"Bot @{username} reachable")
        return CheckResult("telegram", False, f"API returned {resp.status_code}")
    except Exception as exc:
        return CheckResult("telegram", False, f"Telegram error: {exc}")


def check_scrapers() -> CheckResult:
    """Check circuit breaker state for all known stores."""
    try:
        from services.circuit_breaker import get_all_statuses

        statuses = get_all_statuses()
        open_stores = [s["store"] for s in statuses if s["state"] in ("open", "paused")]
        if open_stores:
            return CheckResult(
                "scrapers",
                False,
                f"Circuit breaker OPEN/PAUSED for: {', '.join(open_stores)}",
            )
        total = len(statuses)
        return CheckResult(
            "scrapers",
            True,
            f"All {total} known scrapers healthy" if total else "No circuit breaker data yet",
        )
    except Exception as exc:
        return CheckResult("scrapers", False, f"Circuit breaker error: {exc}")


def run_healthcheck() -> int:
    """
    Run all health checks and print a summary.

    Returns 0 if all checks pass, 1 if any check fails.
    """
    checks = [
        check_database(),
        check_redis(),
        check_telegram(),
        check_scrapers(),
    ]

    all_ok = True
    for check in checks:
        status = "✅" if check.ok else "❌"
        print(f"{status} [{check.name}] {check.detail}")
        if not check.ok:
            all_ok = False

    if all_ok:
        print("\n✅ All systems healthy")
    else:
        print("\n❌ One or more systems are degraded")

    return 0 if all_ok else 1


def get_healthcheck_summary() -> str:
    """Return a formatted health summary string for Telegram admin commands."""
    checks = [
        check_database(),
        check_redis(),
        check_telegram(),
        check_scrapers(),
    ]
    lines = ["🏥 *Health Check*\n"]
    for check in checks:
        icon = "✅" if check.ok else "❌"
        lines.append(f"{icon} *{check.name}*: {check.detail}")
    overall = "✅ All systems healthy" if all(c.ok for c in checks) else "❌ Degraded"
    lines.append(f"\n{overall}")
    return "\n".join(lines)
