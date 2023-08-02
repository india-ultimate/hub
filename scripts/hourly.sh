#!/bin/bash

python manage.py import_uc_events -n 20
python manage.py sync_razorpay_transactions
