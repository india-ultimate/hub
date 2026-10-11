#!/bin/bash

set -euo pipefail

# Migrations run once per release (fly.toml release_command), except where
# the database is a SQLite file in this machine (staging): the release
# machine's copy would be thrown away. Cron and the task queue run on the
# worker machine (deploy/start-worker.sh).
if [ -z "${DATABASE_URL:-}" ]; then
  python manage.py migrate
fi

# Ensure no security check errors
python manage.py check --deploy

# Only now take traffic: until Django has loaded, nginx would answer 502.
sudo nginx

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
