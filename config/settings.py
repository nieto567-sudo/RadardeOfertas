"""
Application settings loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ── Database ────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://radar:radar@localhost:5432/radardeofertas",
)
# Railway (and some other PaaS platforms) inject DATABASE_URL with the legacy
# "postgres://" scheme.  SQLAlchemy 1.4+ requires "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# ── Redis / Celery ───────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

# Comma-separated list of Telegram user IDs that can run admin commands.
# Example: TELEGRAM_ADMIN_USER_IDS=123456789,987654321
_admin_ids_raw = os.getenv("TELEGRAM_ADMIN_USER_IDS", "")
TELEGRAM_ADMIN_USER_IDS: list[int] = []
for _entry in _admin_ids_raw.split(","):
    _entry = _entry.strip()
    if not _entry:
        continue
    if _entry.isdigit():
        TELEGRAM_ADMIN_USER_IDS.append(int(_entry))
    else:
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "TELEGRAM_ADMIN_USER_IDS: invalid entry %r ignored (must be a numeric user ID)",
            _entry,
        )

# ── Monetisation feature flag ─────────────────────────────────────────────────
# Set to "true" to enable affiliate links, UTM parameters and Bitly shortening.
# When "false" (default) the bot publishes only the plain canonical product URL
# with no affiliate tags, no UTM tracking and no URL shortening.
MONETIZED_LINKS_ENABLED: bool = (
    os.getenv("MONETIZED_LINKS_ENABLED", "false").lower() == "true"
)

# ── Offer detection thresholds ────────────────────────────────────────────────
# Percentage of average price below which an offer is classified.
PRICE_ERROR_THRESHOLD: float = float(os.getenv("PRICE_ERROR_THRESHOLD", "0.40"))
OFFER_EXCELLENT_THRESHOLD: float = float(os.getenv("OFFER_EXCELLENT_THRESHOLD", "0.60"))
OFFER_GOOD_THRESHOLD: float = float(os.getenv("OFFER_GOOD_THRESHOLD", "0.80"))

# Rapid price-drop: minimum percentage drop within the look-back window.
RAPID_DROP_THRESHOLD: float = float(os.getenv("RAPID_DROP_THRESHOLD", "0.30"))
# Hours to look back when checking for rapid drops.
RAPID_DROP_WINDOW_HOURS: int = int(os.getenv("RAPID_DROP_WINDOW_HOURS", "2"))

# Minimum score (0–100) required before an offer is published to Telegram.
MIN_PUBLISH_SCORE: int = int(os.getenv("MIN_PUBLISH_SCORE", "60"))

# ── Scraping ──────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "1.5"))
USER_AGENT: str = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
)

# ── Worker schedules (seconds between runs) ───────────────────────────────────
SCHEDULE_AMAZON_SECONDS: int = int(os.getenv("SCHEDULE_AMAZON_SECONDS", "300"))
SCHEDULE_MERCADOLIBRE_SECONDS: int = int(
    os.getenv("SCHEDULE_MERCADOLIBRE_SECONDS", "300")
)
SCHEDULE_WALMART_SECONDS: int = int(os.getenv("SCHEDULE_WALMART_SECONDS", "600"))
SCHEDULE_LIVERPOOL_SECONDS: int = int(os.getenv("SCHEDULE_LIVERPOOL_SECONDS", "600"))
SCHEDULE_BODEGAAURRERA_SECONDS: int = int(
    os.getenv("SCHEDULE_BODEGAAURRERA_SECONDS", "600")
)
SCHEDULE_DEFAULT_SECONDS: int = int(os.getenv("SCHEDULE_DEFAULT_SECONDS", "900"))

# ── Anti-spam cooldown ────────────────────────────────────────────────────────
# Hours that must pass before the same product can be published again.
PUBLICATION_COOLDOWN_HOURS: int = int(os.getenv("PUBLICATION_COOLDOWN_HOURS", "6"))

# ── Scraper health monitoring ─────────────────────────────────────────────────
# Number of consecutive failures before an admin alert is sent.
SCRAPER_FAILURE_ALERT_THRESHOLD: int = int(
    os.getenv("SCRAPER_FAILURE_ALERT_THRESHOLD", "3")
)
# Telegram chat_id (user or group) that receives admin/health alerts.
TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

# ── Price-error admin pre-notification ────────────────────────────────────────
# When true, send a private DM to TELEGRAM_ADMIN_CHAT_ID with the full offer
# details *before* the offer is published to the channel.  This gives the admin
# a heads-up for every "price error" (errores de precio) deal.
# Set to "false" to disable and publish directly without a prior notification.
PRICE_ERROR_NOTIFY_ADMIN: bool = (
    os.getenv("PRICE_ERROR_NOTIFY_ADMIN", "true").lower() == "true"
)

# ── Cross-store price comparison ──────────────────────────────────────────────
# Minimum number of shared significant words to consider two product names the same.
PRICE_COMPARISON_MIN_WORDS: int = int(os.getenv("PRICE_COMPARISON_MIN_WORDS", "3"))

# ── Price chart ───────────────────────────────────────────────────────────────
# Minimum number of price observations before generating a chart.
CHART_MIN_DATA_POINTS: int = int(os.getenv("CHART_MIN_DATA_POINTS", "5"))

# ── Daily digest ─────────────────────────────────────────────────────────────
# Hour (UTC) at which the daily deal digest is published to the channel.
DIGEST_HOUR_UTC: int = int(os.getenv("DIGEST_HOUR_UTC", "16"))  # 16 UTC = 10 AM Mexico City
DIGEST_MINUTE_UTC: int = int(os.getenv("DIGEST_MINUTE_UTC", "0"))
# Number of top offers included in the daily digest.
DIGEST_TOP_N: int = int(os.getenv("DIGEST_TOP_N", "10"))

# ── Price trend ───────────────────────────────────────────────────────────────
# Minimum observations needed to calculate a price trend.
TREND_MIN_POINTS: int = int(os.getenv("TREND_MIN_POINTS", "5"))

# ── Publication cap ───────────────────────────────────────────────────────────
# Maximum number of individual offers published to the channel per 24-hour day.
# Range: 10–20 (as specified).
MAX_DAILY_PUBLICATIONS: int = int(os.getenv("MAX_DAILY_PUBLICATIONS", "15"))

# Maximum minutes after detection before an un-published offer expires.
# Offers that are still PENDING after this window are discarded.
PUBLICATION_WINDOW_MINUTES: int = int(os.getenv("PUBLICATION_WINDOW_MINUTES", "30"))

# ── Quality filter ────────────────────────────────────────────────────────────
# Minimum discount percentage for an offer to pass the quality filter.
MIN_DISCOUNT_PCT: float = float(os.getenv("MIN_DISCOUNT_PCT", "20.0"))
# Minimum absolute saving in MXN (filters cheap products with tiny savings).
MIN_ABSOLUTE_SAVING_MXN: float = float(os.getenv("MIN_ABSOLUTE_SAVING_MXN", "100.0"))

# ── Smart publishing hours (Mexico City time, UTC-6) ─────────────────────────
# Only publish during peak engagement windows.  Set to false to publish 24/7.
SMART_HOURS_ENABLED: bool = os.getenv("SMART_HOURS_ENABLED", "true").lower() == "true"
SMART_HOURS_MORNING_START: int = int(os.getenv("SMART_HOURS_MORNING_START", "7"))
SMART_HOURS_MORNING_END: int = int(os.getenv("SMART_HOURS_MORNING_END", "10"))
SMART_HOURS_AFTERNOON_START: int = int(os.getenv("SMART_HOURS_AFTERNOON_START", "12"))
SMART_HOURS_AFTERNOON_END: int = int(os.getenv("SMART_HOURS_AFTERNOON_END", "15"))
SMART_HOURS_EVENING_START: int = int(os.getenv("SMART_HOURS_EVENING_START", "19"))
SMART_HOURS_EVENING_END: int = int(os.getenv("SMART_HOURS_EVENING_END", "23"))

# ── Weekly summary ────────────────────────────────────────────────────────────
# Day of the week (0=Mon … 6=Sun) and UTC hour to publish the weekly summary.
WEEKLY_SUMMARY_DOW: int = int(os.getenv("WEEKLY_SUMMARY_DOW", "6"))  # Sunday
WEEKLY_SUMMARY_HOUR_UTC: int = int(os.getenv("WEEKLY_SUMMARY_HOUR_UTC", "15"))  # 9 AM MX
WEEKLY_SUMMARY_MINUTE_UTC: int = int(os.getenv("WEEKLY_SUMMARY_MINUTE_UTC", "0"))

# ── Observability ─────────────────────────────────────────────────────────────
# Log format: "text" (human-readable) or "json" (structured for log aggregators)
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
# Port for the Prometheus HTTP metrics server
PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))

# ── Circuit breaker ────────────────────────────────────────────────────────────
# Number of consecutive scraper failures before the circuit opens.
CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(
    os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
)
# Seconds to wait (circuit open) before allowing the next probe attempt.
CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = int(
    os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "300")
)

# ── Deduplication ─────────────────────────────────────────────────────────────
# Set to "true" to deduplicate the same product across different stores.
DEDUP_CROSS_STORE: bool = os.getenv("DEDUP_CROSS_STORE", "false").lower() == "true"
# Set to "true" to reject products without an image_url.
REQUIRE_IMAGE: bool = os.getenv("REQUIRE_IMAGE", "false").lower() == "true"
# Minimum product title length (shorter titles are rejected as garbage).
MIN_TITLE_LENGTH: int = int(os.getenv("MIN_TITLE_LENGTH", "10"))

# ── Publication guard ─────────────────────────────────────────────────────────
# Whitelist of allowed categories (comma-separated).  Offers whose category
# does not appear in this list are silently discarded before publishing.
# Default matches the five categories defined in the product classifier.
_ALLOWED_CATEGORIES_RAW: str = os.getenv(
    "ALLOWED_CATEGORIES",
    "Celulares y Smartphones,Gaming y Videojuegos,Televisores y Audio,"
    "Electrodomésticos,Ropa y Accesorios",
)
ALLOWED_CATEGORIES: list[str] = [
    c.strip() for c in _ALLOWED_CATEGORIES_RAW.split(",") if c.strip()
]

# Maximum publications per rolling 60-minute window.
MAX_PUBLICATIONS_PER_HOUR: int = int(os.getenv("MAX_PUBLICATIONS_PER_HOUR", "15"))

# Minimum seconds that must pass between any two consecutive publications.
MIN_SECONDS_BETWEEN_PUBLICATIONS: int = int(
    os.getenv("MIN_SECONDS_BETWEEN_PUBLICATIONS", "5")
)

# Dry-run mode: when "true" no message is actually sent to Telegram.
# All other logic (validation, dedup tracking) runs normally.
DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"

# Path for the JSON file that persists recently published URLs for 24h dedup.
# Defaults to /tmp so it works on ephemeral filesystems (Railway, Heroku, etc.).
# Override with a path inside a persistent volume when available.
PUBLISHED_URLS_FILE: str = os.getenv("PUBLISHED_URLS_FILE", "/tmp/published_urls.json")
