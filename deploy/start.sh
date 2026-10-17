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

# A bad config fails the boot here, which restarts the machine; found only
# after gunicorn is up, it would leave the machine stopped instead.
sudo nginx -t

# Take traffic only once gunicorn answers: until then nginx would answer 502,
# and Fly's check (answered by nginx) would already pass. If nginx still
# won't start, stop gunicorn ($$, after the exec below).
(
  until curl -sf -o /dev/null --max-time 30 -H "X-Forwarded-Proto: https" \
    http://127.0.0.1:8000/api/health; do
    sleep 0.5
  done
  sudo nginx || kill -TERM $$
) &

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
# Each worker writes its metrics here, and deploy/metrics.py adds them up for
# Fly's scraper. Emptied first: a previous boot's counts would be added in.
export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}"
rm -rf "${PROMETHEUS_MULTIPROC_DIR:?}"/*
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
python deploy/metrics.py &
# gthread + 300s: an agent turn holds its connection for the whole turn.
# Counts come from fly.toml [env]. Recycling caps RSS growth (the PDF stack
# alone is ~70MB on first use); jitter staggers the restarts.
# Accepted: a turn in flight on a recycling worker can be cut short, and
# graceful-timeout can't usefully exceed fly's 30s kill_timeout anyway.
exec gunicorn -c deploy/gunicorn.conf.py -w "${GUNICORN_WORKERS:-4}" -k gthread --threads "${GUNICORN_THREADS:-6}" \
  --timeout 300 --graceful-timeout 25 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" hub.wsgi
