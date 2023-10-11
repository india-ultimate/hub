#!/bin/bash

python manage.py dumpdata -o server/fixtures/sample_data.json
node scripts/mask_email.js
prettier --write server/fixtures/sample_data.json
