# ~/ebi3/messaging/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
import uuid


class Conversation(models.Model):
    """Modèle pour une conversation entre utilisateurs"""

    class ConversationType(models.TextChoices):
        PRIVATE = 'PRIVATE', _('Privé')
        GROUP = 'GROUP', _('Groupe')
        AD_RELATED = 'AD_RELATED', _('Lié à une annonce')
        CARRIER_RELATED = 'CARRIER_RELATED', _('Lié à un transporteur')
        SUPPORT = 'SUPPORT', _('Support')

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("UUID")
    )

    conversation_type = models.CharField(
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.PRIVATE,
        verbose_name=_("Type de conversation")
    )

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
        verbose_name=_("Participants")
    )

    subject = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Sujet")
    )

    # Liens vers d'autres modèles
    related_ad = models.ForeignKey(
        'ads.Ad',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name=_("Annonce liée")
    )

    related_carrier = models.ForeignKey(
        'carriers.Carrier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name=_("Transporteur lié")
    )

    # Métadonnées
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    is_archived = models.BooleanField(
        default=False,
        verbose_name=_("Archivée")
    )

    is_blocked = models.BooleanField(
        default=False,
        verbose_name=_("Bloquée")
    )

    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blocked_conversations',
        verbose_name=_("Bloquée par")
    )

    blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Bloquée le")
    )

    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dernier message le")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['conversation_type', 'is_active']),
            models.Index(fields=['last_message_at']),
        ]

    def __str__(self):
        if self.subject:
            return f"{self.subject} ({self.get_conversation_type_display()})"
        participants = self.participants.all()[:3]
        names = ", ".join([p.username for p in participants])
        if self.participants.count() > 3:
            names += f" + {self.participants.count() - 3} autres"
        return names

    def get_absolute_url(self):
        return reverse('messaging:conversation_detail', kwargs={'uuid': self.uuid})

    def get_participants_except(self, user):
        """Obtenir tous les participants sauf l'utilisateur spécifié"""
        return self.participants.exclude(id=user.id)

    def get_other_participant(self, user):
        """Obtenir l'autre participant (pour les conversations à 2)"""
        if self.participants.count() == 2:
            return self.participants.exclude(id=user.id).first()
        return None

    def update_last_message_time(self):
        """Mettre à jour le temps du dernier message"""
        last_message = self.messages.filter(is_deleted=False).last()
        if last_message:
            self.last_message_at = last_message.sent_at
            self.save(update_fields=['last_message_at'])

    def mark_as_read_for_user(self, user):
        """Marquer tous les messages non lus comme lus pour un utilisateur"""
        self.messages.filter(
            is_read=False,
            recipient=user
        ).update(is_read=True, read_at=timezone.now())

    def get_unread_count_for_user(self, user):
        """Obtenir le nombre de messages non lus pour un utilisateur"""
        return self.messages.filter(
            recipient=user,
            is_read=False,
            is_deleted=False
        ).count()

    def can_user_access(self, user):
        """Vérifier si un utilisateur peut accéder à la conversation"""
        if not self.is_active or self.is_blocked:
            return False
        return self.participants.filter(id=user.id).exists()

    @classmethod
    def get_or_create_conversation(cls, user1, user2, **kwargs):
        """Obtenir ou créer une conversation entre deux utilisateurs"""
        # Rechercher une conversation existante
        conversations = cls.objects.filter(
            participants=user1
        ).filter(
            participants=user2
        ).filter(
            conversation_type=cls.ConversationType.PRIVATE
        ).filter(
            is_active=True,
            is_blocked=False
        )

        if conversations.exists():
            return conversations.first()

        # Créer une nouvelle conversation
        conversation = cls.objects.create(
            conversation_type=cls.ConversationType.PRIVATE,
            **kwargs
        )
        conversation.participants.add(user1, user2)
        return conversation


    def get_other_participant(self, user):
        """Obtenir l'autre participant (pour les conversations à 2)"""
        try:
            if self.participants.count() == 2:
                return self.participants.exclude(id=user.id).first()
        except Exception:
            pass
        return None

    def get_participants_except(self, user):
        """Obtenir tous les participants sauf l'utilisateur spécifié"""
        try:
            return self.participants.exclude(id=user.id)
        except Exception:
            return self.participants.none()


class Message(models.Model):
    """Modèle pour un message dans une conversation"""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("UUID")
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("Conversation")
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_("Expéditeur")
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name=_("Destinataire")
    )

    content = models.TextField(
        verbose_name=_("Contenu"),
        help_text=_("Contenu du message")
    )

    # Métadonnées du message
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Lu")
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Lu le")
    )

    is_deleted = models.BooleanField(
        default=False,
        verbose_name=_("Supprimé")
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Supprimé le")
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_messages',
        verbose_name=_("Supprimé par")
    )

    # Fichiers joints
    attachment = models.FileField(
        upload_to='messaging/attachments/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Pièce jointe")
    )

    attachment_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Nom du fichier")
    )

    attachment_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Taille du fichier (octets)")
    )

    # Références
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_("Message parent")
    )

    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['conversation', 'sent_at']),
            models.Index(fields=['sender', 'sent_at']),
            models.Index(fields=['recipient', 'is_read', 'sent_at']),
            models.Index(fields=['is_deleted', 'sent_at']),
        ]

    def __str__(self):
        return f"Message de {self.sender.username} à {self.recipient.username}"

    def save(self, *args, **kwargs):
        # Mettre à jour le temps du dernier message dans la conversation
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            self.conversation.update_last_message_time()

    def mark_as_read(self):
        """Marquer le message comme lu"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def soft_delete(self, user):
        """Supprimer doucement le message"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def can_user_access(self, user):
        """Vérifier si un utilisateur peut accéder au message"""
        if self.is_deleted and user != self.deleted_by:
            return False
        return user in [self.sender, self.recipient]


class Notification(models.Model):
    """Modèle pour les notifications"""

    class NotificationType(models.TextChoices):
        MESSAGE_RECEIVED = 'MESSAGE_RECEIVED', _('Message reçu')
        MESSAGE_READ = 'MESSAGE_READ', _('Message lu')
        CONVERSATION_NEW = 'CONVERSATION_NEW', _('Nouvelle conversation')
        CONVERSATION_ARCHIVED = 'CONVERSATION_ARCHIVED', _('Conversation archivée')
        SYSTEM = 'SYSTEM', _('Système')
        AD_RELATED = 'AD_RELATED', _('Lié à une annonce')
        CARRIER_RELATED = 'CARRIER_RELATED', _('Lié à un transporteur')
        PAYMENT = 'PAYMENT', _('Paiement')
        SECURITY = 'SECURITY', _('Sécurité')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_("Utilisateur")
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        verbose_name=_("Type de notification")
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre")
    )

    message = models.TextField(
        verbose_name=_("Message")
    )

    # Liens
    related_conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name=_("Conversation liée")
    )

    related_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name=_("Message lié")
    )

    related_ad = models.ForeignKey(
        'ads.Ad',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name=_("Annonce liée")
    )

    # Métadonnées
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Lue")
    )

    is_important = models.BooleanField(
        default=False,
        verbose_name=_("Importante")
    )

    action_url = models.URLField(
        blank=True,
        verbose_name=_("URL d'action")
    )

    action_text = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Texte de l'action")
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expire le")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]

    def __str__(self):
        return f"Notification pour {self.user.username}: {self.title}"

    def mark_as_read(self):
        """Marquer la notification comme lue"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

    def is_expired(self):
        """Vérifier si la notification est expirée"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class UserMessageSettings(models.Model):
    """Paramètres de messagerie pour chaque utilisateur"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_settings',
        verbose_name=_("Utilisateur")
    )

    # Notifications
    email_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Notifications par email")
    )

    push_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Notifications push")
    )

    desktop_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Notifications bureau")
    )

    # Privacy
    allow_messages_from = models.CharField(
        max_length=20,
        choices=[
            ('EVERYONE', _('Tout le monde')),
            ('CONTACTS', _('Contacts uniquement')),
            ('NOBODY', _('Personne')),
        ],
        default='EVERYONE',
        verbose_name=_("Autoriser les messages de")
    )

    auto_archive_conversations = models.BooleanField(
        default=False,
        verbose_name=_("Archiver automatiquement les conversations")
    )

    archive_after_days = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Archiver après (jours)")
    )

    auto_delete_messages = models.BooleanField(
        default=False,
        verbose_name=_("Supprimer automatiquement les messages")
    )

    delete_after_days = models.PositiveIntegerField(
        default=365,
        verbose_name=_("Supprimer après (jours)")
    )

    # Appearance
    show_online_status = models.BooleanField(
        default=True,
        verbose_name=_("Afficher le statut en ligne")
    )

    show_read_receipts = models.BooleanField(
        default=True,
        verbose_name=_("Afficher les accusés de lecture")
    )

    # Security
    block_spam_messages = models.BooleanField(
        default=True,
        verbose_name=_("Bloquer les messages indésirables")
    )

    filter_profanity = models.BooleanField(
        default=True,
        verbose_name=_("Filtrer les gros mots")
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Paramètres de messagerie")
        verbose_name_plural = _("Paramètres de messagerie")

    def __str__(self):
        return f"Paramètres de messagerie pour {self.user.username}"


class BlockedUser(models.Model):
    """Utilisateurs bloqués"""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_users',
        verbose_name=_("Bloqueur")
    )

    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_by',
        verbose_name=_("Bloqué")
    )

    reason = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Raison")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Utilisateur bloqué")
        verbose_name_plural = _("Utilisateurs bloqués")
        unique_together = ['blocker', 'blocked']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.blocker.username} a bloqué {self.blocked.username}"


class ConversationArchive(models.Model):
    """Archive des conversations"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='archived_conversations',
        verbose_name=_("Utilisateur")
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='archives',
        verbose_name=_("Conversation")
    )

    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Archive de conversation")
        verbose_name_plural = _("Archives de conversations")
        unique_together = ['user', 'conversation']
        ordering = ['-archived_at']

    def __str__(self):
        return f"Archive: {self.conversation} par {self.user.username}"


class MessageReport(models.Model):
    """Signalements de messages"""

    class ReportReason(models.TextChoices):
        SPAM = 'SPAM', _('Spam')
        HARASSMENT = 'HARASSMENT', _('Harcèlement')
        INAPPROPRIATE = 'INAPPROPRIATE', _('Contenu inapproprié')
        SCAM = 'SCAM', _('Arnaque')
        THREAT = 'THREAT', _('Menace')
        OTHER = 'OTHER', _('Autre')

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reports',
        verbose_name=_("Signaleur")
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_("Message")
    )

    reason = models.CharField(
        max_length=20,
        choices=ReportReason.choices,
        verbose_name=_("Raison")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    evidence = models.FileField(
        upload_to='messaging/reports/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Preuve")
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', _('En attente')),
            ('UNDER_REVIEW', _('En examen')),
            ('RESOLVED', _('Résolu')),
            ('DISMISSED', _('Rejeté')),
        ],
        default='PENDING',
        verbose_name=_("Statut")
    )

    admin_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de l'administrateur")
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Résolu le")
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_message_reports',
        verbose_name=_("Résolu par")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Signalement de message")
        verbose_name_plural = _("Signalements de messages")
        ordering = ['-created_at']

    def __str__(self):
        return f"Signalement de {self.reporter.username} sur le message {self.message.id}"