# ~/ebi3/check_urls.py
from django.urls import reverse, NoReverseMatch
from django.conf import settings

# Configurez Django
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebi3.settings')
django.setup()

# URLs à vérifier
urls_to_check = [
    'colis:favorite_list',
    'colis:my_offers',
    'colis:available_packages',
    'colis:carrier_dashboard',
    'colis:how_it_works',
    'colis:price_guide',
    'colis:packaging_tips',
    'colis:faq',
    'colis:terms',
    'colis:privacy',
]

print("Vérification des URLs...")
for url_name in urls_to_check:
    try:
        reverse(url_name)
        print(f"✓ {url_name} : OK")
    except NoReverseMatch:
        print(f"✗ {url_name} : MANQUANT")