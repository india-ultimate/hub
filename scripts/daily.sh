#!/bin/bash

python manage.py invalidate_memberships
python manage.py invalidate_accreditations
python manage.py gc_media_files
python manage.py open_or_close_tournament_registrations
python manage.py calculate_player_points
python manage.py cleanup_old_tasks