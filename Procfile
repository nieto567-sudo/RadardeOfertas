# Heroku/Railway Procfile – defines the process types for this application.
#
# Railway usage:
#   Service 1 (worker) – create from this repo, select process type "worker"
#   Service 2 (beat)   – create from this repo, select process type "beat"
#
# The "init-db" step is included in "worker" so the schema is always up to
# date before the worker starts consuming tasks.

worker: python main.py init-db && celery -A workers.celery_app worker --loglevel=info --concurrency=4
beat: celery -A workers.celery_app beat --loglevel=info
