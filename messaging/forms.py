# ~/ebi3/messaging/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MaxValueValidator

from .models import (
    Conversation, Message, Notification,
    UserMessageSettings, BlockedUser,
    ConversationArchive, MessageReport
)

class NewConversationForm(forms.Form):
    """Formulaire pour démarrer une nouvelle conversation"""

    recipient = forms.CharField(
        max_length=150,
        label=_("Destinataire"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Nom d'utilisateur ou email"),
            'autocomplete': 'off'
        })
    )

    subject = forms.CharField(
        max_length=200,
        required=False,
        label=_("Sujet"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Sujet de la conversation (optionnel)")
        })
    )

    message = forms.CharField(
        label=_("Message"),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': _("Votre message..."),
            'style': 'resize: none;'
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_recipient(self):
        recipient_identifier = self.cleaned_data.get('recipient')

        from users.models import User

        # Rechercher l'utilisateur par username ou email
        try:
            if '@' in recipient_identifier:
                recipient = User.objects.get(email=recipient_identifier)
            else:
                recipient = User.objects.get(username=recipient_identifier)
        except User.DoesNotExist:
            raise ValidationError(_("Utilisateur non trouvé."))

        # Ne pas permettre de s'envoyer un message à soi-même
        if recipient == self.user:
            raise ValidationError(_("Vous ne pouvez pas vous envoyer un message à vous-même."))

        # Vérifier si l'utilisateur n'est pas bloqué
        if BlockedUser.objects.filter(blocker=self.user, blocked=recipient).exists():
            raise ValidationError(_("Vous avez bloqué cet utilisateur."))

        # Vérifier les paramètres de confidentialité du destinataire
        try:
            recipient_settings = recipient.message_settings
            if recipient_settings.allow_messages_from == 'CONTACTS':
                # Vérifier si l'expéditeur est dans les contacts
                # À implémenter: logique des contacts
                pass
            elif recipient_settings.allow_messages_from == 'NOBODY':
                raise ValidationError(_("Cet utilisateur n'accepte pas de messages."))
        except UserMessageSettings.DoesNotExist:
            pass

        return recipient

    def clean_message(self):
        message = self.cleaned_data.get('message')
        if len(message.strip()) < 2:
            raise ValidationError(_("Le message est trop court."))
        if len(message) > 5000:
            raise ValidationError(_("Le message est trop long (maximum 5000 caractères)."))
        return message


class MessageForm(forms.ModelForm):
    """Formulaire pour envoyer un message"""

    class Meta:
        model = Message
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _("Tapez votre message ici..."),
                'style': 'resize: none;'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.xls,.xlsx,.zip'
            })
        }
        labels = {
            'content': _("Message"),
            'attachment': _("Pièce jointe")
        }

    def __init__(self, *args, **kwargs):
        self.conversation = kwargs.pop('conversation', None)
        self.sender = kwargs.pop('sender', None)
        self.recipient = kwargs.pop('recipient', None)
        super().__init__(*args, **kwargs)

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')

        if attachment:
            # Valider le type de fichier
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf',
                                 'doc', 'docx', 'xls', 'xlsx', 'zip']
            validator = FileExtensionValidator(allowed_extensions)
            validator(attachment)

            # Valider la taille (10MB maximum)
            max_size = 10 * 1024 * 1024  # 10MB
            if attachment.size > max_size:
                raise ValidationError(
                    _(f"Le fichier est trop volumineux. Taille maximum: {max_size/(1024*1024):.0f}MB")
                )

        return attachment

    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        attachment = cleaned_data.get('attachment')

        # Un message doit avoir au moins du contenu ou une pièce jointe
        if not content and not attachment:
            raise ValidationError(_("Le message doit contenir du texte ou une pièce jointe."))

        return cleaned_data

    def save(self, commit=True):
        message = super().save(commit=False)

        if self.conversation:
            message.conversation = self.conversation

        if self.sender:
            message.sender = self.sender

        if self.recipient:
            message.recipient = self.recipient

        if message.attachment:
            message.attachment_name = message.attachment.name
            message.attachment_size = message.attachment.size

        if commit:
            message.save()

        return message


class ConversationSearchForm(forms.Form):
    """Formulaire de recherche de conversations"""

    q = forms.CharField(
        required=False,
        label=_("Rechercher"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Rechercher dans les conversations...")
        })
    )

    conversation_type = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous"))] + list(Conversation.ConversationType.choices),
        label=_("Type de conversation"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_from = forms.DateField(
        required=False,
        label=_("Du"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    date_to = forms.DateField(
        required=False,
        label=_("Au"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    has_attachment = forms.ChoiceField(
        required=False,
        choices=[
            ('', _("Tous")),
            ('yes', _("Avec pièces jointes")),
            ('no', _("Sans pièces jointes"))
        ],
        label=_("Pièces jointes"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    is_read = forms.ChoiceField(
        required=False,
        choices=[
            ('', _("Tous")),
            ('read', _("Lus")),
            ('unread', _("Non lus"))
        ],
        label=_("Statut de lecture"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to:
            if date_to < date_from:
                raise ValidationError(_("La date de fin doit être postérieure à la date de début."))

        return cleaned_data


class MessageReportForm(forms.ModelForm):
    """Formulaire pour signaler un message"""

    class Meta:
        model = MessageReport
        fields = ['reason', 'description', 'evidence']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _("Décrivez le problème en détail...")
            }),
            'evidence': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf,.doc,.docx'
            }),
        }
        labels = {
            'reason': _("Raison du signalement"),
            'description': _("Description"),
            'evidence': _("Preuve (optionnel)")
        }

    def __init__(self, *args, **kwargs):
        self.reporter = kwargs.pop('reporter', None)
        self.message = kwargs.pop('message', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Vérifier si l'utilisateur a déjà signalé ce message
        if self.reporter and self.message:
            if MessageReport.objects.filter(
                reporter=self.reporter,
                message=self.message
            ).exists():
                raise ValidationError(_("Vous avez déjà signalé ce message."))

        return cleaned_data

    def save(self, commit=True):
        report = super().save(commit=False)

        if self.reporter:
            report.reporter = self.reporter

        if self.message:
            report.message = self.message

        if commit:
            report.save()

        return report


class BlockUserForm(forms.ModelForm):
    """Formulaire pour bloquer un utilisateur"""

    class Meta:
        model = BlockedUser
        fields = ['reason']
        widgets = {
            'reason': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Raison du blocage (optionnel)")
            })
        }
        labels = {
            'reason': _("Raison (optionnel)")
        }

    def __init__(self, *args, **kwargs):
        self.blocker = kwargs.pop('blocker', None)
        self.blocked = kwargs.pop('blocked', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Ne pas permettre de se bloquer soi-même
        if self.blocker == self.blocked:
            raise ValidationError(_("Vous ne pouvez pas vous bloquer vous-même."))

        # Vérifier si l'utilisateur est déjà bloqué
        if BlockedUser.objects.filter(
            blocker=self.blocker,
            blocked=self.blocked
        ).exists():
            raise ValidationError(_("Vous avez déjà bloqué cet utilisateur."))

        return cleaned_data

    def save(self, commit=True):
        blocked_user = super().save(commit=False)

        if self.blocker:
            blocked_user.blocker = self.blocker

        if self.blocked:
            blocked_user.blocked = self.blocked

        if commit:
            blocked_user.save()

        return blocked_user


class UserMessageSettingsForm(forms.ModelForm):
    """Formulaire pour les paramètres de messagerie"""

    class Meta:
        model = UserMessageSettings
        fields = [
            'email_notifications', 'push_notifications', 'desktop_notifications',
            'allow_messages_from', 'auto_archive_conversations', 'archive_after_days',
            'auto_delete_messages', 'delete_after_days', 'show_online_status',
            'show_read_receipts', 'block_spam_messages', 'filter_profanity'
        ]

        widgets = {
            'allow_messages_from': forms.Select(attrs={'class': 'form-control'}),
            'archive_after_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365'
            }),
            'delete_after_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '30',
                'max': '3650'
            }),
        }

        labels = {
            'email_notifications': _("Notifications par email"),
            'push_notifications': _("Notifications push"),
            'desktop_notifications': _("Notifications bureau"),
            'allow_messages_from': _("Autoriser les messages de"),
            'auto_archive_conversations': _("Archiver automatiquement les conversations"),
            'archive_after_days': _("Archiver après (jours)"),
            'auto_delete_messages': _("Supprimer automatiquement les messages"),
            'delete_after_days': _("Supprimer après (jours)"),
            'show_online_status': _("Afficher le statut en ligne"),
            'show_read_receipts': _("Afficher les accusés de lecture"),
            'block_spam_messages': _("Bloquer les messages indésirables"),
            'filter_profanity': _("Filtrer les gros mots"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        settings = super().save(commit=False)

        if self.user:
            settings.user = self.user

        if commit:
            settings.save()

        return settings


class ReplyMessageForm(forms.ModelForm):
    """Formulaire pour répondre à un message"""

    class Meta:
        model = Message
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _("Votre réponse..."),
                'style': 'resize: none;'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx'
            })
        }

    def __init__(self, *args, **kwargs):
        self.parent_message = kwargs.pop('parent_message', None)
        self.conversation = kwargs.pop('conversation', None)
        self.sender = kwargs.pop('sender', None)
        self.recipient = kwargs.pop('recipient', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        message = super().save(commit=False)

        if self.parent_message:
            message.parent_message = self.parent_message

        if self.conversation:
            message.conversation = self.conversation

        if self.sender:
            message.sender = self.sender

        if self.recipient:
            message.recipient = self.recipient

        if message.attachment:
            message.attachment_name = message.attachment.name
            message.attachment_size = message.attachment.size

        if commit:
            message.save()

        return message


class ArchiveConversationForm(forms.Form):
    """Formulaire pour archiver une conversation"""

    confirm = forms.BooleanField(
        required=True,
        label=_("Confirmer l'archivage"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.conversation = kwargs.pop('conversation', None)
        super().__init__(*args, **kwargs)