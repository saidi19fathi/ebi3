# ~/ebi3/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = _('Profil')
    fk_name = 'user'
    fieldsets = (
        (_('Informations personnelles'), {
            'fields': ('date_of_birth', 'gender', 'country_of_origin',
                      'country_of_residence', 'is_expatriate')
        }),
        (_('Informations professionnelles'), {
            'fields': ('company_name', 'company_registration', 'tax_id')
        }),
        (_('Documents'), {
            'fields': ('id_document', 'proof_of_address', 'company_registration_doc'),
            'classes': ('collapse',)
        }),
        (_('Statistiques'), {
            'fields': ('total_ads', 'successful_transactions'),
            'classes': ('collapse',)
        }),
    )

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'country', 'is_verified',
                   'is_active', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active', 'country')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'city')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Informations personnelles'), {
            'fields': ('first_name', 'last_name', 'email', 'phone_number')
        }),
        (_('Localisation'), {
            'fields': ('country', 'city', 'address')
        }),
        (_('Rôles et permissions'), {
            'fields': ('role', 'is_verified', 'kyc_verified',
                      'email_verified', 'phone_verified',
                      'is_staff', 'is_active', 'is_superuser',
                      'groups', 'user_permissions')
        }),
        (_('Préférences'), {
            'fields': ('preferred_language',)
        }),
        (_('Dates importantes'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')
    inlines = (UserProfileInline,)

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'is_expatriate', 'created_at')
    list_filter = ('is_expatriate', 'gender')
    search_fields = ('user__username', 'user__email', 'company_name')
    raw_id_fields = ('user',)

    # ✅ CORRECTION : actions doit être une liste, pas une méthode
    actions = []