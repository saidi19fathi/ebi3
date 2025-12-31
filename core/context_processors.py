# ~/ebi3/core/context_processors.py
from django.conf import settings
from django.utils.translation import get_language, get_language_bidi
from .models import SiteSetting, Page

def site_settings(request):
    """Context processor pour les paramètres du site"""
    return {
        'SITE_NAME': SiteSetting.get_setting('site_name', 'Ebi3'),
        'SITE_DESCRIPTION': SiteSetting.get_setting('site_description', 'Plateforme de petites annonces et de Logistique Transfrontalière'),
        'SITE_URL': SiteSetting.get_setting('site_url', 'https://ebi3.org'),
        'CONTACT_EMAIL': SiteSetting.get_setting('contact_email', 'contact@ebi3.org'),
        'SUPPORT_EMAIL': SiteSetting.get_setting('support_email', 'support@ebi3.org'),
        'PHONE_NUMBER': SiteSetting.get_setting('phone_number', '+33 1 23 45 67 89'),
        'ADDRESS': SiteSetting.get_setting('address', 'Mulhouse, France'),
        'FACEBOOK_URL': SiteSetting.get_setting('facebook_url', '#'),
        'TWITTER_URL': SiteSetting.get_setting('twitter_url', '#'),
        'INSTAGRAM_URL': SiteSetting.get_setting('instagram_url', '#'),
        'LINKEDIN_URL': SiteSetting.get_setting('linkedin_url', '#'),
        'CURRENT_LANGUAGE': get_language(),
        'LANGUAGE_BIDI': get_language_bidi(),
        'ALL_LANGUAGES': settings.LANGUAGES,
    }

def footer_pages(request):
    """Context processor pour les pages du footer"""
    return {
        'FOOTER_PAGES': Page.objects.filter(
            show_in_footer=True,
            status=Page.Status.PUBLISHED
        ).order_by('menu_order')
    }

def menu_pages(request):
    """Context processor pour les pages du menu"""
    return {
        'MENU_PAGES': Page.objects.filter(
            show_in_menu=True,
            status=Page.Status.PUBLISHED
        ).order_by('menu_order')
    }