# Heroku/Railway Procfile – defines the process types for this application.
#
# ── Railway (recommended) ─────────────────────────────────────────────────────
#   Railway reads `railway.toml` startCommand directly, so this Procfile is NOT
#   used by Railway unless you explicitly configure a process type in the
#   service settings.  The recommended setup is a single service running the
#   built-in polling loop (no Redis / Celery required):
#
#     railway.toml startCommand:
#       sh -lc 'set -e; python -u main.py init-db; python -u main.py run-loop --interval 300'
#
# ── Single-service polling loop (no Celery / no Redis) ───────────────────────
worker: sh -lc 'set -e; python -u main.py init-db; python -u main.py run-loop --interval 300'

# ── Legacy Celery mode (requires Redis) ──────────────────────────────────────
# Uncomment the lines below and comment out the worker line above if you want
# to run Celery-based scraping with per-store scheduling.  You will also need
# a Redis service and the REDIS_URL / CELERY_BROKER_URL env vars.
#
# worker: python main.py init-db && celery -A workers.celery_app worker --loglevel=info --concurrency=4
# beat: celery -A workers.celery_app beat --loglevel=info
