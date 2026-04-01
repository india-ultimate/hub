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
gunicorn -w 4 hub.wsgi
