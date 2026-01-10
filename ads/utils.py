from django.db.models import Q
from .models import Category

def get_main_categories():
    """
    Retourne les catégories principales basées sur la structure de données fournie.
    Cette fonction identifie les catégories de haut niveau.
    """
    # Liste des catégories principales basées sur vos données
    main_category_names = [
        'Véhicules',
        'Immobilier',
        'Mode & Accessoires',
        'Maison & Jardin',
        'Électronique & Multimédia',
        'Loisirs & Divertissements',
        'Matériel Professionnel',
        'Services professionnels',
        'Services & Prestations',
        'Animaux',
        'Événements & Animation',
        'Bien-être & Santé',
        'Collection',
        'Luxe & Créateurs',
        'Emploi',
        'Photo & Vidéo',
        'Instruments de musique',
        'Caravanes & Mobil-homes',
        'Vêtements enfants',
        'Transport & Manutention',
        'Chaussures',
        'Vêtements hommes',
        'Voitures',
        'Jeux vidéo & Consoles',
        'Services à la personne',
        'Électroménager',
        'Transport & Déménagement',
        'Informatique & Web',
        'BTP & Chantier',
        'Utilitaires & Poids lourds',
        'Industrie & Production',
        'Travaux & Rénovation',
        'Locations',
        'Accessoires & Bijoux',
        'Motos & Scooters',
        'Téléphonie',
        'Ameublement',
        'Image & Son',
        'Agriculture & Espaces verts',
        'Cuisine & Arts de la table',
        'Commerce & Magasin',
        'Jardin & Extérieur',
        'Offres d emploi',
        'Informatique',
        'Bricolage',
        'Immobilier neuf',
        'Vêtements femmes',
        'Pièces & Accessoires auto',
        'Décoration',
        'Jeux & Jouets',
        'Livres & Magazines',
        'Nautisme',
        '2 Roues'
    ]

    # Récupérer ces catégories depuis la base de données
    main_categories = Category.objects.filter(
        name__in=main_category_names,
        is_active=True
    ).order_by('name')

    # Si on ne trouve pas toutes les catégories, ajouter les catégories sans parent
    if main_categories.count() < 20:  # Si moins de 20 catégories trouvées
        root_categories = Category.objects.filter(
            parent__isnull=True,
            is_active=True
        ).order_by('name')
        main_categories = (main_categories | root_categories).distinct().order_by('name')

    return main_categories