#!/bin/bash

python manage.py invalidate_memberships
python manage.py invalidate_accreditations
python manage.py gc_media_files
