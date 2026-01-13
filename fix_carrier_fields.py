#!/usr/bin/env python3
# ~/ebi3/quick_fix.py
"""
Correction rapide des erreurs is_available
"""

import os
import sys

# Se placer dans le répertoire du projet
os.chdir('/home/saidi19/ebi3')

# 1. Corriger core/views.py
print("Correction de core/views.py...")
with open('core/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remplacer is_available par transport_is_available dans les filtres Carrier
if 'is_available=True' in content and 'Carrier' in content:
    content = content.replace('is_available=True', 'transport_is_available=True')

    with open('core/views.py.bak', 'w', encoding='utf-8') as f:
        f.write(content.replace('transport_is_available', 'is_available'))  # Backup

    with open('core/views.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✓ core/views.py corrigé")

# 2. Ajouter la propriété is_available à Carrier
print("\nAjout de la propriété is_available à Carrier...")
with open('carriers/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Vérifier si la propriété existe déjà
if '@property' not in content or 'def is_available' not in content:
    # Trouver la fin de la classe Carrier
    class_start = content.find('class Carrier(models.Model):')
    if class_start != -1:
        # Trouver la fin de la classe
        class_end = content.find('\nclass ', class_start + 1)
        if class_end == -1:
            class_end = len(content)

        # Ajouter la propriété
        property_code = """
    @property
    def is_available(self):
        \"\"\"Propriété pour compatibilité ascendante\"\"\"
        return self.transport_is_available

    @is_available.setter
    def is_available(self, value):
        \"\"\"Setter pour compatibilité ascendante\"\"\"
        self.transport_is_available = value"""

        # Insérer avant la fin de la classe
        new_content = content[:class_end] + property_code + content[class_end:]

        with open('carriers/models.py.bak', 'w', encoding='utf-8') as f:
            f.write(content)

        with open('carriers/models.py', 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("✓ Propriété is_available ajoutée à Carrier")

# 3. Corriger carriers/views.py
print("\nCorrection de carriers/views.py...")
with open('carriers/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remplacer dans CarrierSearch.execute_search
if 'is_available=True' in content and 'Carrier.Status.APPROVED' in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'is_available=True' in line and 'Carrier.Status.APPROVED' in line:
            lines[i] = line.replace('is_available=True', 'transport_is_available=True')

    new_content = '\n'.join(lines)

    with open('carriers/views.py.bak', 'w', encoding='utf-8') as f:
        f.write(content)

    with open('carriers/views.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✓ carriers/views.py corrigé")

print("\n=== Corrections appliquées ===")
print("1. core/views.py : is_available → transport_is_available")
print("2. carriers/models.py : Propriété @property is_available ajoutée")
print("3. carriers/views.py : is_available → transport_is_available dans les recherches")
print("\nDes fichiers .bak ont été créés en sauvegarde.")
print("\nExécutez maintenant :")
print("python manage.py makemigrations carriers")
print("python manage.py migrate carriers")