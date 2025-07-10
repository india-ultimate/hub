"""
Custom middleware for tracking API metrics.
"""
import time
from django.utils.deprecation import MiddlewareMixin


class APIMetricsMiddleware(MiddlewareMixin):
    """
    Middleware to track API request metrics for Prometheus.
    """
    
    def process_request(self, request):
        request.start_time = time.time()
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            endpoint = request.path
            method = request.method
            
            # Track API request duration if metrics are available
            try:
                from .metrics import api_request_duration
                api_request_duration.labels(
                    endpoint=endpoint,
                    method=method
                ).observe(duration)
            except ImportError:
                # Metrics not available, skip tracking
                pass
        
        return response