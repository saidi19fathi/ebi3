from django import template

register = template.Library()

@register.filter
def get_image_url(image):
    """Retourne l'URL de l'image, priorisant le thumbnail s'il existe"""
    if image and image.image:
        if image.thumbnail and hasattr(image.thumbnail, 'url'):
            try:
                return image.thumbnail.url
            except ValueError:
                return image.image.url
        return image.image.url
    return ''