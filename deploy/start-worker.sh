#!/bin/bash

set -euo pipefail

# The worker machine: cron and the task queue, and nothing that serves requests.
HERE=$(dirname "$0")
"$HERE/make_cron_env.py"
sudo cron

# Foreground, so a crash restarts the machine.
exec python manage.py run_task_worker --sleep-seconds 30
