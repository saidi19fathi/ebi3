"""
Tags de template pour l'affichage des traductions.
"""
from django import template
from django.utils.translation import get_language
from django.contrib.contenttypes.models import ContentType

from translations.models import Translation

register = template.Library()


@register.simple_tag(takes_context=True)
def get_translation(context, instance, field_name, language=None):
    """
    Récupère la traduction d'un champ pour une langue spécifique.

    Usage:
        {% get_translation instance "title" as translated_title %}
        {% get_translation instance "description" "fr" as french_desc %}
    """
    if not instance or not field_name:
        return ""

    # Détermine la langue
    if not language:
        language = get_language()

    # Récupère la traduction
    content_type = ContentType.objects.get_for_model(type(instance))

    try:
        translation = Translation.objects.get(
            content_type=content_type,
            object_id=str(instance.pk),
            field_name=field_name,
            language=language,
            is_current=True
        )
        return translation.translated_text
    except Translation.DoesNotExist:
        # Fallback: retourne la valeur originale
        return getattr(instance, field_name, "")


@register.filter
def translate_field(instance, field_name):
    """
    Filtre pour traduire un champ dans la langue courante.

    Usage:
        {{ article.title|translate_field }}
    """
    if not instance or not field_name:
        return ""

    language = get_language()
    content_type = ContentType.objects.get_for_model(type(instance))

    try:
        translation = Translation.objects.get(
            content_type=content_type,
            object_id=str(instance.pk),
            field_name=field_name,
            language=language,
            is_current=True
        )
        return translation.translated_text
    except Translation.DoesNotExist:
        return getattr(instance, field_name, "")


@register.inclusion_tag('translations/translation_badge.html')
def translation_badge(instance, field_name=None):
    """
    Affiche un badge indiquant si le contenu est traduit automatiquement.

    Usage:
        {% translation_badge article %}
        {% translation_badge article "title" %}
    """
    if not instance:
        return {'show_badge': False}

    content_type = ContentType.objects.get_for_model(type(instance))
    language = get_language()

    # Vérifie si c'est une traduction automatique
    is_auto_translated = False

    if field_name:
        try:
            translation = Translation.objects.get(
                content_type=content_type,
                object_id=str(instance.pk),
                field_name=field_name,
                language=language,
                is_current=True
            )
            is_auto_translated = translation.quality == 'auto'
        except Translation.DoesNotExist:
            pass
    else:
        # Vérifie tous les champs traduits
        translations = Translation.objects.filter(
            content_type=content_type,
            object_id=str(instance.pk),
            language=language,
            is_current=True,
            quality='auto'
        )
        is_auto_translated = translations.exists()

    return {
        'show_badge': is_auto_translated,
        'field_name': field_name,
    }


@register.simple_tag
def available_languages(instance, field_name=None):
    """
    Retourne les langues disponibles pour un contenu.

    Usage:
        {% available_languages article as langs %}
    """
    if not instance:
        return []

    content_type = ContentType.objects.get_for_model(type(instance))
    queryset = Translation.objects.filter(
        content_type=content_type,
        object_id=str(instance.pk),
        is_current=True
    )

    if field_name:
        queryset = queryset.filter(field_name=field_name)

    languages = queryset.values_list('language', flat=True).distinct()
    return list(languages)


@register.simple_tag(takes_context=True)
def language_selector(context):
    """
    Génère un sélecteur de langue basé sur les langues disponibles.

    Usage:
        {% language_selector %}
    """
    request = context.get('request')
    if not request:
        return []

    current_language = get_language()
    supported_languages = getattr(settings, 'SUPPORTED_LANGUAGES', [])

    if not supported_languages:
        from django.conf.locale import LANG_INFO
        supported_languages = [
            (code, LANG_INFO.get(code, {}).get('name', code))
            for code, _ in settings.LANGUAGES
        ]

    languages = []
    for code, name in supported_languages:
        languages.append({
            'code': code,
            'name': name,
            'active': code == current_language,
            'url': f'/{code}{request.path}' if not request.path.startswith(f'/{code}') else request.path
        })

    return languages


@register.filter
def has_translation(instance, language=None):
    """
    Vérifie si une traduction existe pour une langue.

    Usage:
        {% if article|has_translation:"fr" %}
    """
    if not instance:
        return False

    if not language:
        language = get_language()

    content_type = ContentType.objects.get_for_model(type(instance))

    return Translation.objects.filter(
        content_type=content_type,
        object_id=str(instance.pk),
        language=language,
        is_current=True
    ).exists()