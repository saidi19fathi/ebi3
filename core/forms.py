# ~/ebi3/core/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email
from .models import ContactMessage, NewsletterSubscriber

class ContactForm(forms.ModelForm):
    """Formulaire de contact"""

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Votre nom complet')
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('Votre adresse email')
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Sujet de votre message')
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Votre message...')
            }),
        }
        labels = {
            'name': _('Nom'),
            'email': _('Email'),
            'subject': _('Sujet'),
            'message': _('Message'),
        }


class NewsletterForm(forms.Form):
    """Formulaire d'inscription à la newsletter"""

    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('Votre email'),
            'aria-label': _('Email pour newsletter')
        })
    )

    consent = forms.BooleanField(
        required=True,
        label=_("J'accepte de recevoir des newsletters"),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        validate_email(email)

        # Vérifier si l'email est déjà inscrit et actif
        if NewsletterSubscriber.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError(
                _("Cet email est déjà inscrit à notre newsletter.")
            )

        return email

    def save(self, request=None):
        """Sauvegarde l'abonné"""
        email = self.cleaned_data['email']

        # Désactiver l'ancien abonnement s'il existe
        NewsletterSubscriber.objects.filter(email=email).update(is_active=False)

        # Créer un nouvel abonnement
        subscriber = NewsletterSubscriber.objects.create(
            email=email,
            is_active=True
        )

        return subscriber


class LanguageForm(forms.Form):
    """Formulaire de sélection de langue"""

    language = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'this.form.submit()'
        })
    )

    def __init__(self, *args, **kwargs):
        from django.conf import settings
        super().__init__(*args, **kwargs)
        self.fields['language'].choices = settings.LANGUAGES