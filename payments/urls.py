# ~/ebi3/payments/urls.py
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'payments'

urlpatterns = [
    # ============================================================================
    # VUES PUBLIQUES
    # ============================================================================
    path('', views.PaymentHomeView.as_view(), name='home'),
    path('methods/', views.PaymentMethodsView.as_view(), name='payment_methods'),
    path('error/<str:error_code>/', views.PaymentErrorView.as_view(), name='payment_error'),

    # ============================================================================
    # CHECKOUT & PROCESSUS DE PAIEMENT
    # ============================================================================
    path('checkout/', login_required(views.CheckoutView.as_view()), name='checkout'),
    path('card-payment/<uuid:session_id>/', login_required(views.CardPaymentView.as_view()), name='card_payment'),
    path('success/<int:pk>/', login_required(views.PaymentSuccessView.as_view()), name='payment_success'),
    path('failed/', login_required(views.PaymentFailedView.as_view()), name='payment_failed'),

    # ============================================================================
    # GESTION DU PORTEFEUILLE
    # ============================================================================
    path('wallet/', login_required(views.WalletDashboardView.as_view()), name='wallet_dashboard'),
    path('wallet/recharge/', login_required(views.WalletRechargeView.as_view()), name='wallet_recharge'),
    path('wallet/transactions/', login_required(views.WalletTransactionsView.as_view()), name='wallet_transactions'),
    path('wallet/create/', login_required(views.WalletCreateView.as_view()), name='wallet_create'),

    # ============================================================================
    # FACTURES ET DOCUMENTS
    # ============================================================================
    path('invoices/', login_required(views.InvoiceListView.as_view()), name='invoice_list'),
    path('invoices/<int:pk>/', login_required(views.InvoiceDetailView.as_view()), name='invoice_detail'),

    # ============================================================================
    # REMBOURSEMENTS
    # ============================================================================
    path('refunds/request/', login_required(views.RefundRequestView.as_view()), name='refund_request'),
    path('refunds/', login_required(views.RefundListView.as_view()), name='refund_list'),

    # ============================================================================
    # ADMINISTRATION (STAFF)
    # ============================================================================
    path('admin/dashboard/', views.StaffPaymentDashboardView.as_view(), name='staff_dashboard'),
    path('admin/transactions/', views.StaffTransactionListView.as_view(), name='staff_transaction_list'),

    # ============================================================================
    # VUES UTILITAIRES (API/FONCTIONS)
    # ============================================================================
    path('api/verify-payment/<str:reference>/', login_required(views.verify_payment_status), name='verify_payment_status'),
    path('api/payment-methods/', login_required(views.payment_methods_json), name='payment_methods_json'),
    path('api/currency-rates/', login_required(views.currency_rates_json), name='currency_rates_json'),
    path('redirect/', views.payment_redirect, name='payment_redirect'),

    # ============================================================================
    # ALIAS ET REDIRECTIONS POUR COMPATIBILITÉ
    # ============================================================================
    path('payment-status/<uuid:session_id>/', login_required(views.PaymentFailedView.as_view()), name='payment_status'),
]


# URLs supplémentaires si vous développez d'autres fonctionnalités

# PayPal (si implémenté)
# path('paypal-payment/<uuid:session_id>/', login_required(views.PayPalPaymentView.as_view()), name='paypal_payment'),
# path('paypal/execute/<uuid:session_id>/', login_required(views.PayPalExecuteView.as_view()), name='paypal_execute'),
# path('paypal/cancel/<uuid:session_id>/', login_required(views.PayPalCancelView.as_view()), name='paypal_cancel'),

# Mobile Money (si implémenté)
# path('mobile-money/<uuid:session_id>/', login_required(views.MobileMoneyPaymentView.as_view()), name='mobile_money_payment'),

# Bank Transfer (si implémenté)
# path('bank-transfer/<uuid:session_id>/', login_required(views.BankTransferView.as_view()), name='bank_transfer'),

# Wallet Payment (si implémenté)
# path('wallet-payment/<uuid:session_id>/', login_required(views.WalletPaymentView.as_view()), name='wallet_payment'),

# Crypto (si implémenté)
# path('crypto-payment/<uuid:session_id>/', login_required(views.CryptoPaymentView.as_view()), name='crypto_payment'),

# Webhooks (si implémenté)
# path('webhook/<str:gateway>/', views.PaymentWebhookView.as_view(), name='payment_webhook'),

# API supplémentaires
# path('api/calculate-fees/', login_required(views.CalculateFeesAPIView.as_view()), name='calculate_fees'),