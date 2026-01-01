# ~/ebi3/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile

class CustomUserCreationForm(UserCreationForm):
    """Formulaire pour créer un nouvel utilisateur avec des champs supplémentaires"""

    phone_number = forms.CharField(
        label=_("Numéro de téléphone"),
        required=True,
        help_text=_("Format international : +212612345678 (recommandé) ou 00212612345678"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("+212612345678"),
            'title': _("Entrez votre numéro au format international")
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone_number',
                 'country', 'city', 'preferred_language')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_phone_number(self):
        """Valide et formate le numéro de téléphone"""
        phone_number = self.cleaned_data.get('phone_number')

        if phone_number:
            try:
                # Nettoyer le numéro : supprimer les espaces, tirets, etc.
                phone_number = phone_number.strip().replace(' ', '').replace('-', '').replace('.', '')

                # Convertir les formats locaux en format international
                if phone_number.startswith('0'):
                    # L'utilisateur a entré un format local (ex: 0612345678)
                    country = self.cleaned_data.get('country')

                    if country:
                        # Mapper les codes pays
                        country_codes = {
                            'MA': '212',  # Maroc
                            'FR': '33',   # France
                            'BE': '32',   # Belgique
                            'TN': '216',  # Tunisie
                            'DZ': '213',  # Algérie
                            'SN': '221',  # Sénégal
                            'CI': '225',  # Côte d'Ivoire
                            'CM': '237',  # Cameroun
                            'US': '1',    # États-Unis
                            'GB': '44',   # Royaume-Uni
                            'DE': '49',   # Allemagne
                            'ES': '34',   # Espagne
                            'IT': '39',   # Italie
                            'PT': '351',  # Portugal
                            # Ajoutez d'autres pays selon vos besoins
                        }

                        code = country_codes.get(country.code, '')
                        if code:
                            # Enlever le 0 initial et ajouter le code pays
                            phone_number = f"+{code}{phone_number[1:]}"
                        else:
                            # Code pays non trouvé, laisser tel quel
                            pass

                # Convertir 00 en + si présent (format 00212...)
                elif phone_number.startswith('00'):
                    phone_number = '+' + phone_number[2:]

                # S'assurer que le numéro commence par +
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                # Validation de la longueur minimale
                if len(phone_number) < 10:  # +212612345678 = 13 caractères
                    raise forms.ValidationError(
                        _("Numéro de téléphone trop court. Format attendu : +212612345678")
                    )

                # Validation que le numéro ne contient que des chiffres après le +
                if not phone_number[1:].isdigit():
                    raise forms.ValidationError(
                        _("Le numéro de téléphone ne doit contenir que des chiffres après le +")
                    )

                return phone_number

            except Exception as e:
                raise forms.ValidationError(
                    _("Saisissez un numéro de téléphone valide. Format: +212612345678 ou 0612345678")
                )

        return phone_number

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Améliorer les champs existants
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("Choisissez un nom d'utilisateur")
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("votre@email.com")
        })
        self.fields['country'].widget.attrs.update({
            'class': 'form-control'
        })
        self.fields['city'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("Votre ville")
        })
        self.fields['city'].required = False  # Rendre optionnel

        # Rendre le pays obligatoire pour aider à la validation du téléphone
        self.fields['country'].required = True

        # Ajouter une aide pour le format du téléphone
        self.fields['phone_number'].help_text += _(
            "<br><small class='text-muted'>Exemples: +212612345678 (Maroc), +33612345678 (France), +32456123456 (Belgique)</small>"
        )
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