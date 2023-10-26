#!/bin/bash

python manage.py import_uc_events -n 20
python manage.py import_uc_registrations --since 2023-06-01
python manage.py reconcile_phonepe_transactions
