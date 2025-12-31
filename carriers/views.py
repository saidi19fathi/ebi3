# ~/ebi3/carriers/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView,
    TemplateView, DeleteView, FormView
)
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.db.models import Min, Max, Sum

from .models import (
    Carrier, CarrierRoute, CarrierDocument, CarrierReview,
    CarrierAvailability, CarrierNotification
)
from .forms import (
    CarrierApplicationForm, CarrierUpdateForm,
    CarrierRouteForm, CarrierDocumentForm,
    CarrierReviewForm, CarrierSearchForm,
    CarrierDocumentFormSet, CarrierRouteFormSet
)
from users.models import User
from ads.models import Ad


class CarrierListView(ListView):
    """Liste des transporteurs"""
    model = Carrier
    template_name = 'carriers/carrier_list.html'
    context_object_name = 'carriers'
    paginate_by = 12

    def get_queryset(self):
        queryset = Carrier.objects.filter(
            status=Carrier.Status.APPROVED,
            is_available=True
        ).select_related('user').prefetch_related('routes')

        # Appliquer les filtres
        form = CarrierSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('carrier_type'):
                queryset = queryset.filter(carrier_type=form.cleaned_data['carrier_type'])

            if form.cleaned_data.get('vehicle_type'):
                queryset = queryset.filter(vehicle_type=form.cleaned_data['vehicle_type'])

            if form.cleaned_data.get('start_country') and form.cleaned_data.get('end_country'):
                queryset = queryset.filter(
                    routes__start_country=form.cleaned_data['start_country'],
                    routes__end_country=form.cleaned_data['end_country'],
                    routes__is_active=True,
                    routes__is_full=False
                ).distinct()

            if form.cleaned_data.get('start_city'):
                queryset = queryset.filter(
                    routes__start_city__icontains=form.cleaned_data['start_city']
                )

            if form.cleaned_data.get('end_city'):
                queryset = queryset.filter(
                    routes__end_city__icontains=form.cleaned_data['end_city']
                )

            if form.cleaned_data.get('departure_date'):
                queryset = queryset.filter(
                    routes__departure_date=form.cleaned_data['departure_date'],
                    routes__is_active=True
                )

            if form.cleaned_data.get('max_weight'):
                queryset = queryset.filter(max_weight__gte=form.cleaned_data['max_weight'])

            if form.cleaned_data.get('min_rating'):
                queryset = queryset.filter(average_rating__gte=form.cleaned_data['min_rating'])

            if form.cleaned_data.get('provides_insurance'):
                queryset = queryset.filter(provides_insurance=True)

            if form.cleaned_data.get('provides_packaging'):
                queryset = queryset.filter(provides_packaging=True)

        # Tri
        sort_by = form.cleaned_data.get('sort_by', 'rating') if form.is_valid() else 'rating'

        if sort_by == 'rating':
            queryset = queryset.order_by('-average_rating')
        elif sort_by == 'price':
            queryset = queryset.order_by('base_price_per_km')
        elif sort_by == 'experience':
            queryset = queryset.order_by('-completed_missions')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Initialiser le formulaire de recherche
        search_form = CarrierSearchForm(self.request.GET)
        context['search_form'] = search_form

        # Statistiques
        all_carriers = Carrier.objects.filter(status=Carrier.Status.APPROVED)
        context['total_carriers'] = all_carriers.count()
        context['professional_count'] = all_carriers.filter(carrier_type='PROFESSIONAL').count()
        context['personal_count'] = all_carriers.filter(carrier_type='PERSONAL').count()

        # Pagination
        if context['page_obj']:
            context['page_range'] = list(context['page_obj'].paginator.page_range)[:5]

        return context


class CarrierSearchView(FormView):
    """Vue de recherche avancée des transporteurs"""
    template_name = 'carriers/search_results.html'
    form_class = CarrierSearchForm

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        carriers = Carrier.objects.filter(status=Carrier.Status.APPROVED)

        if form.is_valid():
            # Appliquer les filtres (même logique que CarrierListView)
            if form.cleaned_data.get('carrier_type'):
                carriers = carriers.filter(carrier_type=form.cleaned_data['carrier_type'])

            if form.cleaned_data.get('vehicle_type'):
                carriers = carriers.filter(vehicle_type=form.cleaned_data['vehicle_type'])

            if form.cleaned_data.get('start_country'):
                carriers = carriers.filter(routes__start_country=form.cleaned_data['start_country'])

            if form.cleaned_data.get('end_country'):
                carriers = carriers.filter(routes__end_country=form.cleaned_data['end_country'])

            if form.cleaned_data.get('min_rating'):
                carriers = carriers.filter(average_rating__gte=form.cleaned_data['min_rating'])

            if form.cleaned_data.get('provides_insurance'):
                carriers = carriers.filter(provides_insurance=True)

            if form.cleaned_data.get('provides_packaging'):
                carriers = carriers.filter(provides_packaging=True)

        # Pagination
        paginator = Paginator(carriers, 12)
        page = request.GET.get('page')
        carriers_page = paginator.get_page(page)

        context = self.get_context_data(
            form=form,
            carriers=carriers_page,
            total_carriers=carriers.count()
        )

        return render(request, self.template_name, context)


class CarrierDetailView(DetailView):
    """Détail d'un transporteur"""
    model = Carrier
    template_name = 'carriers/carrier_detail.html'
    context_object_name = 'carrier'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'

    def get_object(self):
        return get_object_or_404(
            Carrier.objects.select_related('user').prefetch_related('routes', 'reviews'),
            user__username=self.kwargs['username']
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrier = self.object

        # Routes actives
        context['active_routes'] = carrier.routes.filter(
            is_active=True,
            departure_date__gte=timezone.now().date()
        ).order_by('departure_date')

        # Avis approuvés
        context['reviews'] = carrier.reviews.filter(
            is_approved=True,
            is_visible=True
        ).select_related('reviewer').order_by('-created_at')[:5]

        # Statistiques des avis
        if context['reviews']:
            review_stats = carrier.reviews.filter(is_approved=True, is_visible=True).aggregate(
                total_reviews=Count('id'),
                avg_communication=Avg('communication'),
                avg_punctuality=Avg('punctuality'),
                avg_handling=Avg('handling'),
                avg_professionalism=Avg('professionalism')
            )
            context['review_stats'] = review_stats

        # Documents vérifiés
        context['verified_documents'] = carrier.documents.filter(is_verified=True)

        # Vérifier si l'utilisateur peut laisser un avis
        if self.request.user.is_authenticated:
            context['can_review'] = self.request.user != carrier.user
            context['has_reviewed'] = carrier.reviews.filter(reviewer=self.request.user).exists()

        return context


class CarrierApplyView(LoginRequiredMixin, CreateView):
    """Devenir transporteur"""
    model = Carrier
    form_class = CarrierApplicationForm
    template_name = 'carriers/apply.html'

    def dispatch(self, request, *args, **kwargs):
        # Vérifier si l'utilisateur a déjà un profil transporteur
        if hasattr(request.user, 'carrier_profile'):
            messages.warning(request, _("Vous avez déjà un profil transporteur."))
            return redirect('carriers:carrier_detail', username=request.user.username)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.status = Carrier.Status.PENDING

        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Votre candidature a été soumise avec succès. "
              "Nous la traiterons dans les plus brefs délais.")
        )

        return response

    def get_success_url(self):
        return reverse_lazy('carriers:apply_success')


class CarrierDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Tableau de bord du transporteur"""
    template_name = 'carriers/dashboard.html'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrier = self.request.user.carrier_profile

        # Statistiques
        context['carrier'] = carrier
        context['active_routes'] = carrier.routes.filter(is_active=True).count()
        context['pending_reviews'] = carrier.reviews.filter(is_approved=False).count()
        context['unread_notifications'] = carrier.notifications.filter(is_read=False).count()

        # Missions récentes (à implémenter avec l'app logistics)
        context['recent_missions'] = []  # Placeholder

        # Revenus (à implémenter)
        context['total_earnings'] = 0  # Placeholder
        context['pending_payments'] = 0  # Placeholder

        return context


class CarrierProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Mettre à jour le profil transporteur"""
    model = Carrier
    form_class = CarrierUpdateForm
    template_name = 'carriers/profile_update.html'

    def test_func(self):
        carrier = self.get_object()
        return self.request.user == carrier.user

    def get_object(self):
        return self.request.user.carrier_profile

    def get_success_url(self):
        return reverse_lazy('carriers:carrier_dashboard')


class DocumentUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Télécharger un document"""
    model = CarrierDocument
    form_class = CarrierDocumentForm
    template_name = 'carriers/document_upload.html'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def form_valid(self, form):
        form.instance.carrier = self.request.user.carrier_profile
        messages.success(self.request, _("Document téléchargé avec succès."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('carriers:verification_status')


class ReviewCreateView(LoginRequiredMixin, CreateView):
    """Laisser un avis sur un transporteur"""
    model = CarrierReview
    form_class = CarrierReviewForm
    template_name = 'carriers/review_create.html'

    def dispatch(self, request, *args, **kwargs):
        self.carrier = get_object_or_404(Carrier, user__username=kwargs['username'])

        # Vérifications
        if request.user == self.carrier.user:
            messages.error(request, _("Vous ne pouvez pas laisser un avis sur votre propre profil."))
            return redirect('carriers:carrier_detail', username=self.carrier.user.username)

        if CarrierReview.objects.filter(carrier=self.carrier, reviewer=request.user).exists():
            messages.warning(request, _("Vous avez déjà laissé un avis pour ce transporteur."))
            return redirect('carriers:carrier_detail', username=self.carrier.user.username)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.carrier
        return context

    def form_valid(self, form):
        form.instance.carrier = self.carrier
        form.instance.reviewer = self.request.user
        form.instance.is_approved = False  # Nécessite approbation admin

        messages.success(
            self.request,
            _("Votre avis a été soumis. Il sera visible après modération.")
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('carriers:carrier_detail', username=self.carrier.user.username)


# Vues simples pour les URLs manquantes

class CarrierReviewsView(DetailView):
    """Tous les avis d'un transporteur"""
    model = Carrier
    template_name = 'carriers/carrier_reviews.html'
    slug_field = 'user__username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_reviews'] = self.object.reviews.filter(
            is_approved=True,
            is_visible=True
        ).select_related('reviewer').order_by('-created_at')
        return context


class ReviewUpdateView(LoginRequiredMixin, UpdateView):
    """Modifier un avis"""
    model = CarrierReview
    form_class = CarrierReviewForm
    template_name = 'carriers/review_update.html'

    def dispatch(self, request, *args, **kwargs):
        review = self.get_object()
        if review.reviewer != request.user:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('carriers:carrier_detail', username=self.object.carrier.user.username)


class ReviewDeleteView(LoginRequiredMixin, DeleteView):
    """Supprimer un avis"""
    model = CarrierReview
    template_name = 'carriers/review_delete.html'

    def dispatch(self, request, *args, **kwargs):
        review = self.get_object()
        if review.reviewer != request.user:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('carriers:carrier_detail', username=self.object.carrier.user.username)


class VerificationStatusView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Statut de vérification"""
    template_name = 'carriers/verification_status.html'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrier = self.request.user.carrier_profile
        context['carrier'] = carrier
        context['documents'] = carrier.documents.all().order_by('-created_at')
        return context


class DocumentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Supprimer un document"""
    model = CarrierDocument
    template_name = 'carriers/document_delete.html'

    def test_func(self):
        document = self.get_object()
        return self.request.user == document.carrier.user

    def get_success_url(self):
        return reverse_lazy('carriers:verification_status')


# Vues pour la nouvelle intégration avec logistics (simplifiées)

class CarrierMissionsView(ListView):
    """Missions d'un transporteur (vue publique)"""
    template_name = 'carriers/carrier_missions.html'
    context_object_name = 'missions'

    def get_queryset(self):
        self.carrier = get_object_or_404(Carrier, user__username=self.kwargs['username'])
        # À implémenter avec l'app logistics
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.carrier
        return context


class CarrierRoutesView(ListView):
    """Routes d'un transporteur (vue publique)"""
    template_name = 'carriers/carrier_routes.html'
    context_object_name = 'routes'

    def get_queryset(self):
        self.carrier = get_object_or_404(Carrier, user__username=self.kwargs['username'])
        return self.carrier.routes.filter(is_active=True).order_by('departure_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.carrier
        return context


class CarrierProposalsView(ListView):
    """Propositions d'un transporteur (vue publique)"""
    template_name = 'carriers/carrier_proposals.html'
    context_object_name = 'proposals'

    def get_queryset(self):
        self.carrier = get_object_or_404(Carrier, user__username=self.kwargs['username'])
        # À implémenter avec l'app logistics
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.carrier
        return context


# Vues de dashboard (authentifiées)

class CarrierMissionsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'carriers/dashboard/missions.html'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.request.user.carrier_profile
        # À implémenter avec l'app logistics
        return context


class CarrierRoutesDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'carriers/dashboard/routes.html'
    context_object_name = 'routes'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def get_queryset(self):
        return self.request.user.carrier_profile.routes.all().order_by('-departure_date')


class CarrierProposalsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'carriers/dashboard/proposals.html'

    def test_func(self):
        return hasattr(self.request.user, 'carrier_profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['carrier'] = self.request.user.carrier_profile
        # À implémenter avec l'app logistics
        return context


# Vues utilitaires

@login_required
@require_POST
def toggle_availability(request, username):
    """Basculer la disponibilité"""
    carrier = get_object_or_404(Carrier, user__username=username)

    if request.user != carrier.user:
        return HttpResponseForbidden()

    carrier.is_available = not carrier.is_available
    carrier.save()

    message = _("Vous êtes maintenant disponible.") if carrier.is_available else _("Vous êtes maintenant indisponible.")
    messages.success(request, message)

    return redirect('carriers:carrier_detail', username=username)


@login_required
def mark_all_notifications_read(request):
    """Marquer toutes les notifications comme lues"""
    if hasattr(request.user, 'carrier_profile'):
        request.user.carrier_profile.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, _("Toutes les notifications ont été marquées comme lues."))

    return redirect('carriers:carrier_dashboard')


# Gestionnaires d'erreurs
def handler404(request, exception):
    return render(request, 'carriers/404.html', status=404)

def handler500(request):
    return render(request, 'carriers/500.html', status=500)


# Placeholders pour les autres URLs
class AvailabilityUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/availability.html'

class ProfileCompletionView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/profile_completion.html'

class ActiveMissionsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/active_missions.html'

class CompletedMissionsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/completed_missions.html'

class MissionDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/mission_detail.html'

class RouteCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/route_create.html'

class RouteUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/route_update.html'

class RouteDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/route_delete.html'

@require_POST
def toggle_route_status(request, pk):
    return redirect('carriers:routes_dashboard')

class ActiveProposalsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/active_proposals.html'

class AcceptedProposalsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/accepted_proposals.html'

class ExpiredProposalsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/expired_proposals.html'

class CarrierLogisticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/logistics_dashboard.html'

class CarrierStatisticsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/statistics.html'

class CarrierReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/reports.html'

class EarningsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/earnings.html'

class CapacitiesUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/capacities.html'

class ServicesUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/services.html'

class VehiclesListView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/vehicles.html'

class VehicleCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/vehicle_create.html'

class VehicleUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/vehicle_update.html'

class VehicleDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/vehicle_delete.html'

class DocumentsListView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/documents.html'

class DocumentCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/document_create.html'

class InsuranceInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/insurance.html'

class InsuranceUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/insurance_update.html'

class CarrierMessagesView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/messages.html'

class UnreadMessagesView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/unread_messages.html'

class CarrierNotificationsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/notifications.html'

class CarrierSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/settings.html'

class NotificationSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/notification_settings.html'

class PrivacySettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/privacy_settings.html'

class SecuritySettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/dashboard/security_settings.html'

class CarrierProfileAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/profile.html'

class MissionsAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/missions.html'

class MissionDetailAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/mission_detail.html'

class RoutesAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/routes.html'

class EarningsAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/earnings.html'

class UpdateLocationAPIView(LoginRequiredMixin, TemplateView):
    template_name = 'carriers/api/update_location.html'

class StripeWebhookView(TemplateView):
    template_name = 'carriers/webhooks/stripe.html'

class TrackingWebhookView(TemplateView):
    template_name = 'carriers/webhooks/tracking.html'

class CarrierHelpView(TemplateView):
    template_name = 'carriers/help.html'

class CarrierFAQView(TemplateView):
    template_name = 'carriers/faq.html'

class CarrierGuideView(TemplateView):
    template_name = 'carriers/guide.html'

class ContactSupportView(TemplateView):
    template_name = 'carriers/contact_support.html'

class CarrierTermsView(TemplateView):
    template_name = 'carriers/terms.html'

class CarrierPrivacyView(TemplateView):
    template_name = 'carriers/privacy.html'

def profile_redirect(request):
    if hasattr(request.user, 'carrier_profile'):
        return redirect('carriers:carrier_detail', username=request.user.username)
    return redirect('carriers:carrier_list')

def dashboard_redirect(request):
    if hasattr(request.user, 'carrier_profile'):
        return redirect('carriers:carrier_dashboard')
    return redirect('carriers:carrier_list')

class SuccessStoriesView(TemplateView):
    template_name = 'carriers/success_stories.html'

class TestimonialsView(TemplateView):
    template_name = 'carriers/testimonials.html'

# Vues de test et développement
class TestDashboardView(TemplateView):
    template_name = 'carriers/test/dashboard.html'

class TestMissionsView(TemplateView):
    template_name = 'carriers/test/missions.html'

class TestRoutesView(TemplateView):
    template_name = 'carriers/test/routes.html'

class DebugStatisticsView(TemplateView):
    template_name = 'carriers/debug/statistics.html'