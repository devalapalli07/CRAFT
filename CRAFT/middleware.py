from django.shortcuts import redirect
from django.urls import reverse

class AuthenticationMiddleware:
    """
    Middleware to redirect unauthenticated users to the login page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_url = reverse('login')  # 'login' should be the name of your login URL pattern

        # Allow access to login page, static files, and media files
        allowed_paths = [
            login_url,
            '/static/',
            '/media/',
        ]

        # Check if path starts with any of the allowed paths
        if not request.user.is_authenticated:
            if not any(request.path.startswith(path) for path in allowed_paths):
                return redirect(login_url)

        response = self.get_response(request)
        return response
# This middleware checks if the user is authenticated and redirects to the login page if not.
# It allows access to the login page, static files, and media files without authentication.