from django.core.management.base import BaseCommand
from ads.models import AdImage
from PIL import Image
import os
from io import BytesIO
from django.core.files.base import ContentFile

class Command(BaseCommand):
    help = 'Génère les thumbnails manquantes pour toutes les AdImage'

    def handle(self, *args, **options):
        # Récupérer toutes les images sans thumbnail
        images = AdImage.objects.filter(thumbnail__isnull=True).exclude(image__isnull=True)

        total = images.count()
        self.stdout.write(f"Génération des thumbnails pour {total} images...")

        success = 0
        errors = 0

        for i, ad_image in enumerate(images, 1):
            try:
                if ad_image.image:
                    # Ouvrir l'image originale
                    img = Image.open(ad_image.image.path)

                    # Calculer les dimensions de la miniature (200x200)
                    img.thumbnail((200, 200))

                    # Préparer le nom du fichier thumbnail
                    thumb_name, thumb_extension = os.path.splitext(ad_image.image.name)
                    thumb_extension = thumb_extension.lower()
                    thumb_filename = thumb_name + '_thumb' + thumb_extension

                    # Déterminer le format
                    if thumb_extension in ['.jpg', '.jpeg']:
                        FTYPE = 'JPEG'
                    elif thumb_extension == '.gif':
                        FTYPE = 'GIF'
                    elif thumb_extension == '.png':
                        FTYPE = 'PNG'
                    elif thumb_extension == '.webp':
                        FTYPE = 'WEBP'
                    else:
                        FTYPE = 'JPEG'

                    # Convertir en RGB si nécessaire
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background

                    # Sauvegarder dans un buffer
                    temp_thumb = BytesIO()
                    img.save(temp_thumb, FTYPE, quality=85)
                    temp_thumb.seek(0)

                    # Sauvegarder la miniature
                    ad_image.thumbnail.save(
                        thumb_filename,
                        ContentFile(temp_thumb.read()),
                        save=False
                    )
                    temp_thumb.close()

                    # Sauvegarder l'objet
                    ad_image.save()

                    success += 1
                    self.stdout.write(f"[{i}/{total}] ✓ Miniature générée pour l'image {ad_image.id}")

            except FileNotFoundError:
                self.stdout.write(f"[{i}/{total}] ✗ Fichier image non trouvé pour l'image {ad_image.id}")
                errors += 1
            except Exception as e:
                self.stdout.write(f"[{i}/{total}] ✗ Erreur pour l'image {ad_image.id}: {str(e)}")
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"Terminé ! {success} succès, {errors} erreurs"
        ))