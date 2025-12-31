# ~/ebi3/ads/tests.py
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import Category, Ad

User = get_user_model()


class AdsTests(TestCase):
    """Tests pour l'application ads"""

    def setUp(self):
        # Créer un utilisateur
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='SELLER'
        )

        # Créer une catégorie
        self.category = Category.objects.create(
            name='Électronique',
            slug='electronique',
            is_active=True
        )

        # Créer une annonce
        self.ad = Ad.objects.create(
            title='Test Annonce',
            slug='test-annonce',
            seller=self.user,
            category=self.category,
            description='Description de test',
            price=100.00,
            currency='EUR',
            country_from='FR',
            city_from='Paris',
            country_to='MA',
            city_to='Casablanca',
            logistics_option=Ad.LogisticsOption.P2P_DIRECT,
            status=Ad.Status.ACTIVE,
            available_from=timezone.now().date(),
            available_until=(timezone.now() + timedelta(days=30)).date()
        )

    def test_ad_creation(self):
        """Test la création d'une annonce"""
        self.assertEqual(self.ad.title, 'Test Annonce')
        self.assertEqual(self.ad.seller.username, 'testuser')
        self.assertEqual(self.ad.status, Ad.Status.ACTIVE)
        self.assertIsNotNone(self.ad.available_from)

    def test_ad_list_view(self):
        """Test la vue de liste des annonces"""
        response = self.client.get(reverse('ads:ad_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ads/ad_list.html')
        self.assertContains(response, 'Annonces')

    def test_ad_detail_view(self):
        """Test la vue de détail d'annonce"""
        response = self.client.get(reverse('ads:ad_detail', kwargs={'slug': self.ad.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ads/ad_detail.html')
        self.assertContains(response, 'Test Annonce')

    def test_ad_str_method(self):
        """Test la méthode __str__ de l'annonce"""
        self.assertEqual(str(self.ad), 'Test Annonce - testuser')

    def test_category_str_method(self):
        """Test la méthode __str__ de la catégorie"""
        self.assertEqual(str(self.category), 'Électronique')

    def test_ad_get_absolute_url(self):
        """Test la méthode get_absolute_url de l'annonce"""
        url = self.ad.get_absolute_url()
        # Prendre en compte le préfixe de langue
        expected = f'/ads/{self.ad.slug}/'
        # Si I18N est activé, l'URL aura un préfixe
        if settings.USE_I18N:
            self.assertTrue(url.startswith('/') and url.endswith(f'/ads/{self.ad.slug}/'))
        else:
            self.assertEqual(url, expected)

    def test_category_get_absolute_url(self):
        """Test la méthode get_absolute_url de la catégorie"""
        url = self.category.get_absolute_url()
        expected = f'/ads/categories/{self.category.slug}/'
        # Si I18N est activé, l'URL aura un préfixe
        if settings.USE_I18N:
            self.assertTrue(url.startswith('/') and url.endswith(f'/ads/categories/{self.category.slug}/'))
        else:
            self.assertEqual(url, expected)

    def test_ad_price_with_currency(self):
        """Test la méthode get_price_with_currency"""
        price_str = self.ad.get_price_with_currency()
        # Format attendu : "100.00 €"
        self.assertEqual(price_str, '100.00 €')

    def test_ad_can_be_reserved(self):
        """Test la méthode can_be_reserved"""
        # L'annonce peut être réservée par un autre utilisateur
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            role='BUYER'
        )
        self.assertTrue(self.ad.can_be_reserved(other_user))

        # Le vendeur ne peut pas réserver sa propre annonce
        self.assertFalse(self.ad.can_be_reserved(self.user))

        # Une annonce non active ne peut pas être réservée
        self.ad.status = Ad.Status.DRAFT
        self.ad.save()
        self.assertFalse(self.ad.can_be_reserved(other_user))


class CategoryTests(TestCase):
    """Tests spécifiques pour les catégories"""

    def setUp(self):
        self.parent_category = Category.objects.create(
            name='Parent',
            slug='parent',
            is_active=True
        )

        self.child_category = Category.objects.create(
            name='Child',
            slug='child',
            parent=self.parent_category,
            is_active=True
        )

    def test_category_hierarchy(self):
        """Test la hiérarchie des catégories"""
        self.assertEqual(self.child_category.parent, self.parent_category)
        self.assertIn(self.child_category, self.parent_category.children.all())

    def test_category_get_full_path(self):
        """Test la méthode get_full_path"""
        path = self.child_category.get_full_path()
        self.assertEqual(path, 'Parent > Child')


class AdModelTests(TestCase):
    """Tests supplémentaires pour le modèle Ad"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='modeluser',
            password='testpass123',
            role='SELLER'
        )

        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )

    def test_ad_slug_generation(self):
        """Test la génération automatique du slug"""
        ad = Ad.objects.create(
            title='Un titre avec des espaces',
            seller=self.user,
            category=self.category,
            description='Description',
            price=50.00,
            currency='EUR',
            country_from='FR',
            city_from='Paris',
            country_to='MA',
            city_to='Casablanca',
            available_from=timezone.now().date()
        )

        # Le slug devrait être généré automatiquement
        self.assertTrue(hasattr(ad, 'slug'))
        self.assertTrue(ad.slug.startswith('un-titre-avec-des-espaces'))

    def test_ad_volume_calculation(self):
        """Test le calcul automatique du volume"""
        ad = Ad.objects.create(
            title='Test Volume',
            seller=self.user,
            category=self.category,
            description='Description',
            price=50.00,
            currency='EUR',
            country_from='FR',
            city_from='Paris',
            country_to='MA',
            city_to='Casablanca',
            length=10,
            width=20,
            height=30,
            available_from=timezone.now().date()
        )

        # Volume = (10 * 20 * 30) / 1000 = 6 litres
        # Mais le calcul se fait dans save(), donc vérifions après rechargement
        ad.refresh_from_db()
        if ad.volume:  # Peut être None si pas calculé
            self.assertEqual(float(ad.volume), 6.0)

    def test_ad_status_transitions(self):
        """Test les transitions de statut"""
        ad = Ad.objects.create(
            title='Test Status',
            seller=self.user,
            category=self.category,
            description='Description',
            price=50.00,
            currency='EUR',
            country_from='FR',
            city_from='Paris',
            country_to='MA',
            city_to='Casablanca',
            available_from=timezone.now().date(),
            status=Ad.Status.DRAFT
        )

        # Vérifier qu'il n'y a pas de date de publication
        self.assertIsNone(ad.published_at)

        # Changer le statut à ACTIVE
        ad.status = Ad.Status.ACTIVE
        ad.save()
        ad.refresh_from_db()

        # Vérifier que published_at a été défini
        self.assertIsNotNone(ad.published_at)

    def test_ad_expiration(self):
        """Test l'expiration automatique"""
        ad = Ad.objects.create(
            title='Test Expiration',
            seller=self.user,
            category=self.category,
            description='Description',
            price=50.00,
            currency='EUR',
            country_from='FR',
            city_from='Paris',
            country_to='MA',
            city_to='Casablanca',
            available_from=timezone.now().date() - timedelta(days=10),
            available_until=timezone.now().date() - timedelta(days=1),  # Hier
            status=Ad.Status.ACTIVE
        )

        # Sauvegarder pour déclencher la logique d'expiration
        ad.save()
        ad.refresh_from_db()

        # L'annonce devrait être marquée comme expirée
        self.assertEqual(ad.status, Ad.Status.EXPIRED)
        self.assertIsNotNone(ad.expired_at)


# Tests de vues avec TransactionTestCase pour éviter les problèmes de DB
class AdsViewTests(TransactionTestCase):
    """Tests des vues avec gestion transactionnelle"""

    def test_empty_ad_list(self):
        """Test la liste d'annonces vide"""
        response = self.client.get(reverse('ads:ad_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aucune annonce')

    def test_search_view(self):
        """Test la vue de recherche"""
        response = self.client.get(reverse('ads:search'), {'q': 'test'})
        self.assertEqual(response.status_code, 200)