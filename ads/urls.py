# ~/ebi3/ads/urls.py
from django.urls import path
from . import views

app_name = 'ads'

urlpatterns = [
    # Annonces
    path('', views.AdListView.as_view(), name='ad_list'),
    path('create/', views.AdCreateView.as_view(), name='ad_create'),
    path('search/', views.search_ads, name='search'),
    path('my-ads/', views.MyAdsListView.as_view(), name='my_ads'),

    # Annonce spécifique
    path('<slug:slug>/', views.AdDetailView.as_view(), name='ad_detail'),
    path('<slug:slug>/edit/', views.AdUpdateView.as_view(), name='ad_edit'),
    path('<slug:slug>/delete/', views.AdDeleteView.as_view(), name='ad_delete'),
    path('<slug:slug>/report/', views.AdReportView.as_view(), name='ad_report'),
    path('<slug:slug>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('<slug:slug>/status/<str:status>/', views.change_ad_status, name='change_status'),

    # Nouvelle intégration avec logistics
    path('<slug:slug>/reserve/', views.AdDetailView.as_view(), name='ad_reserve'),
    path('<slug:slug>/propose-transport/', views.AdDetailView.as_view(), name='ad_propose_transport'),
    path('<slug:slug>/transport-proposals/', views.AdTransportProposalsView.as_view(), name='ad_transport_proposals'),

    # Catégories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),

    # Favoris
    path('favorites/', views.FavoriteListView.as_view(), name='favorite_list'),
]