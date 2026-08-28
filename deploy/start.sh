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
# Threaded workers: an agent turn holds its connection open for the whole turn, and
# with 2 sync workers a single stream would eat half the server. The default 30s
# timeout also kills turns long before the model is done, so raise it past the
# provider's own 120s ceiling.
# Counts come from fly.toml [env], set by scripts/apply-profile.py.
gunicorn -w "${GUNICORN_WORKERS:-6}" -k gthread --threads "${GUNICORN_THREADS:-6}" \
  --timeout 300 --graceful-timeout 25 hub.wsgi
