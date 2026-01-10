# debug_error.py - VERSION CORRIGÉE
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebi3.settings')

try:
    django.setup()
    print("✅ Django setup réussi")

    # Importez la VUE correcte (HomeView, pas home)
    from django.test import RequestFactory
    from core.views import HomeView

    factory = RequestFactory()
    request = factory.get('/')

    try:
        # Utilisez HomeView.as_view()
        response = HomeView.as_view()(request)
        print(f"✅ Vue HomeView fonctionne: {response.status_code}")
        print(f"✅ Template utilisé: {response.template_name}")
    except Exception as e:
        print(f"❌ Erreur dans HomeView: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"❌ Erreur setup Django: {e}")
    import traceback
    traceback.print_exc()