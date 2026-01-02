"""
Formulaires pour le module de traduction.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .models import TranslationSettings


class ManualTranslationForm(forms.Form):
    """Formulaire pour la traduction manuelle."""

    content_type = forms.ChoiceField(
        label=_("Type de contenu"),
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    object_id = forms.CharField(
        label=_("ID de l'objet"),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID'})
    )

    field_name = forms.ChoiceField(
        label=_("Champ à traduire"),
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    target_languages = forms.MultipleChoiceField(
        label=_("Langues cibles"),
        choices=[],
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False,
        help_text=_("Laissez vide pour toutes les langues supportées")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialise les choix de langue
        if hasattr(settings, 'DEEPSEEK_CONFIG'):
            languages = settings.DEEPSEEK_CONFIG.get('ENABLED_LANGUAGES', [])
        else:
            languages = ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl']

        language_choices = [(lang, lang.upper()) for lang in languages]
        self.fields['target_languages'].choices = language_choices

        # Initialise les choix de modèle (à compléter dynamiquement)
        self.fields['content_type'].choices = self._get_content_type_choices()
        self.fields['field_name'].choices = self._get_field_choices()

    def _get_content_type_choices(self):
        """Retourne la liste des types de contenu traduisibles."""
        # À implémenter dynamiquement depuis le registre des modèles
        return [('', _('Sélectionnez un type'))]

    def _get_field_choices(self):
        """Retourne la liste des champs traduisibles."""
        # À implémenter dynamiquement
        return [('', _('Sélectionnez un champ'))]

    def clean(self):
        cleaned_data = super().clean()

        # Validation supplémentaire
        content_type = cleaned_data.get('content_type')
        object_id = cleaned_data.get('object_id')

        if content_type and object_id:
            try:
                from django.contrib.contenttypes.models import ContentType
                ct = ContentType.objects.get(model=content_type)
                model_class = ct.model_class()
                instance = model_class.objects.get(pk=object_id)
                cleaned_data['instance'] = instance
            except Exception as e:
                raise forms.ValidationError(
                    _("Objet introuvable: %(error)s"),
                    params={'error': str(e)}
                )

        return cleaned_data


class TranslationSettingsForm(forms.ModelForm):
    """Formulaire pour les paramètres de traduction."""

    class Meta:
        model = TranslationSettings
        fields = [
            'auto_translate_enabled',
            'show_translation_badge',
            'allow_translation_editing',
            'preferred_languages',
            'quality_threshold',
        ]
        widgets = {
            'auto_translate_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_translation_badge': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_translation_editing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'preferred_languages': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'data-placeholder': _('Sélectionnez les langues préférées')
            }),
            'quality_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '1',
                'step': '0.1'
            }),
        }
        labels = {
            'auto_translate_enabled': _('Activer la traduction automatique'),
            'show_translation_badge': _('Afficher le badge "Traduit automatiquement"'),
            'allow_translation_editing': _('Autoriser l\'édition des traductions'),
            'preferred_languages': _('Langues préférées'),
            'quality_threshold': _('Seuil de qualité minimum'),
        }
        help_texts = {
            'preferred_languages': _('Ordre de préférence pour l\'affichage des traductions'),
            'quality_threshold': _('Score de confiance minimum (0-1) pour accepter une traduction'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialise les choix de langue
        if hasattr(settings, 'DEEPSEEK_CONFIG'):
            languages = settings.DEEPSEEK_CONFIG.get('ENABLED_LANGUAGES', [])
        else:
            languages = ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl']

        language_choices = [(lang, self._get_language_display(lang)) for lang in languages]
        self.fields['preferred_languages'].choices = language_choices

    def _get_language_display(self, language_code):
        """Retourne l'affichage d'une langue."""
        from django.utils.translation import get_language_info

        try:
            info = get_language_info(language_code)
            return f"{info['name']} ({language_code})"
        except:
            return language_code.upper()

    def clean_quality_threshold(self):
        """Valide le seuil de qualité."""
        threshold = self.cleaned_data['quality_threshold']
        if threshold < 0 or threshold > 1:
            raise forms.ValidationError(_("Le seuil doit être entre 0 et 1"))
        return threshold

    def clean_preferred_languages(self):
        """Valide les langues préférées."""
        languages = self.cleaned_data['preferred_languages']

        # Vérifie les doublons
        if len(languages) != len(set(languages)):
            raise forms.ValidationError(_("Les langues ne peuvent pas être en double"))

        return languages


class TranslationEditForm(forms.Form):
    """Formulaire pour éditer une traduction."""

    translated_text = forms.CharField(
        label=_("Texte traduit"),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': _('Entrez la traduction...')
        })
    )

    quality = forms.ChoiceField(
        label=_("Qualité"),
        choices=[
            ('auto', _('Automatique')),
            ('edited', _('Éditée')),
            ('human', _('Humaine')),
            ('reviewed', _('Révisée')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Notes sur la traduction...')
        })
    )

    def __init__(self, *args, **kwargs):
        original_text = kwargs.pop('original_text', '')
        super().__init__(*args, **kwargs)

        # Ajoute une aide avec le texte original
        self.fields['translated_text'].help_text = _(
            "Texte original: %(original_text)s"
        ) % {'original_text': original_text[:100] + '...' if len(original_text) > 100 else original_text}


class BatchTranslationForm(forms.Form):
    """Formulaire pour la traduction par lot."""

    texts = forms.CharField(
        label=_("Textes à traduire"),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': _('Un texte par ligne...')
        }),
        help_text=_("Entrez un texte par ligne")
    )

    source_language = forms.ChoiceField(
        label=_("Langue source"),
        choices=[('auto', _('Détection automatique'))] + [
            (lang, lang.upper()) for lang in ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl']
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    target_language = forms.ChoiceField(
        label=_("Langue cible"),
        choices=[(lang, lang.upper()) for lang in ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl']],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean_texts(self):
        """Valide et nettoie les textes."""
        texts = self.cleaned_data['texts']
        lines = [line.strip() for line in texts.split('\n') if line.strip()]

        if len(lines) > 100:
            raise forms.ValidationError(_("Maximum 100 textes à la fois"))

        # Vérifie la longueur totale
        total_chars = sum(len(line) for line in lines)
        if total_chars > 10000:
            raise forms.ValidationError(_("Maximum 10,000 caractères au total"))

        return lines