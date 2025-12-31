# ~/ebi3/users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .forms import (
    CustomUserCreationForm,
    CustomUserChangeForm,
    UserProfileForm,
    LoginForm,
    PasswordResetRequestForm,
    PasswordResetConfirmForm,
    KYCVerificationForm
)
from .models import User, UserProfile

class RegisterView(CreateView):
    """Vue pour l'inscription des utilisateurs"""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Votre compte a été créé avec succès ! Veuillez vérifier votre email.")
        )
        return response

class LoginView(View):
    """Vue pour la connexion"""
    template_name = 'users/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)
                    next_url = request.GET.get('next', 'core:home')
                    messages.success(request, _("Connexion réussie !"))
                    return redirect(next_url)
                else:
                    messages.error(request, _("Votre compte est désactivé."))
            else:
                messages.error(request, _("Nom d'utilisateur ou mot de passe incorrect."))

        return render(request, self.template_name, {'form': form})

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
        return get_object_or_404(User, username=self.kwargs['username'])

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vue pour modifier le profil"""
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user

    def get_success_url(self):
        messages.success(self.request, _("Votre profil a été mis à jour avec succès."))
        return reverse_lazy('users:profile', kwargs={'username': self.request.user.username})

class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Vue pour modifier le profil étendu"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_extended_update.html'

    def get_object(self):
        return self.request.user.profile

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
        user.kyc_submitted = True  # Nous devons ajouter ce champ au modèle
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
        # Logique de vérification du token
        # À implémenter avec des tokens sécurisés
        return render(request, self.template_name)

class PhoneVerificationView(LoginRequiredMixin, View):
    """Vue pour vérifier le numéro de téléphone"""
    template_name = 'users/phone_verification.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Logique d'envoi/validation de code SMS
        # À implémenter avec un service SMS
        return redirect('users:profile', username=request.user.username)