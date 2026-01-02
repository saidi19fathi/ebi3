"""
Signaux pour la détection automatique des modifications de contenu
et déclenchement des traductions.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings

# NE PAS importer les modèles ici directement pour éviter les imports circulaires
# Nous utiliserons des imports paresseux dans les fonctions

logger = logging.getLogger(__name__)

# Signal personnalisé pour déclencher manuellement une traduction
translate_content_signal = Signal()

# Registre des modèles et champs traduisibles
_translatable_models = {}


def register_translatable_model(model_class, fields):
    """
    Enregistre un modèle pour la traduction automatique.

    Args:
        model_class: Classe du modèle Django
        fields: Liste des noms de champs à traduire
    """
    app_label = model_class._meta.app_label
    model_name = model_class._meta.model_name
    key = f"{app_label}.{model_name}"

    _translatable_models[key] = {
        'model_class': model_class,
        'fields': fields,
        'app_label': app_label,
        'model_name': model_name,
    }

    logger.info(f"Modèle enregistré pour traduction: {key} - Champs: {fields}")


def get_translatable_fields_for_model(model_class):
    """Retourne les champs traduisibles d'un modèle."""
    app_label = model_class._meta.app_label
    model_name = model_class._meta.model_name
    key = f"{app_label}.{model_name}"

    return _translatable_models.get(key, {}).get('fields', [])


def should_translate_field(field_name, field_value):
    """
    Détermine si un champ doit être traduit.

    Args:
        field_name: Nom du champ
        field_value: Valeur du champ

    Returns:
        bool: True si le champ doit être traduit
    """
    if not field_value or not isinstance(field_value, str):
        return False

    # Exclusions basiques
    exclusions = ['url', 'email', 'code', 'id', 'password', 'token']
    if any(excl in field_name.lower() for excl in exclusions):
        return False

    # Vérifie la longueur minimale
    if len(field_value.strip()) < 3:
        return False

    # Vérifie si c'est principalement numérique
    if field_value.replace('.', '').replace(',', '').isdigit():
        return False

    return True


def detect_language(text):
    """
    Détecte la langue d'un texte (simplifié).

    Args:
        text: Texte à analyser

    Returns:
        str: Code de langue détecté
    """
    if not text or len(text) < 10:
        return settings.LANGUAGE_CODE

    # Détection simplifiée
    text_lower = text.lower()

    # Mots communs par langue
    language_indicators = {
        'fr': ['le', 'la', 'les', 'un', 'une', 'des', 'et', 'est'],
        'en': ['the', 'a', 'an', 'and', 'is', 'are', 'to', 'of'],
        'ar': ['ال', 'في', 'من', 'على', 'إلى', 'أن', 'كان'],
        'es': ['el', 'la', 'los', 'las', 'un', 'una', 'y', 'es'],
        'de': ['der', 'die', 'das', 'und', 'ist', 'sind', 'ein'],
        'it': ['il', 'la', 'lo', 'gli', 'le', 'e', 'è', 'un'],
        'pt': ['o', 'a', 'os', 'as', 'e', 'é', 'um', 'uma'],
        'ru': ['и', 'в', 'не', 'на', 'я', 'он', 'с', 'что'],
        'zh': ['的', '是', '在', '和', '了', '有', '我', '他'],
        'tr': ['ve', 'bir', 'bu', 'şey', 'için', 'ama', 'gibi'],
        'nl': ['de', 'het', 'een', 'en', 'is', 'van', 'op', 'te'],
    }

    scores = {}
    for lang, words in language_indicators.items():
        score = sum(1 for word in words if word in text_lower)
        if score > 0:
            scores[lang] = score

    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]

    return settings.LANGUAGE_CODE


def get_target_languages(source_language):
    """
    Retourne la liste des langues cibles.

    Args:
        source_language: Langue source

    Returns:
        list: Codes des langues cibles
    """
    if hasattr(settings, 'DEEPSEEK_CONFIG'):
        enabled_languages = settings.DEEPSEEK_CONFIG.get('ENABLED_LANGUAGES', [])
    else:
        enabled_languages = ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl']

    # Retire la langue source
    target_languages = [lang for lang in enabled_languages if lang != source_language]
    return target_languages


@receiver(post_save)
def auto_translate_on_save(sender, instance, created, **kwargs):
    """
    Déclenche la traduction automatique après sauvegarde.
    """
    # Import paresseux pour éviter les imports circulaires
    from .models import TranslationJob, Translation, TranslationSettings, APILog

    # Évite les boucles infinies
    if sender in [TranslationJob, Translation, TranslationSettings, APILog]:
        return

    # Vérifie si le modèle est enregistré pour traduction
    app_label = sender._meta.app_label
    model_name = sender._meta.model_name
    model_key = f"{app_label}.{model_name}"

    if model_key not in _translatable_models:
        return

    # Vérifie si la traduction automatique est activée
    try:
        global_settings = TranslationSettings.objects.filter(user=None).first()
        if global_settings and not global_settings.auto_translate_enabled:
            logger.debug("Traduction automatique désactivée globalement")
            return
    except Exception as e:
        logger.warning(f"Erreur vérification paramètres globaux: {e}")

    translatable_fields = _translatable_models[model_key]['fields']

    for field_name in translatable_fields:
        if not hasattr(instance, field_name):
            continue

        field_value = getattr(instance, field_name)

        if not should_translate_field(field_name, field_value):
            continue

        # Vérifie si une traduction existe déjà
        content_type = ContentType.objects.get_for_model(sender)
        existing_translations = Translation.objects.filter(
            content_type=content_type,
            object_id=str(instance.pk),
            field_name=field_name,
            is_current=True
        ).exists()

        if existing_translations and not created:
            logger.debug(f"Traductions existantes pour {model_key}.{field_name}")
            continue

        # Crée un travail de traduction
        source_language = detect_language(field_value)
        target_languages = get_target_languages(source_language)

        if not target_languages:
            logger.debug(f"Aucune langue cible pour {source_language}")
            continue

        try:
            translation_job = TranslationJob.objects.create(
                content_type=content_type,
                object_id=str(instance.pk),
                field_name=field_name,
                original_text=field_value,
                source_language=source_language,
                target_languages=target_languages,
                total_characters=len(field_value),
                status='pending',
            )

            logger.info(f"Travail créé: {translation_job.id} pour {model_key}.{field_name}")

            # Démarre le traitement asynchrone
            from .tasks import process_translation_job
            process_translation_job.delay(translation_job.id)

        except Exception as e:
            logger.error(f"Erreur création travail traduction: {e}")


@receiver(translate_content_signal)
def manual_translation_trigger(sender, instance, field_name, **kwargs):
    """
    Déclenche une traduction manuellement via signal.
    """
    # Import paresseux
    from .models import TranslationJob, TranslationSettings

    if not hasattr(instance, field_name):
        logger.error(f"Champ {field_name} inexistant sur {instance}")
        return

    field_value = getattr(instance, field_name)

    if not should_translate_field(field_name, field_value):
        logger.debug(f"Champ non traduisible: {field_name}")
        return

    content_type = ContentType.objects.get_for_model(type(instance))
    source_language = detect_language(field_value)
    target_languages = get_target_languages(source_language)

    if not target_languages:
        logger.debug(f"Aucune langue cible pour {source_language}")
        return

    try:
        translation_job = TranslationJob.objects.create(
            content_type=content_type,
            object_id=str(instance.pk),
            field_name=field_name,
            original_text=field_value,
            source_language=source_language,
            target_languages=target_languages,
            total_characters=len(field_value),
            status='pending',
        )

        logger.info(f"Traduction manuelle déclenchée: {translation_job.id}")

        from .tasks import process_translation_job
        process_translation_job.delay(translation_job.id)

    except Exception as e:
        logger.error(f"Erreur traduction manuelle: {e}")


def get_content_translations(instance, field_name=None, language=None):
    """
    Récupère les traductions d'un contenu.

    Args:
        instance: Instance du modèle
        field_name: Champ spécifique (optionnel)
        language: Langue spécifique (optionnel)

    Returns:
        dict: Traductions organisées par champ et langue
    """
    # Import paresseux
    from .models import Translation

    content_type = ContentType.objects.get_for_model(type(instance))
    translations = Translation.objects.filter(
        content_type=content_type,
        object_id=str(instance.pk),
        is_current=True
    )

    if field_name:
        translations = translations.filter(field_name=field_name)

    if language:
        translations = translations.filter(language=language)

    result = {}
    for trans in translations:
        if trans.field_name not in result:
            result[trans.field_name] = {}
        result[trans.field_name][trans.language] = {
            'text': trans.translated_text,
            'quality': trans.quality,
            'confidence': trans.confidence_score,
            'created_at': trans.created_at,
        }

    return result


def get_available_languages(instance, field_name=None):
    """
    Retourne les langues disponibles pour un contenu.

    Args:
        instance: Instance du modèle
        field_name: Champ spécifique (optionnel)

    Returns:
        list: Codes de langue disponibles
    """
    translations = get_content_translations(instance, field_name)
    languages = set()

    for field_data in translations.values():
        languages.update(field_data.keys())

    return sorted(list(languages))