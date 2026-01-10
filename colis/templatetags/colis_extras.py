# ~/ebi3/colis/templatetags/colis_extras.py
from django import template
from colis.models import Package

register = template.Library()

@register.simple_tag
def get_recent_packages(limit=4):
    """Retourne les derniers colis disponibles"""
    try:
        return Package.objects.filter(
            status=Package.Status.AVAILABLE
        ).select_related('sender', 'category').prefetch_related('images')[:limit]
    except Exception:
        return Package.objects.none()

# ~/ebi3/colis/templatetags/__init__.py
# Ce fichier peut être vide, il sert juste à indiquer que c'est un package Python