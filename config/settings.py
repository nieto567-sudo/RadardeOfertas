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

# ── Redis / Celery ───────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

# ── Affiliate tags ────────────────────────────────────────────────────────────
AMAZON_AFFILIATE_TAG: str = os.getenv("AMAZON_AFFILIATE_TAG", "")
MERCADOLIBRE_AFFILIATE_ID: str = os.getenv("MERCADOLIBRE_AFFILIATE_ID", "")
ALIEXPRESS_AFFILIATE_KEY: str = os.getenv("ALIEXPRESS_AFFILIATE_KEY", "")
EBAY_CAMPAIGN_ID: str = os.getenv("EBAY_CAMPAIGN_ID", "")

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
