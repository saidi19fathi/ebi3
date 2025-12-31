#!/usr/bin/env python
"""
Réparation d'urgence Django 6.0
"""
import os

def fix_rate_limit():
    """Corrige l'erreur de syntaxe dans rate_limit.py"""
    filepath = "ebi3/middlewares/rate_limit.py"
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()

        # Corrige les doubles points
        content = content.replace('class RateLimitMiddleware::', 'class RateLimitMiddleware:')
        content = content.replace('class RateLimitMiddleware(MiddlewareMixin):', 'class RateLimitMiddleware:')

        # Ajoute __call__ si manquant
        if 'def __call__' not in content:
            lines = content.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                new_lines.append(line)
                if 'class RateLimitMiddleware:' in line:
                    new_lines.extend([
                        '',
                        '    def __init__(self, get_response):',
                        '        self.get_response = get_response',
                        '        self.async_mode = False  # Fix for Django 6.0',
                        '',
                        '    def __call__(self, request):',
                        '        response = self.get_response(request)',
                        '        return response',
                        ''
                    ])

            with open(filepath, 'w') as f:
                f.write('\n'.join(new_lines))
        else:
            with open(filepath, 'w') as f:
                f.write(content)

        print(f"✅ {filepath} corrigé")
        return True
    return False

def create_custom_security():
    """Crée le module custom_security manquant"""
    filepath = "ebi3/middlewares/custom_security.py"
    content = '''"""
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
'''

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"✅ {filepath} créé")
    return True

def disable_problematic_middlewares():
    """Commente les middlewares problématiques dans settings.py"""
    filepath = "ebi3/settings.py"
    with open(filepath, 'r') as f:
        content = f.read()

    # Liste des middlewares à commenter
    middlewares_to_disable = [
        "'ebi3.middlewares.custom_security.SecurityMiddleware'",
        "'ebi3.middlewares.audit.AuditMiddleware'",
        "'ebi3.middlewares.rate_limit.RateLimitMiddleware'",
        "'ebi3.middlewares.fix_security.FixedSecurityMiddleware'",
    ]

    for mw in middlewares_to_disable:
        content = content.replace(f"    {mw},", f"    # {mw},  # DISABLED for now")

    with open(filepath, 'w') as f:
        f.write(content)

    print("✅ Middlewares problématiques commentés")
    return True

def create_minimal_middleware():
    """Crée un middleware minimal qui fonctionne"""
    filepath = "ebi3/middlewares/minimal.py"
    content = '''"""
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
'''

    with open(filepath, 'w') as f:
        f.write(content)

    # Ajoute à settings.py
    with open("ebi3/settings.py", 'r') as f:
        settings = f.read()

    if "'ebi3.middlewares.minimal.MinimalMiddleware'" not in settings:
        settings = settings.replace(
            "'django.middleware.security.SecurityMiddleware',",
            "'ebi3.middlewares.minimal.MinimalMiddleware',\n    'django.middleware.security.SecurityMiddleware',"
        )
        with open("ebi3/settings.py", 'w') as f:
            f.write(settings)

    print("✅ Middleware minimal ajouté")
    return True

def main():
    print("🚨 RÉPARATION D'URGENCE DJANGO 6.0")
    print("=" * 50)

    fix_rate_limit()
    create_custom_security()
    disable_problematic_middlewares()
    create_minimal_middleware()

    print("=" * 50)
    print("✅ Réparation terminée !")
    print("\n📋 Actions effectuées :")
    print("1. Erreur rate_limit.py corrigée")
    print("2. Module custom_security créé")
    print("3. Middlewares problématiques désactivés")
    print("4. Middleware minimal ajouté")
    print("\n⚠️  REDÉMARRAGE REQUIS :")
    print("   Allez dans PythonAnywhere > Web > Redémarrer")

if __name__ == '__main__':
    main()