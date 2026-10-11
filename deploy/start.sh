#!/bin/bash

set -euo pipefail

sudo nginx

# Migrations run once per release (fly.toml release_command); cron and the
# task queue run on the worker machine (deploy/start-worker.sh).

# Ensure no security check errors
python manage.py check --deploy

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
# gthread + 300s: an agent turn holds its connection for the whole turn.
# Counts come from fly.toml [env]. Recycling caps RSS growth (the PDF stack
# alone is ~70MB on first use); jitter staggers the restarts.
# Accepted: a turn in flight on a recycling worker can be cut short, and
# graceful-timeout can't usefully exceed fly's 30s kill_timeout anyway.
exec gunicorn -w "${GUNICORN_WORKERS:-4}" -k gthread --threads "${GUNICORN_THREADS:-6}" \
  --timeout 300 --graceful-timeout 25 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" hub.wsgi
