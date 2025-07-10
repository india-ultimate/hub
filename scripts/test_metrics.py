#!/usr/bin/env python3
"""
Script to test Prometheus metrics endpoint.
"""
import requests
import sys


def test_metrics_endpoint(base_url="http://localhost:8000"):
    """Test the Prometheus metrics endpoint."""
    try:
        response = requests.get(f"{base_url}/metrics/")
        if response.status_code == 200:
            print("✅ Metrics endpoint is working!")
            print(f"Response length: {len(response.text)} characters")
            print("First 500 characters of response:")
            print(response.text[:500])
            return True
        else:
            print(f"❌ Metrics endpoint returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error accessing metrics endpoint: {e}")
        return False


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    test_metrics_endpoint(base_url)