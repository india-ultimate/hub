#!/bin/bash

set -euo pipefail

# Start services
sudo nginx
sudo cron

# Setup env vars for cron jobs
HERE=$(dirname "$0")
"$HERE/make_cron_env.py"

# Migrate DB
python manage.py migrate

# Ensure no security check errors
python manage.py check --deploy

# Start worker processes using tmux
echo "Starting Hub worker processes..."
tmux new-session -d -s hub-worker "python manage.py run_task_worker --sleep-seconds 30"

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
# gthread + 300s: an agent turn holds its connection for the whole turn.
# Counts come from fly.toml [env]. Recycling caps RSS growth (the PDF stack
# alone is ~70MB on first use); jitter staggers the restarts.
gunicorn -w "${GUNICORN_WORKERS:-4}" -k gthread --threads "${GUNICORN_THREADS:-6}" \
  --timeout 300 --graceful-timeout 25 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" hub.wsgi
