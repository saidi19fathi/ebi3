# ~/ebi3/logistics/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from django.db.models import Q, F, Sum, Count, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Reservation, Mission, Route, TransportProposal, TrackingEvent,
    LogisticsSettings, LogisticsOption, ReservationStatus, MissionStatus,
    RouteStatus, TransportProposalStatus
)
from .forms import (
    ReservationForm, ReservationStatusForm, MissionForm, TrackingEventForm,
    RouteForm, RouteSearchForm, TransportProposalForm, ProposalResponseForm,
    LogisticsSettingsForm, QuickReservationForm
)
from ads.models import Ad
from carriers.models import Carrier
from users.models import User
from carriers.models import CarrierNotification


class LogisticsDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord logistique"""
    template_name = 'logistics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'SELLER':
            # Dashboard vendeur
            context['active_reservations'] = Reservation.objects.filter(
                ad__seller=user,
                status__in=['CONFIRMED', 'PAID', 'IN_TRANSIT']
            ).select_related('buyer', 'carrier', 'ad').order_by('-created_at')[:5]

            context['pending_proposals'] = TransportProposal.objects.filter(
                ad__seller=user,
                status='PENDING'
            ).select_related('carrier', 'ad').order_by('-created_at')[:5]

            context['sales_stats'] = Reservation.objects.filter(
                ad__seller=user,
                status='DELIVERED'
            ).aggregate(
                total_sales=Sum('total_price'),
                total_count=Count('id'),
                avg_sale=Avg('total_price')
            )

        elif user.role == 'CARRIER' and hasattr(user, 'carrier_profile'):
            # Dashboard transporteur
            carrier = user.carrier_profile

            context['active_missions'] = Mission.objects.filter(
                carrier=carrier,
                status__in=['SCHEDULED', 'PICKUP_PENDING', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
            ).select_related('reservation', 'reservation__ad', 'reservation__buyer').order_by('-created_at')[:5]

            context['pending_proposals'] = TransportProposal.objects.filter(
                carrier=carrier,
                status='PENDING'
            ).select_related('ad', 'ad__seller').order_by('-created_at')[:5]

            context['available_routes'] = Route.objects.filter(
                carrier=carrier,
                status='ACTIVE',
                departure_date__gte=timezone.now().date()
            ).order_by('departure_date')[:5]

            context['carrier_stats'] = Mission.objects.filter(
                carrier=carrier
            ).aggregate(
                completed_missions=Count('id', filter=Q(status='DELIVERED')),
                total_earnings=Sum('reservation__shipping_cost'),
                avg_rating=carrier.average_rating
            )

        else:
            # Dashboard acheteur
            context['my_reservations'] = Reservation.objects.filter(
                buyer=user
            ).select_related('ad', 'carrier', 'ad__seller').order_by('-created_at')[:5]

            context['tracking_missions'] = Mission.objects.filter(
                reservation__buyer=user,
                status__in=['PICKUP_PENDING', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERY_PENDING']
            ).select_related('reservation', 'reservation__ad').order_by('-created_at')[:5]

        # Statistiques générales
        context['total_reservations'] = Reservation.objects.count()
        context['active_missions_count'] = Mission.objects.filter(
            status__in=['SCHEDULED', 'PICKUP_PENDING', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
        ).count()
        context['available_routes_count'] = Route.objects.filter(
            status='ACTIVE',
            departure_date__gte=timezone.now().date()
        ).count()

        return context


class ReservationListView(LoginRequiredMixin, ListView):
    """Liste des réservations de l'utilisateur"""
    model = Reservation
    template_name = 'logistics/reservation_list.html'
    context_object_name = 'reservations'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.GET.get('status')
        date_filter = self.request.GET.get('date')

        # Base queryset selon le rôle
        if user.role == 'SELLER':
            queryset = Reservation.objects.filter(ad__seller=user)
        elif user.role == 'CARRIER' and hasattr(user, 'carrier_profile'):
            queryset = Reservation.objects.filter(carrier=user.carrier_profile)
        else:
            queryset = Reservation.objects.filter(buyer=user)

        # Filtres
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        if date_filter == 'this_week':
            week_start = timezone.now() - timezone.timedelta(days=7)
            queryset = queryset.filter(created_at__gte=week_start)
        elif date_filter == 'this_month':
            month_start = timezone.now() - timezone.timedelta(days=30)
            queryset = queryset.filter(created_at__gte=month_start)

        return queryset.select_related(
            'ad', 'ad__seller', 'buyer', 'carrier'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = ReservationStatus.choices
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_date_filter'] = self.request.GET.get('date', 'all')

        # Statistiques
        queryset = self.get_queryset()
        context['stats'] = {
            'total': queryset.count(),
            'pending': queryset.filter(status='PENDING').count(),
            'in_transit': queryset.filter(status='IN_TRANSIT').count(),
            'delivered': queryset.filter(status='DELIVERED').count(),
        }

        return context


class ReservationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Détail d'une réservation"""
    model = Reservation
    template_name = 'logistics/reservation_detail.html'
    context_object_name = 'reservation'

    def test_func(self):
        reservation = self.get_object()
        user = self.request.user

        # Autoriser le vendeur, l'acheteur ou le transporteur
        return (
            user == reservation.ad.seller or
            user == reservation.buyer or
            (reservation.carrier and user == reservation.carrier.user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = self.object

        context['can_edit'] = (
            self.request.user == reservation.buyer and
            reservation.status in ['PENDING', 'CONFIRMED']
        )

        context['can_cancel'] = (
            reservation.can_be_cancelled and
            (
                self.request.user == reservation.buyer or
                self.request.user == reservation.ad.seller
            )
        )

        context['can_update_status'] = (
            self.request.user == reservation.ad.seller or
            self.request.user == reservation.buyer
        )

        context['status_form'] = ReservationStatusForm(instance=reservation)

        # Récupérer la mission associée si elle existe
        if hasattr(reservation, 'mission'):
            context['mission'] = reservation.mission
            context['tracking_events'] = reservation.mission.tracking_events.all().order_by('-created_at')

        # Messages entre parties
        context['can_message_seller'] = self.request.user != reservation.ad.seller
        context['can_message_buyer'] = self.request.user != reservation.buyer
        if reservation.carrier:
            context['can_message_carrier'] = self.request.user != reservation.carrier.user

        return context


class ReservationCreateView(LoginRequiredMixin, CreateView):
    """Création d'une réservation"""
    model = Reservation
    form_class = ReservationForm
    template_name = 'logistics/reservation_create.html'

    def get_initial(self):
        initial = super().get_initial()
        self.ad = get_object_or_404(Ad, slug=self.kwargs['slug'])

        # Calculer le prix total initial
        initial['price_agreed'] = self.ad.price

        # Vérifier si l'annonce peut être réservée
        if not self.ad.can_be_reserved:
            messages.error(self.request, _("Cette annonce n'est pas disponible pour réservation."))
            raise PermissionDenied

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ad'] = self.ad
        kwargs['buyer'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ad'] = self.ad

        # Récupérer les transporteurs recommandés pour cette annonce
        if hasattr(self.ad, 'calculate_shipping_cost'):
            context['recommended_carriers'] = Carrier.objects.filter(
                is_available=True,
                max_weight__gte=self.ad.weight if self.ad.weight else 0
            ).order_by('base_price_per_kg')[:3]

        return context

    def form_valid(self, form):
        form.instance.ad = self.ad
        form.instance.buyer = self.request.user
        form.instance.price_agreed = self.ad.price

        # Calculer le prix total
        shipping_cost = form.cleaned_data.get('shipping_cost', 0)
        insurance_cost = form.cleaned_data.get('insurance_cost', 0)
        form.instance.total_price = self.ad.price + shipping_cost + insurance_cost

        response = super().form_valid(form)

        # Créer une notification pour le vendeur
        Notification.objects.create(
            user=self.ad.seller,
            title=_("Nouvelle réservation"),
            message=_("Votre annonce '{}' a été réservée.").format(self.ad.title),
            url=self.object.get_absolute_url(),
            notification_type='RESERVATION_CREATED'
        )

        messages.success(self.request, _("Réservation créée avec succès !"))
        return response

    def get_success_url(self):
        return reverse('logistics:reservation_detail', kwargs={'pk': self.object.pk})


class ReservationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Modification d'une réservation"""
    model = Reservation
    form_class = ReservationForm
    template_name = 'logistics/reservation_update.html'

    def test_func(self):
        reservation = self.get_object()
        return (
            self.request.user == reservation.buyer and
            reservation.status in ['PENDING', 'CONFIRMED']
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ad'] = self.object.ad
        kwargs['buyer'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Réservation mise à jour avec succès !"))
        return response

    def get_success_url(self):
        return reverse('logistics:reservation_detail', kwargs={'pk': self.object.pk})


@method_decorator(require_POST, name='dispatch')
class ReservationCancelView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Annulation d'une réservation"""
    model = Reservation
    fields = []
    http_method_names = ['post']

    def test_func(self):
        reservation = self.get_object()
        return (
            self.request.user == reservation.buyer or
            self.request.user == reservation.ad.seller
        ) and reservation.can_be_cancelled

    def post(self, request, *args, **kwargs):
        reservation = self.get_object()

        # Annuler la réservation
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = timezone.now()
        reservation.cancelled_by = request.user
        reservation.cancellation_reason = request.POST.get('reason', '')
        reservation.save()

        # Mettre à jour l'annonce pour la rendre à nouveau disponible
        reservation.ad.is_reserved = False
        reservation.ad.save()

        # Notifier les autres parties
        if request.user == reservation.buyer:
            # Notifier le vendeur
            Notification.objects.create(
                user=reservation.ad.seller,
                title=_("Réservation annulée"),
                message=_("La réservation de votre annonce '{}' a été annulée par l'acheteur.").format(reservation.ad.title),
                url=reservation.ad.get_absolute_url(),
                notification_type='RESERVATION_CANCELLED'
            )
        else:
            # Notifier l'acheteur
            Notification.objects.create(
                user=reservation.buyer,
                title=_("Réservation annulée"),
                message=_("Votre réservation pour '{}' a été annulée par le vendeur.").format(reservation.ad.title),
                url=reservation.ad.get_absolute_url(),
                notification_type='RESERVATION_CANCELLED'
            )

        messages.success(request, _("Réservation annulée avec succès."))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('logistics:reservation_detail', pk=reservation.pk)


@method_decorator(require_POST, name='dispatch')
class ReservationStatusUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Mise à jour du statut d'une réservation"""
    model = Reservation
    form_class = ReservationStatusForm
    http_method_names = ['post']

    def test_func(self):
        reservation = self.get_object()
        return (
            self.request.user == reservation.ad.seller or
            self.request.user == reservation.buyer
        )

    def form_valid(self, form):
        old_status = self.object.status
        response = super().form_valid(form)

        # Si le statut passe à "EN TRANSIT", créer une mission
        if self.object.status == ReservationStatus.IN_TRANSIT and self.object.carrier:
            Mission.objects.create(
                reservation=self.object,
                carrier=self.object.carrier,
                status=MissionStatus.IN_TRANSIT
            )

        # Notifier les parties concernées
        self.send_status_notification(old_status)

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'new_status': self.object.status})

        messages.success(self.request, _("Statut mis à jour avec succès."))
        return response

    def send_status_notification(self, old_status):
        """Envoyer des notifications selon le changement de statut"""
        if old_status == self.object.status:
            return

        # Notification à l'acheteur
        if self.request.user != self.object.buyer:
            Notification.objects.create(
                user=self.object.buyer,
                title=_("Mise à jour de votre réservation"),
                message=_("Le statut de votre réservation #{} est maintenant '{}'.").format(
                    self.object.id, self.object.get_status_display()
                ),
                url=self.object.get_absolute_url(),
                notification_type='RESERVATION_STATUS_CHANGED'
            )

        # Notification au transporteur s'il y en a un
        if self.object.carrier and self.request.user != self.object.carrier.user:
            Notification.objects.create(
                user=self.object.carrier.user,
                title=_("Mise à jour de mission"),
                message=_("Le statut de la réservation #{} est maintenant '{}'.").format(
                    self.object.id, self.object.get_status_display()
                ),
                url=self.object.get_absolute_url(),
                notification_type='MISSION_STATUS_CHANGED'
            )

    def get_success_url(self):
        return reverse('logistics:reservation_detail', kwargs={'pk': self.object.pk})


class MissionListView(LoginRequiredMixin, ListView):
    """Liste des missions de l'utilisateur"""
    model = Mission
    template_name = 'logistics/mission_list.html'
    context_object_name = 'missions'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role == 'CARRIER' and hasattr(user, 'carrier_profile'):
            # Missions du transporteur
            queryset = Mission.objects.filter(carrier=user.carrier_profile)
        else:
            # Missions où l'utilisateur est acheteur ou vendeur
            queryset = Mission.objects.filter(
                Q(reservation__buyer=user) |
                Q(reservation__ad__seller=user)
            )

        # Filtres
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related(
            'reservation',
            'reservation__ad',
            'reservation__buyer',
            'carrier'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = MissionStatus.choices
        context['current_status'] = self.request.GET.get('status', 'all')
        return context


class MissionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Détail d'une mission avec suivi"""
    model = Mission
    template_name = 'logistics/mission_detail.html'
    context_object_name = 'mission'

    def test_func(self):
        mission = self.get_object()
        user = self.request.user

        # Autoriser le transporteur, l'acheteur ou le vendeur
        return (
            user == mission.carrier.user or
            user == mission.reservation.buyer or
            user == mission.reservation.ad.seller
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mission = self.object

        context['tracking_events'] = mission.tracking_events.all().order_by('-created_at')
        context['tracking_form'] = TrackingEventForm()
        context['can_update_tracking'] = (
            self.request.user == mission.carrier.user and
            mission.status != 'DELIVERED' and
            mission.status != 'CANCELLED'
        )

        # Statistiques de la mission
        context['mission_stats'] = {
            'distance_traveled': mission.distance_km,
            'estimated_time_remaining': None,
            'delivery_on_time': not mission.is_delayed
        }

        return context


class MissionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Mise à jour d'une mission"""
    model = Mission
    form_class = MissionForm
    template_name = 'logistics/mission_update.html'

    def test_func(self):
        mission = self.get_object()
        return self.request.user == mission.carrier.user

    def form_valid(self, form):
        old_status = self.object.status
        response = super().form_valid(form)

        # Si la mission est marquée comme livrée
        if self.object.status == MissionStatus.DELIVERED:
            self.object.actual_delivery = timezone.now()
            self.object.save()

            # Mettre à jour la réservation
            reservation = self.object.reservation
            reservation.status = ReservationStatus.DELIVERED
            reservation.actual_delivery_date = timezone.now().date()
            reservation.save()

        # Envoyer des notifications
        self.send_status_notification(old_status)

        messages.success(self.request, _("Mission mise à jour avec succès."))
        return response

    def send_status_notification(self, old_status):
        """Envoyer des notifications pour changement de statut"""
        if old_status == self.object.status:
            return

        # Notifier l'acheteur
        Notification.objects.create(
            user=self.object.reservation.buyer,
            title=_("Mise à jour de votre livraison"),
            message=_("Le statut de votre livraison est maintenant '{}'.").format(
                self.object.get_status_display()
            ),
            url=self.object.get_absolute_url(),
            notification_type='MISSION_STATUS_CHANGED'
        )

        # Notifier le vendeur
        Notification.objects.create(
            user=self.object.reservation.ad.seller,
            title=_("Mise à jour de livraison"),
            message=_("Le statut de la livraison pour votre annonce est maintenant '{}'.").format(
                self.object.get_status_display()
            ),
            url=self.object.get_absolute_url(),
            notification_type='MISSION_STATUS_CHANGED'
        )

    def get_success_url(self):
        return reverse('logistics:mission_detail', kwargs={'pk': self.object.pk})


@method_decorator(require_POST, name='dispatch')
class TrackingEventCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Création d'un événement de suivi"""
    model = TrackingEvent
    form_class = TrackingEventForm

    def test_func(self):
        mission = get_object_or_404(Mission, pk=self.kwargs['mission_id'])
        return (
            self.request.user == mission.carrier.user and
            mission.status != 'DELIVERED' and
            mission.status != 'CANCELLED'
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['mission'] = get_object_or_404(Mission, pk=self.kwargs['mission_id'])
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        mission = get_object_or_404(Mission, pk=self.kwargs['mission_id'])

        form.instance.mission = mission
        form.instance.created_by = self.request.user

        # Mettre à jour la localisation de la mission
        if form.cleaned_data.get('location'):
            mission.current_location = form.cleaned_data['location']
            mission.save(update_fields=['current_location'])

        response = super().form_valid(form)

        # Notifier l'acheteur
        Notification.objects.create(
            user=mission.reservation.buyer,
            title=_("Mise à jour de suivi"),
            message=_("Nouvel événement de suivi : {}").format(
                form.instance.get_event_type_display()
            ),
            url=mission.get_absolute_url(),
            notification_type='TRACKING_UPDATED'
        )

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'event': {
                    'type': form.instance.get_event_type_display(),
                    'description': form.instance.description,
                    'location': form.instance.location,
                    'created_at': form.instance.created_at.strftime('%d/%m/%Y %H:%M'),
                    'photo_url': form.instance.photo.url if form.instance.photo else None
                }
            })

        messages.success(self.request, _("Événement de suivi ajouté avec succès."))
        return redirect('logistics:mission_detail', pk=mission.pk)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
        return super().form_invalid(form)


class RouteListView(ListView):
    """Liste des routes disponibles"""
    model = Route
    template_name = 'logistics/route_list.html'
    context_object_name = 'routes'
    paginate_by = 12

    def get_queryset(self):
        queryset = Route.objects.filter(
            status=RouteStatus.ACTIVE,
            departure_date__gte=timezone.now().date()
        ).select_related('carrier', 'carrier__user', 'start_country', 'end_country')

        # Appliquer les filtres de recherche
        form = RouteSearchForm(self.request.GET)
        if form.is_valid():
            data = form.cleaned_data

            if data.get('start_city'):
                queryset = queryset.filter(start_city__icontains=data['start_city'])

            if data.get('start_country'):
                queryset = queryset.filter(start_country=data['start_country'])

            if data.get('end_city'):
                queryset = queryset.filter(end_city__icontains=data['end_city'])

            if data.get('end_country'):
                queryset = queryset.filter(end_country=data['end_country'])

            if data.get('departure_date_from'):
                queryset = queryset.filter(departure_date__gte=data['departure_date_from'])

            if data.get('departure_date_to'):
                queryset = queryset.filter(departure_date__lte=data['departure_date_to'])

            if data.get('max_price'):
                # Filtrer par prix (fixe ou calculé)
                queryset = queryset.filter(
                    Q(fixed_price__lte=data['max_price']) |
                    Q(fixed_price__isnull=True, price_per_kg__lte=data['max_price']/10)  # Estimation
                )

            if data.get('min_available_weight'):
                queryset = queryset.filter(available_weight__gte=data['min_available_weight'])

            if data.get('min_available_volume'):
                queryset = queryset.filter(available_volume__gte=data['min_available_volume'])

            if data.get('includes_insurance'):
                queryset = queryset.filter(includes_insurance=True)

            if data.get('includes_packaging'):
                queryset = queryset.filter(includes_packaging=True)

            if data.get('carrier_type'):
                queryset = queryset.filter(carrier__carrier_type=data['carrier_type'])

            # Tri
            sort_by = data.get('sort_by', 'departure_date')
            if sort_by == 'price':
                queryset = queryset.order_by(
                    'fixed_price', 'price_per_kg', 'price_per_m3'
                )
            elif sort_by == '-price':
                queryset = queryset.order_by(
                    '-fixed_price', '-price_per_kg', '-price_per_m3'
                )
            else:
                queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = RouteSearchForm(self.request.GET)
        context['total_count'] = self.get_queryset().count()
        context['countries'] = Route.objects.values_list(
            'start_country__name', flat=True
        ).distinct().order_by('start_country__name')

        # Statistiques
        context['stats'] = {
            'total_routes': Route.objects.filter(
                status=RouteStatus.ACTIVE,
                departure_date__gte=timezone.now().date()
            ).count(),
            'professional_carriers': Route.objects.filter(
                carrier__carrier_type='PROFESSIONAL'
            ).values('carrier').distinct().count(),
            'personal_carriers': Route.objects.filter(
                carrier__carrier_type='PERSONAL'
            ).values('carrier').distinct().count(),
        }

        return context


class RouteDetailView(DetailView):
    """Détail d'une route"""
    model = Route
    template_name = 'logistics/route_detail.html'
    context_object_name = 'route'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = self.object

        # Calculer le prix estimé pour un objet standard
        context['estimated_price'] = route.calculate_price(weight=10, volume=0.1)

        # Vérifier si l'utilisateur peut réserver
        context['can_book'] = (
            self.request.user.is_authenticated and
            route.is_available
        )

        # Routes similaires
        context['similar_routes'] = Route.objects.filter(
            start_country=route.start_country,
            end_country=route.end_country,
            status=RouteStatus.ACTIVE,
            departure_date__gte=timezone.now().date()
        ).exclude(id=route.id).select_related('carrier')[:4]

        return context

    def post(self, request, *args, **kwargs):
        """Réservation d'une route"""
        if not request.user.is_authenticated:
            return redirect('users:login') + f'?next={request.path}'

        route = self.get_object()

        if not route.is_available:
            messages.error(request, _("Cette route n'est plus disponible."))
            return redirect('logistics:route_detail', pk=route.pk)

        # Rediriger vers la création de réservation avec cette route
        return redirect('logistics:reservation_create_with_route', route_id=route.pk)


class RouteCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Création d'une route"""
    model = Route
    form_class = RouteForm
    template_name = 'logistics/route_create.html'

    def test_func(self):
        # Seuls les transporteurs peuvent créer des routes
        return (
            self.request.user.role == 'CARRIER' and
            hasattr(self.request.user, 'carrier_profile')
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['carrier'] = self.request.user.carrier_profile
        return kwargs

    def form_valid(self, form):
        form.instance.carrier = self.request.user.carrier_profile

        # S'assurer que les capacités disponibles sont égales aux capacités max initialement
        if not form.instance.pk:
            form.instance.available_weight = form.instance.max_weight
            form.instance.available_volume = form.instance.max_volume

        response = super().form_valid(form)
        messages.success(self.request, _("Route créée avec succès !"))
        return response

    def get_success_url(self):
        return reverse('logistics:route_detail', kwargs={'pk': self.object.pk})


class RouteUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Modification d'une route"""
    model = Route
    form_class = RouteForm
    template_name = 'logistics/route_update.html'

    def test_func(self):
        route = self.get_object()
        return self.request.user == route.carrier.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['carrier'] = self.object.carrier
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Route mise à jour avec succès !"))
        return response

    def get_success_url(self):
        return reverse('logistics:route_detail', kwargs={'pk': self.object.pk})


@method_decorator(require_POST, name='dispatch')
class RouteDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Suppression d'une route"""
    model = Route

    def test_func(self):
        route = self.get_object()
        return self.request.user == route.carrier.user

    def delete(self, request, *args, **kwargs):
        route = self.get_object()
        route.delete()

        messages.success(request, _("Route supprimée avec succès."))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('logistics:route_list')


class TransportProposalCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Création d'une proposition de transport"""
    model = TransportProposal
    form_class = TransportProposalForm
    template_name = 'logistics/proposal_create.html'

    def test_func(self):
        # Seuls les transporteurs peuvent faire des propositions
        return (
            self.request.user.role == 'CARRIER' and
            hasattr(self.request.user, 'carrier_profile')
        )

    def get_initial(self):
        initial = super().get_initial()
        self.ad = get_object_or_404(Ad, slug=self.kwargs['slug'])
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ad'] = self.ad
        kwargs['carrier'] = self.request.user.carrier_profile
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ad'] = self.ad
        return context

    def form_valid(self, form):
        form.instance.ad = self.ad
        form.instance.carrier = self.request.user.carrier_profile

        # Définir la date d'expiration (7 jours par défaut)
        if not form.instance.expires_at:
            form.instance.expires_at = timezone.now() + timezone.timedelta(days=7)

        response = super().form_valid(form)

        # Créer une notification pour le vendeur
        Notification.objects.create(
            user=self.ad.seller,
            title=_("Nouvelle proposition de transport"),
            message=_("Un transporteur a fait une proposition pour votre annonce '{}'.").format(self.ad.title),
            url=self.object.get_absolute_url(),
            notification_type='PROPOSAL_CREATED'
        )

        messages.success(self.request, _("Proposition envoyée avec succès !"))
        return response

    def get_success_url(self):
        return reverse('logistics:proposal_detail', kwargs={'pk': self.object.pk})


class TransportProposalDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Détail d'une proposition de transport"""
    model = TransportProposal
    template_name = 'logistics/proposal_detail.html'
    context_object_name = 'proposal'

    def test_func(self):
        proposal = self.get_object()
        user = self.request.user

        # Autoriser le vendeur ou le transporteur
        return (
            user == proposal.ad.seller or
            user == proposal.carrier.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proposal = self.object

        context['can_respond'] = (
            self.request.user == proposal.ad.seller and
            proposal.can_be_accepted
        )

        if context['can_respond']:
            context['response_form'] = ProposalResponseForm(instance=proposal)

        context['is_expired'] = proposal.is_expired
        context['days_until_expiry'] = proposal.days_until_expiry

        return context


@method_decorator(require_POST, name='dispatch')
class TransportProposalRespondView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Réponse à une proposition de transport"""
    model = TransportProposal
    form_class = ProposalResponseForm

    def test_func(self):
        proposal = self.get_object()
        return (
            self.request.user == proposal.ad.seller and
            proposal.can_be_accepted
        )

    def form_valid(self, form):
        old_status = self.object.status
        response = super().form_valid(form)

        # Si la proposition est acceptée, créer une réservation
        if self.object.status == TransportProposalStatus.ACCEPTED:
            reservation = Reservation.objects.create(
                ad=self.object.ad,
                buyer=None,  # À définir plus tard
                carrier=self.object.carrier,
                logistics_option=LogisticsOption.WITH_CARRIER,
                price_agreed=self.object.ad.price,
                shipping_cost=self.object.proposed_price,
                total_price=self.object.ad.price + self.object.proposed_price,
                requires_insurance=self.object.includes_insurance,
                insurance_value=self.object.insurance_value,
                requires_packaging=self.object.includes_packaging,
                pickup_date=self.object.estimated_pickup_date,
                delivery_date=self.object.estimated_delivery_date,
                status=ReservationStatus.PENDING
            )

            # Notifier le transporteur
            Notification.objects.create(
                user=self.object.carrier.user,
                title=_("Proposition acceptée !"),
                message=_("Votre proposition pour '{}' a été acceptée.").format(self.object.ad.title),
                url=reservation.get_absolute_url(),
                notification_type='PROPOSAL_ACCEPTED'
            )

        elif self.object.status == TransportProposalStatus.REJECTED:
            # Notifier le transporteur
            Notification.objects.create(
                user=self.object.carrier.user,
                title=_("Proposition refusée"),
                message=_("Votre proposition pour '{}' a été refusée.").format(self.object.ad.title),
                url=self.object.ad.get_absolute_url(),
                notification_type='PROPOSAL_REJECTED'
            )

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'new_status': self.object.status})

        messages.success(self.request, _("Réponse envoyée avec succès."))
        return redirect('logistics:proposal_detail', pk=self.object.pk)

    def get_success_url(self):
        return reverse('logistics:proposal_detail', kwargs={'pk': self.object.pk})


@login_required
@require_POST
def cancel_proposal(request, pk):
    """Annulation d'une proposition par le transporteur"""
    proposal = get_object_or_404(TransportProposal, pk=pk)

    if request.user != proposal.carrier.user:
        return HttpResponseForbidden()

    if not proposal.can_be_accepted:
        messages.error(request, _("Cette proposition ne peut pas être annulée."))
        return redirect('logistics:proposal_detail', pk=proposal.pk)

    proposal.status = TransportProposalStatus.CANCELLED
    proposal.responded_at = timezone.now()
    proposal.save()

    messages.success(request, _("Proposition annulée avec succès."))
    return redirect('logistics:proposal_detail', pk=proposal.pk)


class MyProposalsListView(LoginRequiredMixin, ListView):
    """Liste des propositions de l'utilisateur"""
    template_name = 'logistics/proposal_list.html'
    context_object_name = 'proposals'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role == 'SELLER':
            # Propositions reçues pour les annonces du vendeur
            queryset = TransportProposal.objects.filter(ad__seller=user)
        elif user.role == 'CARRIER' and hasattr(user, 'carrier_profile'):
            # Propositions faites par le transporteur
            queryset = TransportProposal.objects.filter(carrier=user.carrier_profile)
        else:
            queryset = TransportProposal.objects.none()

        # Filtre par statut
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related('ad', 'carrier', 'carrier__user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TransportProposalStatus.choices
        context['current_status'] = self.request.GET.get('status', 'all')
        return context


# API Views pour le suivi en temps réel

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class TrackingAPIView(DetailView):
    """API pour récupérer les événements de suivi d'une mission"""
    model = Mission

    def get(self, request, *args, **kwargs):
        mission = self.get_object()

        # Vérifier les permissions
        if not (
            request.user == mission.carrier.user or
            request.user == mission.reservation.buyer or
            request.user == mission.reservation.ad.seller
        ):
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Récupérer les événements de suivi
        events = mission.tracking_events.all().order_by('-created_at')

        events_data = []
        for event in events:
            events_data.append({
                'id': event.id,
                'event_type': event.get_event_type_display(),
                'description': event.description,
                'location': event.location,
                'latitude': event.latitude,
                'longitude': event.longitude,
                'photo_url': event.photo.url if event.photo else None,
                'created_at': event.created_at.isoformat(),
                'created_by': event.created_by.username if event.created_by else None
            })

        return JsonResponse({
            'mission_id': mission.id,
            'status': mission.get_status_display(),
            'current_location': mission.current_location,
            'estimated_delivery': mission.estimated_delivery.isoformat() if mission.estimated_delivery else None,
            'progress': mission.progress_percentage,
            'events': events_data
        })


@login_required
@require_POST
@csrf_exempt
def update_location_api(request, mission_id):
    """API pour mettre à jour la localisation d'une mission"""
    mission = get_object_or_404(Mission, pk=mission_id)

    # Vérifier que l'utilisateur est le transporteur
    if request.user != mission.carrier.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')
    location = request.POST.get('location')

    if latitude and longitude:
        mission.latitude = float(latitude)
        mission.longitude = float(longitude)

    if location:
        mission.current_location = location

    mission.save()

    # Créer un événement de suivi automatique
    TrackingEvent.objects.create(
        mission=mission,
        event_type='IN_TRANSIT',
        description=_('Mise à jour de localisation'),
        location=mission.current_location or _('Localisation inconnue'),
        latitude=mission.latitude,
        longitude=mission.longitude,
        created_by=request.user
    )

    return JsonResponse({
        'success': True,
        'location': mission.current_location,
        'latitude': mission.latitude,
        'longitude': mission.longitude,
        'updated_at': timezone.now().isoformat()
    })


# Vues pour l'administration

class LogisticsSettingsView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vue pour modifier les paramètres logistiques"""
    model = LogisticsSettings
    form_class = LogisticsSettingsForm
    template_name = 'logistics/settings.html'

    def test_func(self):
        # Seuls les administrateurs peuvent modifier les paramètres
        return self.request.user.is_staff

    def get_object(self):
        return LogisticsSettings.load()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Paramètres mis à jour avec succès."))
        return response

    def get_success_url(self):
        return reverse('logistics:settings')


# Vues utilitaires

class LogisticsFAQView(TemplateView):
    """FAQ sur la logistique"""
    template_name = 'logistics/faq.html'


class LogisticsGuideView(TemplateView):
    """Guide d'utilisation de la logistique"""
    template_name = 'logistics/guide.html'


@login_required
def reservation_create_with_route(request, route_id):
    """Créer une réservation à partir d'une route"""
    route = get_object_or_404(Route, pk=route_id)

    if not route.is_available:
        messages.error(request, _("Cette route n'est plus disponible."))
        return redirect('logistics:route_detail', pk=route_id)

    # Rediriger vers la liste des annonces compatibles avec cette route
    return redirect('ads:ad_list') + f'?country_from={route.start_country_id}&country_to={route.end_country_id}'


# Vue de rapport/logs

class LogisticsReportsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Rapports et statistiques logistiques"""
    template_name = 'logistics/reports.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques générales
        context['stats'] = {
            'total_reservations': Reservation.objects.count(),
            'reservations_this_month': Reservation.objects.filter(
                created_at__month=timezone.now().month,
                created_at__year=timezone.now().year
            ).count(),
            'total_missions': Mission.objects.count(),
            'completed_missions': Mission.objects.filter(status='DELIVERED').count(),
            'total_routes': Route.objects.count(),
            'active_routes': Route.objects.filter(status='ACTIVE').count(),
            'total_proposals': TransportProposal.objects.count(),
            'accepted_proposals': TransportProposal.objects.filter(status='ACCEPTED').count(),
        }

        # Revenus
        context['revenue_stats'] = Reservation.objects.filter(
            status='DELIVERED'
        ).aggregate(
            total_revenue=Sum('total_price'),
            shipping_revenue=Sum('shipping_cost'),
            avg_transaction=Avg('total_price')
        )

        # Tendances
        last_30_days = timezone.now() - timezone.timedelta(days=30)
        context['trends'] = {
            'reservations_last_30': Reservation.objects.filter(
                created_at__gte=last_30_days
            ).count(),
            'reservations_previous_30': Reservation.objects.filter(
                created_at__gte=last_30_days - timezone.timedelta(days=30),
                created_at__lt=last_30_days
            ).count(),
        }

        return context


# Vues de notification

@login_required
def logistics_notifications(request):
    """Notifications spécifiques à la logistique"""
    notifications = Notification.objects.filter(
        user=request.user,
        notification_type__in=[
            'RESERVATION_CREATED', 'RESERVATION_STATUS_CHANGED',
            'RESERVATION_CANCELLED', 'MISSION_STATUS_CHANGED',
            'TRACKING_UPDATED', 'PROPOSAL_CREATED',
            'PROPOSAL_ACCEPTED', 'PROPOSAL_REJECTED'
        ]
    ).order_by('-created_at')[:50]

    # Marquer comme lues
    unread_notifications = notifications.filter(is_read=False)
    unread_notifications.update(is_read=True)

    return render(request, 'logistics/notifications.html', {
        'notifications': notifications
    })