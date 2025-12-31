# ~/ebi3/colis/management/commands/generate_sitemaps.py
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from colis.sitemaps import SitemapGenerator
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Génère les fichiers sitemap XML pour l\'application colis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'static', 'sitemaps'),
            help='Répertoire de sortie pour les fichiers sitemap'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']

        # Créer le répertoire s'il n'existe pas
        os.makedirs(output_dir, exist_ok=True)

        # Générer l'index des sitemaps
        index_content = SitemapGenerator.generate_sitemap_index()
        index_path = os.path.join(output_dir, 'sitemap_index.xml')

        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)

        self.stdout.write(
            self.style.SUCCESS(f'Index sitemap généré: {index_path}')
        )

        # Afficher les statistiques
        stats = SitemapGenerator.get_sitemap_stats()
        self.stdout.write(f"\nStatistiques des sitemaps:")
        self.stdout.write(f"Total URLs: {stats['total_urls']}")

        for sitemap_name, count in stats['by_type'].items():
            self.stdout.write(f"  {sitemap_name}: {count} URLs")