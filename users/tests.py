# ~/ebi3/users/tests.py
from django.test import TestCase
from django.urls import reverse
from .models import User

class UserModelTests(TestCase):
    def test_user_creation(self):
        """Test la création d'un utilisateur"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=User.Role.SELLER,
            country='FR',
            city='Paris'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.role, User.Role.SELLER)
        self.assertTrue(user.check_password('testpass123'))

    def test_is_carrier_method(self):
        """Test la méthode is_carrier"""
        carrier = User.objects.create_user(
            username='carrier',
            password='testpass123',
            role=User.Role.CARRIER
        )
        self.assertTrue(carrier.is_carrier())

class UserViewsTests(TestCase):
    def test_register_view(self):
        """Test la vue d'inscription"""
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')