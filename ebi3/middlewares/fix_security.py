# ~/ebi3/ebi3/middlewares/fix_security.py
"""
Middleware de correction pour Django 6.0 async_mode error
"""

class FixedSecurityMiddleware:
    """Version corrigée pour Django 6.0+"""

    def __init__(self, get_response):
        self.get_response = get_response
        # Ajoute l'attribut manquant qui cause l'erreur
        self.async_mode = False

    def __call__(self, request):
        response = self.get_response(request)
        return response

    async def __acall__(self, request):
        # Version asynchrone
        response = await self.get_response(request)
        return response
