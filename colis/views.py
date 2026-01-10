# ~/ebi3/colis/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, DecimalField, Min, Max
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView,
    UpdateView, DeleteView, TemplateView, FormView
)
from django.utils.translation import gettext as _
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import transaction
from django.db.models.functions import Coalesce
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
import json
from datetime import datetime, timedelta
from importlib import import_module

# Import des modèles
from .models import (
    Package, PackageCategory, PackageImage,
    TransportOffer, PackageView, PackageFavorite, PackageReport
)
from .forms import (
    PackageCreateForm, PackageUpdateForm, PackageImageFormSet,
    TransportOfferForm, PackageSearchForm, PackageReportForm,
    QuickQuoteForm, PackageFilterForm
)

# Import conditionnel des autres apps
try:
    from users.models import User as UsersUser
except ImportError:
    UsersUser = None

try:
    from carriers.models import Carrier, CarrierReview
except ImportError:
    Carrier = None
    CarrierReview = None

try:
    from messaging.models import Conversation, Message
except ImportError:
    Conversation = None
    Message = None

User = get_user_model()


# ============================================================================
# VUES API POUR CATÉGORIES
# ============================================================================

@require_GET
@csrf_exempt
def get_categories_api(request):
    """API pour charger les catégories hiérarchiques"""
    parent_id = request.GET.get('parent_id')
    level = request.GET.get('level', 'sub')  # 'sub' ou 'final'

    try:
        if not parent_id:
            # Retourner les catégories racines
            categories = PackageCategory.objects.filter(
                parent__isnull=True,
                is_active=True
            ).order_by('name')
        else:
            parent_category = PackageCategory.objects.get(id=parent_id, is_active=True)

            if level == 'sub':
                # Charger les sous-catégories directes
                categories = PackageCategory.objects.filter(
                    parent=parent_category,
                    is_active=True
                ).order_by('name')
            else:  # level == 'final'
                # Charger les catégories finales
                categories = PackageCategory.objects.filter(
                    parent=parent_category,
                    is_active=True
                ).order_by('name')

        categories_data = []
        for category in categories:
            has_children = category.get_children().filter(is_active=True).exists()
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'has_children': has_children,
                'slug': category.slug,
            })

        return JsonResponse({'categories': categories_data})

    except PackageCategory.DoesNotExist:
        return JsonResponse({'categories': []})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# VUES PUBLIQUES
# ============================================================================

class CategoryListView(ListView):
    """Liste des catégories de colis"""
    model = PackageCategory
    template_name = 'colis/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return PackageCategory.objects.filter(
            is_active=True,
            show_in_menu=True
        ).annotate(
            available_packages_count=Count('packages', filter=Q(packages__status=Package.Status.AVAILABLE))
        ).filter(
            available_packages_count__gt=0
        )


class CategoryDetailView(DetailView):
    """Détail d'une catégorie avec ses colis"""
    model = PackageCategory
    template_name = 'colis/category_detail.html'
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.object

        # Récupérer toutes les sous-catégories
        subcategories = category.get_descendants(include_self=False).filter(
            is_active=True
        )

        # Récupérer les colis actifs de cette catégorie et ses sous-catégories
        packages = Package.objects.filter(
            category__in=subcategories.union(PackageCategory.objects.filter(pk=category.pk)),
            status=Package.Status.AVAILABLE
        ).select_related('sender').prefetch_related('images')

        # Appliquer les filtres
        form = PackageSearchForm(self.request.GET)
        if form.is_valid():
            packages = self.apply_search_filters(packages, form.cleaned_data)

        # Pagination
        paginator = Paginator(packages, 20)
        page = self.request.GET.get('page')
        packages_page = paginator.get_page(page)

        context.update({
            'subcategories': subcategories,
            'packages': packages_page,
            'search_form': form,
            'total_packages': packages.count(),
        })
        return context

    def apply_search_filters(self, queryset, cleaned_data):
        """Applique les filtres de recherche"""
        if cleaned_data.get('q'):
            search_term = cleaned_data['q']
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        if cleaned_data.get('package_type'):
            queryset = queryset.filter(package_type=cleaned_data['package_type'])

        if cleaned_data.get('pickup_country'):
            queryset = queryset.filter(pickup_country=cleaned_data['pickup_country'])

        if cleaned_data.get('delivery_country'):
            queryset = queryset.filter(delivery_country=cleaned_data['delivery_country'])

        if cleaned_data.get('pickup_city'):
            queryset = queryset.filter(pickup_city__icontains=cleaned_data['pickup_city'])

        if cleaned_data.get('delivery_city'):
            queryset = queryset.filter(delivery_city__icontains=cleaned_data['delivery_city'])

        if cleaned_data.get('pickup_date_from'):
            queryset = queryset.filter(pickup_date__gte=cleaned_data['pickup_date_from'])

        if cleaned_data.get('pickup_date_to'):
            queryset = queryset.filter(pickup_date__lte=cleaned_data['pickup_date_to'])

        if cleaned_data.get('max_weight'):
            queryset = queryset.filter(weight__lte=cleaned_data['max_weight'])

        if cleaned_data.get('max_volume'):
            queryset = queryset.filter(volume__lte=cleaned_data['max_volume'])

        if cleaned_data.get('min_price'):
            queryset = queryset.filter(asking_price__gte=cleaned_data['min_price'])

        if cleaned_data.get('max_price'):
            queryset = queryset.filter(asking_price__lte=cleaned_data['max_price'])

        if cleaned_data.get('flexible_dates'):
            queryset = queryset.filter(flexible_dates=True)

        # Tri
        sort_by = cleaned_data.get('sort_by', '-created_at')
        if sort_by in ['pickup_date', '-pickup_date', 'asking_price', '-asking_price', '-created_at', '-view_count']:
            queryset = queryset.order_by(sort_by)

        return queryset


class PackageListView(ListView):
    """Liste de tous les colis disponibles"""
    model = Package
    template_name = 'colis/package/package_list.html'
    context_object_name = 'packages'
    paginate_by = 20

    def get_queryset(self):
        queryset = Package.objects.filter(
            status=Package.Status.AVAILABLE
        ).select_related('sender', 'category').prefetch_related('images')

        # Appliquer les filtres
        form = PackageSearchForm(self.request.GET)
        if form.is_valid():
            queryset = self.apply_search_filters(queryset, form.cleaned_data)

        return queryset

    def apply_search_filters(self, queryset, cleaned_data):
        """Applique les filtres de recherche"""
        if cleaned_data.get('q'):
            search_term = cleaned_data['q']
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        if cleaned_data.get('category'):
            category = cleaned_data['category']
            # Inclure les sous-catégories
            subcategories = category.get_descendants(include_self=True)
            queryset = queryset.filter(category__in=subcategories)

        if cleaned_data.get('package_type'):
            queryset = queryset.filter(package_type=cleaned_data['package_type'])

        if cleaned_data.get('pickup_country'):
            queryset = queryset.filter(pickup_country=cleaned_data['pickup_country'])

        if cleaned_data.get('delivery_country'):
            queryset = queryset.filter(delivery_country=cleaned_data['delivery_country'])

        if cleaned_data.get('pickup_city'):
            queryset = queryset.filter(pickup_city__icontains=cleaned_data['pickup_city'])

        if cleaned_data.get('delivery_city'):
            queryset = queryset.filter(delivery_city__icontains=cleaned_data['delivery_city'])

        if cleaned_data.get('pickup_date_from'):
            queryset = queryset.filter(pickup_date__gte=cleaned_data['pickup_date_from'])

        if cleaned_data.get('pickup_date_to'):
            queryset = queryset.filter(pickup_date__lte=cleaned_data['pickup_date_to'])

        if cleaned_data.get('max_weight'):
            queryset = queryset.filter(weight__lte=cleaned_data['max_weight'])

        if cleaned_data.get('max_volume'):
            queryset = queryset.filter(volume__lte=cleaned_data['max_volume'])

        if cleaned_data.get('min_price'):
            queryset = queryset.filter(asking_price__gte=cleaned_data['min_price'])

        if cleaned_data.get('max_price'):
            queryset = queryset.filter(asking_price__lte=cleaned_data['max_price'])

        if cleaned_data.get('flexible_dates'):
            queryset = queryset.filter(flexible_dates=True)

        # Tri
        sort_by = cleaned_data.get('sort_by', '-created_at')
        if sort_by in ['pickup_date', '-pickup_date', 'asking_price', '-asking_price', '-created_at', '-view_count']:
            queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PackageSearchForm(self.request.GET)
        context['total_packages'] = self.get_queryset().count()

        # Catégories populaires
        context['categories'] = PackageCategory.objects.filter(
            is_active=True
        ).annotate(
            active_packages=Count('packages', filter=Q(packages__status=Package.Status.AVAILABLE))
        ).filter(
            active_packages__gt=0
        ).order_by('-active_packages', 'name')[:10]

        # Stats pour les filtres
        price_stats = Package.objects.filter(status=Package.Status.AVAILABLE).aggregate(
            min_price=Min('asking_price'),
            max_price=Max('asking_price')
        )

        context['min_price_range'] = price_stats['min_price'] or 0
        context['max_price_range'] = price_stats['max_price'] or 10000

        return context


# Ajoutez cette fonction dans views.py
@login_required
@require_POST
def send_contact_message(request):
    """Envoie un message de contact à un utilisateur"""
    user_id = request.POST.get('user_id')
    message = request.POST.get('message')

    if not user_id or not message:
        return JsonResponse({
            'success': False,
            'error': _('Données manquantes')
        })

    try:
        recipient = User.objects.get(id=user_id)

        # Ici, vous pouvez implémenter l'envoi d'email ou de notification
        # Pour l'instant, on retourne juste un succès

        # Exemple d'envoi d'email (à implémenter)
        # send_mail(
        #     subject=_('Nouveau message de contact sur Ebi3'),
        #     message=f"{request.user.username} vous a envoyé un message:\n\n{message}",
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     recipient_list=[recipient.email],
        # )

        return JsonResponse({
            'success': True,
            'message': _('Message envoyé avec succès')
        })
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Utilisateur non trouvé')
        })


class PackageDetailView(DetailView):
    """Détail d'un colis"""
    model = Package
    template_name = 'colis/package/package_detail.html'
    context_object_name = 'package'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object

        # Enregistrer la vue
        self.record_package_view(package)

        # Offres de transport (si l'utilisateur est le propriétaire ou un transporteur)
        if self.request.user.is_authenticated:
            if self.request.user == package.sender:
                # Propriétaire : voir toutes les offres
                offers = package.transport_offers.all().select_related('carrier', 'carrier__user')
                context['transport_offers'] = offers
                context['has_pending_offers'] = offers.filter(status=TransportOffer.Status.PENDING).exists()
            elif hasattr(self.request.user, 'carrier_profile'):
                # Transporteur : voir si il a déjà fait une offre
                user_offer = package.transport_offers.filter(
                    carrier=self.request.user.carrier_profile
                ).first()
                context['user_offer'] = user_offer

        # Colis similaires
        similar_packages = Package.objects.filter(
            category=package.category,
            status=Package.Status.AVAILABLE
        ).exclude(pk=package.pk).select_related('sender').prefetch_related('images')[:4]

        # Vérifier si le colis est dans les favoris de l'utilisateur
        is_favorite = False
        if self.request.user.is_authenticated:
            is_favorite = PackageFavorite.objects.filter(
                user=self.request.user,
                package=package
            ).exists()

        # Vérifier les permissions
        context.update({
            'similar_packages': similar_packages,
            'is_favorite': is_favorite,
            'can_edit': self.request.user == package.sender or self.request.user.is_staff,
            'can_report': self.request.user.is_authenticated and self.request.user != package.sender,
            'can_make_offer': self.can_make_offer(package),
            'transport_offer_form': TransportOfferForm() if self.can_make_offer(package) else None,
        })

        return context

    def record_package_view(self, package):
        """Enregistre une vue pour le colis"""
        if self.request.user.is_authenticated:
            PackageView.objects.create(
                package=package,
                user=self.request.user,
                session_key=self.request.session.session_key,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                referer=self.request.META.get('HTTP_REFERER', '')
            )
        else:
            PackageView.objects.create(
                package=package,
                session_key=self.request.session.session_key,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                referer=self.request.META.get('HTTP_REFERER', '')
            )

        # Mettre à jour le compteur de vues
        package.view_count = PackageView.objects.filter(package=package).count()
        package.save(update_fields=['view_count'])

    def can_make_offer(self, package):
        """Vérifie si l'utilisateur peut faire une offre"""
        if not self.request.user.is_authenticated:
            return False

        # L'expéditeur ne peut pas faire d'offre sur son propre colis
        if self.request.user == package.sender:
            return False

        # Vérifier si l'utilisateur est un transporteur approuvé
        try:
            if Carrier:
                carrier_profile = self.request.user.carrier_profile
                if carrier_profile.status != Carrier.Status.APPROVED:
                    return False
                if not carrier_profile.is_available:
                    return False
        except AttributeError:
            return False

        # Vérifier si le colis est disponible
        if package.status != Package.Status.AVAILABLE:
            return False

        # Vérifier si une offre existe déjà
        if package.transport_offers.filter(carrier=carrier_profile).exists():
            return False

        return True


# ============================================================================
# VUES UTILISATEUR AUTHENTIFIÉ
# ============================================================================

class PackageCreateView(LoginRequiredMixin, CreateView):
    """Création d'un colis"""
    model = Package
    form_class = PackageCreateForm
    template_name = 'colis/package/package_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['image_formset'] = PackageImageFormSet(
                self.request.POST,
                self.request.FILES,
                prefix='images'
            )
        else:
            context['image_formset'] = PackageImageFormSet(
                prefix='images'
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']

        # Valider d'abord le formulaire principal
        if not form.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            form.instance.sender = self.request.user
            form.instance.status = Package.Status.AVAILABLE
            self.object = form.save()

            if image_formset.is_valid():
                images = image_formset.save(commit=False)
                for image in images:
                    image.package = self.object
                    # Vérifier si une image a été uploadée
                    if image.image:
                        image.save()

                # Gérer les images marquées pour suppression
                for obj in image_formset.deleted_objects:
                    obj.delete()

                # Vérifier le nombre d'images
                free_images_count = self.object.packageimage_set.filter(is_paid=False).count()
                if free_images_count > self.object.free_images_allowed:
                    messages.warning(
                        self.request,
                        _(f"Vous avez téléchargé {free_images_count} images gratuites, "
                          f"mais seulement {self.object.free_images_allowed} sont autorisées gratuitement.")
                    )
            else:
                # Ajouter les erreurs du formset au formulaire
                for form in image_formset.forms:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(self.request, f"Image: {error}")
                return self.form_invalid(form)

        messages.success(self.request, _("Votre colis a été publié avec succès !"))
        return super().form_valid(form)

    def form_invalid(self, form):
        # Log des erreurs pour le débogage
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('colis:package_detail', kwargs={'slug': self.object.slug})


class PackageUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'un colis"""
    model = Package
    form_class = PackageUpdateForm
    template_name = 'colis/package/package_create.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['image_formset'] = PackageImageFormSet(
                self.request.POST,
                self.request.FILES,
                instance=self.object,
                prefix='images'
            )
        else:
            context['image_formset'] = PackageImageFormSet(
                instance=self.object,
                prefix='images'
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']

        with transaction.atomic():
            self.object = form.save()

            if image_formset.is_valid():
                images = image_formset.save(commit=False)
                for image in images:
                    image.package = self.object
                    # Vérifier si une image a été uploadée
                    if image.image:
                        image.save()

                # Supprimer les images marquées pour suppression
                for obj in image_formset.deleted_objects:
                    obj.delete()
            else:
                # Log des erreurs
                for form in image_formset.forms:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(self.request, f"Image: {error}")
                return self.form_invalid(form)

        messages.success(self.request, _("Votre colis a été mis à jour avec succès !"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('colis:package_detail', kwargs={'slug': self.object.slug})


class PackageDeleteView(LoginRequiredMixin, DeleteView):
    """Suppression d'un colis"""
    model = Package
    template_name = 'colis/package_delete.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('colis:package_list')

    def dispatch(self, request, *args, **kwargs):
        package = self.get_object()
        if package.sender != request.user and not request.user.is_staff:
            messages.error(request, _("Vous n'êtes pas autorisé à supprimer ce colis."))
            return redirect('colis:package_detail', slug=package.slug)

        # Empêcher la suppression si le colis est réservé ou en transit
        if package.status in [Package.Status.RESERVED, Package.Status.IN_TRANSIT]:
            messages.error(request, _("Ce colis ne peut pas être supprimé car il est réservé ou en transit."))
            return redirect('colis:package_detail', slug=package.slug)

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Le colis a été supprimé avec succès."))
        return super().delete(request, *args, **kwargs)


class MyPackagesListView(LoginRequiredMixin, ListView):
    """Liste des colis de l'utilisateur"""
    model = Package
    template_name = 'colis/my_packages.html'
    context_object_name = 'packages'
    paginate_by = 10

    def get_queryset(self):
        queryset = Package.objects.filter(
            sender=self.request.user
        ).select_related('category').prefetch_related('images').order_by('-created_at')

        # Appliquer les filtres
        form = PackageFilterForm(self.request.GET)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')

            if status:
                queryset = queryset.filter(status=status)
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = PackageFilterForm(self.request.GET)

        # Statistiques
        stats = Package.objects.filter(sender=self.request.user).aggregate(
            total=Count('id'),
            available=Count('id', filter=Q(status=Package.Status.AVAILABLE)),
            reserved=Count('id', filter=Q(status=Package.Status.RESERVED)),
            in_transit=Count('id', filter=Q(status=Package.Status.IN_TRANSIT)),
            delivered=Count('id', filter=Q(status=Package.Status.DELIVERED)),
            cancelled=Count('id', filter=Q(status=Package.Status.CANCELLED)),
        )

        context.update(stats)
        return context


@login_required
@require_POST
def toggle_package_favorite(request, slug):
    """Ajouter/retirer un colis des favoris"""
    package = get_object_or_404(Package, slug=slug)

    favorite, created = PackageFavorite.objects.get_or_create(
        user=request.user,
        package=package
    )

    if not created:
        favorite.delete()
        action = 'retiré'
    else:
        action = 'ajouté'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'action': 'added' if created else 'removed',
            'favorite_count': package.favorite_count
        })

    messages.success(request, _(f"Colis {action} aux favoris."))
    return redirect('colis:package_detail', slug=slug)


class PackageFavoritesListView(LoginRequiredMixin, ListView):
    """Liste des colis favoris de l'utilisateur"""
    model = PackageFavorite
    template_name = 'colis/favorite_list.html'
    context_object_name = 'favorites'

    def get_queryset(self):
        return PackageFavorite.objects.filter(
            user=self.request.user
        ).select_related('package', 'package__sender', 'package__category').prefetch_related('package__images')


# ============================================================================
# OFFRES DE TRANSPORT
# ============================================================================

class TransportOfferCreateView(LoginRequiredMixin, CreateView):
    """Créer une offre de transport pour un colis"""
    model = TransportOffer
    form_class = TransportOfferForm
    template_name = 'colis/transport_offer_create.html'

    def dispatch(self, request, *args, **kwargs):
        self.package = get_object_or_404(Package, slug=kwargs['slug'])

        # Vérifications
        if not self.can_make_offer(request.user):
            messages.error(request, _("Vous ne pouvez pas faire d'offre pour ce colis."))
            return redirect('colis:package_detail', slug=self.package.slug)

        return super().dispatch(request, *args, **kwargs)

    def can_make_offer(self, user):
        """Vérifie si l'utilisateur peut faire une offre"""
        # L'expéditeur ne peut pas faire d'offre sur son propre colis
        if user == self.package.sender:
            return False

        # Vérifier si l'utilisateur est un transporteur approuvé
        try:
            if not Carrier:
                return False
            carrier_profile = user.carrier_profile
            if carrier_profile.status != Carrier.Status.APPROVED:
                return False
            if not carrier_profile.is_available:
                return False
        except AttributeError:
            return False

        # Vérifier si le colis est disponible
        if self.package.status != Package.Status.AVAILABLE:
            return False

        # Vérifier si une offre existe déjà
        if self.package.transport_offers.filter(carrier=carrier_profile).exists():
            return False

        return True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['package'] = self.package
        kwargs['carrier'] = self.request.user.carrier_profile
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.package

        # Calculer une estimation de prix
        estimated_price = self.calculate_estimated_price()
        context['estimated_price'] = estimated_price

        return context

    def calculate_estimated_price(self):
        """Calcule une estimation de prix basée sur la distance et le volume"""
        # Logique simplifiée
        if self.package.weight and self.package.volume:
            base_price_per_kg = 0.5
            base_price_per_volume = 10

            estimated_price = (
                float(self.package.weight) * base_price_per_kg +
                float(self.package.volume) / 1000 * base_price_per_volume
            )

            # Ajustements
            if self.package.is_fragile:
                estimated_price *= 1.2
            if self.package.requires_insurance:
                estimated_price *= 1.1
            if self.package.requires_packaging:
                estimated_price *= 1.15

            return round(estimated_price, 2)
        return None

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()

            # Créer une conversation entre l'expéditeur et le transporteur
            try:
                if Conversation and Message:
                    conversation = Conversation.objects.get_or_create_conversation(
                        self.package.sender,
                        self.request.user,
                        f"Offre pour colis: {self.package.title}"
                    )

                    # Ajouter un message initial
                    Message.objects.create(
                        conversation=conversation,
                        sender=self.request.user,
                        content=_("Bonjour, je vous propose de transporter votre colis pour {price}€. {message}").format(
                            price=self.object.price,
                            message=self.object.message or ""
                        )
                    )
            except Exception as e:
                # Ne pas bloquer l'offre si la conversation échoue
                pass

        messages.success(
            self.request,
            _("Votre offre a été envoyée avec succès ! L'expéditeur a été notifié.")
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('colis:package_detail', kwargs={'slug': self.package.slug})


class MyTransportOffersListView(LoginRequiredMixin, ListView):
    """Liste des offres de transport de l'utilisateur"""
    model = TransportOffer
    template_name = 'colis/my_transport_offers.html'
    context_object_name = 'offers'
    paginate_by = 10

    def get_queryset(self):
        # Si l'utilisateur est un transporteur, voir ses offres
        if hasattr(self.request.user, 'carrier_profile'):
            return TransportOffer.objects.filter(
                carrier=self.request.user.carrier_profile
            ).select_related('package', 'package__sender').order_by('-created_at')

        # Si l'utilisateur est un expéditeur, voir les offres reçues
        return TransportOffer.objects.filter(
            package__sender=self.request.user
        ).select_related('package', 'carrier', 'carrier__user').order_by('-created_at')


@login_required
@require_POST
def accept_transport_offer(request, pk):
    """Accepter une offre de transport"""
    offer = get_object_or_404(TransportOffer, pk=pk)

    # Vérifier les permissions
    if offer.package.sender != request.user:
        raise PermissionDenied(_("Vous n'êtes pas autorisé à accepter cette offre."))

    # Vérifier que l'offre peut être acceptée
    if offer.status != TransportOffer.Status.PENDING:
        messages.error(request, _("Cette offre ne peut pas être acceptée."))
        return redirect('colis:my_transport_offers')

    with transaction.atomic():
        # Accepter l'offre
        offer.status = TransportOffer.Status.ACCEPTED
        offer.accepted_at = timezone.now()
        offer.save()

        # Mettre à jour le statut du colis
        offer.package.status = Package.Status.RESERVED
        offer.package.reserved_at = timezone.now()
        offer.package.save()

        # Rejeter automatiquement les autres offres en attente
        TransportOffer.objects.filter(
            package=offer.package,
            status=TransportOffer.Status.PENDING
        ).exclude(pk=offer.pk).update(
            status=TransportOffer.Status.REJECTED,
            rejection_reason=_("Une autre offre a été acceptée")
        )

        # Mettre à jour la conversation
        try:
            if Conversation and Message:
                conversation = Conversation.objects.get_or_create_conversation(
                    offer.package.sender,
                    offer.carrier.user,
                    f"Colis accepté: {offer.package.title}"
                )

                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=_("Bonjour, j'ai accepté votre offre de {price}€. Merci ! Nous pouvons maintenant organiser les détails du transport.").format(
                        price=offer.price
                    )
                )
        except Exception as e:
            pass

    messages.success(request, _("L'offre a été acceptée avec succès !"))
    return redirect('colis:my_transport_offers')


@login_required
@require_POST
def reject_transport_offer(request, pk):
    """Rejeter une offre de transport"""
    offer = get_object_or_404(TransportOffer, pk=pk)

    # Vérifier les permissions
    if offer.package.sender != request.user:
        raise PermissionDenied(_("Vous n'êtes pas autorisé à rejeter cette offre."))

    if offer.status != TransportOffer.Status.PENDING:
        messages.error(request, _("Cette offre ne peut pas être rejetée."))
        return redirect('colis:my_transport_offers')

    reason = request.POST.get('reason', '')

    with transaction.atomic():
        offer.status = TransportOffer.Status.REJECTED
        offer.rejection_reason = reason
        offer.save()

        # Mettre à jour la conversation
        try:
            if Conversation and Message:
                conversation = Conversation.objects.get_or_create_conversation(
                    offer.package.sender,
                    offer.carrier.user,
                    f"Colis: {offer.package.title}"
                )

                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=_("Bonjour, je regrette mais je ne peux pas accepter votre offre. {reason}").format(
                        reason=f"Raison: {reason}" if reason else ""
                    )
                )
        except Exception as e:
            pass

    messages.success(request, _("L'offre a été rejetée."))
    return redirect('colis:my_transport_offers')


@login_required
@require_POST
def cancel_transport_offer(request, pk):
    """Annuler une offre de transport (transporteur)"""
    offer = get_object_or_404(TransportOffer, pk=pk)

    # Vérifier les permissions
    if offer.carrier.user != request.user:
        raise PermissionDenied(_("Vous n'êtes pas autorisé à annuler cette offre."))

    if offer.status != TransportOffer.Status.PENDING:
        messages.error(request, _("Cette offre ne peut pas être annulée."))
        return redirect('colis:my_transport_offers')

    with transaction.atomic():
        offer.status = TransportOffer.Status.CANCELLED
        offer.save()

        # Mettre à jour la conversation
        try:
            if Conversation and Message:
                conversation = Conversation.objects.get_or_create_conversation(
                    offer.package.sender,
                    offer.carrier.user,
                    f"Colis: {offer.package.title}"
                )

                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=_("Je regrette mais je dois annuler mon offre pour votre colis.")
                )
        except Exception as e:
            pass

    messages.success(request, _("Votre offre a été annulée."))
    return redirect('colis:my_transport_offers')


# ============================================================================
# VUES POUR TRANSPORTEURS
# ============================================================================

class AvailablePackagesView(LoginRequiredMixin, ListView):
    """Colis disponibles pour les transporteurs"""
    model = Package
    template_name = 'colis/available_packages.html'
    context_object_name = 'packages'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Vérifier que l'utilisateur est un transporteur approuvé
        if not hasattr(request.user, 'carrier_profile'):
            messages.error(request, _("Vous devez être transporteur pour voir les colis disponibles."))
            return redirect('carriers:apply')

        if not Carrier:
            messages.error(request, _("Module transporteur non disponible."))
            return redirect('colis:package_list')

        carrier = request.user.carrier_profile
        if carrier.status != Carrier.Status.APPROVED:
            messages.error(request, _("Votre compte transporteur n'est pas encore approuvé."))
            return redirect('carriers:carrier_detail', username=request.user.username)

        if not carrier.is_available:
            messages.warning(request, _("Vous êtes marqué comme indisponible. Activez votre disponibilité pour voir les colis."))

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Filtrer les colis disponibles
        queryset = Package.objects.filter(
            status=Package.Status.AVAILABLE
        ).select_related('sender', 'category').prefetch_related('images')

        # Filtrer par capacités du transporteur
        carrier = self.request.user.carrier_profile
        queryset = queryset.filter(
            weight__lte=carrier.max_weight
        )

        # Exclure les colis pour lesquels le transporteur a déjà fait une offre
        offered_packages = TransportOffer.objects.filter(
            carrier=carrier,
            package__in=queryset
        ).values_list('package_id', flat=True)

        queryset = queryset.exclude(id__in=offered_packages)

        # Appliquer les filtres de recherche
        form = PackageSearchForm(self.request.GET)
        if form.is_valid():
            queryset = self.apply_search_filters(queryset, form.cleaned_data)

        return queryset

    def apply_search_filters(self, queryset, cleaned_data):
        """Applique les filtres de recherche"""
        if cleaned_data.get('q'):
            search_term = cleaned_data['q']
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        if cleaned_data.get('category'):
            category = cleaned_data['category']
            subcategories = category.get_descendants(include_self=True)
            queryset = queryset.filter(category__in=subcategories)

        if cleaned_data.get('pickup_country'):
            queryset = queryset.filter(pickup_country=cleaned_data['pickup_country'])

        if cleaned_data.get('delivery_country'):
            queryset = queryset.filter(delivery_country=cleaned_data['delivery_country'])

        if cleaned_data.get('pickup_city'):
            queryset = queryset.filter(pickup_city__icontains=cleaned_data['pickup_city'])

        if cleaned_data.get('delivery_city'):
            queryset = queryset.filter(delivery_city__icontains=cleaned_data['delivery_city'])

        if cleaned_data.get('pickup_date_from'):
            queryset = queryset.filter(pickup_date__gte=cleaned_data['pickup_date_from'])

        if cleaned_data.get('pickup_date_to'):
            queryset = queryset.filter(pickup_date__lte=cleaned_data['pickup_date_to'])

        if cleaned_data.get('max_weight'):
            queryset = queryset.filter(weight__lte=cleaned_data['max_weight'])

        if cleaned_data.get('max_volume'):
            queryset = queryset.filter(volume__lte=cleaned_data['max_volume'])

        if cleaned_data.get('min_price'):
            queryset = queryset.filter(asking_price__gte=cleaned_data['min_price'])

        if cleaned_data.get('max_price'):
            queryset = queryset.filter(asking_price__lte=cleaned_data['max_price'])

        if cleaned_data.get('flexible_dates'):
            queryset = queryset.filter(flexible_dates=True)

        # Tri
        sort_by = cleaned_data.get('sort_by', '-created_at')
        if sort_by in ['pickup_date', '-pickup_date', 'asking_price', '-asking_price', '-created_at']:
            queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PackageSearchForm(self.request.GET)
        context['total_packages'] = self.get_queryset().count()

        # Statistiques du transporteur
        carrier = self.request.user.carrier_profile
        context['carrier_stats'] = {
            'max_weight': carrier.max_weight,
            'max_volume': carrier.max_volume,
            'completed_missions': carrier.completed_missions,
            'average_rating': carrier.average_rating,
        }

        return context


class CarrierDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord du transporteur"""
    template_name = 'colis/carrier_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Vérifier que l'utilisateur est un transporteur
        if not hasattr(request.user, 'carrier_profile'):
            messages.error(request, _("Vous devez être transporteur pour accéder au tableau de bord."))
            return redirect('carriers:apply')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrier = self.request.user.carrier_profile

        # Statistiques
        offers = TransportOffer.objects.filter(carrier=carrier)

        stats = {
            'total_offers': offers.count(),
            'pending_offers': offers.filter(status=TransportOffer.Status.PENDING).count(),
            'accepted_offers': offers.filter(status=TransportOffer.Status.ACCEPTED).count(),
            'rejected_offers': offers.filter(status=TransportOffer.Status.REJECTED).count(),
            'total_earnings': offers.filter(status=TransportOffer.Status.ACCEPTED).aggregate(
                total=Sum('price')
            )['total'] or 0,
        }

        # Offres récentes
        recent_offers = offers.select_related('package', 'package__sender').order_by('-created_at')[:5]

        # Colis en transit
        packages_in_transit = Package.objects.filter(
            transport_offers__carrier=carrier,
            transport_offers__status=TransportOffer.Status.ACCEPTED,
            status=Package.Status.IN_TRANSIT
        ).select_related('sender')[:5]

        context.update({
            'carrier': carrier,
            'stats': stats,
            'recent_offers': recent_offers,
            'packages_in_transit': packages_in_transit,
        })

        return context


# ============================================================================
# SIGNALEMENT ET MODÉRATION
# ============================================================================

class PackageReportView(LoginRequiredMixin, CreateView):
    """Signaler un colis"""
    model = PackageReport
    form_class = PackageReportForm
    template_name = 'colis/package_report.html'

    def dispatch(self, request, *args, **kwargs):
        self.package = get_object_or_404(Package, slug=kwargs['slug'])

        # Empêcher l'utilisateur de signaler son propre colis
        if request.user == self.package.sender:
            messages.error(request, _("Vous ne pouvez pas signaler votre propre colis."))
            return redirect('colis:package_detail', slug=self.package.slug)

        # Vérifier si l'utilisateur a déjà signalé ce colis
        if PackageReport.objects.filter(package=self.package, reporter=request.user).exists():
            messages.warning(request, _("Vous avez déjà signalé ce colis."))
            return redirect('colis:package_detail', slug=self.package.slug)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.package
        return context

    def form_valid(self, form):
        form.instance.package = self.package
        form.instance.reporter = self.request.user

        messages.success(
            self.request,
            _("Votre signalement a été soumis. Nous l'examinerons sous 24 heures.")
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('colis:package_detail', kwargs={'slug': self.package.slug})


# ============================================================================
# RECHERCHE ET FONCTIONNALITÉS
# ============================================================================

def search_packages(request):
    """Recherche avancée de colis"""
    form = PackageSearchForm(request.GET)
    packages = Package.objects.filter(status=Package.Status.AVAILABLE)

    if form.is_valid():
        packages = apply_search_filters(packages, form.cleaned_data)

    # Pagination
    paginator = Paginator(packages, 20)
    page = request.GET.get('page')
    packages_page = paginator.get_page(page)

    context = {
        'packages': packages_page,
        'search_form': form,
        'total_packages': packages.count(),
    }

    return render(request, 'colis/search_results.html', context)


def apply_search_filters(queryset, cleaned_data):
    """Applique les filtres de recherche"""
    if cleaned_data.get('q'):
        search_term = cleaned_data['q']
        queryset = queryset.filter(
            Q(title__icontains=search_term) |
            Q(description__icontains=search_term)
        )

    if cleaned_data.get('category'):
        category = cleaned_data['category']
        subcategories = category.get_descendants(include_self=True)
        queryset = queryset.filter(category__in=subcategories)

    if cleaned_data.get('package_type'):
        queryset = queryset.filter(package_type=cleaned_data['package_type'])

    if cleaned_data.get('pickup_country'):
        queryset = queryset.filter(pickup_country=cleaned_data['pickup_country'])

    if cleaned_data.get('delivery_country'):
        queryset = queryset.filter(delivery_country=cleaned_data['delivery_country'])

    if cleaned_data.get('pickup_city'):
        queryset = queryset.filter(pickup_city__icontains=cleaned_data['pickup_city'])

    if cleaned_data.get('delivery_city'):
        queryset = queryset.filter(delivery_city__icontains=cleaned_data['delivery_city'])

    if cleaned_data.get('pickup_date_from'):
        queryset = queryset.filter(pickup_date__gte=cleaned_data['pickup_date_from'])

    if cleaned_data.get('pickup_date_to'):
        queryset = queryset.filter(pickup_date__lte=cleaned_data['pickup_date_to'])

    if cleaned_data.get('max_weight'):
        queryset = queryset.filter(weight__lte=cleaned_data['max_weight'])

    if cleaned_data.get('max_volume'):
        queryset = queryset.filter(volume__lte=cleaned_data['max_volume'])

    if cleaned_data.get('min_price'):
        queryset = queryset.filter(asking_price__gte=cleaned_data['min_price'])

    if cleaned_data.get('max_price'):
        queryset = queryset.filter(asking_price__lte=cleaned_data['max_price'])

    if cleaned_data.get('flexible_dates'):
        queryset = queryset.filter(flexible_dates=True)

    # Tri
    sort_by = cleaned_data.get('sort_by', '-created_at')
    if sort_by in ['pickup_date', '-pickup_date', 'asking_price', '-asking_price', '-created_at', '-view_count']:
        queryset = queryset.order_by(sort_by)

    return queryset


@login_required
@require_GET
def quick_quote(request):
    """Devis rapide pour transporteurs"""
    form = QuickQuoteForm(request.GET)

    if form.is_valid():
        # Calcul simplifié du prix
        weight = form.cleaned_data['weight']
        length = form.cleaned_data.get('length', 0)
        width = form.cleaned_data.get('width', 0)
        height = form.cleaned_data.get('height', 0)

        # Calcul de base
        base_price = float(weight) * 0.5  # 0.5€ par kg

        if length and width and height:
            volume = (float(length) * float(width) * float(height)) / 1000000  # m³
            base_price += volume * 10  # 10€ par m³

        # Majorations
        if form.cleaned_data.get('is_fragile'):
            base_price *= 1.2

        if form.cleaned_data.get('requires_insurance'):
            base_price *= 1.1

        estimated_price = round(base_price, 2)

        return JsonResponse({
            'success': True,
            'estimated_price': estimated_price,
            'currency': 'EUR',
            'message': _("Prix estimé basé sur les informations fournies.")
        })

    return JsonResponse({
        'success': False,
        'errors': form.errors
    })


# ============================================================================
# FONCTIONS AJAX ET API
# ============================================================================

@login_required
@require_POST
def update_package_status(request, slug, status):
    """Changer le statut d'un colis (AJAX)"""
    package = get_object_or_404(Package, slug=slug, sender=request.user)

    if status not in dict(Package.Status.choices):
        return JsonResponse({'success': False, 'error': _("Statut invalide.")})

    # Vérifier les transitions autorisées
    allowed_transitions = {
        Package.Status.AVAILABLE: [Package.Status.CANCELLED],
        Package.Status.RESERVED: [Package.Status.IN_TRANSIT, Package.Status.CANCELLED],
        Package.Status.IN_TRANSIT: [Package.Status.DELIVERED, Package.Status.CANCELLED],
    }

    if package.status in allowed_transitions and status not in allowed_transitions[package.status]:
        return JsonResponse({
            'success': False,
            'error': _("Transition de statut non autorisée.")
        })

    previous_status = package.status
    package.status = status

    # Mettre à jour les dates de statut
    if status == Package.Status.IN_TRANSIT:
        package.in_transit_at = timezone.now()
    elif status == Package.Status.DELIVERED:
        package.delivered_at = timezone.now()

    package.save()

    return JsonResponse({
        'success': True,
        'new_status': status,
        'new_status_display': package.get_status_display(),
        'message': _("Statut mis à jour avec succès.")
    })


@login_required
@require_GET
def package_stats(request, slug):
    """Récupérer les statistiques d'un colis (AJAX)"""
    package = get_object_or_404(Package, slug=slug)

    # Vérifier les permissions
    if package.sender != request.user and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': _("Accès non autorisé.")})

    stats = {
        'view_count': package.view_count,
        'offer_count': package.offer_count,
        'favorite_count': package.favorite_count,
        'created_at': package.created_at.isoformat(),
        'published_at': package.published_at.isoformat() if package.published_at else None,
        'status': package.status,
        'status_display': package.get_status_display(),
    }

    return JsonResponse({'success': True, 'stats': stats})


# ============================================================================
# VUES DE GESTION ET ADMIN
# ============================================================================

@login_required
def package_management(request, slug):
    """Gestion complète d'un colis (pour l'expéditeur)"""
    package = get_object_or_404(Package, slug=slug)

    # Vérifier les permissions
    if package.sender != request.user and not request.user.is_staff:
        messages.error(request, _("Accès non autorisé."))
        return redirect('colis:package_detail', slug=slug)

    # Récupérer toutes les offres
    offers = package.transport_offers.all().select_related('carrier', 'carrier__user')

    context = {
        'package': package,
        'offers': offers,
        'can_edit': package.status in [Package.Status.AVAILABLE, Package.Status.DRAFT],
        'can_delete': package.status in [Package.Status.AVAILABLE, Package.Status.DRAFT, Package.Status.CANCELLED],
    }

    return render(request, 'colis/package_management.html', context)


class PackageStatisticsView(LoginRequiredMixin, TemplateView):
    """Statistiques des colis de l'utilisateur"""
    template_name = 'colis/package_statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Statistiques générales
        packages = Package.objects.filter(sender=user)

        stats = packages.aggregate(
            total=Count('id'),
            total_views=Sum('view_count'),
            total_offers=Sum('offer_count'),
            total_favorites=Sum('favorite_count'),
            avg_price=Avg('asking_price'),
            total_value=Sum('asking_price'),
        )

        # Statistiques par statut
        status_stats = []
        for status_code, status_name in Package.Status.choices:
            count = packages.filter(status=status_code).count()
            if count > 0:
                status_stats.append({
                    'status': status_code,
                    'status_display': status_name,
                    'count': count,
                    'percentage': round((count / stats['total']) * 100, 1) if stats['total'] > 0 else 0
                })

        context.update({
            'stats': stats,
            'status_stats': status_stats,
        })

        return context


class NewsSitemapView(TemplateView):
    """
    Vue pour générer un sitemap spécifique Google News
    """
    template_name = 'colis/sitemap_news.xml'
    content_type = 'application/xml'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Articles publiés dans les dernières 48h
        two_days_ago = timezone.now() - timedelta(days=2)

        news_packages = Package.objects.filter(
            created_at__gte=two_days_ago,
            status='AVAILABLE'
        ).order_by('-created_at')[:1000]

        context['news_packages'] = news_packages
        context['publication_date'] = datetime.now().strftime('%Y-%m-%d')
        context['site_name'] = 'Ebi3 Colis'

        return context


def robots_txt(request):
    """
    Vue pour servir le fichier robots.txt
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Sitemaps",
        f"Sitemap: https://{request.get_host()}/colis/sitemap.xml",
        "",
        "# Disallow certaines pages",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /api/",
        "Disallow: /search/?q=*",
        "Disallow: /*/edit/",
        "Disallow: /*/delete/",
        "",
        "# Crawl-delay pour éviter de surcharger le serveur",
        "Crawl-delay: 2",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")


# ============================================================================
# VUES D'ACTIONS EN MASSE
# ============================================================================

@login_required
def bulk_publish_packages(request):
    """Publie tous les colis en brouillon de l'utilisateur"""
    if request.method == 'POST':
        # Récupérer tous les brouillons de l'utilisateur
        draft_packages = Package.objects.filter(
            sender=request.user,
            status=Package.Status.DRAFT
        )

        count = draft_packages.count()

        if count > 0:
            # Mettre à jour le statut
            draft_packages.update(
                status=Package.Status.AVAILABLE,
                published_at=timezone.now()
            )

            messages.success(
                request,
                _(f'{count} colis ont été publiés avec succès.')
            )
        else:
            messages.info(
                request,
                _("Vous n'avez aucun colis en brouillon à publier.")
            )

    return redirect('colis:my_packages')


@login_required
def bulk_expire_packages(request):
    """Marque tous les colis disponibles de l'utilisateur comme expirés"""
    if request.method == 'POST':
        # Récupérer tous les colis disponibles de l'utilisateur
        available_packages = Package.objects.filter(
            sender=request.user,
            status=Package.Status.AVAILABLE
        )

        count = available_packages.count()

        if count > 0:
            # Mettre à jour le statut
            available_packages.update(
                status=Package.Status.EXPIRED,
                expired_at=timezone.now()
            )

            messages.warning(
                request,
                _(f'{count} colis ont été marqués comme expirés.')
            )
        else:
            messages.info(
                request,
                _("Vous n'avez aucun colis disponible à expirer.")
            )

    return redirect('colis:my_packages')


@login_required
def bulk_delete_packages(request):
    """Supprime tous les brouillons de l'utilisateur"""
    if request.method == 'POST':
        # Récupérer tous les brouillons de l'utilisateur
        draft_packages = Package.objects.filter(
            sender=request.user,
            status=Package.Status.DRAFT
        )

        count = draft_packages.count()

        if count > 0:
            # Supprimer les brouillons
            draft_packages.delete()

            messages.success(
                request,
                _(f'{count} brouillons ont été supprimés.')
            )
        else:
            messages.info(
                request,
                _("Vous n'avez aucun brouillon à supprimer.")
            )

    return redirect('colis:my_packages')


@login_required
def bulk_archive_packages(request):
    """Archive tous les colis livrés/annulés/expirés"""
    if request.method == 'POST':
        # Récupérer les colis terminés
        completed_packages = Package.objects.filter(
            sender=request.user,
            status__in=[Package.Status.DELIVERED, Package.Status.CANCELLED, Package.Status.EXPIRED]
        )

        count = completed_packages.count()

        if count > 0:
            messages.info(
                request,
                _(f'{count} colis ont été marqués comme terminés.')
            )
        else:
            messages.info(
                request,
                _("Vous n'avez aucun colis terminé à archiver.")
            )

    return redirect('colis:my_packages')


# ============================================================================
# VUES D'ERREUR
# ============================================================================

def custom_404(request, exception):
    """Vue personnalisée pour l'erreur 404"""
    return render(request, 'colis/errors/404.html', status=404)


def custom_500(request):
    """Vue personnalisée pour l'erreur 500"""
    return render(request, 'colis/errors/500.html', status=500)