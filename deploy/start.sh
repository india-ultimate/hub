#!/bin/bash

# Start services
sudo nginx
sudo cron

# Migrate DB
python manage.py migrate

# Start the server using gunicorn
export PATH="$HOME/.local/bin:$PATH"
gunicorn -w 2 hub.wsgi
