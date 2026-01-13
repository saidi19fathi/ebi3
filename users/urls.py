# ~/ebi3/users/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # Garder cet import

# NE PAS ajouter d'imports de carriers ici
# from carriers import views as carriers_views  # ← SUPPRIMER SI EXISTE

app_name = 'users'

urlpatterns = [
    # Inscription
    path('register/', views.RegisterView.as_view(), name='register'),
    path('register/carrier/', views.CarrierRegisterView.as_view(), name='carrier_register'),
    path('register/success/carrier/', views.CarrierRegisterSuccessView.as_view(), name='carrier_register_success'),

    # Connexion/Déconnexion
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profil
    path('profile/<str:username>/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/extended/update/', views.UserProfileUpdateView.as_view(), name='profile_extended_update'),

    # Sécurité
    path('password/change/', views.change_password, name='change_password'),
    path('password/reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Vérification
    path('verify/email/<str:token>/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('verify/phone/', views.PhoneVerificationView.as_view(), name='verify_phone'),
    path('verify/kyc/', views.KYCVerificationView.as_view(), name='verify_kyc'),

    # Redirection
    path('account-type/', views.AccountTypeRedirectView.as_view(), name='account_type'),
]