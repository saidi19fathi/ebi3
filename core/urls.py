# ~/ebi3/core/urls.py
from django.urls import path
from django.views.i18n import set_language
from . import views

app_name = 'core'

urlpatterns = [
    # Pages principales
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('faq/', views.FAQListView.as_view(), name='faq'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    path('page/<slug:slug>/', views.PageDetailView.as_view(), name='page'),

    # Actions
    path('set-language/', set_language, name='set_language'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
]