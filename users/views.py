# ~/ebi3/users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView, FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.core.exceptions import ValidationError
import logging

from .forms import (
    CustomUserCreationForm,
    CustomUserChangeForm,
    UserProfileForm,
    LoginForm,
    PasswordResetRequestForm,
    PasswordResetConfirmForm,
    KYCVerificationForm,
    CarrierRegistrationForm  # Ceci est dans users/forms.py
)
from .models import User, UserProfile
from carriers.models import Carrier  # Seulement le modèle

logger = logging.getLogger(__name__)

class CarrierRegisterView(CreateView):
    """
    VUE UNIFIÉE D'INSCRIPTION TRANSPORTEUR
    Utilise CarrierRegistrationForm de users/forms.py
    """
    model = User
    form_class = CarrierRegistrationForm  # Ceci vient de users/forms.py
    template_name = 'users/register_carrier.html'
    success_url = reverse_lazy('users:register_carrier_success')

    def dispatch(self, request, *args, **kwargs):
        # Si l'utilisateur est déjà connecté
        if request.user.is_authenticated:
            # Vérifier s'il a déjà un profil transporteur
            if hasattr(request.user, 'carrier_profile'):
                messages.info(request, _("Vous avez déjà un profil transporteur."))
                return redirect('carriers:dashboard')
            else:
                # S'il est connecté mais pas transporteur, rediriger vers le formulaire d'application
                return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Devenez transporteur")
        context['page_description'] = _("Inscrivez-vous pour commencer à livrer des colis et gagner de l'argent.")
        return context

    def form_valid(self, form):
        try:
            # Créer l'utilisateur, le profil et le transporteur
            user = form.save()

            # Connecter automatiquement l'utilisateur
            login(self.request, user)

            # Journaliser la création
            logger.info(f"Nouveau transporteur inscrit: {user.username} ({user.email})")

            # Message de succès
            messages.success(
                self.request,
                _("Félicitations ! Votre compte transporteur a été créé avec succès. "
                  "Votre profil est en attente de validation par notre équipe.")
            )

            return redirect(self.get_success_url())

        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            logger.error(f"Erreur lors de l'inscription transporteur: {e}")
            messages.error(
                self.request,
                _("Une erreur est survenue lors de votre inscription. "
                  "Veuillez réessayer ou contacter le support.")
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Afficher les erreurs spécifiques
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{form.fields[field].label}: {error}")
        return super().form_invalid(form)


class CarrierRegisterSuccessView(TemplateView):
    """Page de succès après inscription transporteur"""
    template_name = 'users/register_carrier_success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Inscription réussie !")
        context['next_steps'] = [
            _("Votre compte est en attente de validation (24-48h)"),
            _("Vous pouvez déjà compléter votre profil"),
            _("Explorez le tableau de bord transporteur"),
            _("Consultez les missions disponibles")
        ]
        return context


class RegisterView(CreateView):
    """Vue pour l'inscription des utilisateurs STANDARD (non transporteurs)"""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _("Créer un compte")
        context['user_types'] = [
            {
                'title': _("Acheteur"),
                'description': _("Achetez des produits en toute sécurité"),
                'value': User.Role.BUYER,
                'icon': 'fas fa-shopping-cart'
            },
            {
                'title': _("Vendeur"),
                'description': _("Vendez vos produits en ligne"),
                'value': User.Role.SELLER,
                'icon': 'fas fa-store'
            },
            {
                'title': _("Transporteur"),
                'description': _("Livrez des colis et gagnez de l'argent"),
                'value': 'CARRIER',  # Changé de 'CARRIER_REDIRECT' à 'CARRIER'
                'icon': 'fas fa-truck',
                'is_carrier': True
            }
        ]
        return context

    def form_valid(self, form):
        # Récupérer le type d'utilisateur sélectionné
        user_type = form.cleaned_data.get('user_type')

        # Si c'est un transporteur, rediriger vers l'inscription transporteur
        if user_type == 'CARRIER':
            # Sauvegarder temporairement les données du formulaire dans la session
            self.request.session['user_registration_data'] = {
                'email': form.cleaned_data.get('email'),
                'password': form.cleaned_data.get('password1'),
                'first_name': form.cleaned_data.get('first_name'),
                'last_name': form.cleaned_data.get('last_name'),
                'phone': form.cleaned_data.get('phone'),
            }
            return redirect('carriers:register')

        # Pour les autres types d'utilisateur, procéder normalement
        user = form.save(commit=False)
        user.role = user_type
        user.save()

        # Envoyer email de vérification si nécessaire
        # ...

        messages.success(
            self.request,
            _("Votre compte a été créé avec succès ! Veuillez vérifier votre email.")
        )
        return super().form_valid(form)

class LoginView(View):
    """Vue pour la connexion"""
    template_name = 'users/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        form = LoginForm()

        # Déterminer la redirection après login
        next_url = request.GET.get('next', '')
        if not next_url:
            # Si l'utilisateur a un profil transporteur, aller vers dashboard carriers
            if hasattr(request.user, 'carrier_profile'):
                next_url = 'carriers:dashboard'
            else:
                next_url = 'core:home'

        return render(request, self.template_name, {
            'form': form,
            'next': next_url
        })

    def post(self, request):
        form = LoginForm(request.POST)
        next_url = request.POST.get('next', 'core:home')

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)

                    # Message de bienvenue personnalisé
                    welcome_msg = _("Bon retour, {} !").format(user.first_name or user.username)
                    if hasattr(user, 'carrier_profile'):
                        if user.carrier_profile.status == Carrier.Status.APPROVED:
                            welcome_msg += " " + _("Votre profil transporteur est actif.")
                        elif user.carrier_profile.status == Carrier.Status.PENDING:
                            welcome_msg += " " + _("Votre profil transporteur est en attente de validation.")

                    messages.success(request, welcome_msg)
                    return redirect(next_url)
                else:
                    messages.error(request, _("Votre compte est désactivé."))
            else:
                messages.error(request, _("Nom d'utilisateur ou mot de passe incorrect."))

        return render(request, self.template_name, {
            'form': form,
            'next': next_url
        })


@login_required
def logout_view(request):
    """Vue pour la déconnexion"""
    logout(request)
    messages.success(request, _("Vous avez été déconnecté avec succès."))
    return redirect('core:home')


class ProfileView(LoginRequiredMixin, DetailView):
    """Vue pour afficher le profil"""
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'user_profile'

    def get_object(self):
        username = self.kwargs.get('username')
        if username:
            return get_object_or_404(User, username=username)
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object

        # Ajouter des informations supplémentaires
        context['is_own_profile'] = (user == self.request.user)
        context['has_carrier_profile'] = hasattr(user, 'carrier_profile')

        if context['has_carrier_profile']:
            context['carrier_profile'] = user.carrier_profile
            context['carrier_status'] = user.carrier_profile.get_status_display()
            context['carrier_type'] = user.carrier_profile.get_carrier_type_display()

        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vue pour modifier le profil"""
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/profile_update.html'

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        messages.success(self.request, _("Votre profil a été mis à jour avec succès."))
        return reverse_lazy('users:profile', kwargs={'username': self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_carrier_profile'] = hasattr(self.request.user, 'carrier_profile')
        return context


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vue pour modifier le profil étendu"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_extended_update.html'

    def get_object(self):
        # Créer le profil s'il n'existe pas
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        if created:
            logger.info(f"UserProfile créé pour {self.request.user.username}")
        return profile

    def get_success_url(self):
        messages.success(self.request, _("Vos informations supplémentaires ont été mises à jour."))
        return reverse_lazy('users:profile', kwargs={'username': self.request.user.username})


@login_required
def change_password(request):
    """Vue pour changer le mot de passe"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _("Votre mot de passe a été changé avec succès !"))
            return redirect('users:profile', username=request.user.username)
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/change_password.html', {'form': form})


class KYCVerificationView(LoginRequiredMixin, UpdateView):
    """Vue pour soumettre la vérification KYC"""
    model = User
    form_class = KYCVerificationForm
    template_name = 'users/kyc_verification.html'

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        user = form.save(commit=False)
        user.kyc_submitted = True

        # Pour les transporteurs, augmenter le niveau de vérification
        if hasattr(user, 'carrier_profile'):
            user.carrier_profile.verification_level += 1
            user.carrier_profile.save()

        user.save()

        messages.success(
            self.request,
            _("Votre demande de vérification KYC a été soumise. Nous la traiterons sous 48h.")
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('users:profile', kwargs={'username': self.request.user.username})


class EmailVerificationView(LoginRequiredMixin, View):
    """Vue pour vérifier l'email"""
    template_name = 'users/email_verification.html'

    def get(self, request, token):
        # À implémenter avec des tokens sécurisés
        # Pour l'instant, simple confirmation
        if request.user.email_verified:
            messages.info(request, _("Votre email est déjà vérifié."))
        else:
            request.user.email_verified = True
            request.user.save()
            messages.success(request, _("Votre email a été vérifié avec succès !"))

        return render(request, self.template_name)


class PhoneVerificationView(LoginRequiredMixin, View):
    """Vue pour vérifier le numéro de téléphone"""
    template_name = 'users/phone_verification.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Logique d'envoi/validation de code SMS
        # À implémenter avec un service SMS
        code = request.POST.get('verification_code', '')

        # Simulation de vérification
        if code == '123456':  # À remplacer par une vraie validation
            request.user.phone_verified = True
            request.user.save()
            messages.success(request, _("Votre numéro de téléphone a été vérifié avec succès !"))
            return redirect('users:profile', username=request.user.username)
        else:
            messages.error(request, _("Code de vérification incorrect."))
            return render(request, self.template_name)


class AccountTypeRedirectView(View):
    """Vue pour rediriger vers le bon type d'inscription"""

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')

        return render(request, 'users/account_type.html', {
            'user_types': [
                {
                    'title': _("Je veux acheter"),
                    'description': _("Trouvez et achetez des produits en toute sécurité"),
                    'url': reverse_lazy('users:register'),
                    'icon': 'fas fa-shopping-cart',
                    'color': 'primary'
                },
                {
                    'title': _("Je veux vendre"),
                    'description': _("Vendez vos produits et gérez vos ventes"),
                    'url': reverse_lazy('users:register'),
                    'icon': 'fas fa-store',
                    'color': 'success'
                },
                {
                    'title': _("Je veux livrer"),
                    'description': _("Devenez transporteur et gagnez de l'argent en livrant des colis"),
                    'url': reverse_lazy('users:register_carrier'),
                    'icon': 'fas fa-truck',
                    'color': 'warning'
                }
            ]
        })


def handler404(request, exception):
    """Handler 404 personnalisé"""
    return render(request, 'users/404.html', status=404)


def handler500(request):
    """Handler 500 personnalisé"""
    return render(request, 'users/500.html', status=500)
