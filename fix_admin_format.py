#!/usr/bin/env python3
"""
Script pour détecter et corriger les méthodes format_html problématiques
dans carriers/admin.py qui causent l'erreur "Unknown format code 'f' for object of type 'SafeString'"
"""

import re
import sys
import os
from pathlib import Path

def analyze_admin_file(file_path):
    """Analyse le fichier admin.py pour trouver les méthodes problématiques"""

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern pour trouver les méthodes format_html avec formatage numérique
    pattern_format_html = r'format_html\s*\(([\s\S]*?)\)'
    pattern_float_format = r'\{[^}]*:\s*\.\d*f[^}]*\}'

    lines = content.split('\n')
    problematic_methods = []

    for i, line in enumerate(lines):
        # Chercher format_html dans la ligne
        if 'format_html' in line:
            # Trouver le début et la fin de l'appel format_html
            start = line.find('format_html')
            bracket_count = 0
            end = -1

            for j, char in enumerate(line[start:], start=start):
                if char == '(':
                    bracket_count += 1
                elif char == ')':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = j + 1
                        break

            if end > 0:
                format_html_call = line[start:end]

                # Vérifier s'il y a un formatage numérique dans l'appel
                if re.search(pattern_float_format, format_html_call):
                    # Trouver le nom de la méthode (regarder 5 lignes avant)
                    method_name = None
                    for j in range(min(5, i), 0, -1):
                        if 'def ' in lines[i - j]:
                            match = re.search(r'def\s+(\w+)', lines[i - j])
                            if match:
                                method_name = match.group(1)
                                break

                    if method_name:
                        problematic_methods.append({
                            'line_number': i + 1,
                            'method_name': method_name,
                            'code': line.strip(),
                            'full_method': get_full_method(content, method_name)
                        })

    return problematic_methods, content

def get_full_method(content, method_name):
    """Extrait le code complet d'une méthode"""
    pattern = rf'def\s+{method_name}\s*\([^)]*\):(.*?)(?=\n\s*def\s+|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    return match.group(0) if match else None

def fix_method(method_code):
    """Corrige une méthode complète"""

    # Diviser en lignes
    lines = method_code.split('\n')
    fixed_lines = []

    for line in lines:
        if 'format_html' in line and '{:' in line:
            # Cette ligne a potentiellement un problème
            # On va utiliser mark_safe à la place

            # Extraire les parties avant et après format_html
            parts = line.split('format_html')
            before = parts[0]
            after = 'format_html'.join(parts[1:])

            # Chercher le format string
            format_match = re.search(r"format_html\s*\(\s*['\"]([^'\"]+)['\"]", line)
            if format_match:
                format_string = format_match.group(1)

                # Remplacer tous les formatages numériques
                fixed_format_string = re.sub(r'\{[^}]*:\s*\.?\d*f[^}]*\}', '{}', format_string)

                # Construire la nouvelle ligne avec mark_safe
                fixed_line = f'{before}mark_safe({fixed_format_string}.format('

                # Extraire les arguments
                args_match = re.search(r'format_html\s*\([^)]*,\s*(.*)\)', line)
                if args_match:
                    args = args_match.group(1)
                    fixed_line += args + '))'
                else:
                    fixed_line += '))'

                fixed_lines.append(fixed_line)
                continue

        # Si pas de problème, garder la ligne telle quelle
        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def generate_fixed_content(content, problematic_methods):
    """Génère le contenu corrigé"""

    fixed_content = content

    for method in problematic_methods:
        method_name = method['method_name']
        original_method = method['full_method']
        fixed_method = fix_method(original_method)

        # Remplacer l'ancienne méthode par la nouvelle
        fixed_content = fixed_content.replace(original_method, fixed_method)

    return fixed_content

def create_backup(file_path):
    """Crée une sauvegarde du fichier"""
    backup_path = file_path.with_suffix('.admin.py.backup')
    with open(file_path, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
        dst.write(src.read())
    print(f"✅ Backup créé : {backup_path}")
    return backup_path

def main():
    # Chemin vers carriers/admin.py (ajuste selon ta structure)
    admin_path = Path('carriers/admin.py')

    if not admin_path.exists():
        print(f"❌ Fichier non trouvé : {admin_path}")
        print("Veuillez exécuter ce script depuis le répertoire contenant carriers/")
        sys.exit(1)

    print(f"🔍 Analyse de {admin_path}...")

    # Analyser le fichier
    problematic_methods, content = analyze_admin_file(admin_path)

    if not problematic_methods:
        print("✅ Aucune méthode problématique détectée.")
        return

    print(f"⚠️  {len(problematic_methods)} méthode(s) problématique(s) détectée(s) :")
    print("-" * 60)

    for i, method in enumerate(problematic_methods, 1):
        print(f"{i}. Méthode : {method['method_name']}")
        print(f"   Ligne : {method['line_number']}")
        print(f"   Code : {method['code'][:100]}...")
        print()

    # Demander confirmation
    response = input("Voulez-vous corriger ces méthodes ? (oui/non) : ").strip().lower()

    if response not in ['oui', 'o', 'yes', 'y']:
        print("❌ Correction annulée.")
        return

    # Créer une sauvegarde
    backup = create_backup(admin_path)

    # Générer le contenu corrigé
    fixed_content = generate_fixed_content(content, problematic_methods)

    # Écrire le fichier corrigé
    with open(admin_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print(f"✅ Fichier corrigé : {admin_path}")
    print(f"📋 Résumé des corrections :")

    for method in problematic_methods:
        print(f"   - {method['method_name']} : format_html → mark_safe")

    print("\n⚠️  IMPORTANT : Vérifiez manuellement les corrections car certaines")
    print("   conversions peuvent nécessiter un ajustement manuel.")

def quick_fix_suggestion():
    """Affiche une suggestion de correction rapide"""

    suggestion = """
# SOLUTION RAPIDE POUR carriers/admin.py :

# 1. REMPLACER toutes les méthodes format_html avec formatage numérique
#    par des méthodes utilisant mark_safe

# 2. AJOUTER cet import en haut du fichier :
from django.utils.safestring import mark_safe

# 3. CORRIGER chaque méthode problématique :

# AVANT :
def transport_average_rating_display(self, obj):
    rating = obj.transport_average_rating
    stars = '★' * int(rating)
    half_star = '½' if rating % 1 >= 0.5 else ''
    empty_stars = '☆' * (5 - int(rating) - (1 if half_star else 0))

    return format_html(
        '<span style="color: gold; font-size: 14px;">{}{}{}</span> '
        '<span>({:.1f}/5)</span>',
        stars, half_star, empty_stars, rating
    )

# APRÈS :
def transport_average_rating_display(self, obj):
    # Convertir en float de manière sécurisée
    try:
        rating = float(obj.transport_average_rating)
    except (ValueError, TypeError):
        rating = 0.0

    full_stars = int(rating)
    half_star = '½' if rating - full_stars >= 0.5 else ''
    empty_stars = 5 - full_stars - (1 if half_star else 0)

    html = (f'<span style="color: gold; font-size: 14px;">'
            f'{"★" * full_stars}{half_star}{"☆" * empty_stars}'
            f'</span> <span>({rating:.1f}/5)</span>')

    return mark_safe(html)

# 4. APPLIQUER la même logique pour toutes les méthodes similaires.
"""

    print(suggestion)

def create_automatic_fix():
    """Crée un fichier de correction automatique"""

    fix_content = """
# Fichier de correction pour carriers/admin.py
# Exécutez ce code pour corriger automatiquement

import re

def safe_float(value, default=0.0):
    \"\"\"Convertit en float de manière sécurisée\"\"\"
    try:
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

# Méthodes de correction pour carriers/admin.py
def get_fixed_methods():
    \"\"\"Retourne les versions corrigées des méthodes\"\"\"

    methods = {}

    # 1. transport_average_rating_display
    methods['transport_average_rating_display'] = '''
def transport_average_rating_display(self, obj):
    \"\"\"Affiche la note moyenne avec des étoiles - Version corrigée\"\"\"
    from django.utils.safestring import mark_safe

    # Convertir en float de manière sécurisée
    rating = 0.0
    try:
        rating = float(obj.transport_average_rating)
    except (ValueError, TypeError):
        rating = 0.0

    full_stars = int(rating)
    half_star = '½' if rating - full_stars >= 0.5 else ''
    empty_stars = 5 - full_stars - (1 if half_star else 0)

    html = f'<span style="color: gold; font-size: 14px;">'
    html += '★' * full_stars
    html += half_star
    html += '☆' * empty_stars
    html += f'</span> <span>({rating:.1f}/5)</span>'

    return mark_safe(html)
'''

    # 2. verification_level_display
    methods['verification_level_display'] = '''
def verification_level_display(self, obj):
    \"\"\"Affiche le niveau de vérification - Version corrigée\"\"\"
    from django.utils.safestring import mark_safe

    level = obj.verification_level
    try:
        level_int = int(level)
    except (ValueError, TypeError):
        level_int = 0

    if level_int == 0:
        html = '<span style="color: red;">● Non vérifié</span>'
    elif level_int == 1:
        html = '<span style="color: orange;">● Basique</span>'
    elif level_int == 2:
        html = '<span style="color: blue;">● Intermédiaire</span>'
    elif level_int == 3:
        html = '<span style="color: green;">● Avancé</span>'
    elif level_int >= 4:
        html = '<span style="color: darkgreen; font-weight: bold;">★ Expert</span>'
    else:
        html = f'<span>● {level_int}</span>'

    return mark_safe(html)
'''

    return methods
"""

    return fix_content

if __name__ == '__main__':
    print("=" * 70)
    print("SCRIPT DE DÉTECTION ET CORRECTION DES FORMAT_HTML PROBLÉMATIQUES")
    print("=" * 70)
    print()

    print("1. Analyse complète du fichier")
    print("2. Correction automatique")
    print("3. Afficher la suggestion de correction rapide")
    print("4. Générer un fichier de correction")
    print()

    try:
        choice = input("Choisissez une option (1-4) : ").strip()

        if choice == '1':
            main()
        elif choice == '2':
            # Exécuter la correction automatique
            main()
        elif choice == '3':
            quick_fix_suggestion()
        elif choice == '4':
            fix_methods = create_automatic_fix()
            with open('carrier_admin_fixes.py', 'w', encoding='utf-8') as f:
                f.write(fix_methods)
            print("✅ Fichier de correction généré : carrier_admin_fixes.py")
            print("Importez ce fichier et utilisez les méthodes corrigées.")
        else:
            print("❌ Option invalide.")
    except KeyboardInterrupt:
        print("\n\n❌ Opération annulée par l'utilisateur.")