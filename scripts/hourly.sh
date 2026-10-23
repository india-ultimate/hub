#!/bin/bash

# python manage.py import_uc_events -n 20
# python manage.py import_uc_registrations --since 2023-06-01

# Hourly, so a tournament is listed soon after its registration opens (India time).
python manage.py open_or_close_tournament_registrations
