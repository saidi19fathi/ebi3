# ~/ebi3/payments/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView,
    DeleteView, TemplateView, FormView, View
)
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q, F
from django.db import transaction, models
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.core.paginator import Paginator
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    PaymentTransaction, PaymentMethod, Invoice, Refund,
    Commission, Payout, Wallet, WalletTransaction, Tax, ExchangeRate,
    FraudAlert, Subscription, Plan, Coupon, PaymentSession, PaymentCard, Currency
)
from .forms import (
    PaymentForm, WalletRechargeForm, WalletWithdrawalForm,
    CreditCardPaymentForm, PayPalPaymentForm, BankTransferForm,
    MobileMoneyForm, InvoiceForm, RefundRequestForm,
    PaymentMethodForm, PayoutRequestForm, TaxConfigurationForm,
    CommissionConfigurationForm, ExchangeRateForm,
    PaymentReportForm, TransactionSearchForm, RefundReviewForm,
    PayoutProcessForm, AdPaymentForm, MissionPaymentForm,
    PaymentCheckoutForm, FinancialReportForm, PaymentNotificationForm,
    WalletTransferForm, CardPaymentForm, MobileMoneyPaymentForm,
    TaxForm, CommissionForm, PlanForm, SubscriptionForm,
    CouponForm, PaymentSessionForm, CurrencyForm, PaymentCardForm
)

logger = logging.getLogger(__name__)

# ============================================================================
# VUES PUBLIQUES
# ============================================================================

class PaymentHomeView(TemplateView):
    """Page d'accueil des paiements"""
    template_name = 'payments/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Récupérer les méthodes de paiement
        try:
            context['payment_methods'] = PaymentMethod.objects.filter(is_active=True)
        except:
            context['payment_methods'] = []

        # Récupérer les devises
        try:
            context['currencies'] = Currency.objects.filter(is_active=True)
        except Exception:
            context['currencies'] = []

        # Statistiques
        try:
            context['total_transactions'] = PaymentTransaction.objects.filter(status='COMPLETED').count()
            context['total_volume'] = PaymentTransaction.objects.filter(
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))['total'] or 0
        except:
            context['total_transactions'] = 0
            context['total_volume'] = 0

        return context


class PaymentMethodsView(TemplateView):
    """Liste des méthodes de paiement disponibles"""
    template_name = 'payments/payment_methods.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Méthodes actives
        try:
            active_methods = PaymentMethod.objects.filter(is_active=True).order_by('created_at')

            # Grouper par type
            context['card_methods'] = active_methods.filter(method_type='CARD')
            context['bank_transfers'] = active_methods.filter(method_type='BANK_ACCOUNT')
            context['digital_wallets'] = active_methods.filter(method_type='DIGITAL_WALLET')
            context['mobile_money'] = active_methods.filter(method_type='MOBILE_MONEY')
        except:
            context['card_methods'] = []
            context['bank_transfers'] = []
            context['digital_wallets'] = []
            context['mobile_money'] = []

        return context


# ============================================================================
# CHECKOUT & PROCESSUS DE PAIEMENT
# ============================================================================

class CheckoutView(LoginRequiredMixin, FormView):
    """Vue de checkout pour un paiement"""
    template_name = 'payments/checkout/checkout.html'
    form_class = PaymentCheckoutForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user

        # Récupérer le type d'objet (ad, mission, etc.)
        object_type = self.request.GET.get('object_type')
        object_id = self.request.GET.get('object_id')

        if object_type and object_id:
            if object_type == 'ad':
                from ads.models import Ad
                try:
                    obj = Ad.objects.get(id=object_id)
                    kwargs['object'] = obj
                except Ad.DoesNotExist:
                    pass
            elif object_type == 'mission':
                from logistics.models import Mission
                try:
                    obj = Mission.objects.get(id=object_id)
                    kwargs['object'] = obj
                except Mission.DoesNotExist:
                    pass

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Portefeuille de l'utilisateur
        try:
            context['wallet'] = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            context['wallet'] = None

        # Cartes enregistrées
        try:
            context['saved_cards'] = PaymentCard.objects.filter(user=user, is_active=True)
        except Exception:
            context['saved_cards'] = []

        # Méthodes de paiement disponibles
        try:
            context['payment_methods'] = PaymentMethod.objects.filter(is_active=True)
        except:
            context['payment_methods'] = []

        # Taxes applicables
        try:
            context['taxes'] = Tax.objects.filter(is_active=True)
        except:
            context['taxes'] = []

        return context

    def form_valid(self, form):
        try:
            # Créer la session de paiement
            payment_session = PaymentSession.objects.create(
                user=self.request.user,
                amount=form.cleaned_data['amount'],
                currency=form.cleaned_data['currency'],
                payment_method=form.cleaned_data['payment_method'],
                metadata={
                    'object_type': form.cleaned_data.get('object_type'),
                    'object_id': form.cleaned_data.get('object_id'),
                    'notes': form.cleaned_data.get('notes', '')
                },
                expires_at=timezone.now() + timedelta(minutes=30),
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )

            # Rediriger vers le processus de paiement spécifique
            payment_method_type = form.cleaned_data['payment_method']
            if payment_method_type == 'CREDIT_CARD':
                return redirect('payments:card_payment', session_id=payment_session.id)
            elif payment_method_type == 'PAYPAL':
                return redirect('payments:paypal_payment', session_id=payment_session.id)
            elif payment_method_type == 'MOBILE_MONEY':
                return redirect('payments:mobile_money_payment', session_id=payment_session.id)
            elif payment_method_type == 'BANK_TRANSFER':
                return redirect('payments:bank_transfer', session_id=payment_session.id)
            elif payment_method_type == 'EBI3_WALLET':
                return redirect('payments:wallet_payment', session_id=payment_session.id)
            else:
                return redirect('payments:payment_process', session_id=payment_session.id)

        except Exception as e:
            logger.error(f"Checkout error: {e}")
            messages.error(self.request, _("Une erreur est survenue lors de la création du paiement."))
            return self.form_invalid(form)


class CardPaymentView(LoginRequiredMixin, FormView):
    """Paiement par carte bancaire"""
    template_name = 'payments/checkout/card_payment.html'
    form_class = CardPaymentForm

    def dispatch(self, request, *args, **kwargs):
        try:
            self.session = get_object_or_404(
                PaymentSession,
                id=kwargs['session_id'],
                user=request.user
            )
        except:
            messages.error(request, _("Session de paiement non trouvée."))
            return redirect('payments:checkout')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['session'] = self.session

        # Cartes sauvegardées
        try:
            context['saved_cards'] = PaymentCard.objects.filter(
                user=self.request.user,
                is_active=True
            )
        except Exception:
            context['saved_cards'] = []

        context['stripe_publishable_key'] = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '')

        return context

    def form_valid(self, form):
        try:
            # Traiter le paiement par carte
            # Note: Cette partie nécessite l'intégration avec Stripe ou autre processeur
            # Pour l'instant, créons simplement la transaction

            with transaction.atomic():
                # Créer la transaction
                payment_transaction = PaymentTransaction.objects.create(
                    payer=self.request.user,
                    amount=self.session.amount,
                    currency=self.session.currency,
                    payment_type='OTHER',
                    payment_method='CREDIT_CARD',
                    status='PENDING',
                    metadata={
                        'card_last_four': form.cleaned_data['card_number'][-4:],
                        'card_holder': form.cleaned_data['card_holder'],
                        'session_id': str(self.session.id)
                    }
                )

                # Mettre à jour la session
                self.session.status = 'PROCESSING'
                self.session.save()

                # Sauvegarder la carte si demandé
                if form.cleaned_data.get('save_card'):
                    try:
                        PaymentCard.objects.create(
                            user=self.request.user,
                            last_four=form.cleaned_data['card_number'][-4:],
                            expiry_month=form.cleaned_data['expiry_month'],
                            expiry_year=form.cleaned_data['expiry_year'],
                            cardholder_name=form.cleaned_data['card_holder'],
                            card_type=PaymentCard.detect_card_type(form.cleaned_data['card_number']),
                            is_active=True
                        )
                    except Exception as e:
                        logger.error(f"Error saving card: {e}")

                messages.success(self.request, _("Paiement par carte traité avec succès."))
                return redirect('payments:payment_success', transaction_id=payment_transaction.id)

        except Exception as e:
            logger.error(f"Card payment error: {e}")
            messages.error(self.request, _("Une erreur est survenue lors du traitement de votre carte."))
            return self.form_invalid(form)


class PaymentSuccessView(LoginRequiredMixin, DetailView):
    """Page de succès du paiement"""
    template_name = 'payments/checkout/success.html'
    model = PaymentTransaction
    context_object_name = 'transaction'

    def get_queryset(self):
        return PaymentTransaction.objects.filter(payer=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transaction = self.object

        # Récupérer la facture
        try:
            context['invoice'] = Invoice.objects.get(transaction=transaction)
        except Invoice.DoesNotExist:
            context['invoice'] = None

        return context


class PaymentFailedView(LoginRequiredMixin, TemplateView):
    """Page d'échec du paiement"""
    template_name = 'payments/checkout/failed.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.request.GET.get('session_id')

        if session_id:
            try:
                context['session'] = PaymentSession.objects.get(id=session_id, user=self.request.user)
            except PaymentSession.DoesNotExist:
                context['session'] = None

        return context


# ============================================================================
# GESTION DU PORTEFEUILLE
# ============================================================================

class WalletDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord du portefeuille"""
    template_name = 'payments/wallet/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Récupérer ou créer le portefeuille
        wallet, created = Wallet.objects.get_or_create(user=user)
        context['wallet'] = wallet

        # Transactions récentes
        context['recent_transactions'] = WalletTransaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')[:10]

        # Statistiques
        try:
            context['stats'] = {
                'total_deposits': WalletTransaction.objects.filter(
                    wallet=wallet, transaction_type='CREDIT'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'total_withdrawals': WalletTransaction.objects.filter(
                    wallet=wallet, transaction_type='DEBIT'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'transaction_count': WalletTransaction.objects.filter(wallet=wallet).count(),
                'last_deposit': WalletTransaction.objects.filter(
                    wallet=wallet, transaction_type='CREDIT'
                ).order_by('-created_at').first(),
            }
        except:
            context['stats'] = {
                'total_deposits': Decimal('0'),
                'total_withdrawals': Decimal('0'),
                'transaction_count': 0,
                'last_deposit': None,
            }

        # Limites
        try:
            context['limits'] = wallet.get_current_limits()
        except Exception:
            context['limits'] = {}

        return context


class WalletRechargeView(LoginRequiredMixin, FormView):
    """Rechargement du portefeuille"""
    template_name = 'payments/wallet/recharge.html'
    form_class = WalletRechargeForm
    success_url = reverse_lazy('payments:wallet_dashboard')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            context['wallet'] = Wallet.objects.get(user=self.request.user)
        except Wallet.DoesNotExist:
            context['wallet'] = None

        try:
            context['payment_methods'] = PaymentMethod.objects.filter(is_active=True)
        except:
            context['payment_methods'] = []

        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Récupérer le portefeuille
                wallet = Wallet.objects.get(user=self.request.user)

                # Créer une session de paiement pour le rechargement
                session = PaymentSession.objects.create(
                    user=self.request.user,
                    amount=form.cleaned_data['amount'],
                    currency=form.cleaned_data['currency'],
                    payment_method=form.cleaned_data['payment_method'],
                    metadata={'recharge': True},
                    expires_at=timezone.now() + timedelta(minutes=30),
                    ip_address=self.request.META.get('REMOTE_ADDR'),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', '')
                )

                messages.success(self.request, _(
                    "Demande de rechargement créée. "
                    "Veuillez compléter le paiement."
                ))

                # Rediriger vers le paiement
                return redirect('payments:checkout') + f'?session_id={session.id}'

        except Wallet.DoesNotExist:
            messages.error(self.request, _("Vous n'avez pas de portefeuille."))
            return redirect('payments:wallet_create')
        except Exception as e:
            logger.error(f"Wallet recharge error: {e}")
            messages.error(self.request, _("Une erreur est survenue lors de la création du rechargement."))
            return self.form_invalid(form)


class WalletTransactionsView(LoginRequiredMixin, ListView):
    """Historique des transactions du portefeuille"""
    template_name = 'payments/wallet/transactions.html'
    model = WalletTransaction
    context_object_name = 'transactions'
    paginate_by = 20

    def get_queryset(self):
        try:
            wallet = Wallet.objects.get(user=self.request.user)
            return WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        except Wallet.DoesNotExist:
            return WalletTransaction.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            context['wallet'] = Wallet.objects.get(user=self.request.user)
        except Wallet.DoesNotExist:
            context['wallet'] = None

        # Filtres
        context['filter_form'] = TransactionSearchForm(self.request.GET or None)

        # Statistiques
        if context['wallet']:
            try:
                context['stats'] = {
                    'total_credited': WalletTransaction.objects.filter(
                        wallet=context['wallet'],
                        transaction_type='CREDIT',
                        status='COMPLETED'
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                    'total_debited': WalletTransaction.objects.filter(
                        wallet=context['wallet'],
                        transaction_type='DEBIT',
                        status='COMPLETED'
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                }
            except:
                context['stats'] = {
                    'total_credited': Decimal('0'),
                    'total_debited': Decimal('0'),
                }

        return context


class WalletCreateView(LoginRequiredMixin, View):
    """Création d'un portefeuille"""

    def get(self, request):
        # Vérifier si l'utilisateur a déjà un portefeuille
        if hasattr(request.user, 'wallet'):
            messages.info(request, _("Vous avez déjà un portefeuille."))
            return redirect('payments:wallet_dashboard')

        return render(request, 'payments/wallet/create.html')

    def post(self, request):
        try:
            with transaction.atomic():
                # Créer le portefeuille
                wallet = Wallet.objects.create(
                    user=request.user,
                    currency='EUR',  # Devise par défaut
                    status='ACTIVE'
                )

                # Créer le code PIN
                pin = request.POST.get('pin')
                confirm_pin = request.POST.get('confirm_pin')

                if not pin or not confirm_pin:
                    messages.error(request, _("Le code PIN est requis."))
                    return render(request, 'payments/wallet/create.html')

                if pin != confirm_pin:
                    messages.error(request, _("Les codes PIN ne correspondent pas."))
                    return render(request, 'payments/wallet/create.html')

                if len(pin) != 4 or not pin.isdigit():
                    messages.error(request, _("Le code PIN doit être composé de 4 chiffres."))
                    return render(request, 'payments/wallet/create.html')

                # Hasher et sauvegarder le PIN
                wallet.set_pin(pin)
                wallet.save()

                messages.success(request, _("Votre portefeuille a été créé avec succès."))
                return redirect('payments:wallet_dashboard')

        except Exception as e:
            logger.error(f"Wallet creation error: {e}")
            messages.error(request, _("Une erreur est survenue lors de la création du portefeuille."))
            return render(request, 'payments/wallet/create.html')


# ============================================================================
# FACTURES ET DOCUMENTS
# ============================================================================

class InvoiceListView(LoginRequiredMixin, ListView):
    """Liste des factures"""
    template_name = 'payments/invoices/list.html'
    model = Invoice
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        return Invoice.objects.filter(
            transaction__payer=self.request.user
        ).select_related('transaction').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        try:
            context['stats'] = {
                'total_invoices': self.get_queryset().count(),
                'total_paid': self.get_queryset().filter(
                    status='PAID'
                ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0'),
                'pending_invoices': self.get_queryset().filter(status='DRAFT').count(),
            }
        except:
            context['stats'] = {
                'total_invoices': 0,
                'total_paid': Decimal('0'),
                'pending_invoices': 0,
            }

        return context


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une facture"""
    template_name = 'payments/invoices/detail.html'
    model = Invoice
    context_object_name = 'invoice'

    def get_queryset(self):
        return Invoice.objects.filter(transaction__payer=self.request.user)


# ============================================================================
# REMBOURSEMENTS
# ============================================================================

class RefundRequestView(LoginRequiredMixin, CreateView):
    """Demande de remboursement"""
    template_name = 'payments/refunds/request.html'
    form_class = RefundRequestForm
    success_url = reverse_lazy('payments:refund_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Transactions éligibles au remboursement
        try:
            context['eligible_transactions'] = PaymentTransaction.objects.filter(
                payer=self.request.user,
                status='COMPLETED',
                created_at__gte=timezone.now() - timedelta(days=30)  # 30 jours max
            ).exclude(
                refunds__status__in=['REQUESTED', 'APPROVED', 'COMPLETED']
            )
        except:
            context['eligible_transactions'] = []

        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                refund = form.save(commit=False)
                refund.requested_by = self.request.user
                refund.status = 'REQUESTED'
                refund.save()

                messages.success(self.request, _(
                    "Votre demande de remboursement a été soumise. "
                    "Elle sera traitée sous 24-48 heures."
                ))

                return super().form_valid(form)

        except Exception as e:
            logger.error(f"Refund request error: {e}")
            messages.error(self.request, _("Une erreur est survenue."))
            return self.form_invalid(form)


class RefundListView(LoginRequiredMixin, ListView):
    """Liste des remboursements"""
    template_name = 'payments/refunds/list.html'
    model = Refund
    context_object_name = 'refunds'
    paginate_by = 20

    def get_queryset(self):
        return Refund.objects.filter(requested_by=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        try:
            context['stats'] = {
                'total_refunds': self.get_queryset().count(),
                'total_refunded': self.get_queryset().filter(
                    status='COMPLETED'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'pending_refunds': self.get_queryset().filter(status='REQUESTED').count(),
            }
        except:
            context['stats'] = {
                'total_refunds': 0,
                'total_refunded': Decimal('0'),
                'pending_refunds': 0,
            }

        return context


# ============================================================================
# VUES D'ADMINISTRATION (STAFF)
# ============================================================================

class StaffPaymentDashboardView(UserPassesTestMixin, TemplateView):
    """Tableau de bord admin des paiements"""
    template_name = 'payments/admin/dashboard.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques générales
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        try:
            # Transactions
            context['total_transactions'] = PaymentTransaction.objects.count()
            context['today_transactions'] = PaymentTransaction.objects.filter(
                created_at__date=today
            ).count()
            context['week_transactions'] = PaymentTransaction.objects.filter(
                created_at__date__gte=week_ago
            ).count()

            # Volume
            context['total_volume'] = PaymentTransaction.objects.filter(
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            context['today_volume'] = PaymentTransaction.objects.filter(
                status='COMPLETED',
                created_at__date=today
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            context['week_volume'] = PaymentTransaction.objects.filter(
                status='COMPLETED',
                created_at__date__gte=week_ago
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            # Portefeuilles
            context['total_wallets'] = Wallet.objects.count()
            context['active_wallets'] = Wallet.objects.filter(status='ACTIVE').count()
            context['total_wallet_balance'] = Wallet.objects.aggregate(
                total=Sum('balance')
            )['total'] or Decimal('0')

            # Paiements en attente
            context['pending_payouts'] = Payout.objects.filter(status='PENDING').count()
            context['pending_refunds'] = Refund.objects.filter(status='REQUESTED').count()

        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            # Valeurs par défaut en cas d'erreur
            context['total_transactions'] = 0
            context['total_volume'] = Decimal('0')
            context['total_wallets'] = 0
            context['pending_payouts'] = 0
            context['pending_refunds'] = 0

        # Transactions récentes
        try:
            context['recent_transactions'] = PaymentTransaction.objects.select_related(
                'payer', 'payee'
            ).order_by('-created_at')[:10]
        except:
            context['recent_transactions'] = []

        return context


class StaffTransactionListView(UserPassesTestMixin, ListView):
    """Liste des transactions (admin)"""
    template_name = 'payments/admin/transactions.html'
    model = PaymentTransaction
    context_object_name = 'transactions'
    paginate_by = 50

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related(
            'payer', 'payee'
        ).order_by('-created_at')

        # Filtres
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search) |
                Q(payer__username__icontains=search) |
                Q(payer__email__icontains=search) |
                Q(payee__username__icontains=search) |
                Q(payee__email__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Formulaires de filtre
        context['filter_form'] = TransactionSearchForm(self.request.GET or None)

        # Statistiques des filtres
        queryset = self.get_queryset()
        try:
            context['filter_stats'] = {
                'total': queryset.count(),
                'total_amount': queryset.filter(status='COMPLETED').aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0'),
                'pending': queryset.filter(status='PENDING').count(),
                'completed': queryset.filter(status='COMPLETED').count(),
                'failed': queryset.filter(status='FAILED').count(),
            }
        except:
            context['filter_stats'] = {
                'total': 0,
                'total_amount': Decimal('0'),
                'pending': 0,
                'completed': 0,
                'failed': 0,
            }

        return context


# ============================================================================
# VUES D'ERREUR ET REDIRECTIONS
# ============================================================================

class PaymentErrorView(TemplateView):
    """Page d'erreur générique"""
    template_name = 'payments/error.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Récupérer le code d'erreur
        error_code = self.kwargs.get('error_code', 'generic')
        error_messages = {
            'insufficient_funds': _("Fonds insuffisants."),
            'card_declined': _("Carte refusée."),
            'expired_card': _("Carte expirée."),
            'invalid_card': _("Carte invalide."),
            'fraud_detected': _("Paiement détecté comme frauduleux."),
            'timeout': _("Délai d'attente dépassé."),
            'gateway_error': _("Erreur de la passerelle de paiement."),
            'generic': _("Une erreur est survenue lors du paiement."),
        }

        context['error_message'] = error_messages.get(error_code, error_messages['generic'])
        context['error_code'] = error_code

        # Session ID pour réessayer
        session_id = self.request.GET.get('session_id')
        if session_id:
            try:
                context['session'] = PaymentSession.objects.get(id=session_id)
            except PaymentSession.DoesNotExist:
                pass

        return context


# ============================================================================
# VUES UTILITAIRES
# ============================================================================

@login_required
def verify_payment_status(request, reference):
    """Vérifier le statut d'un paiement par référence"""
    try:
        transaction = PaymentTransaction.objects.get(
            Q(reference=reference) | Q(payment_gateway_id=reference),
            payer=request.user
        )

        return JsonResponse({
            'status': transaction.status,
            'status_display': transaction.get_status_display(),
            'amount': str(transaction.amount),
            'currency': transaction.currency,
            'created_at': transaction.created_at.isoformat(),
        })

    except PaymentTransaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction non trouvée'}, status=404)


@login_required
def payment_methods_json(request):
    """Retourner les méthodes de paiement en JSON"""
    try:
        methods = PaymentMethod.objects.filter(is_active=True).values(
            'id', 'method_type', 'is_default', 'is_verified'
        )
        return JsonResponse({'methods': list(methods)})
    except:
        return JsonResponse({'methods': []})


@login_required
def currency_rates_json(request):
    """Retourner les taux de change en JSON"""
    try:
        rates = ExchangeRate.objects.filter(
            is_active=True
        ).values('base_currency', 'target_currency', 'rate', 'last_updated')
        return JsonResponse({'rates': list(rates)})
    except:
        return JsonResponse({'rates': []})


# ============================================================================
# VUE PAR DÉFAUT (REDIRECTION)
# ============================================================================

def payment_redirect(request):
    """Rediriger vers la page de paiement appropriée"""
    # Vérifier s'il y a une session en cours
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            session = PaymentSession.objects.get(id=session_id)
            return redirect('payments:payment_status', session_id=session_id)
        except PaymentSession.DoesNotExist:
            pass

    # Sinon, rediriger vers la page d'accueil des paiements
    return redirect('payments:home')