# Fly.io Monitoring Setup

This application has been configured to export metrics for Fly.io's built-in monitoring system.

## Configuration

### Fly.io Configuration

The application is configured to work with Fly.io's managed monitoring:

1. **Correct internal port**: Set to `8000` to match the Django application port
2. **Metrics configuration**: Added `[metrics]` section to tell Fly.io where to find metrics
3. **Proper port binding**: Updated the start script to bind to `0.0.0.0:8000`

### Django Configuration

The application uses `django-prometheus` for automatic metric collection:

- **Database metrics**: Automatically collected for all models using `ExportModelOperationsMixin`
- **HTTP metrics**: Request counts and durations
- **Custom metrics**: Application-specific metrics defined in `server/metrics.py`

## Metrics Endpoints

### Local Development
```
http://localhost:8000/metrics/
```

### Production (Fly.io)
```
https://your-app.fly.dev/metrics/
```

**Note**: Fly.io automatically scrapes metrics from the main HTTP port, not a separate metrics port.

## Available Metrics

### Automatic Metrics (django-prometheus)
- `django_http_requests_total`: Total HTTP requests
- `django_http_requests_latency_seconds`: Request latency
- `django_model_inserts_total`: Database insert operations
- `django_model_updates_total`: Database update operations
- `django_model_deletes_total`: Database delete operations

### Custom Metrics
- `hub_user_registrations_total`: User registration count
- `hub_active_users`: Active users gauge
- `hub_tournament_registrations_total`: Tournament registration count
- `hub_payment_transactions_total`: Payment transaction count (by status and method)
- `hub_api_request_duration_seconds`: API request duration histogram

## Testing

Run the test script to verify the metrics endpoint:

```bash
python scripts/test_metrics.py
```

## Fly.io Deployment

After deploying to Fly.io, your metrics will automatically appear in Fly.io's managed Grafana dashboard.

### Accessing Metrics

1. **Fly.io Dashboard**: Go to your app in the Fly.io dashboard
2. **Metrics Tab**: Click on the "Metrics" tab to see your custom metrics
3. **Grafana**: Access the full Grafana dashboard from the Fly.io dashboard

### Available in Fly.io Dashboard

Your custom metrics will appear in Fly.io's managed Grafana with these names:
- `hub_user_registrations_total`
- `hub_active_users`
- `hub_tournament_registrations_total`
- `hub_payment_transactions_total`
- `hub_api_request_duration_seconds`
- `hub_total_teams`
- `hub_total_players`
- `hub_active_tournaments`
- `hub_database_connections`

## Automatic Metrics Updates

The application automatically updates business metrics every 5 minutes via a cron job:
- Team count
- Player count
- Active tournaments
- Database connections

## Troubleshooting

### Common Issues

1. **Metrics not appearing in Fly.io dashboard**: Ensure the `[metrics]` section is properly configured in `fly.toml`
2. **Internal port mismatch**: Verify `internal_port` matches your application's listening port
3. **Metrics not updating**: Check that the cron job is running and the management command works

### Debugging

1. **Check application logs**:
   ```bash
   fly logs
   ```

2. **Test metrics endpoint locally**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   curl http://localhost:8000/metrics/
   ```

3. **Test metrics update command**:
   ```bash
   python manage.py update_metrics
   ```

4. **Verify Fly.io configuration**:
   ```bash
   fly status
   ```

5. **Check Fly.io dashboard**: Go to your app's metrics tab in the Fly.io dashboard