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

# Application health metrics
database_connections_gauge = Gauge(
    'hub_database_connections',
    'Number of active database connections',
    namespace='hub'
)

cache_hit_ratio_gauge = Gauge(
    'hub_cache_hit_ratio',
    'Cache hit ratio percentage',
    namespace='hub'
)

# Business metrics
total_teams_gauge = Gauge(
    'hub_total_teams',
    'Total number of teams in the system',
    namespace='hub'
)

total_players_gauge = Gauge(
    'hub_total_players',
    'Total number of players in the system',
    namespace='hub'
)

active_tournaments_gauge = Gauge(
    'hub_active_tournaments',
    'Number of active tournaments',
    namespace='hub'
)

# Database metrics (these are automatically collected by django-prometheus)
# ModelHistogram, ModelCounter, ModelGauge are used for database operations