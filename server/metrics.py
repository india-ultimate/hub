"""
Custom Prometheus metrics for the India Ultimate Hub application.
"""
from prometheus_client import Counter, Gauge, Histogram
from django_prometheus.metrics import ModelHistogram, ModelCounter, ModelGauge

# Custom application metrics
user_registration_counter = Counter(
    'hub_user_registrations_total',
    'Total number of user registrations',
    namespace='hub'
)

active_users_gauge = Gauge(
    'hub_active_users',
    'Number of active users',
    namespace='hub'
)

tournament_registration_counter = Counter(
    'hub_tournament_registrations_total',
    'Total number of tournament registrations',
    namespace='hub'
)

payment_transaction_counter = Counter(
    'hub_payment_transactions_total',
    'Total number of payment transactions',
    ['status', 'payment_method'],
    namespace='hub'
)

api_request_duration = Histogram(
    'hub_api_request_duration_seconds',
    'API request duration in seconds',
    ['endpoint', 'method'],
    namespace='hub'
)

# Database metrics (these are automatically collected by django-prometheus)
# ModelHistogram, ModelCounter, ModelGauge are used for database operations