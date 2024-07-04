#!/bin/bash

python manage.py invalidate_memberships
python manage.py invalidate_accreditations
python manage.py gc_media_files
python manage.py open_or_close_tournament_registrations