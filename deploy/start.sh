#!/bin/bash

set -euo pipefail

# Start services
sudo nginx
sudo cron

# Setup env vars for cron jobs
HERE=$(dirname "$0")
"$HERE/make_cron_env.py"

# Install and setup worker systemd service
echo "Installing Hub worker systemd service..."
sudo cp "$HERE/hub-worker.service" /etc/systemd/system/
sudo mkdir -p /etc/hub

# Setup env vars for worker service
echo "Setting up worker environment..."
"$HERE/make_worker_env.py"

# Migrate DB
python manage.py migrate

# Ensure no security check errors
python manage.py check --deploy

# Start the worker service
echo "Starting Hub worker service..."
sudo systemctl daemon-reload
sudo systemctl enable hub-worker
sudo systemctl start hub-worker

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
gunicorn -w 4 hub.wsgi
