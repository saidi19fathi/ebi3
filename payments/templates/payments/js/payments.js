// ~/ebi3/payments/static/payments/js/payments.js

class PaymentManager {
    constructor() {
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.setupPaymentForm();
        this.setupCountdownTimers();
        this.setupQRCodeGenerator();
        this.setupPrintFunctionality();
    }

    setupEventListeners() {
        // Gestion des méthodes de paiement
        document.querySelectorAll('.payment-method-card').forEach(card => {
            card.addEventListener('click', (e) => this.selectPaymentMethod(e));
        });

        // Validation des formulaires
        document.querySelectorAll('.payment-form').forEach(form => {
            form.addEventListener('submit', (e) => this.validatePaymentForm(e));
        });

        // Copie des références
        document.querySelectorAll('.copy-reference').forEach(button => {
            button.addEventListener('click', (e) => this.copyToClipboard(e));
        });

        // Téléchargement des factures
        document.querySelectorAll('.download-invoice').forEach(button => {
            button.addEventListener('click', (e) => this.downloadInvoice(e));
        });

        // Affichage des détails
        document.querySelectorAll('.toggle-details').forEach(button => {
            button.addEventListener('click', (e) => this.toggleDetails(e));
        });
    }

    setupPaymentForm() {
        const paymentForm = document.getElementById('payment-form');
        if (!paymentForm) return;

        // Masquage des numéros de carte
        const cardNumberInput = paymentForm.querySelector('input[name="card_number"]');
        if (cardNumberInput) {
            cardNumberInput.addEventListener('input', (e) => this.formatCardNumber(e));
        }

        // Formatage de la date d'expiration
        const expiryInput = paymentForm.querySelector('input[name="expiry_date"]');
        if (expiryInput) {
            expiryInput.addEventListener('input', (e) => this.formatExpiryDate(e));
        }

        // Validation en temps réel
        paymentForm.querySelectorAll('input').forEach(input => {
            input.addEventListener('blur', (e) => this.validateField(e.target));
        });
    }

    setupCountdownTimers() {
        const countdownElements = document.querySelectorAll('.countdown-timer');
        countdownElements.forEach(element => {
            const seconds = parseInt(element.dataset.seconds) || 1800; // 30 minutes par défaut
            this.startCountdown(element, seconds);
        });
    }

    setupQRCodeGenerator() {
        const generateQRButtons = document.querySelectorAll('.generate-qr');
        generateQRButtons.forEach(button => {
            button.addEventListener('click', (e) => this.generateQRCode(e));
        });
    }

    setupPrintFunctionality() {
        const printButtons = document.querySelectorAll('.print-receipt');
        printButtons.forEach(button => {
            button.addEventListener('click', (e) => this.printReceipt(e));
        });
    }

    selectPaymentMethod(event) {
        const card = event.currentTarget;
        const method = card.dataset.method;

        // Désélectionner toutes les cartes
        document.querySelectorAll('.payment-method-card').forEach(c => {
            c.classList.remove('selected');
        });

        // Sélectionner la carte cliquée
        card.classList.add('selected');

        // Mettre à jour le champ caché
        const hiddenInput = document.getElementById('selected_payment_method');
        if (hiddenInput) {
            hiddenInput.value = method;
        }

        // Afficher/masquer les détails spécifiques
        this.togglePaymentDetails(method);

        // Activer le bouton de soumission
        const submitButton = document.getElementById('submit-btn');
        if (submitButton) {
            submitButton.disabled = false;
        }

        // Envoyer un événement analytics
        this.trackEvent('payment_method_selected', { method: method });
    }

    togglePaymentDetails(method) {
        // Masquer tous les détails
        const allDetails = document.querySelectorAll('.payment-details');
        allDetails.forEach(detail => {
            detail.style.display = 'none';
        });

        // Afficher les détails spécifiques
        const targetDetails = document.getElementById(`${method}-details`);
        if (targetDetails) {
            targetDetails.style.display = 'block';
        }
    }

    formatCardNumber(event) {
        let value = event.target.value.replace(/\s/g, '');
        let formatted = '';

        for (let i = 0; i < value.length; i++) {
            if (i > 0 && i % 4 === 0) {
                formatted += ' ';
            }
            formatted += value[i];
        }

        event.target.value = formatted;

        // Détecter le type de carte
        const cardType = this.detectCardType(value);
        this.updateCardIcon(cardType);
    }

    detectCardType(cardNumber) {
        const patterns = {
            visa: /^4/,
            mastercard: /^(5[1-5]|2[2-7])/,
            amex: /^3[47]/,
            discover: /^6(?:011|5)/,
            diners: /^3(?:0[0-5]|[68])/,
            jcb: /^35/,
            unionpay: /^62/,
        };

        for (const [type, pattern] of Object.entries(patterns)) {
            if (pattern.test(cardNumber)) {
                return type;
            }
        }

        return 'unknown';
    }

    updateCardIcon(cardType) {
        const iconMap = {
            visa: 'fab fa-cc-visa',
            mastercard: 'fab fa-cc-mastercard',
            amex: 'fab fa-cc-amex',
            discover: 'fab fa-cc-discover',
            diners: 'fab fa-cc-diners-club',
            jcb: 'fab fa-cc-jcb',
            unionpay: 'fab fa-cc-unionpay',
            unknown: 'fas fa-credit-card'
        };

        const iconElement = document.querySelector('.card-type-icon');
        if (iconElement) {
            iconElement.className = iconMap[cardType] || 'fas fa-credit-card';
        }
    }

    formatExpiryDate(event) {
        let value = event.target.value.replace(/\D/g, '');

        if (value.length >= 2) {
            value = value.substring(0, 2) + '/' + value.substring(2, 4);
        }

        event.target.value = value;
    }

    validateField(field) {
        const value = field.value.trim();
        const name = field.name;
        let isValid = true;
        let message = '';

        switch (name) {
            case 'card_number':
                isValid = this.validateCardNumber(value);
                message = isValid ? '' : 'Numéro de carte invalide';
                break;
            case 'expiry_date':
                isValid = this.validateExpiryDate(value);
                message = isValid ? '' : 'Date d\'expiration invalide';
                break;
            case 'cvv':
                isValid = this.validateCVV(value);
                message = isValid ? '' : 'CVV invalide';
                break;
            case 'amount':
                isValid = this.validateAmount(value);
                message = isValid ? '' : 'Montant invalide';
                break;
        }

        this.showFieldValidation(field, isValid, message);
        return isValid;
    }

    validateCardNumber(cardNumber) {
        const cleaned = cardNumber.replace(/\s/g, '');

        // Vérifier la longueur
        if (cleaned.length < 13 || cleaned.length > 19) {
            return false;
        }

        // Algorithme de Luhn
        let sum = 0;
        let isEven = false;

        for (let i = cleaned.length - 1; i >= 0; i--) {
            let digit = parseInt(cleaned.charAt(i), 10);

            if (isEven) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }

            sum += digit;
            isEven = !isEven;
        }

        return (sum % 10) === 0;
    }

    validateExpiryDate(expiryDate) {
        if (!/^\d{2}\/\d{2}$/.test(expiryDate)) {
            return false;
        }

        const [month, year] = expiryDate.split('/').map(Number);
        const now = new Date();
        const currentYear = now.getFullYear() % 100;
        const currentMonth = now.getMonth() + 1;

        if (month < 1 || month > 12) {
            return false;
        }

        if (year < currentYear || (year === currentYear && month < currentMonth)) {
            return false;
        }

        return true;
    }

    validateCVV(cvv) {
        return /^\d{3,4}$/.test(cvv);
    }

    validateAmount(amount) {
        const min = parseFloat(document.getElementById('amount').dataset.min) || 0.01;
        const max = parseFloat(document.getElementById('amount').dataset.max) || 100000;
        const value = parseFloat(amount);

        return !isNaN(value) && value >= min && value <= max;
    }

    showFieldValidation(field, isValid, message) {
        const feedbackElement = field.nextElementSibling;

        if (feedbackElement && feedbackElement.classList.contains('invalid-feedback')) {
            feedbackElement.textContent = message;
            feedbackElement.style.display = message ? 'block' : 'none';
        }

        if (isValid) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        } else {
            field.classList.remove('is-valid');
            field.classList.add('is-invalid');
        }
    }

    validatePaymentForm(event) {
        const form = event.currentTarget;
        const selectedMethod = document.getElementById('selected_payment_method')?.value;

        if (!selectedMethod) {
            event.preventDefault();
            this.showToast('Veuillez sélectionner une méthode de paiement', 'error');
            return false;
        }

        // Validation spécifique selon la méthode
        let isValid = true;

        if (selectedMethod === 'CREDIT_CARD' || selectedMethod === 'DEBIT_CARD') {
            isValid = this.validateCardForm();
        } else if (selectedMethod === 'BANK_TRANSFER') {
            isValid = this.validateBankTransferForm();
        }

        if (!isValid) {
            event.preventDefault();
            return false;
        }

        // Validation des conditions générales
        const termsCheckbox = document.getElementById('terms');
        if (termsCheckbox && !termsCheckbox.checked) {
            event.preventDefault();
            this.showToast('Veuillez accepter les conditions générales', 'error');
            return false;
        }

        // Afficher le loader
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="payment-loader"></span> Traitement en cours...';
        }

        // Envoyer un événement analytics
        this.trackEvent('payment_form_submitted', {
            method: selectedMethod,
            amount: document.getElementById('amount')?.value
        });

        return true;
    }

    validateCardForm() {
        const cardNumber = document.querySelector('input[name="card_number"]')?.value;
        const expiryDate = document.querySelector('input[name="expiry_date"]')?.value;
        const cvv = document.querySelector('input[name="cvv"]')?.value;
        const cardName = document.querySelector('input[name="card_name"]')?.value;

        let isValid = true;

        if (!this.validateCardNumber(cardNumber)) {
            this.showToast('Numéro de carte invalide', 'error');
            isValid = false;
        }

        if (!this.validateExpiryDate(expiryDate)) {
            this.showToast('Date d\'expiration invalide', 'error');
            isValid = false;
        }

        if (!this.validateCVV(cvv)) {
            this.showToast('CVV invalide', 'error');
            isValid = false;
        }

        if (!cardName || cardName.trim().length < 2) {
            this.showToast('Nom sur la carte invalide', 'error');
            isValid = false;
        }

        return isValid;
    }

    validateBankTransferForm() {
        // Validation spécifique aux virements bancaires
        return true;
    }

    startCountdown(element, seconds) {
        let timeLeft = seconds;

        const updateTimer = () => {
            const minutes = Math.floor(timeLeft / 60);
            const secs = timeLeft % 60;

            element.textContent = `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

            if (timeLeft <= 0) {
                clearInterval(timer);
                element.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Session expirée';
                element.classList.add('expired');

                // Désactiver le formulaire
                const form = element.closest('form');
                if (form) {
                    form.querySelectorAll('button').forEach(btn => {
                        btn.disabled = true;
                    });
                }

                this.showToast('Votre session a expiré. Veuillez recommencer.', 'error');
            }

            timeLeft--;
        };

        updateTimer();
        const timer = setInterval(updateTimer, 1000);
    }

    generateQRCode(event) {
        const button = event.currentTarget;
        const data = button.dataset.qrData;
        const size = button.dataset.qrSize || 200;
        const container = document.getElementById('qr-code-container');

        if (!container) return;

        // Afficher un loader
        container.innerHTML = '<div class="payment-loader"></div>';

        // Générer le QR code avec une API
        fetch('/payments/api/generate-qr/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                data: data,
                size: size
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                container.innerHTML = `<img src="${result.qr_code}" alt="QR Code" class="img-fluid">`;
                this.showToast('QR Code généré avec succès', 'success');
            } else {
                container.innerHTML = '<p class="text-danger">Erreur lors de la génération</p>';
                this.showToast('Erreur lors de la génération du QR Code', 'error');
            }
        })
        .catch(error => {
            console.error('Error generating QR code:', error);
            container.innerHTML = '<p class="text-danger">Erreur réseau</p>';
            this.showToast('Erreur réseau', 'error');
        });
    }

    copyToClipboard(event) {
        const button = event.currentTarget;
        const text = button.dataset.copyText || button.textContent;

        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Copié dans le presse-papier', 'success');

            // Changer temporairement l'icône
            const icon = button.querySelector('i');
            if (icon) {
                const originalClass = icon.className;
                icon.className = 'fas fa-check';

                setTimeout(() => {
                    icon.className = originalClass;
                }, 2000);
            }
        }).catch(err => {
            console.error('Failed to copy:', err);
            this.showToast('Échec de la copie', 'error');
        });
    }

    downloadInvoice(event) {
        const button = event.currentTarget;
        const invoiceId = button.dataset.invoiceId;

        // Afficher un loader
        const originalText = button.innerHTML;
        button.innerHTML = '<span class="payment-loader"></span> Téléchargement...';
        button.disabled = true;

        // Télécharger la facture
        fetch(`/payments/invoices/${invoiceId}/download/`)
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `facture-${invoiceId}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                this.showToast('Facture téléchargée', 'success');
            })
            .catch(error => {
                console.error('Download error:', error);
                this.showToast('Erreur lors du téléchargement', 'error');
            })
            .finally(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            });
    }

    toggleDetails(event) {
        const button = event.currentTarget;
        const targetId = button.dataset.target;
        const target = document.getElementById(targetId);

        if (target) {
            const isHidden = target.style.display === 'none';
            target.style.display = isHidden ? 'block' : 'none';
            button.querySelector('i').className = isHidden ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
        }
    }

    printReceipt(event) {
        window.print();
    }

    showToast(message, type = 'info') {
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
        }

        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        container.appendChild(toastElement.firstElementChild);

        const toast = new bootstrap.Toast(toastElement.firstElementChild);
        toast.show();

        // Supprimer le toast après disparition
        toastElement.firstElementChild.addEventListener('hidden.bs.toast', function () {
            this.remove();
        });
    }

    trackEvent(eventName, data) {
        // Implémentation de tracking (Google Analytics, etc.)
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, data);
        }

        // Envoyer à votre propre backend
        fetch('/payments/api/track-event/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                event: eventName,
                data: data,
                timestamp: new Date().toISOString()
            })
        }).catch(error => console.error('Tracking error:', error));
    }

    getCSRFToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
}

// Initialisation lorsque le DOM est chargé
document.addEventListener('DOMContentLoaded', function() {
    window.paymentManager = new PaymentManager();
});

// Exports pour les tests
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PaymentManager;
}