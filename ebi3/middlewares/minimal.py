"""
Middleware minimal compatible Django 6.0
"""

class MinimalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = False

    def __call__(self, request):
        response = self.get_response(request)
        return response

    async def __acall__(self, request):
        response = await self.get_response(request)
        return response
