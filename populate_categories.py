# ~/ebi3/populate_categories.py
import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebi3.settings')
django.setup()

from ads.models import Category as AdCategory
from colis.models import PackageCategory as ColisCategory
from django.utils.text import slugify

# Couleurs d'affichage
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def create_categories(model_class, categories_data, parent=None, indent=0):
    """
    Crée récursivement les catégories
    """
    for category_data in categories_data:
        name = category_data['name']
        slug = slugify(name)

        # Vérifier si la catégorie existe déjà
        existing = model_class.objects.filter(slug=slug).first()
        if existing:
            print(f"{'  ' * indent}↳ {Colors.YELLOW}Existe déjà{Colors.END}: {name}")
            category = existing
        else:
            # Créer la catégorie
            category = model_class(
                name=name,
                slug=slug,
                parent=parent,
                icon=category_data.get('icon', ''),
                description=category_data.get('description', ''),
                requires_dimensions=category_data.get('requires_dimensions', False),
                requires_weight=category_data.get('requires_weight', True),
                is_active=True,
                show_in_menu=True,
                display_order=category_data.get('order', 0)
            )
            category.save()
            print(f"{'  ' * indent}↳ {Colors.GREEN}Créé{Colors.END}: {name}")

        # Créer les sous-catégories
        if 'subcategories' in category_data:
            create_categories(model_class, category_data['subcategories'], category, indent + 1)

def main():
    print(f"{Colors.BOLD}{Colors.BLUE}=== POPULATION DES CATÉGORIES D'ANNONCES ==={Colors.END}")

    # CATÉGORIES POUR LES ANNONCES (ads)
    ad_categories = [
        {
            'name': 'Véhicules',
            'icon': 'fa-car',
            'description': 'Voitures, motos, utilitaires, pièces auto',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 1,
            'subcategories': [
                {
                    'name': 'Voitures',
                    'icon': 'fa-car',
                    'description': 'Voitures particulières neuves et d\'occasion',
                    'requires_dimensions': False,
                    'requires_weight': True,
                    'order': 1,
                    'subcategories': [
                        {'name': 'Citadines', 'icon': 'fa-car', 'order': 1},
                        {'name': 'Berlines', 'icon': 'fa-car', 'order': 2},
                        {'name': 'SUV & 4x4', 'icon': 'fa-truck', 'order': 3},
                        {'name': 'Voitures de sport', 'icon': 'fa-tachometer-alt', 'order': 4},
                        {'name': 'Voitures électriques', 'icon': 'fa-charging-station', 'order': 5},
                        {'name': 'Voitures hybrides', 'icon': 'fa-leaf', 'order': 6},
                        {'name': 'Voitures anciennes', 'icon': 'fa-history', 'order': 7},
                        {'name': 'Voitures de luxe', 'icon': 'fa-gem', 'order': 8},
                    ]
                },
                {
                    'name': 'Motos & Scooters',
                    'icon': 'fa-motorcycle',
                    'description': 'Deux-roues motorisés',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Scooters', 'icon': 'fa-motorcycle', 'order': 1},
                        {'name': 'Motos 125cm3', 'icon': 'fa-motorcycle', 'order': 2},
                        {'name': 'Grosses cylindrées', 'icon': 'fa-motorcycle', 'order': 3},
                        {'name': 'Motos custom', 'icon': 'fa-motorcycle', 'order': 4},
                        {'name': 'Motos sportives', 'icon': 'fa-motorcycle', 'order': 5},
                        {'name': 'Motos tout-terrain', 'icon': 'fa-motorcycle', 'order': 6},
                        {'name': 'Vélos électriques', 'icon': 'fa-bicycle', 'order': 7},
                    ]
                },
                {
                    'name': 'Utilitaires & Poids lourds',
                    'icon': 'fa-truck',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Fourgons', 'icon': 'fa-truck', 'order': 1},
                        {'name': 'Pick-up', 'icon': 'fa-truck-pickup', 'order': 2},
                        {'name': 'Camions', 'icon': 'fa-truck', 'order': 3},
                        {'name': 'Camping-cars', 'icon': 'fa-caravan', 'order': 4},
                        {'name': 'Remorques', 'icon': 'fa-trailer', 'order': 5},
                    ]
                },
                {
                    'name': 'Caravanes & Mobil-homes',
                    'icon': 'fa-caravan',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Caravanes', 'icon': 'fa-caravan', 'order': 1},
                        {'name': 'Mobil-homes', 'icon': 'fa-home', 'order': 2},
                        {'name': 'Fourgons aménagés', 'icon': 'fa-van-shuttle', 'order': 3},
                    ]
                },
                {
                    'name': 'Nautisme',
                    'icon': 'fa-ship',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Bateaux à moteur', 'icon': 'fa-ship', 'order': 1},
                        {'name': 'Voiliers', 'icon': 'fa-sailboat', 'order': 2},
                        {'name': 'Jet-skis', 'icon': 'fa-water', 'order': 3},
                        {'name': 'Pneumatiques', 'icon': 'fa-life-ring', 'order': 4},
                        {'name': 'Accessoires nautiques', 'icon': 'fa-anchor', 'order': 5},
                    ]
                },
                {
                    'name': 'Pièces & Accessoires auto',
                    'icon': 'fa-cogs',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 6,
                    'subcategories': [
                        {'name': 'Moteurs', 'icon': 'fa-cogs', 'order': 1},
                        {'name': 'Pneus & Jantes', 'icon': 'fa-tire', 'order': 2},
                        {'name': 'Carrosserie', 'icon': 'fa-car', 'order': 3},
                        {'name': 'Système électronique', 'icon': 'fa-microchip', 'order': 4},
                        {'name': 'Intérieur & Sièges', 'icon': 'fa-chair', 'order': 5},
                        {'name': 'Outils & Équipement', 'icon': 'fa-tools', 'order': 6},
                        {'name': 'Lubrifiants & Additifs', 'icon': 'fa-oil-can', 'order': 7},
                    ]
                },
            ]
        },
        {
            'name': 'Immobilier',
            'icon': 'fa-home',
            'description': 'Ventes et locations immobilières',
            'requires_dimensions': False,
            'requires_weight': False,
            'order': 2,
            'subcategories': [
                {
                    'name': 'Ventes immobilières',
                    'icon': 'fa-home',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Maisons', 'icon': 'fa-home', 'order': 1},
                        {'name': 'Appartements', 'icon': 'fa-building', 'order': 2},
                        {'name': 'Terrains', 'icon': 'fa-mountain', 'order': 3},
                        {'name': 'Parkings & Box', 'icon': 'fa-car', 'order': 4},
                        {'name': 'Locaux commerciaux', 'icon': 'fa-store', 'order': 5},
                        {'name': 'Bureaux', 'icon': 'fa-briefcase', 'order': 6},
                        {'name': 'Immeubles', 'icon': 'fa-city', 'order': 7},
                        {'name': 'Châteaux & Propriétés', 'icon': 'fa-chess-rook', 'order': 8},
                    ]
                },
                {
                    'name': 'Locations',
                    'icon': 'fa-key',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Maisons à louer', 'icon': 'fa-home', 'order': 1},
                        {'name': 'Appartements à louer', 'icon': 'fa-building', 'order': 2},
                        {'name': 'Colocations', 'icon': 'fa-users', 'order': 3},
                        {'name': 'Locations saisonnières', 'icon': 'fa-umbrella-beach', 'order': 4},
                        {'name': 'Locations meublées', 'icon': 'fa-couch', 'order': 5},
                        {'name': 'Chambres chez l\'habitant', 'icon': 'fa-bed', 'order': 6},
                        {'name': 'Bureaux à louer', 'icon': 'fa-briefcase', 'order': 7},
                        {'name': 'Locaux commerciaux à louer', 'icon': 'fa-store', 'order': 8},
                    ]
                },
                {
                    'name': 'Immobilier neuf',
                    'icon': 'fa-hard-hat',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Programmes neufs', 'icon': 'fa-hard-hat', 'order': 1},
                        {'name': 'Ventes en VEFA', 'icon': 'fa-file-contract', 'order': 2},
                        {'name': 'Investissements locatifs', 'icon': 'fa-chart-line', 'order': 3},
                    ]
                },
            ]
        },
        {
            'name': 'Emploi',
            'icon': 'fa-briefcase',
            'description': 'Offres d\'emploi et services professionnels',
            'requires_dimensions': False,
            'requires_weight': False,
            'order': 3,
            'subcategories': [
                {
                    'name': 'Offres d\'emploi',
                    'icon': 'fa-user-tie',
                    'order': 1,
                    'subcategories': [
                        {'name': 'CDI', 'icon': 'fa-file-contract', 'order': 1},
                        {'name': 'CDD', 'icon': 'fa-calendar-alt', 'order': 2},
                        {'name': 'Intérim', 'icon': 'fa-clock', 'order': 3},
                        {'name': 'Stages', 'icon': 'fa-graduation-cap', 'order': 4},
                        {'name': 'Alternance', 'icon': 'fa-university', 'order': 5},
                        {'name': 'Télétravail', 'icon': 'fa-laptop-house', 'order': 6},
                        {'name': 'Emplois saisonniers', 'icon': 'fa-sun', 'order': 7},
                        {'name': 'Jobs étudiants', 'icon': 'fa-user-graduate', 'order': 8},
                    ]
                },
                {
                    'name': 'Services à la personne',
                    'icon': 'fa-hands-helping',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Baby-sitting', 'icon': 'fa-baby', 'order': 1},
                        {'name': 'Ménage & Repassage', 'icon': 'fa-broom', 'order': 2},
                        {'name': 'Jardinage', 'icon': 'fa-leaf', 'order': 3},
                        {'name': 'Bricolage', 'icon': 'fa-tools', 'order': 4},
                        {'name': 'Cours particuliers', 'icon': 'fa-chalkboard-teacher', 'order': 5},
                        {'name': 'Soins aux personnes âgées', 'icon': 'fa-wheelchair', 'order': 6},
                        {'name': 'Garde d\'animaux', 'icon': 'fa-paw', 'order': 7},
                        {'name': 'Cuisine à domicile', 'icon': 'fa-utensils', 'order': 8},
                    ]
                },
                {
                    'name': 'Services professionnels',
                    'icon': 'fa-user-md',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Informatique & Web', 'icon': 'fa-laptop-code', 'order': 1},
                        {'name': 'Graphisme & Design', 'icon': 'fa-palette', 'order': 2},
                        {'name': 'Travaux & Construction', 'icon': 'fa-hard-hat', 'order': 3},
                        {'name': 'Transport & Déménagement', 'icon': 'fa-truck-moving', 'order': 4},
                        {'name': 'Comptabilité', 'icon': 'fa-calculator', 'order': 5},
                        {'name': 'Juridique', 'icon': 'fa-balance-scale', 'order': 6},
                        {'name': 'Traduction', 'icon': 'fa-language', 'order': 7},
                        {'name': 'Coaching', 'icon': 'fa-brain', 'order': 8},
                    ]
                },
            ]
        },
        {
            'name': 'Mode & Accessoires',
            'icon': 'fa-tshirt',
            'description': 'Vêtements, chaussures, bijoux et accessoires',
            'requires_dimensions': False,
            'requires_weight': False,
            'order': 4,
            'subcategories': [
                {
                    'name': 'Vêtements femmes',
                    'icon': 'fa-female',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Robes', 'icon': 'fa-tshirt', 'order': 1},
                        {'name': 'Hauts & T-shirts', 'icon': 'fa-tshirt', 'order': 2},
                        {'name': 'Pantalons & Jeans', 'icon': 'fa-tshirt', 'order': 3},
                        {'name': 'Jupes', 'icon': 'fa-tshirt', 'order': 4},
                        {'name': 'Vestes & Manteaux', 'icon': 'fa-tshirt', 'order': 5},
                        {'name': 'Lingerie', 'icon': 'fa-tshirt', 'order': 6},
                        {'name': 'Maillots de bain', 'icon': 'fa-swimmer', 'order': 7},
                        {'name': 'Vêtements de grossesse', 'icon': 'fa-baby', 'order': 8},
                    ]
                },
                {
                    'name': 'Vêtements hommes',
                    'icon': 'fa-male',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Chemises', 'icon': 'fa-tshirt', 'order': 1},
                        {'name': 'T-shirts & Polos', 'icon': 'fa-tshirt', 'order': 2},
                        {'name': 'Pantalons & Jeans', 'icon': 'fa-tshirt', 'order': 3},
                        {'name': 'Costumes & Vestes', 'icon': 'fa-tshirt', 'order': 4},
                        {'name': 'Sweats & Pulls', 'icon': 'fa-tshirt', 'order': 5},
                        {'name': 'Shorts & Bermudas', 'icon': 'fa-tshirt', 'order': 6},
                        {'name': 'Sous-vêtements', 'icon': 'fa-tshirt', 'order': 7},
                        {'name': 'Maillots de bain', 'icon': 'fa-swimmer', 'order': 8},
                    ]
                },
                {
                    'name': 'Vêtements enfants',
                    'icon': 'fa-child',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Bébés 0-24 mois', 'icon': 'fa-baby', 'order': 1},
                        {'name': 'Filles 2-14 ans', 'icon': 'fa-female', 'order': 2},
                        {'name': 'Garçons 2-14 ans', 'icon': 'fa-male', 'order': 3},
                        {'name': 'Chaussures enfants', 'icon': 'fa-shoe-prints', 'order': 4},
                        {'name': 'Vêtements scolaire', 'icon': 'fa-graduation-cap', 'order': 5},
                    ]
                },
                {
                    'name': 'Chaussures',
                    'icon': 'fa-shoe-prints',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Chaussures femmes', 'icon': 'fa-female', 'order': 1},
                        {'name': 'Chaussures hommes', 'icon': 'fa-male', 'order': 2},
                        {'name': 'Chaussures enfants', 'icon': 'fa-child', 'order': 3},
                        {'name': 'Baskets & Sneakers', 'icon': 'fa-running', 'order': 4},
                        {'name': 'Sandales & Tong', 'icon': 'fa-umbrella-beach', 'order': 5},
                        {'name': 'Bottes', 'icon': 'fa-snowflake', 'order': 6},
                        {'name': 'Chaussures de sport', 'icon': 'fa-futbol', 'order': 7},
                        {'name': 'Chaussures de sécurité', 'icon': 'fa-hard-hat', 'order': 8},
                    ]
                },
                {
                    'name': 'Accessoires & Bijoux',
                    'icon': 'fa-gem',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Sacs & Portefeuilles', 'icon': 'fa-shopping-bag', 'order': 1},
                        {'name': 'Montres', 'icon': 'fa-clock', 'order': 2},
                        {'name': 'Bijoux', 'icon': 'fa-gem', 'order': 3},
                        {'name': 'Lunettes', 'icon': 'fa-glasses', 'order': 4},
                        {'name': 'Ceintures', 'icon': 'fa-tshirt', 'order': 5},
                        {'name': 'Écharpes & Foulards', 'icon': 'fa-tshirt', 'order': 6},
                        {'name': 'Chapeaux & Casquettes', 'icon': 'fa-tshirt', 'order': 7},
                        {'name': 'Accessoires cheveux', 'icon': 'fa-tshirt', 'order': 8},
                    ]
                },
                {
                    'name': 'Luxe & Créateurs',
                    'icon': 'fa-crown',
                    'order': 6,
                    'subcategories': [
                        {'name': 'Marques de luxe', 'icon': 'fa-crown', 'order': 1},
                        {'name': 'Haute couture', 'icon': 'fa-tshirt', 'order': 2},
                        {'name': 'Accessoires luxe', 'icon': 'fa-gem', 'order': 3},
                        {'name': 'Montres de luxe', 'icon': 'fa-clock', 'order': 4},
                        {'name': 'Bijoux précieux', 'icon': 'fa-gem', 'order': 5},
                        {'name': 'Maroquinerie luxe', 'icon': 'fa-shopping-bag', 'order': 6},
                    ]
                },
            ]
        },
        {
            'name': 'Maison & Jardin',
            'icon': 'fa-couch',
            'description': 'Ameublement, décoration, électroménager, bricolage',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 5,
            'subcategories': [
                {
                    'name': 'Ameublement',
                    'icon': 'fa-couch',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Sofas & Canapés', 'icon': 'fa-couch', 'order': 1},
                        {'name': 'Tables', 'icon': 'fa-utensils', 'order': 2},
                        {'name': 'Chaises & Tabourets', 'icon': 'fa-chair', 'order': 3},
                        {'name': 'Armoires & Dressings', 'icon': 'fa-archive', 'order': 4},
                        {'name': 'Lits & Matelas', 'icon': 'fa-bed', 'order': 5},
                        {'name': 'Étagères & Bibliothèques', 'icon': 'fa-book', 'order': 6},
                        {'name': 'Meubles TV & Meubles bas', 'icon': 'fa-tv', 'order': 7},
                        {'name': 'Meubles enfants', 'icon': 'fa-child', 'order': 8},
                    ]
                },
                {
                    'name': 'Électroménager',
                    'icon': 'fa-plug',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Cuisine', 'icon': 'fa-blender', 'order': 1},
                        {'name': 'Lave-linge & Sèche-linge', 'icon': 'fa-soap', 'order': 2},
                        {'name': 'Réfrigérateurs & Congélateurs', 'icon': 'fa-snowflake', 'order': 3},
                        {'name': 'Lave-vaisselle', 'icon': 'fa-shower', 'order': 4},
                        {'name': 'Fours & Micro-ondes', 'icon': 'fa-fire', 'order': 5},
                        {'name': 'Aspirateurs & Nettoyeurs', 'icon': 'fa-broom', 'order': 6},
                        {'name': 'Climatisation & Chauffage', 'icon': 'fa-temperature-high', 'order': 7},
                        {'name': 'Petit électroménager', 'icon': 'fa-utensils', 'order': 8},
                    ]
                },
                {
                    'name': 'Décoration',
                    'icon': 'fa-palette',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 3,
                    'subcategories': [
                        {'name': 'Luminaires & Lampes', 'icon': 'fa-lightbulb', 'order': 1},
                        {'name': 'Tapis & Moquettes', 'icon': 'fa-square', 'order': 2},
                        {'name': 'Rideaux & Voilages', 'icon': 'fa-window-maximize', 'order': 3},
                        {'name': 'Tableaux & Posters', 'icon': 'fa-image', 'order': 4},
                        {'name': 'Vases & Décoration table', 'icon': 'fa-wine-glass', 'order': 5},
                        {'name': 'Horloges', 'icon': 'fa-clock', 'order': 6},
                        {'name': 'Bougies & Parfums d\'ambiance', 'icon': 'fa-fire', 'order': 7},
                        {'name': 'Objets de décoration', 'icon': 'fa-gem', 'order': 8},
                    ]
                },
                {
                    'name': 'Jardin & Extérieur',
                    'icon': 'fa-tree',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Mobilier de jardin', 'icon': 'fa-chair', 'order': 1},
                        {'name': 'Barbecues & Planchas', 'icon': 'fa-fire', 'order': 2},
                        {'name': 'Piscines & Spas', 'icon': 'fa-swimming-pool', 'order': 3},
                        {'name': 'Outils de jardin', 'icon': 'fa-tools', 'order': 4},
                        {'name': 'Plantes & Fleurs', 'icon': 'fa-leaf', 'order': 5},
                        {'name': 'Tondeuses & Outils motorisés', 'icon': 'fa-tractor', 'order': 6},
                        {'name': 'Éclairage extérieur', 'icon': 'fa-lightbulb', 'order': 7},
                        {'name': 'Serres & Abris', 'icon': 'fa-home', 'order': 8},
                    ]
                },
                {
                    'name': 'Bricolage',
                    'icon': 'fa-tools',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Outils à main', 'icon': 'fa-hammer', 'order': 1},
                        {'name': 'Outils électroportatifs', 'icon': 'fa-plug', 'order': 2},
                        {'name': 'Matériaux de construction', 'icon': 'fa-hard-hat', 'order': 3},
                        {'name': 'Quincaillerie', 'icon': 'fa-cogs', 'order': 4},
                        {'name': 'Peinture & Revêtements', 'icon': 'fa-paint-roller', 'order': 5},
                        {'name': 'Plomberie & Sanitaire', 'icon': 'fa-faucet', 'order': 6},
                        {'name': 'Électricité', 'icon': 'fa-bolt', 'order': 7},
                        {'name': 'Menuiserie', 'icon': 'fa-tree', 'order': 8},
                    ]
                },
                {
                    'name': 'Cuisine & Arts de la table',
                    'icon': 'fa-utensils',
                    'order': 6,
                    'subcategories': [
                        {'name': 'Vaisselle & Verrerie', 'icon': 'fa-wine-glass', 'order': 1},
                        {'name': 'Couverts & Ustensiles', 'icon': 'fa-utensil-spoon', 'order': 2},
                        {'name': 'Appareils de cuisine', 'icon': 'fa-blender', 'order': 3},
                        {'name': 'Casseroles & Poêles', 'icon': 'fa-fire', 'order': 4},
                        {'name': 'Accessoires de cuisine', 'icon': 'fa-mortar-pestle', 'order': 5},
                        {'name': 'Nappes & Serviettes', 'icon': 'fa-square', 'order': 6},
                    ]
                },
            ]
        },
        {
            'name': 'Électronique & Multimédia',
            'icon': 'fa-laptop',
            'description': 'Informatique, téléphonie, photo, jeux vidéo',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 6,
            'subcategories': [
                {
                    'name': 'Informatique',
                    'icon': 'fa-desktop',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Ordinateurs portables', 'icon': 'fa-laptop', 'order': 1},
                        {'name': 'Ordinateurs fixes', 'icon': 'fa-desktop', 'order': 2},
                        {'name': 'Tablettes', 'icon': 'fa-tablet-alt', 'order': 3},
                        {'name': 'Périphériques', 'icon': 'fa-keyboard', 'order': 4},
                        {'name': 'Composants', 'icon': 'fa-microchip', 'order': 5},
                        {'name': 'Réseaux & Connexion', 'icon': 'fa-wifi', 'order': 6},
                        {'name': 'Logiciels', 'icon': 'fa-file-code', 'order': 7},
                        {'name': 'Accessoires informatiques', 'icon': 'fa-mouse', 'order': 8},
                    ]
                },
                {
                    'name': 'Téléphonie',
                    'icon': 'fa-mobile-alt',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Smartphones', 'icon': 'fa-mobile-alt', 'order': 1},
                        {'name': 'Téléphones fixes', 'icon': 'fa-phone', 'order': 2},
                        {'name': 'Accessoires téléphone', 'icon': 'fa-headphones', 'order': 3},
                        {'name': 'Forfaits & Recharges', 'icon': 'fa-sim-card', 'order': 4},
                        {'name': 'Montres connectées', 'icon': 'fa-clock', 'order': 5},
                        {'name': 'Tablettes tactiles', 'icon': 'fa-tablet-alt', 'order': 6},
                    ]
                },
                {
                    'name': 'Photo & Vidéo',
                    'icon': 'fa-camera',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Appareils photo', 'icon': 'fa-camera', 'order': 1},
                        {'name': 'Objectifs', 'icon': 'fa-camera', 'order': 2},
                        {'name': 'Caméras & Caméscopes', 'icon': 'fa-video', 'order': 3},
                        {'name': 'Accessoires photo', 'icon': 'fa-camera-retro', 'order': 4},
                        {'name': 'Drones', 'icon': 'fa-helicopter', 'order': 5},
                        {'name': 'Trépieds & Stabilisateurs', 'icon': 'fa-camera', 'order': 6},
                        {'name': 'Éclairage photo', 'icon': 'fa-lightbulb', 'order': 7},
                        {'name': 'Logiciels photo/vidéo', 'icon': 'fa-file-video', 'order': 8},
                    ]
                },
                {
                    'name': 'Image & Son',
                    'icon': 'fa-tv',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Téléviseurs', 'icon': 'fa-tv', 'order': 1},
                        {'name': 'Home cinéma', 'icon': 'fa-film', 'order': 2},
                        {'name': 'Enceintes & Haut-parleurs', 'icon': 'fa-volume-up', 'order': 3},
                        {'name': 'Amplificateurs & Chaînes Hi-Fi', 'icon': 'fa-broadcast-tower', 'order': 4},
                        {'name': 'Casques & Écouteurs', 'icon': 'fa-headphones', 'order': 5},
                        {'name': 'Platines vinyle & CD', 'icon': 'fa-compact-disc', 'order': 6},
                        {'name': 'Projecteurs & Écrans', 'icon': 'fa-film', 'order': 7},
                        {'name': 'Accessoires audio/vidéo', 'icon': 'fa-plug', 'order': 8},
                    ]
                },
                {
                    'name': 'Jeux vidéo & Consoles',
                    'icon': 'fa-gamepad',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Consoles de salon', 'icon': 'fa-gamepad', 'order': 1},
                        {'name': 'Consoles portables', 'icon': 'fa-gamepad', 'order': 2},
                        {'name': 'Jeux vidéo', 'icon': 'fa-compact-disc', 'order': 3},
                        {'name': 'Accessoires gaming', 'icon': 'fa-keyboard', 'order': 4},
                        {'name': 'PC Gaming', 'icon': 'fa-desktop', 'order': 5},
                        {'name': 'Réalité virtuelle', 'icon': 'fa-vr-cardboard', 'order': 6},
                        {'name': 'Figurines & Collection', 'icon': 'fa-robot', 'order': 7},
                        {'name': 'Rétrogaming', 'icon': 'fa-history', 'order': 8},
                    ]
                },
                {
                    'name': 'Instruments de musique',
                    'icon': 'fa-guitar',
                    'order': 6,
                    'subcategories': [
                        {'name': 'Guitares & Basses', 'icon': 'fa-guitar', 'order': 1},
                        {'name': 'Pianos & Claviers', 'icon': 'fa-music', 'order': 2},
                        {'name': 'Batteries & Percussions', 'icon': 'fa-drum', 'order': 3},
                        {'name': 'Instruments à vent', 'icon': 'fa-music', 'order': 4},
                        {'name': 'Instruments à cordes', 'icon': 'fa-music', 'order': 5},
                        {'name': 'Équipement studio', 'icon': 'fa-microphone', 'order': 6},
                        {'name': 'Accessoires musique', 'icon': 'fa-headphones', 'order': 7},
                        {'name': 'Partitions & Méthodes', 'icon': 'fa-book', 'order': 8},
                    ]
                },
            ]
        },
        {
            'name': 'Loisirs & Divertissements',
            'icon': 'fa-futbol',
            'description': 'Sports, musique, livres, jeux, collections',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 7,
            'subcategories': [
                {
                    'name': 'Sports & Plein air',
                    'icon': 'fa-running',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Vélos', 'icon': 'fa-bicycle', 'order': 1},
                        {'name': 'Fitness & Musculation', 'icon': 'fa-dumbbell', 'order': 2},
                        {'name': 'Sports d\'hiver', 'icon': 'fa-skiing', 'order': 3},
                        {'name': 'Sports nautiques', 'icon': 'fa-sailboat', 'order': 4},
                        {'name': 'Sports de raquette', 'icon': 'fa-table-tennis', 'order': 5},
                        {'name': 'Football', 'icon': 'fa-futbol', 'order': 6},
                        {'name': 'Rugby', 'icon': 'fa-football-ball', 'order': 7},
                        {'name': 'Sports de combat', 'icon': 'fa-user-ninja', 'order': 8},
                    ]
                },
                {
                    'name': 'Livres & Magazines',
                    'icon': 'fa-book',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 2,
                    'subcategories': [
                        {'name': 'Romans & Littérature', 'icon': 'fa-book', 'order': 1},
                        {'name': 'BD & Comics', 'icon': 'fa-book', 'order': 2},
                        {'name': 'Livres jeunesse', 'icon': 'fa-child', 'order': 3},
                        {'name': 'Scolaire & Universitaire', 'icon': 'fa-graduation-cap', 'order': 4},
                        {'name': 'Livres professionnels', 'icon': 'fa-briefcase', 'order': 5},
                        {'name': 'Magazines & Revues', 'icon': 'fa-newspaper', 'order': 6},
                        {'name': 'Livres anciens', 'icon': 'fa-history', 'order': 7},
                        {'name': 'Mangas', 'icon': 'fa-book', 'order': 8},
                    ]
                },
                {
                    'name': 'Films & Séries',
                    'icon': 'fa-film',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 3,
                    'subcategories': [
                        {'name': 'DVD & Blu-ray', 'icon': 'fa-compact-disc', 'order': 1},
                        {'name': 'Films', 'icon': 'fa-film', 'order': 2},
                        {'name': 'Séries TV', 'icon': 'fa-tv', 'order': 3},
                        {'name': 'Documentaires', 'icon': 'fa-video', 'order': 4},
                        {'name': 'Films d\'animation', 'icon': 'fa-film', 'order': 5},
                        {'name': 'Films anciens', 'icon': 'fa-history', 'order': 6},
                    ]
                },
                {
                    'name': 'Musique & CD',
                    'icon': 'fa-music',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 4,
                    'subcategories': [
                        {'name': 'CD musique', 'icon': 'fa-compact-disc', 'order': 1},
                        {'name': 'Vinyles', 'icon': 'fa-compact-disc', 'order': 2},
                        {'name': 'DVD musique & Concerts', 'icon': 'fa-video', 'order': 3},
                        {'name': 'Musique digitale', 'icon': 'fa-file-audio', 'order': 4},
                        {'name': 'Tous styles musicaux', 'icon': 'fa-music', 'order': 5},
                    ]
                },
                {
                    'name': 'Jeux & Jouets',
                    'icon': 'fa-puzzle-piece',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Jeux de société', 'icon': 'fa-chess-board', 'order': 1},
                        {'name': 'Jouets enfants', 'icon': 'fa-robot', 'order': 2},
                        {'name': 'Poupées & Figurines', 'icon': 'fa-child', 'order': 3},
                        {'name': 'Jeux de construction', 'icon': 'fa-cube', 'order': 4},
                        {'name': 'Peluches', 'icon': 'fa-paw', 'order': 5},
                        {'name': 'Jeux éducatifs', 'icon': 'fa-graduation-cap', 'order': 6},
                        {'name': 'Jeux extérieurs', 'icon': 'fa-tree', 'order': 7},
                        {'name': 'Jeux anciens', 'icon': 'fa-history', 'order': 8},
                    ]
                },
                {
                    'name': 'Collection',
                    'icon': 'fa-chess-queen',
                    'order': 6,
                    'subcategories': [
                        {'name': 'Monnaies & Billets', 'icon': 'fa-money-bill', 'order': 1},
                        {'name': 'Timbres', 'icon': 'fa-stamp', 'order': 2},
                        {'name': 'Cartes & Albums', 'icon': 'fa-id-card', 'order': 3},
                        {'name': 'Figurines de collection', 'icon': 'fa-robot', 'order': 4},
                        {'name': 'Objets militaires', 'icon': 'fa-helmet-battle', 'order': 5},
                        {'name': 'Objets anciens', 'icon': 'fa-history', 'order': 6},
                        {'name': 'Automobiles miniatures', 'icon': 'fa-car', 'order': 7},
                        {'name': 'Souvenirs & Memorabilia', 'icon': 'fa-star', 'order': 8},
                    ]
                },
                {
                    'name': 'Billeterie',
                    'icon': 'fa-ticket-alt',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 7,
                    'subcategories': [
                        {'name': 'Concerts & Spectacles', 'icon': 'fa-music', 'order': 1},
                        {'name': 'Sports', 'icon': 'fa-futbol', 'order': 2},
                        {'name': 'Théâtre & Danse', 'icon': 'fa-theater-masks', 'order': 3},
                        {'name': 'Cinéma', 'icon': 'fa-film', 'order': 4},
                        {'name': 'Parcs d\'attractions', 'icon': 'fa-ferris-wheel', 'order': 5},
                        {'name': 'Événements', 'icon': 'fa-calendar-alt', 'order': 6},
                        {'name': 'Transport & Voyages', 'icon': 'fa-plane', 'order': 7},
                        {'name': 'Abonnements', 'icon': 'fa-id-card', 'order': 8},
                    ]
                },
            ]
        },
        {
            'name': 'Animaux',
            'icon': 'fa-paw',
            'description': 'Animaux de compagnie, accessoires, nourriture',
            'requires_dimensions': False,
            'requires_weight': False,
            'order': 8,
            'subcategories': [
                {
                    'name': 'Animaux de compagnie',
                    'icon': 'fa-dog',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Chiens', 'icon': 'fa-dog', 'order': 1},
                        {'name': 'Chats', 'icon': 'fa-cat', 'order': 2},
                        {'name': 'Oiseaux', 'icon': 'fa-dove', 'order': 3},
                        {'name': 'Rongeurs', 'icon': 'fa-paw', 'order': 4},
                        {'name': 'Poissons & Aquariophilie', 'icon': 'fa-fish', 'order': 5},
                        {'name': 'Reptiles & Amphibiens', 'icon': 'fa-dragon', 'order': 6},
                        {'name': 'NAC (Nouveaux animaux de compagnie)', 'icon': 'fa-paw', 'order': 7},
                        {'name': 'Animaux de ferme', 'icon': 'fa-horse', 'order': 8},
                    ]
                },
                {
                    'name': 'Accessoires animaux',
                    'icon': 'fa-bone',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Nourriture & Friandises', 'icon': 'fa-utensils', 'order': 1},
                        {'name': 'Jouets', 'icon': 'fa-baseball-ball', 'order': 2},
                        {'name': 'Cages & Habitats', 'icon': 'fa-home', 'order': 3},
                        {'name': 'Litières & Hygiène', 'icon': 'fa-broom', 'order': 4},
                        {'name': 'Transport & Voyage', 'icon': 'fa-suitcase', 'order': 5},
                        {'name': 'Soins & Santé', 'icon': 'fa-heartbeat', 'order': 6},
                        {'name': 'Vêtements & Accessoires', 'icon': 'fa-tshirt', 'order': 7},
                        {'name': 'Éducation & Dressage', 'icon': 'fa-graduation-cap', 'order': 8},
                    ]
                },
                {
                    'name': 'Services pour animaux',
                    'icon': 'fa-hands-helping',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Garde d\'animaux', 'icon': 'fa-home', 'order': 1},
                        {'name': 'Toilettage', 'icon': 'fa-shower', 'order': 2},
                        {'name': 'Éducation & Comportement', 'icon': 'fa-brain', 'order': 3},
                        {'name': 'Vétérinaire & Soins', 'icon': 'fa-user-md', 'order': 4},
                        {'name': 'Transport animalier', 'icon': 'fa-truck', 'order': 5},
                        {'name': 'Crémation & Sépulture', 'icon': 'fa-monument', 'order': 6},
                    ]
                },
            ]
        },
        {
            'name': 'Matériel Professionnel',
            'icon': 'fa-tools',
            'description': 'Matériel pour entreprises, commerces, agriculture',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 9,
            'subcategories': [
                {
                    'name': 'BTP & Chantier',
                    'icon': 'fa-hard-hat',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Engins de chantier', 'icon': 'fa-tractor', 'order': 1},
                        {'name': 'Matériel BTP', 'icon': 'fa-tools', 'order': 2},
                        {'name': 'Échafaudages & Échafaudage', 'icon': 'fa-hard-hat', 'order': 3},
                        {'name': 'Grues & Matériel de levage', 'icon': 'fa-anchor', 'order': 4},
                        {'name': 'Bétonnières & Malaxeurs', 'icon': 'fa-industry', 'order': 5},
                        {'name': 'Compresseurs & Groupes électrogènes', 'icon': 'fa-bolt', 'order': 6},
                        {'name': 'Outillage professionnel', 'icon': 'fa-wrench', 'order': 7},
                        {'name': 'Signalisation & Sécurité', 'icon': 'fa-exclamation-triangle', 'order': 8},
                    ]
                },
                {
                    'name': 'Agriculture & Espaces verts',
                    'icon': 'fa-tractor',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Tracteurs & Matériel agricole', 'icon': 'fa-tractor', 'order': 1},
                        {'name': 'Moissonneuses-batteuses', 'icon': 'fa-tractor', 'order': 2},
                        {'name': 'Matériel d\'élevage', 'icon': 'fa-cow', 'order': 3},
                        {'name': 'Irrigation & Arrosage', 'icon': 'fa-tint', 'order': 4},
                        {'name': 'Serres & Abris agricoles', 'icon': 'fa-seedling', 'order': 5},
                        {'name': 'Matériel viticole', 'icon': 'fa-wine-glass', 'order': 6},
                        {'name': 'Matériel forestier', 'icon': 'fa-tree', 'order': 7},
                        {'name': 'Équipement apicole', 'icon': 'fa-bee', 'order': 8},
                    ]
                },
                {
                    'name': 'Transport & Manutention',
                    'icon': 'fa-truck-moving',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Chariots élévateurs', 'icon': 'fa-truck', 'order': 1},
                        {'name': 'Transpalettes', 'icon': 'fa-dolly', 'order': 2},
                        {'name': 'Gerbeurs & Préparateurs de commandes', 'icon': 'fa-boxes', 'order': 3},
                        {'name': 'Remorques industrielles', 'icon': 'fa-trailer', 'order': 4},
                        {'name': 'Camions & Véhicules utilitaires', 'icon': 'fa-truck', 'order': 5},
                        {'name': 'Grues & Élévateurs', 'icon': 'fa-anchor', 'order': 6},
                        {'name': 'Bennes & Containers', 'icon': 'fa-trash-alt', 'order': 7},
                        {'name': 'Matériel de levage', 'icon': 'fa-anchor', 'order': 8},
                    ]
                },
                {
                    'name': 'Commerce & Magasin',
                    'icon': 'fa-store',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Vitrines & Présentoirs', 'icon': 'fa-store', 'order': 1},
                        {'name': 'Caisse enregistreuse', 'icon': 'fa-calculator', 'order': 2},
                        {'name': 'Matériel de pesée', 'icon': 'fa-balance-scale', 'order': 3},
                        {'name': 'Équipement frigorifique', 'icon': 'fa-snowflake', 'order': 4},
                        {'name': 'Mobilier de magasin', 'icon': 'fa-chair', 'order': 5},
                        {'name': 'Systèmes de sécurité', 'icon': 'fa-shield-alt', 'order': 6},
                        {'name': 'Matériel de bureau commercial', 'icon': 'fa-print', 'order': 7},
                        {'name': 'Signalétique & Affichage', 'icon': 'fa-sign', 'order': 8},
                    ]
                },
                {
                    'name': 'Industrie & Production',
                    'icon': 'fa-industry',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Machines-outils', 'icon': 'fa-cogs', 'order': 1},
                        {'name': 'Matériel de soudure', 'icon': 'fa-fire', 'order': 2},
                        {'name': 'Équipement de contrôle qualité', 'icon': 'fa-search', 'order': 3},
                        {'name': 'Matériel de laboratoire', 'icon': 'fa-flask', 'order': 4},
                        {'name': 'Robots industriels', 'icon': 'fa-robot', 'order': 5},
                        {'name': 'Systèmes de convoyage', 'icon': 'fa-conveyor-belt', 'order': 6},
                        {'name': 'Matériel de nettoyage industriel', 'icon': 'fa-broom', 'order': 7},
                        {'name': 'Équipement de sécurité industrielle', 'icon': 'fa-hard-hat', 'order': 8},
                    ]
                },
            ]
        },
        {
            'name': 'Services & Prestations',
            'icon': 'fa-handshake',
            'description': 'Services divers, cours, événements, locations',
            'requires_dimensions': False,
            'requires_weight': False,
            'order': 10,
            'subcategories': [
                {
                    'name': 'Cours & Formations',
                    'icon': 'fa-chalkboard-teacher',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Cours particuliers', 'icon': 'fa-user-graduate', 'order': 1},
                        {'name': 'Formations professionnelles', 'icon': 'fa-briefcase', 'order': 2},
                        {'name': 'Cours de langues', 'icon': 'fa-language', 'order': 3},
                        {'name': 'Cours de musique', 'icon': 'fa-music', 'order': 4},
                        {'name': 'Cours de sport', 'icon': 'fa-running', 'order': 5},
                        {'name': 'Cours d\'art & Création', 'icon': 'fa-palette', 'order': 6},
                        {'name': 'Soutien scolaire', 'icon': 'fa-book', 'order': 7},
                        {'name': 'Formations en ligne', 'icon': 'fa-laptop', 'order': 8},
                    ]
                },
                {
                    'name': 'Événements & Animation',
                    'icon': 'fa-birthday-cake',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Traiteurs & Restauration', 'icon': 'fa-utensils', 'order': 1},
                        {'name': 'Animation & Spectacle', 'icon': 'fa-magic', 'order': 2},
                        {'name': 'Location de matériel', 'icon': 'fa-chair', 'order': 3},
                        {'name': 'Décoration événementielle', 'icon': 'fa-palette', 'order': 4},
                        {'name': 'Photographie & Vidéo', 'icon': 'fa-camera', 'order': 5},
                        {'name': 'Salles & Lieux', 'icon': 'fa-home', 'order': 6},
                        {'name': 'Organisation d\'événements', 'icon': 'fa-calendar-alt', 'order': 7},
                        {'name': 'Artistes & Musiciens', 'icon': 'fa-microphone', 'order': 8},
                    ]
                },
                {
                    'name': 'Travaux & Rénovation',
                    'icon': 'fa-paint-roller',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Maçonnerie', 'icon': 'fa-hard-hat', 'order': 1},
                        {'name': 'Plomberie', 'icon': 'fa-faucet', 'order': 2},
                        {'name': 'Électricité', 'icon': 'fa-bolt', 'order': 3},
                        {'name': 'Menuiserie', 'icon': 'fa-tree', 'order': 4},
                        {'name': 'Peinture', 'icon': 'fa-paint-roller', 'order': 5},
                        {'name': 'Carrelage & Revêtements', 'icon': 'fa-square', 'order': 6},
                        {'name': 'Toiture & Façade', 'icon': 'fa-home', 'order': 7},
                        {'name': 'Isolation', 'icon': 'fa-temperature-low', 'order': 8},
                    ]
                },
                {
                    'name': 'Transport & Déménagement',
                    'icon': 'fa-truck-moving',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Déménagement', 'icon': 'fa-boxes', 'order': 1},
                        {'name': 'Transport de marchandises', 'icon': 'fa-truck', 'order': 2},
                        {'name': 'Transport de personnes', 'icon': 'fa-users', 'order': 3},
                        {'name': 'Location de véhicules', 'icon': 'fa-car', 'order': 4},
                        {'name': 'Messagerie & Coursier', 'icon': 'fa-shipping-fast', 'order': 5},
                        {'name': 'Transport international', 'icon': 'fa-plane', 'order': 6},
                        {'name': 'Manutention & Chargement', 'icon': 'fa-dolly', 'order': 7},
                        {'name': 'Stockage & Garde-meubles', 'icon': 'fa-warehouse', 'order': 8},
                    ]
                },
                {
                    'name': 'Informatique & Web',
                    'icon': 'fa-laptop-code',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Développement web', 'icon': 'fa-code', 'order': 1},
                        {'name': 'Design graphique', 'icon': 'fa-palette', 'order': 2},
                        {'name': 'Maintenance informatique', 'icon': 'fa-tools', 'order': 3},
                        {'name': 'Hébergement web', 'icon': 'fa-server', 'order': 4},
                        {'name': 'Marketing digital', 'icon': 'fa-bullhorn', 'order': 5},
                        {'name': 'Formation informatique', 'icon': 'fa-chalkboard-teacher', 'order': 6},
                        {'name': 'Sécurité informatique', 'icon': 'fa-shield-alt', 'order': 7},
                        {'name': 'Rédaction web', 'icon': 'fa-keyboard', 'order': 8},
                    ]
                },
                {
                    'name': 'Bien-être & Santé',
                    'icon': 'fa-spa',
                    'order': 6,
                    'subcategories': [
                        {'name': 'Massage & Relaxation', 'icon': 'fa-hands', 'order': 1},
                        {'name': 'Coaching sportif', 'icon': 'fa-running', 'order': 2},
                        {'name': 'Nutrition & Diététique', 'icon': 'fa-apple-alt', 'order': 3},
                        {'name': 'Thérapie & Psychologie', 'icon': 'fa-brain', 'order': 4},
                        {'name': 'Soins esthétiques', 'icon': 'fa-spa', 'order': 5},
                        {'name': 'Yoga & Méditation', 'icon': 'fa-om', 'order': 6},
                        {'name': 'Médecine douce', 'icon': 'fa-leaf', 'order': 7},
                        {'name': 'Soins à domicile', 'icon': 'fa-home', 'order': 8},
                    ]
                },
            ]
        },
    ]

    # CATÉGORIES POUR LES COLIS (colis)
    colis_categories = [
        {
            'name': 'Petits colis',
            'icon': 'fa-box',
            'description': 'Colis légers et de petite taille',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 1,
            'subcategories': [
                {
                    'name': 'Documents & Papiers',
                    'icon': 'fa-file',
                    'description': 'Lettres, documents, dossiers',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 1,
                    'subcategories': [
                        {'name': 'Lettres recommandées', 'icon': 'fa-envelope', 'order': 1},
                        {'name': 'Documents officiels', 'icon': 'fa-file-contract', 'order': 2},
                        {'name': 'Dossiers professionnels', 'icon': 'fa-briefcase', 'order': 3},
                        {'name': 'Livres & Manuscrits', 'icon': 'fa-book', 'order': 4},
                        {'name': 'Archives', 'icon': 'fa-archive', 'order': 5},
                    ]
                },
                {
                    'name': 'Vêtements & Textiles',
                    'icon': 'fa-tshirt',
                    'description': 'Vêtements, tissus, linge',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Vêtements légers', 'icon': 'fa-tshirt', 'order': 1},
                        {'name': 'Linge de maison', 'icon': 'fa-bed', 'order': 2},
                        {'name': 'Tissus & Coupons', 'icon': 'fa-cut', 'order': 3},
                        {'name': 'Accessoires mode', 'icon': 'fa-glasses', 'order': 4},
                    ]
                },
                {
                    'name': 'Électronique portable',
                    'icon': 'fa-mobile-alt',
                    'description': 'Appareils électroniques petits',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Smartphones & Tablettes', 'icon': 'fa-tablet-alt', 'order': 1},
                        {'name': 'Ordinateurs portables', 'icon': 'fa-laptop', 'order': 2},
                        {'name': 'Appareils photo', 'icon': 'fa-camera', 'order': 3},
                        {'name': 'Accessoires électroniques', 'icon': 'fa-headphones', 'order': 4},
                    ]
                },
                {
                    'name': 'Livres & Médias',
                    'icon': 'fa-book',
                    'description': 'Livres, CD, DVD',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Livres', 'icon': 'fa-book', 'order': 1},
                        {'name': 'CD & DVD', 'icon': 'fa-compact-disc', 'order': 2},
                        {'name': 'Jeux vidéo', 'icon': 'fa-gamepad', 'order': 3},
                        {'name': 'Magazines & Revues', 'icon': 'fa-newspaper', 'order': 4},
                    ]
                },
                {
                    'name': 'Bijoux & Objets de valeur',
                    'icon': 'fa-gem',
                    'description': 'Petits objets précieux',
                    'requires_dimensions': False,
                    'requires_weight': False,
                    'order': 5,
                    'subcategories': [
                        {'name': 'Bijoux', 'icon': 'fa-gem', 'order': 1},
                        {'name': 'Montres', 'icon': 'fa-clock', 'order': 2},
                        {'name': 'Objets de collection', 'icon': 'fa-chess-queen', 'order': 3},
                        {'name': 'Pièces & Timbres', 'icon': 'fa-money-bill', 'order': 4},
                    ]
                },
            ]
        },
        {
            'name': 'Colis moyens',
            'icon': 'fa-box-open',
            'description': 'Colis de taille et poids moyens',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 2,
            'subcategories': [
                {
                    'name': 'Électroménager petit',
                    'icon': 'fa-blender',
                    'description': 'Petits appareils électroménagers',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Micro-ondes', 'icon': 'fa-fire', 'order': 1},
                        {'name': 'Aspirateurs', 'icon': 'fa-broom', 'order': 2},
                        {'name': 'Cafetières & Bouilloires', 'icon': 'fa-coffee', 'order': 3},
                        {'name': 'Mixeurs & Robots', 'icon': 'fa-blender', 'order': 4},
                        {'name': 'Grille-pain & Friteuses', 'icon': 'fa-bread-slice', 'order': 5},
                    ]
                },
                {
                    'name': 'Informatique & Bureau',
                    'icon': 'fa-desktop',
                    'description': 'Matériel informatique de bureau',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Ordinateurs fixes', 'icon': 'fa-desktop', 'order': 1},
                        {'name': 'Écrans & Moniteurs', 'icon': 'fa-tv', 'order': 2},
                        {'name': 'Imprimantes & Scanners', 'icon': 'fa-print', 'order': 3},
                        {'name': 'Serveurs & NAS', 'icon': 'fa-server', 'order': 4},
                        {'name': 'Mobilier de bureau', 'icon': 'fa-chair', 'order': 5},
                    ]
                },
                {
                    'name': 'Son & Hi-Fi',
                    'icon': 'fa-volume-up',
                    'description': 'Équipement audio',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Enceintes', 'icon': 'fa-volume-up', 'order': 1},
                        {'name': 'Amplificateurs', 'icon': 'fa-broadcast-tower', 'order': 2},
                        {'name': 'Chaînes Hi-Fi', 'icon': 'fa-music', 'order': 3},
                        {'name': 'Platines vinyle', 'icon': 'fa-compact-disc', 'order': 4},
                        {'name': 'Home cinéma', 'icon': 'fa-film', 'order': 5},
                    ]
                },
                {
                    'name': 'Jeux & Jouets',
                    'icon': 'fa-gamepad',
                    'description': 'Jouets et jeux de taille moyenne',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Jeux de société', 'icon': 'fa-chess-board', 'order': 1},
                        {'name': 'Jouets enfants', 'icon': 'fa-robot', 'order': 2},
                        {'name': 'Consoles de jeux', 'icon': 'fa-gamepad', 'order': 3},
                        {'name': 'Vélos enfants', 'icon': 'fa-bicycle', 'order': 4},
                        {'name': 'Jeux extérieurs', 'icon': 'fa-tree', 'order': 5},
                    ]
                },
                {
                    'name': 'Outillage & Bricolage',
                    'icon': 'fa-tools',
                    'description': 'Outils et matériel de bricolage',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Outils électroportatifs', 'icon': 'fa-screwdriver', 'order': 1},
                        {'name': 'Outillage à main', 'icon': 'fa-hammer', 'order': 2},
                        {'name': 'Matériaux de construction', 'icon': 'fa-hard-hat', 'order': 3},
                        {'name': 'Peinture & Revêtements', 'icon': 'fa-paint-roller', 'order': 4},
                        {'name': 'Quincaillerie', 'icon': 'fa-cogs', 'order': 5},
                    ]
                },
            ]
        },
        {
            'name': 'Gros colis',
            'icon': 'fa-boxes',
            'description': 'Colis volumineux et lourds',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 3,
            'subcategories': [
                {
                    'name': 'Meubles',
                    'icon': 'fa-couch',
                    'description': 'Meubles et ameublement',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Canapés & Fauteuils', 'icon': 'fa-couch', 'order': 1},
                        {'name': 'Tables & Bureau', 'icon': 'fa-table', 'order': 2},
                        {'name': 'Armoires & Dressings', 'icon': 'fa-archive', 'order': 3},
                        {'name': 'Lits & Sommiers', 'icon': 'fa-bed', 'order': 4},
                        {'name': 'Étagères & Bibliothèques', 'icon': 'fa-book', 'order': 5},
                    ]
                },
                {
                    'name': 'Électroménager gros',
                    'icon': 'fa-snowflake',
                    'description': 'Gros appareils électroménagers',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Réfrigérateurs', 'icon': 'fa-snowflake', 'order': 1},
                        {'name': 'Laves-linge & Sèche-linge', 'icon': 'fa-soap', 'order': 2},
                        {'name': 'Lave-vaisselle', 'icon': 'fa-shower', 'order': 3},
                        {'name': 'Cuisinières & Fours', 'icon': 'fa-fire', 'order': 4},
                        {'name': 'Congélateurs', 'icon': 'fa-icicles', 'order': 5},
                    ]
                },
                {
                    'name': 'TV & Écrans grands',
                    'icon': 'fa-tv',
                    'description': 'Téléviseurs et grands écrans',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Téléviseurs LED/LCD', 'icon': 'fa-tv', 'order': 1},
                        {'name': 'Écrans plasma', 'icon': 'fa-tv', 'order': 2},
                        {'name': 'Projecteurs', 'icon': 'fa-film', 'order': 3},
                        {'name': 'Écrans incurvés', 'icon': 'fa-tv', 'order': 4},
                        {'name': 'Téléviseurs OLED', 'icon': 'fa-tv', 'order': 5},
                    ]
                },
                {
                    'name': 'Vélos & Mobilité',
                    'icon': 'fa-bicycle',
                    'description': 'Vélos et moyens de déplacement',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Vélos adultes', 'icon': 'fa-bicycle', 'order': 1},
                        {'name': 'Vélos électriques', 'icon': 'fa-bolt', 'order': 2},
                        {'name': 'Trottinettes électriques', 'icon': 'fa-scooter', 'order': 3},
                        {'name': 'Gyropodes & Hoverboards', 'icon': 'fa-balance-scale', 'order': 4},
                        {'name': 'Accessoires vélos', 'icon': 'fa-cogs', 'order': 5},
                    ]
                },
                {
                    'name': 'Sports & Loisirs',
                    'icon': 'fa-dumbbell',
                    'description': 'Équipement sportif volumineux',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Matériel de fitness', 'icon': 'fa-dumbbell', 'order': 1},
                        {'name': 'Tapis de sport', 'icon': 'fa-square', 'order': 2},
                        {'name': 'Canots & Kayaks', 'icon': 'fa-ship', 'order': 3},
                        {'name': 'Planches de surf', 'icon': 'fa-water', 'order': 4},
                        {'name': 'Matériel de camping', 'icon': 'fa-campground', 'order': 5},
                    ]
                },
            ]
        },
        {
            'name': 'Très gros colis',
            'icon': 'fa-pallet',
            'description': 'Colis très volumineux, palettes',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 4,
            'subcategories': [
                {
                    'name': 'Palettes',
                    'icon': 'fa-pallet',
                    'description': 'Colis sur palette',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Palettes standard', 'icon': 'fa-pallet', 'order': 1},
                        {'name': 'Palettes Europe', 'icon': 'fa-pallet', 'order': 2},
                        {'name': 'Palettes industries', 'icon': 'fa-industry', 'order': 3},
                        {'name': 'Palettes alimentaires', 'icon': 'fa-utensils', 'order': 4},
                        {'name': 'Palettes pharmaceutiques', 'icon': 'fa-pills', 'order': 5},
                    ]
                },
                {
                    'name': 'Meubles très volumineux',
                    'icon': 'fa-bed',
                    'description': 'Meubles de grande taille',
                    'order': 2,
                    'subcategories': [
                        {'name': 'Armoires grand format', 'icon': 'fa-archive', 'order': 1},
                        {'name': 'Canapés d\'angle', 'icon': 'fa-couch', 'order': 2},
                        {'name': 'Lits double place', 'icon': 'fa-bed', 'order': 3},
                        {'name': 'Cuisines équipées', 'icon': 'fa-utensils', 'order': 4},
                        {'name': 'Dressing sur mesure', 'icon': 'fa-tshirt', 'order': 5},
                    ]
                },
                {
                    'name': 'Équipement professionnel',
                    'icon': 'fa-industry',
                    'description': 'Matériel professionnel lourd',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Machines industrielles', 'icon': 'fa-cogs', 'order': 1},
                        {'name': 'Matériel médical', 'icon': 'fa-heartbeat', 'order': 2},
                        {'name': 'Équipement de restauration', 'icon': 'fa-utensils', 'order': 3},
                        {'name': 'Matériel agricole', 'icon': 'fa-tractor', 'order': 4},
                        {'name': 'Outillage professionnel', 'icon': 'fa-tools', 'order': 5},
                    ]
                },
                {
                    'name': 'Véhicules & Pièces',
                    'icon': 'fa-car',
                    'description': 'Pièces automobiles volumineuses',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Moteurs & Boîtes de vitesse', 'icon': 'fa-cogs', 'order': 1},
                        {'name': 'Carrosseries', 'icon': 'fa-car', 'order': 2},
                        {'name': 'Pneumatiques & Jantes', 'icon': 'fa-tire', 'order': 3},
                        {'name': 'Pièces moteur', 'icon': 'fa-cogs', 'order': 4},
                        {'name': 'Suspensions', 'icon': 'fa-car', 'order': 5},
                    ]
                },
                {
                    'name': 'Conteneurs & Caisses',
                    'icon': 'fa-container-storage',
                    'description': 'Conteneurs et caisses de transport',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Conteneurs maritimes', 'icon': 'fa-ship', 'order': 1},
                        {'name': 'Caisses en bois', 'icon': 'fa-tree', 'order': 2},
                        {'name': 'Conteneurs aériens', 'icon': 'fa-plane', 'order': 3},
                        {'name': 'Caisses métalliques', 'icon': 'fa-box', 'order': 4},
                        {'name': 'Conteneurs frigorifiques', 'icon': 'fa-snowflake', 'order': 5},
                    ]
                },
            ]
        },
        {
            'name': 'Spécial & Fragile',
            'icon': 'fa-exclamation-triangle',
            'description': 'Colis nécessitant un traitement spécial',
            'requires_dimensions': True,
            'requires_weight': True,
            'order': 5,
            'subcategories': [
                {
                    'name': 'Objets fragiles',
                    'icon': 'fa-glass-martini',
                    'description': 'Colis nécessitant une manipulation délicate',
                    'order': 1,
                    'subcategories': [
                        {'name': 'Verre & Cristal', 'icon': 'fa-glass-martini', 'order': 1},
                        {'name': 'Céramique & Porcelaine', 'icon': 'fa-mug-hot', 'order': 2},
                        {'name': 'Œuvres d\'art', 'icon': 'fa-palette', 'order': 3},
                        {'name': 'Instruments de musique', 'icon': 'fa-guitar', 'order': 4},
                        {'name': 'Électronique sensible', 'icon': 'fa-microchip', 'order': 5},
                    ]
                },
                {
                    'name': 'Alimentaire',
                    'icon': 'fa-utensils',
                    'description': 'Produits alimentaires',
                    'requires_dimensions': True,
                    'requires_weight': True,
                    'order': 2,
                    'subcategories': [
                        {'name': 'Produits frais', 'icon': 'fa-apple-alt', 'order': 1},
                        {'name': 'Produits surgelés', 'icon': 'fa-snowflake', 'order': 2},
                        {'name': 'Vins & Spiritueux', 'icon': 'fa-wine-glass', 'order': 3},
                        {'name': 'Produits locaux', 'icon': 'fa-tractor', 'order': 4},
                        {'name': 'Aliments spéciaux', 'icon': 'fa-heart', 'order': 5},
                    ]
                },
                {
                    'name': 'Médical & Pharmaceutique',
                    'icon': 'fa-heartbeat',
                    'description': 'Produits médicaux et pharmaceutiques',
                    'order': 3,
                    'subcategories': [
                        {'name': 'Médicaments', 'icon': 'fa-pills', 'order': 1},
                        {'name': 'Matériel médical', 'icon': 'fa-stethoscope', 'order': 2},
                        {'name': 'Équipement hospitalier', 'icon': 'fa-hospital', 'order': 3},
                        {'name': 'Produits biologiques', 'icon': 'fa-dna', 'order': 4},
                        {'name': 'Vaccins', 'icon': 'fa-syringe', 'order': 5},
                    ]
                },
                {
                    'name': 'Dangereux & Réglementé',
                    'icon': 'fa-radiation',
                    'description': 'Marchandises dangereuses',
                    'order': 4,
                    'subcategories': [
                        {'name': 'Produits chimiques', 'icon': 'fa-flask', 'order': 1},
                        {'name': 'Batteries & Piles', 'icon': 'fa-battery-full', 'order': 2},
                        {'name': 'Matériaux inflammables', 'icon': 'fa-fire', 'order': 3},
                        {'name': 'Gaz comprimés', 'icon': 'fa-wind', 'order': 4},
                        {'name': 'Matériaux radioactifs', 'icon': 'fa-radiation', 'order': 5},
                    ]
                },
                {
                    'name': 'Vivant',
                    'icon': 'fa-paw',
                    'description': 'Animaux et plantes vivantes',
                    'order': 5,
                    'subcategories': [
                        {'name': 'Animaux de compagnie', 'icon': 'fa-dog', 'order': 1},
                        {'name': 'Animaux d\'élevage', 'icon': 'fa-horse', 'order': 2},
                        {'name': 'Plantes & Fleurs', 'icon': 'fa-leaf', 'order': 3},
                        {'name': 'Aquariums', 'icon': 'fa-fish', 'order': 4},
                        {'name': 'Insectes & Reptiles', 'icon': 'fa-dragon', 'order': 5},
                    ]
                },
            ]
        },
    ]

    print(f"\n{Colors.BOLD}1. Création des catégories pour les annonces (ads){Colors.END}")
    create_categories(AdCategory, ad_categories)

    print(f"\n{Colors.BOLD}2. Création des catégories pour les colis (colis){Colors.END}")
    create_categories(ColisCategory, colis_categories)

    # Statistiques
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== STATISTIQUES FINALES ==={Colors.END}")
    print(f"Catégories annonces: {AdCategory.objects.count()}")
    print(f"Catégories colis: {ColisCategory.objects.count()}")
    print(f"{Colors.GREEN}✓ Population terminée avec succès !{Colors.END}")

if __name__ == '__main__':
    main()