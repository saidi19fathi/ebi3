# ~/ebi3/core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import SiteSetting, Page, FAQ, Country, NewsletterSubscriber, ContactMessage

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    """Administration des paramètres du site"""
    list_display = ('key', 'name', 'setting_type', 'group', 'is_public', 'updated_at')
    list_filter = ('setting_type', 'group', 'is_public')
    search_fields = ('key', 'name', 'description')
    list_editable = ('is_public',)

    fieldsets = (
        (_('Paramètre'), {
            'fields': ('key', 'name', 'description', 'group')
        }),
        (_('Valeur'), {
            'fields': ('setting_type', 'value')
        }),
        (_('Visibilité'), {
            'fields': ('is_public',)
        }),
    )

    # ✅ CORRECTION : actions doit être une liste, pas une méthode
    actions = ['clear_cache']

    def clear_cache(self, request, queryset):
        """Efface le cache des paramètres sélectionnés"""
        from django.core.cache import cache
        for setting in queryset:
            cache.delete(f'site_setting_{setting.key}')
        self.message_user(request, _('Cache effacé pour les paramètres sélectionnés.'))
    clear_cache.short_description = _('Effacer le cache')


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Administration des pages"""
    list_display = ('title', 'slug', 'language', 'status', 'show_in_menu', 'show_in_footer', 'updated_at')
    list_filter = ('status', 'language', 'show_in_menu', 'show_in_footer')
    search_fields = ('title', 'content', 'slug')
    list_editable = ('status', 'show_in_menu', 'show_in_footer')
    prepopulated_fields = {'slug': ('title',)}

    fieldsets = (
        (_('Contenu'), {
            'fields': ('title', 'slug', 'content', 'language')
        }),
        (_('Publication'), {
            'fields': ('status', 'published_at')
        }),
        (_('Navigation'), {
            'fields': ('show_in_menu', 'show_in_footer', 'menu_order')
        }),
        (_('SEO'), {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION : actions doit être une liste de noms de méthodes
    actions = ['make_published', 'make_draft']

    def make_published(self, request, queryset):
        updated = queryset.update(status='PUBLISHED')
        self.message_user(request, _(f'{updated} pages ont été publiées.'))
    make_published.short_description = _('Publier les pages sélectionnées')

    def make_draft(self, request, queryset):
        updated = queryset.update(status='DRAFT')
        self.message_user(request, _(f'{updated} pages sont maintenant en brouillon.'))
    make_draft.short_description = _('Mettre en brouillon')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """Administration des FAQs"""
    list_display = ('question', 'category', 'language', 'display_order', 'is_active')
    list_filter = ('category', 'language', 'is_active')
    search_fields = ('question', 'answer')
    list_editable = ('display_order', 'is_active')

    fieldsets = (
        (_('Contenu'), {
            'fields': ('question', 'answer', 'category', 'language')
        }),
        (_('Affichage'), {
            'fields': ('display_order', 'is_active')
        }),
    )

    # ✅ CORRECTION : actions doit être une liste de noms de méthodes
    actions = ['activate_faqs', 'deactivate_faqs']

    def activate_faqs(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _(f'{updated} FAQs ont été activées.'))
    activate_faqs.short_description = _('Activer les FAQs')

    def deactivate_faqs(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _(f'{updated} FAQs ont été désactivées.'))
    deactivate_faqs.short_description = _('Désactiver les FAQs')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    """Administration des pays"""
    list_display = ('name', 'code', 'is_active', 'is_departure', 'is_destination', 'currency_code', 'display_order')
    list_filter = ('is_active', 'is_departure', 'is_destination')
    search_fields = ('name', 'code', 'name_ar', 'name_fr', 'name_en')
    list_editable = ('is_active', 'is_departure', 'is_destination', 'display_order')

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('code', 'name', 'name_ar', 'name_fr', 'name_en')
        }),
        (_('Configuration'), {
            'fields': ('is_active', 'is_departure', 'is_destination', 'display_order')
        }),
        (_('Monnaie'), {
            'fields': ('currency_code', 'currency_symbol')
        }),
        (_('Contact'), {
            'fields': ('phone_code', 'flag')
        }),
    )

    # ✅ AJOUT : actions doit être défini (liste vide si pas d'actions)
    actions = []


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    """Administration des abonnés newsletter"""
    list_display = ('email', 'is_active', 'subscribed_at', 'unsubscribed_at')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at', 'unsubscribed_at')

    # ✅ CORRECTION : actions doit être une liste de noms de méthodes
    actions = ['unsubscribe_selected']

    def unsubscribe_selected(self, request, queryset):
        updated = 0
        for subscriber in queryset:
            subscriber.unsubscribe()
            updated += 1
        self.message_user(request, _(f'{updated} abonnés ont été désinscrits.'))
    unsubscribe_selected.short_description = _('Désinscrire les abonnés sélectionnés')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Administration des messages de contact"""
    list_display = ('name', 'email', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at', 'updated_at', 'ip_address', 'user_agent')
    list_editable = ('status',)

    fieldsets = (
        (_('Message'), {
            'fields': ('name', 'email', 'subject', 'message')
        }),
        (_('Statut'), {
            'fields': ('status', 'admin_notes')
        }),
        (_('Métadonnées'), {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION : actions doit être une liste de noms de méthodes
    actions = ['mark_as_resolved', 'mark_as_spam']

    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='RESOLVED')
        self.message_user(request, _(f'{updated} messages ont été marqués comme résolus.'))
    mark_as_resolved.short_description = _('Marquer comme résolu')

    def mark_as_spam(self, request, queryset):
        updated = queryset.update(status='SPAM')
        self.message_user(request, _(f'{updated} messages ont été marqués comme spam.'))
    mark_as_spam.short_description = _('Marquer comme spam')