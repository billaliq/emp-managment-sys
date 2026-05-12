"""
Custom middleware for cache control
"""
from django.utils.deprecation import MiddlewareMixin


class NoCacheMiddleware(MiddlewareMixin):
    """
    Middleware to disable caching for static and media files in development
    """
    def process_response(self, request, response):
        # Disable caching for static and media files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response

