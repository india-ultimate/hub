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
# A worker's resident memory only grows across its life (fragmentation, the
# lazily-imported PDF stack in server/receipts/render.py that alone costs
# ~70MB the first time a receipt is downloaded, general creep). Recycling a
# worker after ~1000 requests hands that memory back instead of holding it
# for the machine's lifetime; the jitter staggers restarts so workers don't
# all recycle together. Hazard: graceful-timeout is 25s but an agent turn can
# run to the 300s timeout, so a turn in flight on a recycling worker can be
# cut short - the high request count and the jitter are what make that rare.
# Not raising graceful-timeout for this: fly.toml's kill_timeout is 30s, so
# anything past that is moot anyway.
gunicorn -w "${GUNICORN_WORKERS:-6}" -k gthread --threads "${GUNICORN_THREADS:-6}" \
  --timeout 300 --graceful-timeout 25 \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" hub.wsgi
