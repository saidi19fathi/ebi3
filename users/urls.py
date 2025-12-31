# ~/ebi3/users/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Inscription et connexion
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profil
    path('profile/<str:username>/', views.ProfileView.as_view(), name='profile'),
    path('profile/<str:username>/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('profile/<str:username>/edit-extended/',
         views.UserProfileUpdateView.as_view(), name='profile_edit_extended'),

    # Sécurité
    path('change-password/', views.change_password, name='change_password'),

    # Vérifications
    path('verify/email/<str:token>/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('verify/phone/', views.PhoneVerificationView.as_view(), name='verify_phone'),
    path('verify/kyc/', views.KYCVerificationView.as_view(), name='kyc_verification'),

    # Réinitialisation de mot de passe
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             success_url='/users/password-reset/done/'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/users/password-reset-complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]