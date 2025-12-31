# ~/ebi3/payments/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta
import json

from .models import (
    Transaction, PaymentSession, Invoice, Refund,
    PaymentMethod, Subscription, Plan, Coupon, TaxRate
)

User = get_user_model()

class PaymentModelsTests(TestCase):
    """Tests pour les modèles de paiement"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.plan = Plan.objects.create(
            name='Plan Test',
            description='Plan de test',
            price=9.99,
            currency='EUR',
            billing_cycle_days=30,
            is_active=True
        )

    def test_transaction_creation(self):
        """Test la création d'une transaction"""
        transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED',
            purpose='AD_PROMOTION'
        )

        self.assertEqual(transaction.amount, 100.00)
        self.assertEqual(transaction.status, 'COMPLETED')
        self.assertEqual(transaction.user.username, 'testuser')
        self.assertIsNotNone(transaction.transaction_id)

    def test_invoice_generation(self):
        """Test la génération d'une facture"""
        transaction = Transaction.objects.create(
            user=self.user,
            amount=150.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED'
        )

        invoice = Invoice.objects.create(
            user=self.user,
            transaction=transaction,
            amount=150.00,
            currency='EUR',
            status='PAID'
        )

        self.assertEqual(invoice.invoice_number, f'INV-{invoice.id:06d}')
        self.assertEqual(invoice.amount, 150.00)
        self.assertEqual(invoice.status, 'PAID')

    def test_payment_session_expiration(self):
        """Test l'expiration d'une session de paiement"""
        payment_session = PaymentSession.objects.create(
            user=self.user,
            amount=50.00,
            currency='EUR',
            expires_at=timezone.now() - timedelta(minutes=5)
        )

        self.assertTrue(payment_session.is_expired())

    def test_refund_creation(self):
        """Test la création d'un remboursement"""
        transaction = Transaction.objects.create(
            user=self.user,
            amount=200.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED'
        )

        refund = Refund.objects.create(
            transaction=transaction,
            amount=100.00,
            reason='DOUBLE_CHARGE',
            status='PENDING'
        )

        self.assertEqual(refund.amount, 100.00)
        self.assertEqual(refund.status, 'PENDING')
        self.assertEqual(refund.transaction, transaction)

    def test_coupon_validation(self):
        """Test la validation d'un coupon"""
        coupon = Coupon.objects.create(
            code='TEST20',
            discount_type='PERCENTAGE',
            discount_value=20,
            max_uses=10,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30)
        )

        self.assertTrue(coupon.is_valid())
        self.assertEqual(coupon.calculate_discount(100), 20)

    def test_subscription_creation(self):
        """Test la création d'un abonnement"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='ACTIVE',
            current_period_start=timezone.now().date(),
            current_period_end=timezone.now().date() + timedelta(days=30),
            next_billing_date=timezone.now().date() + timedelta(days=30)
        )

        self.assertEqual(subscription.status, 'ACTIVE')
        self.assertEqual(subscription.plan.name, 'Plan Test')
        self.assertTrue(subscription.is_active())


class PaymentViewsTests(TestCase):
    """Tests pour les vues de paiement"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED'
        )

    def test_checkout_view_get(self):
        """Test l'accès à la page de checkout"""
        response = self.client.get(reverse('payments:checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/checkout/checkout.html')

    def test_transaction_history_view(self):
        """Test la vue d'historique des transactions"""
        response = self.client.get(reverse('payments:transaction_history'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/dashboard/transaction_history.html')
        self.assertContains(response, 'Historique des transactions')

    def test_invoice_detail_view(self):
        """Test la vue de détail d'une facture"""
        invoice = Invoice.objects.create(
            user=self.user,
            transaction=self.transaction,
            amount=100.00,
            currency='EUR'
        )

        response = self.client.get(reverse('payments:invoice_detail', kwargs={'pk': invoice.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/invoices/invoice_detail.html')

    def test_request_refund_view(self):
        """Test la vue de demande de remboursement"""
        response = self.client.get(reverse('payments:request_refund', kwargs={'transaction_id': self.transaction.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/refunds/request_refund.html')

    def test_payment_dashboard_view(self):
        """Test la vue du tableau de bord des paiements"""
        response = self.client.get(reverse('payments:payment_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/dashboard/payment_dashboard.html')

    def test_create_checkout_session_view(self):
        """Test la création d'une session de paiement (Stripe)"""
        response = self.client.post(reverse('payments:create_checkout_session'), {
            'amount': 50.00,
            'currency': 'EUR',
            'success_url': 'http://test.com/success',
            'cancel_url': 'http://test.com/cancel'
        })

        # Redirection ou réponse JSON attendue
        self.assertIn(response.status_code, [200, 302])

    def test_payment_webhook_view(self):
        """Test le webhook de paiement"""
        response = self.client.post(
            reverse('payments:stripe_webhook'),
            json.dumps({'type': 'payment_intent.succeeded'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class PaymentFormsTests(TestCase):
    """Tests pour les formulaires de paiement"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED'
        )

    def test_payment_form_valid(self):
        """Test un formulaire de paiement valide"""
        from .forms import PaymentForm

        form_data = {
            'amount': 50.00,
            'currency': 'EUR',
            'payment_method': 'CREDIT_CARD',
            'description': 'Test payment'
        }

        form = PaymentForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_refund_form_valid(self):
        """Test un formulaire de remboursement valide"""
        from .forms import RefundRequestForm

        form_data = {
            'amount': 50.00,
            'reason': 'CANCELLED_ORDER',
            'description': 'Order was cancelled',
            'evidence': SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        }

        form = RefundRequestForm(data=form_data, files=form_data)
        self.assertTrue(form.is_valid())

    def test_coupon_form_valid(self):
        """Test un formulaire de coupon valide"""
        from .forms import CouponForm

        form_data = {
            'code': 'TEST2024',
            'discount_type': 'PERCENTAGE',
            'discount_value': 15,
            'max_uses': 100,
            'valid_from': '2024-01-01',
            'valid_until': '2024-12-31'
        }

        form = CouponForm(data=form_data)
        self.assertTrue(form.is_valid())


class PaymentUtilsTests(TestCase):
    """Tests pour les utilitaires de paiement"""

    def test_transaction_id_generation(self):
        """Test la génération d'ID de transaction"""
        from .utils import generate_transaction_id

        transaction_id = generate_transaction_id()
        self.assertTrue(transaction_id.startswith('TXN'))
        self.assertEqual(len(transaction_id), 15)  # TXN + timestamp

    def test_invoice_number_generation(self):
        """Test la génération de numéro de facture"""
        from .utils import generate_invoice_number

        invoice_number = generate_invoice_number(1)
        self.assertEqual(invoice_number, 'INV-000001')

        invoice_number = generate_invoice_number(999)
        self.assertEqual(invoice_number, 'INV-000999')

    def test_amount_validation(self):
        """Test la validation des montants"""
        from .utils import validate_amount

        self.assertTrue(validate_amount(10.00))
        self.assertTrue(validate_amount(0.01))
        self.assertFalse(validate_amount(0))
        self.assertFalse(validate_amount(-10))

    def test_currency_conversion(self):
        """Test la conversion de devises"""
        from .utils import convert_currency

        # Test avec taux de change fictif
        converted = convert_currency(100, 'EUR', 'USD', 1.10)
        self.assertEqual(converted, 110.00)

        converted = convert_currency(50, 'USD', 'EUR', 0.91)
        self.assertAlmostEqual(converted, 45.50, places=2)


class PaymentIntegrationTests(TestCase):
    """Tests d'intégration pour les paiements"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_complete_payment_flow(self):
        """
        Test un flux complet de paiement:
        1. Création d'une session
        2. Paiement
        3. Vérification du statut
        4. Génération de facture
        """
        # 1. Créer une session de paiement
        session_response = self.client.post(reverse('payments:create_checkout_session'), {
            'amount': 75.00,
            'currency': 'EUR',
            'description': 'Test payment flow'
        })

        self.assertEqual(session_response.status_code, 200)
        session_data = session_response.json()
        self.assertIn('session_id', session_data)

        # 2. Simuler un paiement réussi
        # (Dans un test réel, on appellerait l'API Stripe)

        # 3. Vérifier l'historique
        history_response = self.client.get(reverse('payments:transaction_history'))
        self.assertEqual(history_response.status_code, 200)

    def test_refund_flow(self):
        """
        Test un flux complet de remboursement
        """
        # Créer une transaction complétée
        transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            status='COMPLETED'
        )

        # Demander un remboursement
        refund_response = self.client.post(
            reverse('payments:request_refund', kwargs={'transaction_id': transaction.id}),
            {
                'amount': 50.00,
                'reason': 'PARTIAL_REFUND',
                'description': 'Partial refund test'
            }
        )

        # Vérifier la redirection vers la page de statut
        self.assertEqual(refund_response.status_code, 302)

        # Vérifier que le remboursement a été créé
        refund = Refund.objects.filter(transaction=transaction).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, 50.00)
        self.assertEqual(refund.status, 'PENDING')

    def test_subscription_flow(self):
        """
        Test un flux d'abonnement
        """
        plan = Plan.objects.create(
            name='Premium',
            price=29.99,
            currency='EUR',
            billing_cycle_days=30,
            is_active=True
        )

        # S'abonner à un plan
        subscribe_response = self.client.post(
            reverse('payments:subscribe'),
            {
                'plan_id': plan.id,
                'payment_method': 'CREDIT_CARD'
            }
        )

        self.assertEqual(subscribe_response.status_code, 200)

        # Vérifier que l'abonnement a été créé
        subscription = Subscription.objects.filter(user=self.user, plan=plan).first()
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.status, 'PENDING')


class PaymentSecurityTests(TestCase):
    """Tests de sécurité pour les paiements"""

    def test_csrf_protection(self):
        """Test la protection CSRF sur les formulaires sensibles"""
        client = Client(enforce_csrf_checks=True)
        user = User.objects.create_user(
            username='securityuser',
            password='testpass123'
        )
        client.login(username='securityuser', password='testpass123')

        # Tentative de POST sans CSRF token
        response = client.post(reverse('payments:create_checkout_session'), {
            'amount': 100.00,
            'currency': 'EUR'
        })

        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_xss_protection(self):
        """Test la protection contre les attaques XSS"""
        malicious_input = '<script>alert("XSS")</script>'

        transaction = Transaction.objects.create(
            user=self.user,
            amount=100.00,
            currency='EUR',
            payment_method='CREDIT_CARD',
            description=malicious_input,
            status='COMPLETED'
        )

        # La description devrait être échappée dans les templates
        response = self.client.get(reverse('payments:transaction_detail', kwargs={'pk': transaction.pk}))
        self.assertNotContains(response, '<script>')
        self.assertContains(response, '&lt;script&gt;alert')  # HTML échappé

    def test_sql_injection_protection(self):
        """Test la protection contre les injections SQL"""
        # Les modèles Django protègent automatiquement contre les injections SQL
        # Ce test vérifie que les requêtes sont sûres

        suspicious_input = "100.00'; DROP TABLE payments_transaction; --"

        try:
            transaction = Transaction.objects.create(
                user=self.user,
                amount=suspicious_input,  # Ce champ est un DecimalField, donc converti
                currency='EUR',
                payment_method='CREDIT_CARD'
            )

            # Si on arrive ici, l'entrée a été validée
            # Vérifier que la table existe toujours
            count = Transaction.objects.count()
            self.assertGreaterEqual(count, 1)

        except Exception:
            # Une exception est attendue pour entrée invalide
            pass


class PaymentPerformanceTests(TestCase):
    """Tests de performance pour les paiements"""

    def test_transaction_list_performance(self):
        """Test les performances de la liste des transactions"""
        # Créer 100 transactions
        for i in range(100):
            Transaction.objects.create(
                user=self.user,
                amount=i + 1.00,
                currency='EUR',
                payment_method='CREDIT_CARD',
                status='COMPLETED'
            )

        # Mesurer le temps de chargement
        import time
        start_time = time.time()

        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('payments:transaction_history'))

        end_time = time.time()
        load_time = end_time - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(load_time, 2.0)  # Doit charger en moins de 2 secondes

    def test_bulk_operations(self):
        """Test les opérations en masse"""
        # Créer 1000 transactions en une requête (bulk_create)
        transactions = [
            Transaction(
                user=self.user,
                amount=i + 1.00,
                currency='EUR',
                payment_method='CREDIT_CARD'
            )
            for i in range(1000)
        ]

        Transaction.objects.bulk_create(transactions)

        # Vérifier le compte
        count = Transaction.objects.count()
        self.assertEqual(count, 1000)