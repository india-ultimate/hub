#!/bin/bash

# Start services
sudo nginx
sudo cron

# Setup env vars for cron jobs
HERE=$(dirname "$0")
"$HERE/make_cron_env.py"

# Migrate DB
python manage.py migrate

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
gunicorn -w 2 hub.wsgi
