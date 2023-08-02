#!/bin/bash

sudo nginx
sudo cron
export PATH="$HOME/.local/bin:$PATH"
python manage.py migrate
gunicorn -w 2 hub.wsgi
