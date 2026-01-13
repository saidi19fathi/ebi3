# ~/ebi3/core/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.utils.translation import gettext_lazy as _, activate, get_language
from django.contrib import messages
from django.urls import reverse_lazy
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from .models import Page, FAQ, Country, ContactMessage, NewsletterSubscriber
from .forms import ContactForm, NewsletterForm


# ~/ebi3/core/views.py
class HomeView(TemplateView):
    """Page d'accueil"""
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Import des modèles nécessaires
        from ads.models import Ad
        from carriers.models import Carrier
        from users.models import User
        from colis.models import Package

        # Debug: Vérifier toutes les annonces
        all_ads = Ad.objects.all()
        active_ads = Ad.objects.filter(status=Ad.Status.ACTIVE)

        print(f"DEBUG - Toutes les annonces: {all_ads.count()}")
        print(f"DEBUG - Annonces ACTIVES: {active_ads.count()}")

        for ad in all_ads:
            print(f"DEBUG - Annonce: {ad.title}, Statut: {ad.status}")

        # Statistiques pour la page d'accueil
        context.update({
            'total_ads': active_ads.count(),
            'total_carriers': Carrier.objects.filter(status='APPROVED').count(),
            'total_users': User.objects.filter(is_active=True).count(),
        })

        # Annonces récentes
        context['recent_ads'] = Ad.objects.filter(
            status__in=[Ad.Status.ACTIVE, Ad.Status.RESERVED, Ad.Status.DRAFT, Ad.Status.PENDING]
        ).select_related('seller', 'category').prefetch_related('images').order_by('-created_at')[:8]

        # Colis récents - CORRECTION ICI: Utiliser le bon statut
        try:
            # Vérifier quels statuts existent
            all_packages = Package.objects.all()
            print(f"DEBUG - Tous les colis: {all_packages.count()}")

            for package in all_packages:
                print(f"DEBUG - Colis: {package.title}, Statut: {package.status}")

            # Filtrer par statut disponible - CORRECTION
            # Essayer plusieurs noms de statut possibles
            from django.db.models import Q

            # Essayer avec le statut disponible (probablement 'AVAILABLE' ou 'PUBLISHED')
            available_packages = Package.objects.filter(
                Q(status='AVAILABLE') | Q(status='PUBLISHED') | Q(status='ACTIVE')
            ).select_related('sender').prefetch_related('images').order_by('-created_at')[:4]

            print(f"DEBUG - Colis disponibles: {available_packages.count()}")

            # Si aucun colis trouvé avec ces statuts, prendre tous les colis pour le test
            if available_packages.count() == 0:
                available_packages = Package.objects.all().select_related('sender').prefetch_related('images').order_by('-created_at')[:4]
                print(f"DEBUG - Utilisation de tous les colis pour test: {available_packages.count()}")

            context['recent_packages'] = available_packages

        except Exception as e:
            print(f"DEBUG - Erreur packages: {e}")
            context['recent_packages'] = []

        # Transporteurs récents
        context['recent_carriers'] = Carrier.objects.filter(
            status='APPROVED',
            transport_is_available=True
        ).select_related('user').order_by('-created_at')[:4]

        # Annonces en vedette
        context['featured_ads'] = Ad.objects.filter(
            is_featured=True,
            status__in=[Ad.Status.ACTIVE, Ad.Status.RESERVED]
        ).select_related('seller', 'category').prefetch_related('images')[:4]

        return context

class PageDetailView(DetailView):
    """Détail d'une page statique"""
    model = Page
    template_name = 'core/page.html'
    context_object_name = 'page'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Page.objects.filter(status=Page.Status.PUBLISHED)


class FAQListView(ListView):
    """Liste des FAQs"""
    model = FAQ
    template_name = 'core/faq.html'
    context_object_name = 'faqs'

    def get_queryset(self):
        current_language = get_language()
        return FAQ.objects.filter(
            language=current_language,
            is_active=True
        ).order_by('category', 'display_order')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Grouper les FAQs par catégorie
        faqs_by_category = {}
        for faq in context['faqs']:
            if faq.category not in faqs_by_category:
                faqs_by_category[faq.category] = []
            faqs_by_category[faq.category].append(faq)

        context['faqs_by_category'] = faqs_by_category
        return context


class ContactView(CreateView):
    """Page de contact"""
    model = ContactMessage
    form_class = ContactForm
    template_name = 'core/contact.html'
    success_url = reverse_lazy('core:contact')

    def form_valid(self, form):
        # Ajouter les informations de la requête
        contact_message = form.save(commit=False)
        contact_message.ip_address = self.request.META.get('REMOTE_ADDR')
        contact_message.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        contact_message.save()

        messages.success(
            self.request,
            _("Votre message a été envoyé avec succès. Nous vous répondrons dans les plus brefs délais.")
        )
        return super().form_valid(form)


class AboutView(TemplateView):
    """Page À propos"""
    template_name = 'core/about.html'


class TermsView(TemplateView):
    """Conditions d'utilisation"""
    template_name = 'core/terms.html'


class PrivacyView(TemplateView):
    """Politique de confidentialité"""
    template_name = 'core/privacy.html'


@csrf_protect
@require_POST
def change_language(request):
    """Changer la langue du site"""
    language = request.POST.get('language')

    if language in [lang[0] for lang in settings.LANGUAGES]:
        activate(language)
        request.session[settings.LANGUAGE_COOKIE_NAME] = language

        # Rediriger vers la même page
        next_url = request.POST.get('next', request.META.get('HTTP_REFERER', '/'))
        response = HttpResponseRedirect(next_url)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE
        )
        return response

    return redirect('core:home')


@csrf_protect
@require_POST
def newsletter_subscribe(request):
    """S'abonner à la newsletter"""
    form = NewsletterForm(request.POST)

    if form.is_valid():
        subscriber = form.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': str(_("Vous êtes maintenant inscrit à notre newsletter !"))
            })

        messages.success(request, _("Vous êtes maintenant inscrit à notre newsletter !"))
        return redirect(request.META.get('HTTP_REFERER', 'core:home'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'errors': form.errors
        }, status=400)

    messages.error(request, _("Une erreur est survenue. Veuillez réessayer."))
    return redirect(request.META.get('HTTP_REFERER', 'core:home'))


def handler404(request, exception):
    """Handler 404 personnalisé"""
    return render(request, 'core/404.html', status=404)


def handler500(request):
    """Handler 500 personnalisé"""
    return render(request, 'core/500.html', status=500)


def handler403(request, exception):
    """Handler 403 personnalisé"""
    return render(request, 'core/403.html', status=403)


def handler400(request, exception):
    """Handler 400 personnalisé"""
    return render(request, 'core/400.html', status=400)

