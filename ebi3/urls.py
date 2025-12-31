# ~/ebi3/ebi3/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.views.i18n import set_language

urlpatterns = [
    path('set-language/', set_language, name='set_language'),
    path('admin/', admin.site.urls),
    path('rosetta/', include('rosetta.urls')),
    # REMOVED: path('logistics-admin/', logistics_admin_site.urls),  # Cette ligne cause l'erreur
]

# URLs avec support de langue
urlpatterns += i18n_patterns(
    path('', include('core.urls', namespace='core')),
    path('users/', include('users.urls', namespace='users')),
    path('ads/', include('ads.urls', namespace='ads')),
    path('carriers/', include('carriers.urls', namespace='carriers')),
    path('colis/', include('colis.urls', namespace='colis')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('logistics/', include('logistics.urls', namespace='logistics')),
    path('messages/', include('messaging.urls', namespace='messaging')),
    path('reviews/', include('reviews.urls', namespace='reviews')),
    path('tracking/', include('tracking.urls', namespace='tracking')),
    prefix_default_language=True,
)

# Fichiers statiques et médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Handlers d'erreur
handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'
handler403 = 'core.views.handler403'
handler400 = 'core.views.handler400'