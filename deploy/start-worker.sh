#!/bin/bash

set -euo pipefail

# The worker machine: cron and the task queue, and nothing that serves requests.
HERE=$(dirname "$0")
"$HERE/make_cron_env.py"
sudo cron

# The public page cache, shared by every app machine; Fly's private network only
# (the worker has no [[services]]). Optional: if it can't start, the queue still runs.
if PASS=$(python -c "from django.conf import settings; from hub.redis_auth import password; print(password(settings.SECRET_KEY))"); then
  redis-server --daemonize yes --bind "* -::*" --port 6379 --requirepass "$PASS" \
    --maxmemory 64mb --maxmemory-policy allkeys-lru --save "" --appendonly no \
    || echo "redis-server failed to start; running without the shared cache" >&2
else
  echo "could not derive the Redis password; running without the shared cache" >&2
fi

# Foreground, so a crash restarts the machine.
exec python manage.py run_task_worker --sleep-seconds 30
