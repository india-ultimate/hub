#!/usr/bin/env python3
"""
Script to test Fly.io metrics endpoint.
"""
import requests
import sys
import os


def test_fly_metrics(base_url="http://localhost:8000"):
    """Test the metrics endpoint for Fly.io monitoring."""
    try:
        response = requests.get(f"{base_url}/metrics/")
        if response.status_code == 200:
            print("✅ Metrics endpoint is working!")
            print(f"Response length: {len(response.text)} characters")
            
            # Check for custom metrics
            content = response.text
            custom_metrics = [
                'hub_user_registrations_total',
                'hub_active_users',
                'hub_tournament_registrations_total',
                'hub_payment_transactions_total',
                'hub_api_request_duration_seconds',
                'hub_total_teams',
                'hub_total_players',
                'hub_active_tournaments',
                'hub_database_connections'
            ]
            
            found_metrics = []
            for metric in custom_metrics:
                if metric in content:
                    found_metrics.append(metric)
                    print(f"✅ Found metric: {metric}")
                else:
                    print(f"⚠️  Missing metric: {metric}")
            
            print(f"\nFound {len(found_metrics)} out of {len(custom_metrics)} custom metrics")
            
            # Check for django-prometheus metrics
            django_metrics = [
                'django_http_requests_total',
                'django_http_requests_latency_seconds',
                'django_model_inserts_total'
            ]
            
            django_found = []
            for metric in django_metrics:
                if metric in content:
                    django_found.append(metric)
                    print(f"✅ Found Django metric: {metric}")
            
            print(f"Found {len(django_found)} out of {len(django_metrics)} Django metrics")
            
            return True
        else:
            print(f"❌ Metrics endpoint returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error accessing metrics endpoint: {e}")
        return False


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    test_fly_metrics(base_url)