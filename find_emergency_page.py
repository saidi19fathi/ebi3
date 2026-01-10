# find_emergency_page.py
import os
import re

print("=== RECHERCHE DE LA PAGE D'URGENCE ===")

# Le contenu exact de la page que vous voyez
emergency_text = """EBi3 Platform
✅ SITE OPÉRATIONNEL

Plateforme de petites annonces et transport de colis entre particuliers"""

# Chercher dans tous les fichiers Python
for root, dirs, files in os.walk('.'):
    # Ignorer les dossiers system
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'node_modules']]

    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'SITE OPÉRATIONNEL' in content and 'Plateforme de petites annonces' in content:
                        print(f"\n⚠️  TROUVÉ dans: {filepath}")

                        # Afficher le contexte
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if 'SITE OPÉRATIONNEL' in line or 'class.*View' in line or 'def.*home' in line:
                                print(f"   Ligne {i+1}: {line[:100]}")
            except:
                pass

print("\n=== VÉRIFICATION DES IMPORTS ===")

# Vérifier core/urls.py
try:
    with open('core/urls.py', 'r') as f:
        content = f.read()
        print("core/urls.py:")
        for line in content.split('\n'):
            if 'import' in line or 'path' in line or 'home' in line.lower():
                print(f"  {line}")
except:
    print("core/urls.py non trouvé")

print("\n=== INSTRUCTIONS ===")
print("1. Supprimez le fichier trouvé ci-dessus")
print("2. Vérifiez que core/urls.py pointe vers views.HomeView")
print("3. Redémarrez l'application")