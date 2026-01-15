# ~/ebi3/carriers/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json
import logging

from .models import (
    Carrier, CarrierRoute, Mission, CollectionDay,
    CarrierDocument, FinancialTransaction, CarrierReview,
    CarrierOffer, CarrierAvailability, CarrierNotification,
    CarrierStatistics, ExpenseReport
)
from .forms import (
    CarrierProfileForm, CarrierRouteForm,
    MissionForm, CollectionDayForm, DocumentUploadForm,
    FinancialTransactionForm, CarrierReviewForm, CarrierOfferForm,
    MissionAcceptanceForm, MissionStatusUpdateForm, DeliveryProofForm,
    MissionFilterForm, RouteOptimizationForm, CarrierSearchForm
)
from users.models import User

logger = logging.getLogger(__name__)



def is_carrier(user):
    """Vérifie si l'utilisateur est un transporteur"""
    return hasattr(user, 'carrier_profile')


def is_approved_carrier(user):
    """Vérifie si l'utilisateur est un transporteur approuvé"""
    if hasattr(user, 'carrier_profile'):
        return user.carrier_profile.status == Carrier.Status.APPROVED
    return False


def is_carrier_owner(user, carrier):
    """Vérifie si l'utilisateur est propriétaire du transporteur"""
    return user == carrier.user




@login_required
def carrier_dashboard(request):
    """Tableau de bord du transporteur"""
    try:
        carrier = request.user.carrier_profile
    except Carrier.DoesNotExist:
        return redirect('carriers:register')

    # Récupérer les statistiques
    today = timezone.now().date()

    # Missions du jour
    today_missions = Mission.objects.filter(
        carrier=carrier,
        preferred_pickup_date=today
    ).order_by('collection_order')

    # Missions en attente
    pending_missions = Mission.objects.filter(
        carrier=carrier,
        status=Mission.MissionStatus.PENDING
    ).count()

    # Missions en cours
    active_missions = Mission.objects.filter(
        carrier=carrier,
        status__in=[
            Mission.MissionStatus.ACCEPTED,
            Mission.MissionStatus.COLLECTING,
            Mission.MissionStatus.IN_TRANSIT,
            Mission.MissionStatus.DELIVERING
        ]
    ).count()

    # Revenus du mois
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    monthly_income = FinancialTransaction.objects.filter(
        carrier=carrier,
        transaction_type=FinancialTransaction.TransactionType.PAYMENT,
        transaction_date__range=[month_start, month_end],
        is_completed=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Notifications non lues
    unread_notifications = CarrierNotification.objects.filter(
        carrier=carrier,
        is_read=False
    ).count()

    # Prochain jour de collecte
    next_collection_day = CollectionDay.objects.filter(
        carrier=carrier,
        date__gte=today,
        is_completed=False
    ).order_by('date').first()

    context = {
        'carrier': carrier,
        'today_missions': today_missions,
        'pending_missions': pending_missions,
        'active_missions': active_missions,
        'monthly_income': monthly_income,
        'unread_notifications': unread_notifications,
        'next_collection_day': next_collection_day,
        'today': today,
    }

    return render(request, 'carriers/dashboard.html', context)


@login_required
@user_passes_test(is_carrier)
def carrier_profile(request):
    """Profil du transporteur"""
    carrier = request.user.carrier_profile

    if request.method == 'POST':
        form = CarrierProfileForm(request.POST, request.FILES, instance=carrier)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profil mis à jour avec succès !"))
            return redirect('carriers:profile')
    else:
        form = CarrierProfileForm(instance=carrier)

    # Documents du transporteur
    documents = CarrierDocument.objects.filter(carrier=carrier)

    # Routes actives
    routes = CarrierRoute.objects.filter(carrier=carrier, is_active=True)

    context = {
        'carrier': carrier,
        'form': form,
        'documents': documents,
        'routes': routes,
    }

    return render(request, 'carriers/profile.html', context)


@login_required
@user_passes_test(is_carrier)
def mission_list(request):
    """Liste des missions"""
    carrier = request.user.carrier_profile

    form = MissionFilterForm(request.GET or None)

    missions = Mission.objects.filter(carrier=carrier)

    if form.is_valid():
        status = form.cleaned_data.get('status')
        priority = form.cleaned_data.get('priority')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        if status:
            missions = missions.filter(status=status)

        if priority:
            missions = missions.filter(priority=priority)

        if date_from:
            missions = missions.filter(preferred_pickup_date__gte=date_from)

        if date_to:
            missions = missions.filter(preferred_pickup_date__lte=date_to)

    # Statistiques
    stats = {
        'total': missions.count(),
        'pending': missions.filter(status=Mission.MissionStatus.PENDING).count(),
        'active': missions.filter(
            status__in=[
                Mission.MissionStatus.ACCEPTED,
                Mission.MissionStatus.COLLECTING,
                Mission.MissionStatus.IN_TRANSIT,
                Mission.MissionStatus.DELIVERING
            ]
        ).count(),
        'delivered': missions.filter(status=Mission.MissionStatus.DELIVERED).count(),
    }

    context = {
        'missions': missions.order_by('-created_at'),
        'form': form,
        'stats': stats,
    }

    return render(request, 'carriers/missions/list.html', context)


@login_required
@user_passes_test(is_carrier)
def mission_detail(request, pk):
    """Détail d'une mission"""
    mission = get_object_or_404(Mission, pk=pk)
    carrier = request.user.carrier_profile

    # Vérifier que la mission appartient au transporteur
    if mission.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à cette mission."))

    # Formulaires
    status_form = MissionStatusUpdateForm(instance=mission)
    delivery_form = DeliveryProofForm(instance=mission)

    # Transactions liées
    transactions = FinancialTransaction.objects.filter(
        mission=mission,
        carrier=carrier
    )

    context = {
        'mission': mission,
        'status_form': status_form,
        'delivery_form': delivery_form,
        'transactions': transactions,
    }

    return render(request, 'carriers/missions/detail.html', context)


@login_required
@user_passes_test(is_carrier)
def mission_accept(request, pk):
    """Accepter ou refuser une mission"""
    mission = get_object_or_404(Mission, pk=pk)
    carrier = request.user.carrier_profile

    if mission.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à cette mission."))

    if mission.status != Mission.MissionStatus.PENDING:
        messages.error(request, _("Cette mission ne peut plus être acceptée ou refusée."))
        return redirect('carriers:mission_detail', pk=mission.pk)

    if request.method == 'POST':
        form = MissionAcceptanceForm(request.POST)
        if form.is_valid():
            accept = form.cleaned_data.get('accept')

            if accept:
                mission.accept()
                messages.success(request, _("Mission acceptée avec succès !"))
            else:
                mission.status = Mission.MissionStatus.CANCELLED
                mission.save()
                messages.info(request, _("Mission refusée."))

            return redirect('carriers:mission_detail', pk=mission.pk)

    return redirect('carriers:mission_detail', pk=mission.pk)


@login_required
@user_passes_test(is_carrier)
def update_mission_status(request, pk):
    """Mettre à jour le statut d'une mission"""
    mission = get_object_or_404(Mission, pk=pk)
    carrier = request.user.carrier_profile

    if mission.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à cette mission."))

    if request.method == 'POST':
        form = MissionStatusUpdateForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()

            # Si la mission passe en collecte, mettre à jour la date de collecte
            if mission.status == Mission.MissionStatus.COLLECTING:
                mission.actual_pickup_date = timezone.now()
                mission.save(update_fields=['actual_pickup_date'])

            messages.success(request, _("Statut de la mission mis à jour."))

    return redirect('carriers:mission_detail', pk=mission.pk)


@login_required
@user_passes_test(is_carrier)
def upload_delivery_proof(request, pk):
    """Uploader la preuve de livraison"""
    mission = get_object_or_404(Mission, pk=pk)
    carrier = request.user.carrier_profile

    if mission.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à cette mission."))

    if request.method == 'POST':
        form = DeliveryProofForm(request.POST, request.FILES, instance=mission)
        if form.is_valid():
            mission = form.save(commit=False)
            mission.status = Mission.MissionStatus.DELIVERED
            mission.actual_delivery_date = timezone.now()
            mission.save()

            messages.success(request, _("Preuve de livraison enregistrée !"))

    return redirect('carriers:mission_detail', pk=mission.pk)


@login_required
@user_passes_test(is_carrier)
def collection_days(request):
    """Gestion des jours de collecte"""
    carrier = request.user.carrier_profile

    # Jours de collecte à venir
    upcoming_days = CollectionDay.objects.filter(
        carrier=carrier,
        date__gte=timezone.now().date()
    ).order_by('date')

    # Jours de collecte passés
    past_days = CollectionDay.objects.filter(
        carrier=carrier,
        date__lt=timezone.now().date()
    ).order_by('-date')[:10]

    # Missions sans jour de collecte assigné
    unassigned_missions = Mission.objects.filter(
        carrier=carrier,
        status__in=[Mission.MissionStatus.ACCEPTED, Mission.MissionStatus.PENDING],
        preferred_pickup_date__gte=timezone.now().date()
    ).exclude(
        preferred_pickup_date__in=upcoming_days.values_list('date', flat=True)
    )

    if request.method == 'POST':
        form = CollectionDayForm(request.POST)
        if form.is_valid():
            collection_day = form.save(commit=False)
            collection_day.carrier = carrier
            collection_day.save()

            messages.success(request, _("Jour de collecte créé avec succès !"))
            return redirect('carriers:collection_days')
    else:
        form = CollectionDayForm()

    context = {
        'upcoming_days': upcoming_days,
        'past_days': past_days,
        'unassigned_missions': unassigned_missions,
        'form': form,
    }

    return render(request, 'carriers/collection/days.html', context)


@login_required
@user_passes_test(is_carrier)
def collection_day_detail(request, pk):
    """Détail d'un jour de collecte"""
    collection_day = get_object_or_404(CollectionDay, pk=pk)
    carrier = request.user.carrier_profile

    if collection_day.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce jour de collecte."))

    # Missions associées
    missions = Mission.objects.filter(
        carrier=carrier,
        preferred_pickup_date=collection_day.date,
        status__in=[Mission.MissionStatus.ACCEPTED, Mission.MissionStatus.COLLECTING]
    ).order_by('collection_order')

    # Calcul de la planification
    planning = collection_day.calculate_planning()

    # Générer la liste de collecte
    collection_list = collection_day.generate_collection_list()

    # Formulaire d'optimisation
    optimization_form = RouteOptimizationForm()

    context = {
        'collection_day': collection_day,
        'missions': missions,
        'planning': planning,
        'collection_list': collection_list,
        'optimization_form': optimization_form,
    }

    return render(request, 'carriers/collection/detail.html', context)


@login_required
@user_passes_test(is_carrier)
def organize_collection(request, pk):
    """Organiser la collecte pour un jour donné"""
    collection_day = get_object_or_404(CollectionDay, pk=pk)
    carrier = request.user.carrier_profile

    if collection_day.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce jour de collecte."))

    if request.method == 'POST':
        # Récupérer l'ordre de collecte
        order_data = json.loads(request.POST.get('order_data', '[]'))

        for item in order_data:
            mission_id = item.get('mission_id')
            order = item.get('order')
            position = item.get('position')

            try:
                mission = Mission.objects.get(pk=mission_id, carrier=carrier)
                mission.collection_order = order
                mission.position_in_vehicle = position
                mission.save()
            except Mission.DoesNotExist:
                pass

        messages.success(request, _("Collecte organisée avec succès !"))

        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


@login_required
@user_passes_test(is_carrier)
def optimize_route(request, pk):
    """Optimiser l'itinéraire de collecte"""
    collection_day = get_object_or_404(CollectionDay, pk=pk)
    carrier = request.user.carrier_profile

    if collection_day.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce jour de collecte."))

    if request.method == 'POST':
        form = RouteOptimizationForm(request.POST)
        if form.is_valid():
            # Optimiser l'itinéraire
            optimized_route = collection_day.optimize_route()

            messages.success(request, _("Itinéraire optimisé avec succès !"))

            return JsonResponse({
                'success': True,
                'route': optimized_route
            })

    return JsonResponse({'success': False})


@login_required
@user_passes_test(is_carrier)
def start_collection(request, pk):
    """Démarrer la collecte"""
    collection_day = get_object_or_404(CollectionDay, pk=pk)
    carrier = request.user.carrier_profile

    if collection_day.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce jour de collecte."))

    collection_day.start_collection()
    messages.success(request, _("Collecte démarrée !"))

    return redirect('carriers:collection_day_detail', pk=collection_day.pk)


@login_required
@user_passes_test(is_carrier)
def financial_dashboard(request):
    """Tableau de bord financier"""
    carrier = request.user.carrier_profile

    # Transactions récentes
    recent_transactions = FinancialTransaction.objects.filter(
        carrier=carrier
    ).order_by('-transaction_date')[:20]

    # Statistiques financières
    today = timezone.now().date()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=today.weekday())

    # Revenus
    monthly_income = FinancialTransaction.objects.filter(
        carrier=carrier,
        transaction_type=FinancialTransaction.TransactionType.PAYMENT,
        transaction_date__gte=month_start,
        is_completed=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    weekly_income = FinancialTransaction.objects.filter(
        carrier=carrier,
        transaction_type=FinancialTransaction.TransactionType.PAYMENT,
        transaction_date__gte=week_start,
        is_completed=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Dépenses
    monthly_expenses = FinancialTransaction.objects.filter(
        carrier=carrier,
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
        transaction_date__gte=month_start,
        is_completed=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Catégories de dépenses
    expense_categories = FinancialTransaction.objects.filter(
        carrier=carrier,
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
        transaction_date__year=today.year
    ).values('expense_category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')

    # Missions non payées
    unpaid_missions = Mission.objects.filter(
        carrier=carrier,
        status=Mission.MissionStatus.DELIVERED
    ).exclude(
        pk__in=FinancialTransaction.objects.filter(
            transaction_type=FinancialTransaction.TransactionType.PAYMENT
        ).values_list('mission', flat=True)
    )

    if request.method == 'POST':
        form = FinancialTransactionForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.carrier = carrier
            transaction.save()

            messages.success(request, _("Transaction enregistrée !"))
            return redirect('carriers:financial_dashboard')
    else:
        form = FinancialTransactionForm(carrier=carrier)

    context = {
        'recent_transactions': recent_transactions,
        'monthly_income': monthly_income,
        'weekly_income': weekly_income,
        'monthly_expenses': monthly_expenses,
        'expense_categories': expense_categories,
        'unpaid_missions': unpaid_missions,
        'form': form,
        'today': today,
    }

    return render(request, 'carriers/financial/dashboard.html', context)


@login_required
@user_passes_test(is_carrier)
def expense_reports(request):
    """Rapports de dépenses"""
    carrier = request.user.carrier_profile

    reports = ExpenseReport.objects.filter(carrier=carrier).order_by('-period_end')

    if request.method == 'POST':
        # Générer un nouveau rapport
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')

        if period_start and period_end:
            report = ExpenseReport.objects.create(
                carrier=carrier,
                period_start=period_start,
                period_end=period_end
            )
            report.calculate_totals()

            messages.success(request, _("Rapport généré avec succès !"))
            return redirect('carriers:expense_report_detail', pk=report.pk)

    context = {
        'reports': reports,
    }

    return render(request, 'carriers/financial/reports.html', context)


@login_required
@user_passes_test(is_carrier)
def expense_report_detail(request, pk):
    """Détail d'un rapport de dépenses"""
    report = get_object_or_404(ExpenseReport, pk=pk)
    carrier = request.user.carrier_profile

    if report.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce rapport."))

    # Générer le rapport détaillé
    detailed_report = report.generate_report()

    context = {
        'report': report,
        'detailed_report': detailed_report,
    }

    return render(request, 'carriers/financial/report_detail.html', context)


@login_required
@user_passes_test(is_carrier)
def marketplace_offers(request):
    """Gérer les offres sur la marketplace"""
    carrier = request.user.carrier_profile

    # Offres actives
    active_offers = CarrierOffer.objects.filter(
        carrier=carrier,
        is_active=True
    ).order_by('-created_at')

    # Offres expirées
    expired_offers = CarrierOffer.objects.filter(
        carrier=carrier,
        available_until__lt=timezone.now()
    ).order_by('-available_until')[:10]

    if request.method == 'POST':
        form = CarrierOfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.carrier = carrier
            offer.save()

            messages.success(request, _("Offre créée avec succès !"))
            return redirect('carriers:marketplace_offers')
    else:
        form = CarrierOfferForm()

    context = {
        'active_offers': active_offers,
        'expired_offers': expired_offers,
        'form': form,
    }

    return render(request, 'carriers/marketplace/offers.html', context)

@login_required
def marketplace_search(request):
    """Rechercher des transporteurs"""
    form = CarrierSearchForm(request.GET or None)
    results = []

    if form.is_valid():
        # Construire la requête de recherche
        query = Q(status=Carrier.Status.APPROVED, is_available=True)  # CORRIGÉ: utiliser is_available

        start_country = form.cleaned_data.get('start_country')
        if start_country:
            query &= Q(routes__start_country=start_country)

        start_city = form.cleaned_data.get('start_city')
        if start_city:
            query &= Q(routes__start_city__icontains=start_city)

        end_country = form.cleaned_data.get('end_country')
        if end_country:
            query &= Q(routes__end_country=end_country)

        end_city = form.cleaned_data.get('end_city')
        if end_city:
            query &= Q(routes__end_city__icontains=end_city)

        departure_date = form.cleaned_data.get('departure_date')
        if departure_date:
            query &= Q(routes__departure_date=departure_date)

        max_weight = form.cleaned_data.get('max_weight')
        if max_weight:
            query &= Q(max_weight__gte=max_weight)

        max_volume = form.cleaned_data.get('max_volume')
        if max_volume:
            query &= Q(max_volume__gte=max_volume)

        vehicle_types = form.cleaned_data.get('vehicle_types')
        if vehicle_types:
            query &= Q(vehicle_type__in=vehicle_types)

        min_rating = form.cleaned_data.get('min_rating')
        if min_rating:
            # Utiliser le champ correct pour la note moyenne
            query &= Q(average_rating__gte=min_rating)  # CORRIGÉ: utiliser average_rating

        results = Carrier.objects.filter(query).distinct().order_by('-average_rating')  # CORRIGÉ

    context = {
        'form': form,
        'results': results,
    }

    return render(request, 'carriers/marketplace/search.html', context)

def carrier_public_profile(request, username):
    """Profil public d'un transporteur"""
    carrier = get_object_or_404(Carrier, user__username=username)

    # Vérifier que le transporteur est approuvé
    if carrier.status != Carrier.Status.APPROVED:
        return HttpResponseForbidden(_("Ce profil n'est pas disponible."))

    # Avis vérifiés
    reviews = CarrierReview.objects.filter(
        carrier=carrier,
        is_approved=True,
        is_visible=True
    ).order_by('-created_at')[:10]

    # Routes actives
    routes = CarrierRoute.objects.filter(
        carrier=carrier,
        is_active=True,
        departure_date__gte=timezone.now().date()
    ).order_by('departure_date')

    # Offres actives
    offers = CarrierOffer.objects.filter(
        carrier=carrier,
        is_active=True,
        is_booked=False,
        available_until__gte=timezone.now()
    ).order_by('available_from')

    context = {
        'carrier': carrier,
        'reviews': reviews,
        'routes': routes,
        'offers': offers,
    }

    return render(request, 'carriers/public/profile.html', context)


@login_required
def leave_review(request, username):
    """Laisser un avis sur un transporteur"""
    carrier = get_object_or_404(Carrier, user__username=username)

    # Vérifier que l'utilisateur peut laisser un avis
    # (doit avoir eu une mission avec ce transporteur)
    has_mission = Mission.objects.filter(
        sender=request.user,
        carrier=carrier,
        status=Mission.MissionStatus.DELIVERED
    ).exists()

    if not has_mission:
        messages.error(request,
            _("Vous devez avoir eu une mission livrée avec ce transporteur pour laisser un avis."))
        return redirect('carriers:public_profile', username=username)

    # Vérifier s'il y a déjà un avis
    existing_review = CarrierReview.objects.filter(
        carrier=carrier,
        reviewer=request.user
    ).first()

    if request.method == 'POST':
        if existing_review:
            form = CarrierReviewForm(request.POST, instance=existing_review)
        else:
            form = CarrierReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.carrier = carrier
            review.reviewer = request.user

            # L'avis doit être approuvé par un admin
            review.is_approved = False

            review.save()

            messages.success(request,
                _("Votre avis a été soumis et sera publié après validation."))
            return redirect('carriers:public_profile', username=username)
    else:
        if existing_review:
            form = CarrierReviewForm(instance=existing_review)
        else:
            form = CarrierReviewForm()

    context = {
        'carrier': carrier,
        'form': form,
        'existing_review': existing_review,
    }

    return render(request, 'carriers/public/review.html', context)


@login_required
@user_passes_test(is_carrier)
def notifications(request):
    """Gestion des notifications"""
    carrier = request.user.carrier_profile

    # Marquer toutes comme lues
    if request.method == 'POST' and request.POST.get('mark_all_read'):
        CarrierNotification.objects.filter(
            carrier=carrier,
            is_read=False
        ).update(is_read=True)

        messages.success(request, _("Toutes les notifications marquées comme lues."))
        return redirect('carriers:notifications')

    # Notifications non lues
    unread_notifications = CarrierNotification.objects.filter(
        carrier=carrier,
        is_read=False
    ).order_by('-created_at')

    # Notifications lues (récentes)
    read_notifications = CarrierNotification.objects.filter(
        carrier=carrier,
        is_read=True
    ).order_by('-created_at')[:50]

    context = {
        'unread_notifications': unread_notifications,
        'read_notifications': read_notifications,
    }

    return render(request, 'carriers/notifications/list.html', context)


@login_required
@user_passes_test(is_carrier)
def mark_notification_read(request, pk):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(CarrierNotification, pk=pk)
    carrier = request.user.carrier_profile

    if notification.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à cette notification."))

    notification.mark_as_read()

    if request.headers.get('HTTP_REFERER'):
        return redirect(request.headers.get('HTTP_REFERER'))

    return redirect('carriers:notifications')


@login_required
@user_passes_test(is_carrier)
def documents_management(request):
    """Gestion des documents"""
    carrier = request.user.carrier_profile

    documents = CarrierDocument.objects.filter(carrier=carrier).order_by('-created_at')

    # Documents expirés ou à renouveler
    expired_documents = []
    renewal_documents = []

    for doc in documents:
        if doc.is_expired():
            expired_documents.append(doc)
        elif doc.needs_renewal():
            renewal_documents.append(doc)

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.carrier = carrier
            document.save()

            messages.success(request, _("Document uploadé avec succès !"))
            return redirect('carriers:documents')
    else:
        form = DocumentUploadForm()

    context = {
        'documents': documents,
        'expired_documents': expired_documents,
        'renewal_documents': renewal_documents,
        'form': form,
    }

    return render(request, 'carriers/documents/list.html', context)


@login_required
@user_passes_test(is_carrier)
def generate_customs_form(request, document_id):
    """Générer un formulaire douanier"""
    document = get_object_or_404(CarrierDocument, pk=document_id)
    carrier = request.user.carrier_profile

    if document.carrier != carrier:
        return HttpResponseForbidden(_("Vous n'avez pas accès à ce document."))

    if not document.is_customs_document:
        messages.error(request, _("Ce document n'est pas un document douanier."))
        return redirect('carriers:documents')

    # Générer le formulaire
    customs_form = document.generate_customs_form()

    if not customs_form:
        messages.error(request, _("Impossible de générer le formulaire."))
        return redirect('carriers:documents')

    context = {
        'document': document,
        'customs_form': customs_form,
    }

    return render(request, 'carriers/documents/customs_form.html', context)


# API Views pour AJAX
@login_required
@user_passes_test(is_carrier)
def api_carrier_stats(request):
    """API pour les statistiques du transporteur"""
    carrier = request.user.carrier_profile

    # Statistiques en temps réel
    stats = {
        'pending_missions': Mission.objects.filter(
            carrier=carrier,
            status=Mission.MissionStatus.PENDING
        ).count(),

        'active_missions': Mission.objects.filter(
            carrier=carrier,
            status__in=[
                Mission.MissionStatus.ACCEPTED,
                Mission.MissionStatus.COLLECTING,
                Mission.MissionStatus.IN_TRANSIT,
                Mission.MissionStatus.DELIVERING
            ]
        ).count(),

        'unread_notifications': CarrierNotification.objects.filter(
            carrier=carrier,
            is_read=False
        ).count(),

        'today_missions': Mission.objects.filter(
            carrier=carrier,
            preferred_pickup_date=timezone.now().date()
        ).count(),
    }

    return JsonResponse(stats)


@login_required
@user_passes_test(is_carrier)
def api_collection_planning(request, day_id):
    """API pour la planification de collecte"""
    collection_day = get_object_or_404(CollectionDay, pk=day_id)
    carrier = request.user.carrier_profile

    if collection_day.carrier != carrier:
        return JsonResponse({'error': 'Accès interdit'}, status=403)

    planning = collection_day.calculate_planning()
    collection_list = collection_day.generate_collection_list()

    return JsonResponse({
        'planning': planning,
        'collection_list': collection_list,
    })


@login_required
@user_passes_test(is_carrier)
def api_mission_update_location(request, mission_id):
    """API pour mettre à jour la localisation d'une mission"""
    mission = get_object_or_404(Mission, pk=mission_id)
    carrier = request.user.carrier_profile

    if mission.carrier != carrier:
        return JsonResponse({'error': 'Accès interdit'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')

            if lat and lng:
                from django.contrib.gis.geos import Point
                mission.current_location = Point(float(lng), float(lat))
                mission.last_location_update = timezone.now()
                mission.save()

                return JsonResponse({'success': True})
        except (ValueError, TypeError) as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)



class CarrierListView(ListView):
    """Vue pour afficher la liste des transporteurs"""
    model = Carrier
    template_name = 'carriers/list.html'
    context_object_name = 'carriers'
    paginate_by = 12

    def get_queryset(self):
        queryset = Carrier.objects.filter(
            status='APPROVED',  # Seulement les transporteurs approuvés
            user__is_active=True  # Seulement les utilisateurs actifs
        ).select_related('user')

        # Filtres
        country = self.request.GET.get('country')
        if country:
            queryset = queryset.filter(coverage_countries__icontains=country)

        vehicle_type = self.request.GET.get('vehicle_type')
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)

        min_rating = self.request.GET.get('min_rating')
        if min_rating:
            queryset = queryset.filter(transport_average_rating__gte=float(min_rating))

        min_weight = self.request.GET.get('min_weight')
        if min_weight:
            queryset = queryset.filter(max_weight__gte=float(min_weight))

        min_volume = self.request.GET.get('min_volume')
        if min_volume:
            queryset = queryset.filter(max_volume__gte=float(min_volume))

        verified_only = self.request.GET.get('verified_only')
        if verified_only:
            queryset = queryset.filter(verification_level__gte=3)

        available_now = self.request.GET.get('available_now')
        if available_now:
            queryset = queryset.filter(transport_is_available=True)

        provides_insurance = self.request.GET.get('provides_insurance')
        if provides_insurance:
            queryset = queryset.filter(provides_insurance=True)

        # Trier par note (par défaut)
        queryset = queryset.order_by('-transport_average_rating', '-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        context['total_carriers'] = self.get_queryset().count()

        # Filtres disponibles
        # Vérifier comment les choix sont définis dans votre modèle
        from django_countries import countries
        context['countries'] = [country.name for country in countries]

        # Obtenir les choix de vehicle_type depuis le modèle
        # Vérifier comment votre modèle définit les choix
        try:
            # Essayer différentes façons d'obtenir les choix
            if hasattr(Carrier, '_meta'):
                vehicle_field = Carrier._meta.get_field('vehicle_type')
                context['vehicle_types'] = vehicle_field.choices
            elif hasattr(Carrier, 'VEHICLE_CHOICES'):
                context['vehicle_types'] = Carrier.VEHICLE_CHOICES
            elif hasattr(Carrier, 'VEHICLE_TYPES'):
                context['vehicle_types'] = Carrier.VEHICLE_TYPES
            else:
                # Valeurs par défaut
                context['vehicle_types'] = [
                    ('VAN', 'Camionnette'),
                    ('TRUCK', 'Camion'),
                    ('CAR', 'Voiture'),
                    ('MOTORBIKE', 'Moto'),
                    ('BICYCLE', 'Vélo'),
                ]
        except:
            context['vehicle_types'] = [
                ('VAN', 'Camionnette'),
                ('TRUCK', 'Camion'),
                ('CAR', 'Voiture'),
                ('MOTORBIKE', 'Moto'),
                ('BICYCLE', 'Vélo'),
            ]

        # Types de marchandises
        try:
            if hasattr(Carrier, '_meta'):
                merch_field = Carrier._meta.get_field('accepted_merchandise_types')
                context['merchandise_types'] = merch_field.choices
            elif hasattr(Carrier, 'MERCHANDISE_CHOICES'):
                context['merchandise_types'] = Carrier.MERCHANDISE_CHOICES
            else:
                context['merchandise_types'] = [
                    ('GENERAL', 'Général'),
                    ('FRAGILE', 'Fragile'),
                    ('PERISHABLE', 'Périssable'),
                    ('DANGEROUS', 'Dangereux'),
                    ('ELECTRONICS', 'Électronique'),
                    ('FURNITURE', 'Meuble'),
                ]
        except:
            context['merchandise_types'] = [
                ('GENERAL', 'Général'),
                ('FRAGILE', 'Fragile'),
                ('PERISHABLE', 'Périssable'),
                ('DANGEROUS', 'Dangereux'),
                ('ELECTRONICS', 'Électronique'),
                ('FURNITURE', 'Meuble'),
            ]

        return context