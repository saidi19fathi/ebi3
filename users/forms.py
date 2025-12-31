# ~/ebi3/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile

class CustomUserCreationForm(UserCreationForm):
    """Formulaire pour créer un nouvel utilisateur avec des champs supplémentaires"""

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone_number',
                 'country', 'city', 'preferred_language')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
        }

class CustomUserChangeForm(UserChangeForm):
    """Formulaire pour modifier un utilisateur existant"""

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone_number',
                 'country', 'city', 'address', 'preferred_language',
                 'is_verified', 'kyc_verified', 'is_active')


class LoginForm(forms.Form):
    """Formulaire de connexion"""
    username = forms.CharField(
        label=_("Nom d'utilisateur ou Email"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre nom d'utilisateur ou email")
        })
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre mot de passe")
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        label=_("Se souvenir de moi"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class UserProfileForm(forms.ModelForm):
    """Formulaire pour le profil utilisateur étendu"""
    class Meta:
        model = UserProfile
        fields = [
            'date_of_birth', 'gender', 'company_name',
            'company_registration', 'tax_id', 'country_of_origin',
            'country_of_residence', 'is_expatriate'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }

class PasswordResetRequestForm(forms.Form):
    """Formulaire pour demander une réinitialisation de mot de passe"""
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre email")
        })
    )

class PasswordResetConfirmForm(forms.Form):
    """Formulaire pour confirmer la réinitialisation du mot de passe"""
    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label=_("Confirmer le nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

class KYCVerificationForm(forms.ModelForm):
    """Formulaire pour la vérification KYC"""
    id_document = forms.FileField(
        label=_("Document d'identité"),
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    proof_of_address = forms.FileField(
        label=_("Justificatif de domicile"),
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    selfie_with_id = forms.FileField(
        label=_("Selfie avec document d'identité"),
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = []  # Aucun champ du modèle User, seulement les fichiers

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Logique spécifique pour les transporteurs professionnels
        if self.instance and self.instance.role == User.Role.CARRIER:
            self.fields['company_registration_doc'] = forms.FileField(
                label=_("Document d'immatriculation"),
                required=True,
                widget=forms.FileInput(attrs={'class': 'form-control'})
            )