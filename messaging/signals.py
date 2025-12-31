# ~/ebi3/messaging/signals.py
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from .models import (
    Conversation, Message, Notification,
    UserMessageSettings, BlockedUser,
    ConversationArchive, MessageReport
)

@receiver(post_save, sender=Message)
def create_notification_on_new_message(sender, instance, created, **kwargs):
    """Créer une notification lors d'un nouveau message"""
    if created:
        # Créer une notification pour le destinataire
        Notification.objects.create(
            user=instance.recipient,
            notification_type=Notification.NotificationType.MESSAGE_RECEIVED,
            title=_("Nouveau message"),
            message=_("Vous avez reçu un nouveau message de {}").format(
                instance.sender.username
            ),
            related_conversation=instance.conversation,
            related_message=instance,
            action_url=instance.conversation.get_absolute_url()
        )

        # Invalider le cache du nombre de messages non lus
        cache_key = f"unread_messages_count_{instance.recipient.id}"
        cache.delete(cache_key)

@receiver(post_save, sender=Message)
def update_conversation_last_message(sender, instance, created, **kwargs):
    """Mettre à jour le dernier message de la conversation"""
    if created:
        instance.conversation.last_message_at = instance.sent_at
        instance.conversation.save(update_fields=['last_message_at'])

@receiver(post_save, sender=Conversation)
def create_default_settings(sender, instance, created, **kwargs):
    """Créer des paramètres par défaut pour les nouveaux utilisateurs"""
    if created:
        # Cette logique serait dans le signal de création d'utilisateur
        pass

@receiver(post_save, sender=BlockedUser)
def block_conversations_on_user_block(sender, instance, created, **kwargs):
    """Bloquer les conversations existantes lors du blocage d'un utilisateur"""
    if created:
        # Trouver toutes les conversations entre ces deux utilisateurs
        conversations = Conversation.objects.filter(
            participants=instance.blocker
        ).filter(
            participants=instance.blocked
        ).filter(
            is_active=True,
            is_blocked=False
        )

        for conversation in conversations:
            conversation.is_blocked = True
            conversation.blocked_by = instance.blocker
            conversation.blocked_at = timezone.now()
            conversation.save(update_fields=['is_blocked', 'blocked_by', 'blocked_at'])

@receiver(post_delete, sender=BlockedUser)
def unblock_conversations_on_user_unblock(sender, instance, **kwargs):
    """Débloquer les conversations lors du déblocage d'un utilisateur"""
    # Débloquer les conversations entre ces deux utilisateurs
    conversations = Conversation.objects.filter(
        participants=instance.blocker
    ).filter(
        participants=instance.blocked
    ).filter(
        is_blocked=True,
        blocked_by=instance.blocker
    )

    for conversation in conversations:
        conversation.is_blocked = False
        conversation.blocked_by = None
        conversation.blocked_at = None
        conversation.save(update_fields=['is_blocked', 'blocked_by', 'blocked_at'])

@receiver(pre_save, sender=Notification)
def set_expiration_date(sender, instance, **kwargs):
    """Définir une date d'expiration pour les notifications"""
    if not instance.expires_at:
        # Par défaut, les notifications expirent après 30 jours
        instance.expires_at = timezone.now() + timezone.timedelta(days=30)

@receiver(post_save, sender=MessageReport)
def notify_admin_on_message_report(sender, instance, created, **kwargs):
    """Notifier les administrateurs lors d'un signalement de message"""
    if created and instance.status == 'PENDING':
        from django.contrib.auth.models import User

        # Notifier les administrateurs
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                notification_type=Notification.NotificationType.SYSTEM,
                title=_("Nouveau signalement de message"),
                message=_("Un message a été signalé par {}").format(
                    instance.reporter.username
                ),
                action_url=f"/admin/messaging/messagereport/{instance.id}/change/",
                is_important=True
            )

@receiver(post_save, sender=ConversationArchive)
def archive_conversation_for_user(sender, instance, created, **kwargs):
    """Archiver la conversation pour l'utilisateur spécifique"""
    if created:
        # Marquer la conversation comme archivée pour cet utilisateur
        # (Cette logique peut être étendue pour gérer l'archivage multiple)
        pass

@receiver(post_delete, sender=ConversationArchive)
def unarchive_conversation_for_user(sender, instance, **kwargs):
    """Désarchiver la conversation pour l'utilisateur"""
    # (Cette logique peut être étendue pour gérer le désarchivage)
    pass

@receiver(pre_save, sender=Message)
def check_message_block_status(sender, instance, **kwargs):
    """Vérifier si l'expéditeur est bloqué par le destinataire"""
    if instance.pk is None:  # Nouveau message seulement
        if BlockedUser.objects.filter(
            blocker=instance.recipient,
            blocked=instance.sender
        ).exists():
            # L'expéditeur est bloqué par le destinataire
            # On peut soit empêcher l'envoi, soit marquer le message comme bloqué
            instance.is_deleted = True
            instance.deleted_by = instance.recipient
            instance.deleted_at = timezone.now()

# CORRECTION : Utiliser une importation différée pour éviter les import circulaires
@receiver(post_save)
def create_user_message_settings(sender, instance, created, **kwargs):
    """Créer des paramètres de messagerie par défaut pour les nouveaux utilisateurs"""
    # Vérifier si c'est le modèle User
    if sender.__name__ == 'User' and created:
        # Utiliser une importation locale pour éviter les problèmes circulaires
        from .models import UserMessageSettings
        UserMessageSettings.objects.get_or_create(user=instance)

# Alternative : Déplacer ce signal dans apps.py pour un meilleur contrôle