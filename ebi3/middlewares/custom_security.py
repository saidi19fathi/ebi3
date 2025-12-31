"""
Middleware de sécurité personnalisé
"""

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = False  # Fix for Django 6.0

    def __call__(self, request):
        # Votre logique de sécurité ici
        response = self.get_response(request)
        return response
