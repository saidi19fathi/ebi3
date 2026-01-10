# ads/management/commands/update_ad_counts.py
from django.core.management.base import BaseCommand
from ads.models import Category, Ad

class Command(BaseCommand):
    help = 'Met à jour les compteurs d\'annonces pour toutes les catégories'

    def handle(self, *args, **kwargs):
        categories = Category.objects.all()

        for category in categories:
            old_count = category.ad_count
            category.update_ad_count()
            category.refresh_from_db()

            if old_count != category.ad_count:
                self.stdout.write(
                    self.style.SUCCESS(f'Catégorie {category.name}: {old_count} → {category.ad_count}')
                )

        self.stdout.write(self.style.SUCCESS('Compteurs mis à jour avec succès!'))