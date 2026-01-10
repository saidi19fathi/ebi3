# ~/ebi3/ads/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView,
    UpdateView, DeleteView, TemplateView
)
from django.db.models import Sum, Count, Q, Avg, F
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.db import models

from .models import Category, Ad, AdImage, Favorite, AdView, AdReport
from .forms import (
    AdCreateForm, AdUpdateForm,
    AdImageFormSet, AdSearchForm,
    AdReportForm
)
from users.models import User
from django.views.decorators.http import require_GET


class CategoryListView(ListView):
    """Liste des catégories"""
    model = Category
    template_name = 'ads/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(
            is_active=True,
            show_in_menu=True
        ).annotate(
            active_ads_count=Count('ads', filter=Q(ads__status=Ad.Status.ACTIVE))
        ).filter(
            active_ads_count__gt=0
        )


class CategoryDetailView(DetailView):
    """Détail d'une catégorie avec ses annonces"""
    model = Category
    template_name = 'ads/category_detail.html'
    context_object_name = 'category'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.object

        # Récupérer toutes les sous-catégories
        subcategories = category.get_descendants(include_self=False).filter(
            is_active=True
        )

        # Récupérer les annonces actives de cette catégorie et ses sous-catégories
        ads = Ad.objects.filter(
            category__in=subcategories.union(Category.objects.filter(pk=category.pk)),
            status=Ad.Status.ACTIVE
        ).select_related('seller', 'category').prefetch_related('images')

        # Appliquer les filtres
        form = AdSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('min_price'):
                ads = ads.filter(price__gte=form.cleaned_data['min_price'])
            if form.cleaned_data.get('max_price'):
                ads = ads.filter(price__lte=form.cleaned_data['max_price'])
            if form.cleaned_data.get('condition'):
                ads = ads.filter(condition=form.cleaned_data['condition'])
            if form.cleaned_data.get('logistics_option'):
                ads = ads.filter(logistics_option=form.cleaned_data['logistics_option'])
            if form.cleaned_data.get('country_from'):
                ads = ads.filter(country_from=form.cleaned_data['country_from'])
            if form.cleaned_data.get('country_to'):
                ads = ads.filter(country_to=form.cleaned_data['country_to'])

        # Pagination
        paginator = Paginator(ads, 20)  # 20 annonces par page
        page = self.request.GET.get('page')
        ads_page = paginator.get_page(page)

        context.update({
            'subcategories': subcategories,
            'ads': ads_page,
            'search_form': form,
            'total_ads': ads.count(),
        })
        return context


from django.db.models import Count, Q
from ads.models import Ad, Category
from ads.forms import AdSearchForm

class AdListView(ListView):
    """Liste de toutes les annonces"""
    model = Ad
    template_name = 'ads/ad_list.html'
    context_object_name = 'ads'
    paginate_by = 20

    def get_queryset(self):
        queryset = Ad.objects.filter(
            status=Ad.Status.ACTIVE
        ).select_related('seller', 'category').prefetch_related('images')

        # Appliquer les filtres
        form = AdSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('category'):
                category = form.cleaned_data['category']
                # Inclure les sous-catégories
                subcategories = category.get_descendants(include_self=True)
                queryset = queryset.filter(category__in=subcategories)

            if form.cleaned_data.get('q'):
                search_term = form.cleaned_data['q']
                queryset = queryset.filter(
                    Q(title__icontains=search_term) |
                    Q(description__icontains=search_term)
                )

            if form.cleaned_data.get('min_price'):
                queryset = queryset.filter(price__gte=form.cleaned_data['min_price'])
            if form.cleaned_data.get('max_price'):
                queryset = queryset.filter(price__lte=form.cleaned_data['max_price'])
            if form.cleaned_data.get('condition'):
                queryset = queryset.filter(condition=form.cleaned_data['condition'])
            if form.cleaned_data.get('logistics_option'):
                queryset = queryset.filter(logistics_option=form.cleaned_data['logistics_option'])
            if form.cleaned_data.get('country_from'):
                queryset = queryset.filter(country_from=form.cleaned_data['country_from'])
            if form.cleaned_data.get('country_to'):
                queryset = queryset.filter(country_to=form.cleaned_data['country_to'])

        # Tri
        sort_by = self.request.GET.get('sort', '-created_at')
        if sort_by in ['price', '-price', 'created_at', '-created_at', 'view_count', '-view_count']:
            queryset = queryset.order_by(sort_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AdSearchForm(self.request.GET)
        context['total_ads'] = self.get_queryset().count()

        # ✅ CORRECTION: Ajouter les catégories au contexte avec comptage des annonces actives
        context['categories'] = Category.objects.filter(
            is_active=True,
            ad_count__gt=0  # Filtre les catégories qui ont des annonces
        ).order_by('-ad_count', 'name')[:10]

        # Stats pour les filtres
        from django.db.models import Min, Max
        context['min_price_range'] = Ad.objects.filter(status=Ad.Status.ACTIVE).aggregate(Min('price'))['price__min'] or 0
        context['max_price_range'] = Ad.objects.filter(status=Ad.Status.ACTIVE).aggregate(Max('price'))['price__max'] or 10000

        return context


class AdDetailView(DetailView):
    """Détail d'une annonce"""
    model = Ad
    template_name = 'ads/ad_detail.html'
    context_object_name = 'ad'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ad = self.object

        # Enregistrer la vue
        if self.request.user.is_authenticated:
            AdView.objects.create(
                ad=ad,
                user=self.request.user,
                session_key=self.request.session.session_key,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                referer=self.request.META.get('HTTP_REFERER', '')
            )
        else:
            AdView.objects.create(
                ad=ad,
                session_key=self.request.session.session_key,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                referer=self.request.META.get('HTTP_REFERER', '')
            )

        # Annonces similaires
        similar_ads = Ad.objects.filter(
            category=ad.category,
            status=Ad.Status.ACTIVE
        ).exclude(pk=ad.pk).select_related('seller').prefetch_related('images')[:4]

        # Vérifier si l'annonce est dans les favoris de l'utilisateur
        is_favorite = False
        if self.request.user.is_authenticated:
            is_favorite = Favorite.objects.filter(
                user=self.request.user,
                ad=ad
            ).exists()

        context.update({
            'similar_ads': similar_ads,
            'is_favorite': is_favorite,
            'can_edit': self.request.user == ad.seller or self.request.user.is_staff,
            'can_report': self.request.user.is_authenticated and self.request.user != ad.seller,
        })
        return context


class AdCreateView(LoginRequiredMixin, CreateView):
    """Création d'une annonce"""
    model = Ad
    form_class = AdCreateForm
    template_name = 'ads/ad_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ✅ AJOUTER LES CATÉGORIES AU CONTEXTE
        # Catégories principales (sans parent)
        context['main_categories'] = Category.objects.filter(
            parent__isnull=True,
            is_active=True
        ).order_by('display_order', 'name')

        # ✅ TOUTES les catégories pour la sélection directe
        context['all_categories'] = Category.objects.filter(
            is_active=True
        ).order_by('lft')  # Utilisez 'lft' pour l'ordre hiérarchique

        if self.request.POST:
            context['image_formset'] = AdImageFormSet(self.request.POST, self.request.FILES)
        else:
            context['image_formset'] = AdImageFormSet()

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']

        with transaction.atomic():
            form.instance.seller = self.request.user
            self.object = form.save()

            if image_formset.is_valid():
                images = image_formset.save(commit=False)
                for image in images:
                    image.ad = self.object
                    image.save()

                # Vérifier le nombre d'images gratuites vs payantes
                free_images_count = sum(1 for img in images if not img.is_paid)
                if free_images_count > self.object.free_images_allowed:
                    messages.warning(
                        self.request,
                        _(f"Vous avez téléchargé {free_images_count} images gratuites, "
                          f"mais seulement {self.object.free_images_allowed} sont autorisées gratuitement. "
                          f"Les images supplémentaires seront marquées comme payantes.")
                    )

            else:
                return self.form_invalid(form)

        messages.success(self.request, _("Votre annonce a été créée avec succès !"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('ads:ad_detail', kwargs={'slug': self.object.slug})


class AdUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'une annonce"""
    model = Ad
    form_class = AdUpdateForm
    template_name = 'ads/ad_update.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def dispatch(self, request, *args, **kwargs):
        ad = self.get_object()
        if ad.seller != request.user and not request.user.is_staff:
            messages.error(request, _("Vous n'êtes pas autorisé à modifier cette annonce."))
            return redirect('ads:ad_detail', slug=ad.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['image_formset'] = AdImageFormSet(
                self.request.POST, self.request.FILES,
                instance=self.object
            )
        else:
            context['image_formset'] = AdImageFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        image_formset = context['image_formset']

        with transaction.atomic():
            self.object = form.save()

            if image_formset.is_valid():
                images = image_formset.save(commit=False)
                for image in images:
                    image.ad = self.object
                    image.save()

                # Supprimer les images marquées pour suppression
                for obj in image_formset.deleted_objects:
                    obj.delete()
            else:
                return self.form_invalid(form)

        messages.success(self.request, _("Votre annonce a été mise à jour avec succès !"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('ads:ad_detail', kwargs={'slug': self.object.slug})


class AdDeleteView(LoginRequiredMixin, DeleteView):
    """Suppression d'une annonce"""
    model = Ad
    template_name = 'ads/ad_delete.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('ads:ad_list')

    def dispatch(self, request, *args, **kwargs):
        ad = self.get_object()
        if ad.seller != request.user and not request.user.is_staff:
            messages.error(request, _("Vous n'êtes pas autorisé à supprimer cette annonce."))
            return redirect('ads:ad_detail', slug=ad.slug)
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("L'annonce a été supprimée avec succès."))
        return super().delete(request, *args, **kwargs)


@require_GET
def get_categories(request):
    """API pour récupérer les catégories dynamiquement"""
    parent_id = request.GET.get('parent_id')
    level = request.GET.get('level', 'sub')  # main, sub

    if level == 'main':
        # Utiliser l'utilitaire pour les catégories principales
        from .utils import get_main_categories
        categories = get_main_categories()

    elif level == 'sub' and parent_id:
        # Sous-catégorie directes
        categories = Category.objects.filter(
            parent_id=parent_id,
            is_active=True
        ).order_by('display_order', 'name')

        # Si aucune sous-catégorie directe, chercher les "petits-enfants"
        if not categories.exists():
            # Chercher les catégories dont le parent a comme parent parent_id
            sub_categories = Category.objects.filter(
                parent__isnull=False,
                parent__parent_id=parent_id,
                is_active=True
            ).order_by('display_order', 'name')

            categories = sub_categories

    else:
        categories = Category.objects.none()

    # Formater la réponse
    data = [{
        'id': cat.id,
        'name': cat.name,
        'has_children': cat.children.filter(is_active=True).exists(),
        'icon': cat.icon or '',
        'description': cat.description or '',
        'ad_count': cat.ad_count
    } for cat in categories]

    return JsonResponse({'categories': data})



@login_required
@require_POST
def toggle_favorite(request, slug):
    """Ajouter/retirer une annonce des favoris"""
    ad = get_object_or_404(Ad, slug=slug)

    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        ad=ad
    )

    if not created:
        favorite.delete()
        action = 'removed'
    else:
        action = 'added'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'action': action,
            'favorite_count': ad.favorite_count
        })

    messages.success(request, _(f"Annonce {action} aux favoris."))
    return redirect('ads:ad_detail', slug=slug)


class FavoriteListView(LoginRequiredMixin, ListView):
    """Liste des annonces favorites"""
    model = Favorite
    template_name = 'ads/favorite_list.html'
    context_object_name = 'favorites'

    def get_queryset(self):
        return Favorite.objects.filter(
            user=self.request.user
        ).select_related('ad', 'ad__seller', 'ad__category').prefetch_related('ad__images')


class AdReportView(LoginRequiredMixin, CreateView):
    """Signaler une annonce"""
    model = AdReport
    form_class = AdReportForm
    template_name = 'ads/ad_report.html'

    def dispatch(self, request, *args, **kwargs):
        self.ad = get_object_or_404(Ad, slug=kwargs['slug'])

        # Empêcher l'utilisateur de signaler sa propre annonce
        if request.user == self.ad.seller:
            messages.error(request, _("Vous ne pouvez pas signaler votre propre annonce."))
            return redirect('ads:ad_detail', slug=self.ad.slug)

        # Vérifier si l'utilisateur a déjà signalé cette annonce
        if AdReport.objects.filter(ad=self.ad, reporter=request.user).exists():
            messages.warning(request, _("Vous avez déjà signalé cette annonce."))
            return redirect('ads:ad_detail', slug=self.ad.slug)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ad'] = self.ad
        return context

    def form_valid(self, form):
        form.instance.ad = self.ad
        form.instance.reporter = self.request.user

        messages.success(
            self.request,
            _("Votre signalement a été soumis. Nous l'examinerons sous 24 heures.")
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('ads:ad_detail', kwargs={'slug': self.ad.slug})


class MyAdsListView(LoginRequiredMixin, ListView):
    """Liste des annonces de l'utilisateur"""
    model = Ad
    template_name = 'ads/my_ads.html'
    context_object_name = 'ads'
    paginate_by = 10

    def get_queryset(self):
        return Ad.objects.filter(
            seller=self.request.user
        ).select_related('category').prefetch_related('images').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        stats = Ad.objects.filter(seller=self.request.user).aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status=Ad.Status.ACTIVE)),
            draft=Count('id', filter=Q(status=Ad.Status.DRAFT)),
            sold=Count('id', filter=Q(status=Ad.Status.SOLD)),
            reserved=Count('id', filter=Q(status=Ad.Status.RESERVED)),
            total_views=Sum('view_count'),
            total_favorites=Sum('favorite_count'),
        )

        context.update(stats)
        return context


@login_required
@require_POST
def change_ad_status(request, slug, status):
    """Changer le statut d'une annonce"""
    ad = get_object_or_404(Ad, slug=slug, seller=request.user)

    if status not in dict(Ad.Status.choices):
        messages.error(request, _("Statut invalide."))
        return redirect('ads:my_ads')

    previous_status = ad.status
    ad.status = status

    if status == Ad.Status.ACTIVE and not ad.published_at:
        ad.published_at = timezone.now()

    ad.save()

    # FORCER la mise à jour du compteur de la catégorie
    if ad.category:
        ad.category.update_ad_count()

    messages.success(
        request,
        _(f"Statut de l'annonce changé de {previous_status} à {status}.")
    )

    return redirect('ads:ad_detail', slug=slug)


def search_ads(request):
    """Recherche avancée d'annonces"""
    form = AdSearchForm(request.GET)
    ads = Ad.objects.filter(status=Ad.Status.ACTIVE)

    if form.is_valid():
        if form.cleaned_data.get('q'):
            search_term = form.cleaned_data['q']
            ads = ads.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        if form.cleaned_data.get('category'):
            category = form.cleaned_data['category']
            subcategories = category.get_descendants(include_self=True)
            ads = ads.filter(category__in=subcategories)

        if form.cleaned_data.get('min_price'):
            ads = ads.filter(price__gte=form.cleaned_data['min_price'])
        if form.cleaned_data.get('max_price'):
            ads = ads.filter(price__lte=form.cleaned_data['max_price'])
        if form.cleaned_data.get('condition'):
            ads = ads.filter(condition=form.cleaned_data['condition'])
        if form.cleaned_data.get('logistics_option'):
            ads = ads.filter(logistics_option=form.cleaned_data['logistics_option'])
        if form.cleaned_data.get('country_from'):
            ads = ads.filter(country_from=form.cleaned_data['country_from'])
        if form.cleaned_data.get('country_to'):
            ads = ads.filter(country_to=form.cleaned_data['country_to'])

    # Pagination
    paginator = Paginator(ads, 20)
    page = request.GET.get('page')
    ads_page = paginator.get_page(page)

    context = {
        'ads': ads_page,
        'search_form': form,
        'total_ads': ads.count(),
    }

    return render(request, 'ads/search_results.html', context)

# ads/views.py - AJOUTER à la fin du fichier

class AdTransportProposalsView(LoginRequiredMixin, DetailView):
    """Vue pour voir les propositions de transport pour une annonce"""
    model = Ad
    template_name = 'ads/ad_transport_proposals.html'
    context_object_name = 'ad'

    def dispatch(self, request, *args, **kwargs):
        # Vérifier que l'utilisateur est le vendeur
        ad = self.get_object()
        if ad.seller != request.user:
            messages.error(request, _("Vous n'êtes pas autorisé à voir les propositions de transport."))
            return redirect('ads:ad_detail', slug=ad.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ad = self.object

        # Ici vous récupéreriez les propositions de transport depuis l'app logistics
        # Pour l'instant, retourner un contexte vide
        context['transport_proposals'] = []
        return context


@login_required
def ad_reserve(request, slug):
    """Réservation d'une annonce"""
    ad = get_object_or_404(Ad, slug=slug)

    if not ad.can_be_reserved(request.user):
        messages.error(request, _("Cette annonce ne peut pas être réservée."))
        return redirect('ads:ad_detail', slug=slug)

    # Logique de réservation temporaire
    messages.success(request, _("Réservation effectuée avec succès !"))
    return redirect('ads:ad_detail', slug=slug)


@login_required
def ad_propose_transport(request, slug):
    """Proposer un transport pour une annonce"""
    ad = get_object_or_404(Ad, slug=slug)

    if request.user == ad.seller:
        messages.error(request, _("Vous ne pouvez pas proposer un transport pour votre propre annonce."))
        return redirect('ads:ad_detail', slug=slug)

    # Logique de proposition de transport temporaire
    messages.info(request, _("Fonctionnalité de proposition de transport à implémenter."))
    return redirect('ads:ad_detail', slug=slug)