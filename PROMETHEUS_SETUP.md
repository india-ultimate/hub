# Prometheus Metrics Setup

This application has been configured to export Prometheus metrics for monitoring.

## Configuration

### Fly.io Configuration

The application exposes Prometheus metrics on port `9090`. The Fly.io configuration has been updated to:

1. **Correct internal port**: Changed from `80` to `8000` to match the Django application port
2. **Added metrics port**: Exposed port `9090` for Prometheus scraping
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
https://your-app.fly.dev:9090/metrics/
```

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

After deploying to Fly.io, you can access metrics at:

```
https://upai-hub.fly.dev:9090/metrics/
https://upai-hub-staging.fly.dev:9090/metrics/
```

## Monitoring Setup

To set up monitoring with Fly.io:

1. **Create a monitoring app** (if not already done):
   ```bash
   fly apps create your-monitoring-app
   ```

2. **Deploy Prometheus** to your Fly.io account
3. **Configure scraping** to target your app's metrics endpoint
4. **Set up Grafana** for visualization

## Troubleshooting

### Common Issues

1. **Port not accessible**: Ensure the metrics port (9090) is properly exposed in `fly.toml`
2. **Internal port mismatch**: Verify `internal_port` matches your application's listening port
3. **Metrics not appearing**: Check that `django_prometheus` is properly installed and configured

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

3. **Verify Fly.io configuration**:
   ```bash
   fly status
   ```