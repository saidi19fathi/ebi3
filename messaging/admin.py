# ~/ebi3/messaging/admin.py
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect

from .models import (
    Conversation, Message, Notification,
    UserMessageSettings, BlockedUser,
    ConversationArchive, MessageReport
)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Administration des conversations"""

    list_display = (
        'uuid_short', 'conversation_type', 'subject_preview',
        'participants_count', 'is_active', 'is_blocked',
        'last_message_at', 'created_at'
    )

    list_filter = (
        'conversation_type', 'is_active', 'is_blocked',
        'is_archived', 'created_at'
    )

    search_fields = (
        'uuid', 'subject', 'participants__username',
        'participants__email', 'related_ad__title'
    )

    readonly_fields = (
        'uuid', 'created_at', 'updated_at',
        'last_message_at', 'blocked_at'
    )

    filter_horizontal = ('participants',)

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('uuid', 'conversation_type', 'subject')
        }),
        (_('Participants'), {
            'fields': ('participants',)
        }),
        (_('Liens'), {
            'fields': ('related_ad', 'related_carrier'),
            'classes': ('collapse',)
        }),
        (_('Statut'), {
            'fields': ('is_active', 'is_archived', 'is_blocked')
        }),
        (_('Bloquage'), {
            'fields': ('blocked_by', 'blocked_at'),
            'classes': ('collapse',)
        }),
        (_('Dates'), {
            'fields': ('last_message_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION : actions doit être une LISTE de noms de méthodes
    actions = [
        'activate_conversations', 'deactivate_conversations',
        'archive_conversations', 'unarchive_conversations',
        'block_conversations', 'unblock_conversations'
    ]

    def uuid_short(self, obj):
        return str(obj.uuid)[:8]
    uuid_short.short_description = _('UUID')
    uuid_short.admin_order_field = 'uuid'

    def subject_preview(self, obj):
        if obj.subject:
            return obj.subject[:50]
        participants = obj.participants.all()[:3]
        names = ", ".join([p.username for p in participants])
        if obj.participants.count() > 3:
            names += "..."
        return names
    subject_preview.short_description = _('Sujet/Participants')

    def participants_count(self, obj):
        return obj.participants.count()
    participants_count.short_description = _('Participants')

    # Les méthodes d'action doivent être séparées
    def activate_conversations(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _(f'{updated} conversations ont été activées.'))
    activate_conversations.short_description = _('Activer les conversations')

    def deactivate_conversations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _(f'{updated} conversations ont été désactivées.'))
    deactivate_conversations.short_description = _('Désactiver les conversations')

    def archive_conversations(self, request, queryset):
        updated = queryset.update(is_archived=True)
        self.message_user(request, _(f'{updated} conversations ont été archivées.'))
    archive_conversations.short_description = _('Archiver les conversations')

    def unarchive_conversations(self, request, queryset):
        updated = queryset.update(is_archived=False)
        self.message_user(request, _(f'{updated} conversations ont été désarchivées.'))
    unarchive_conversations.short_description = _('Désarchiver les conversations')

    def block_conversations(self, request, queryset):
        updated = queryset.update(
            is_blocked=True,
            blocked_by=request.user,
            blocked_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} conversations ont été bloquées.'))
    block_conversations.short_description = _('Bloquer les conversations')

    def unblock_conversations(self, request, queryset):
        updated = queryset.update(
            is_blocked=False,
            blocked_by=None,
            blocked_at=None
        )
        self.message_user(request, _(f'{updated} conversations ont été débloquées.'))
    unblock_conversations.short_description = _('Débloquer les conversations')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('participants')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Administration des messages"""

    list_display = (
        'uuid_short', 'conversation_link', 'sender_username',
        'recipient_username', 'content_preview', 'is_read',
        'is_deleted', 'sent_at'
    )

    list_filter = (
        'is_read', 'is_deleted', 'sent_at',
        'conversation__conversation_type'
    )

    search_fields = (
        'uuid', 'content', 'sender__username',
        'recipient__username', 'conversation__subject'
    )

    readonly_fields = (
        'uuid', 'sent_at', 'updated_at',
        'read_at', 'deleted_at'
    )

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('uuid', 'conversation', 'sender', 'recipient')
        }),
        (_('Contenu'), {
            'fields': ('content', 'parent_message')
        }),
        (_('Pièces jointes'), {
            'fields': ('attachment', 'attachment_name', 'attachment_size'),
            'classes': ('collapse',)
        }),
        (_('Statut'), {
            'fields': ('is_read', 'read_at', 'is_deleted', 'deleted_by', 'deleted_at')
        }),
        (_('Dates'), {
            'fields': ('sent_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ actions doit être une liste
    actions = ['mark_as_read', 'mark_as_unread', 'soft_delete_messages', 'restore_messages']

    def uuid_short(self, obj):
        return str(obj.uuid)[:8]
    uuid_short.short_description = _('UUID')

    def conversation_link(self, obj):
        url = reverse('admin:messaging_conversation_change', args=[obj.conversation.id])
        return format_html('<a href="{}">{}</a>', url, obj.conversation.uuid_short())
    conversation_link.short_description = _('Conversation')
    conversation_link.admin_order_field = 'conversation'

    def sender_username(self, obj):
        return obj.sender.username
    sender_username.short_description = _('Expéditeur')
    sender_username.admin_order_field = 'sender__username'

    def recipient_username(self, obj):
        return obj.recipient.username
    recipient_username.short_description = _('Destinataire')
    recipient_username.admin_order_field = 'recipient__username'

    def content_preview(self, obj):
        return obj.content[:100] + ('...' if len(obj.content) > 100 else '')
    content_preview.short_description = _('Contenu')

    # Actions
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, _(f'{updated} messages ont été marqués comme lus.'))
    mark_as_read.short_description = _('Marquer comme lu')

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None)
        self.message_user(request, _(f'{updated} messages ont été marqués comme non lus.'))
    mark_as_unread.short_description = _('Marquer comme non lu')

    def soft_delete_messages(self, request, queryset):
        for message in queryset:
            message.soft_delete(request.user)
        self.message_user(request, _(f'{queryset.count()} messages ont été supprimés.'))
    soft_delete_messages.short_description = _('Supprimer (soft delete)')

    def restore_messages(self, request, queryset):
        updated = queryset.update(
            is_deleted=False,
            deleted_by=None,
            deleted_at=None
        )
        self.message_user(request, _(f'{updated} messages ont été restaurés.'))
    restore_messages.short_description = _('Restaurer')

    def has_add_permission(self, request):
        # Empêcher l'ajout manuel de messages via l'admin
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'conversation', 'sender', 'recipient', 'deleted_by'
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Administration des notifications"""

    list_display = (
        'user_username', 'notification_type', 'title_preview',
        'is_read', 'is_important', 'created_at'
    )

    list_filter = (
        'notification_type', 'is_read', 'is_important',
        'created_at'
    )

    search_fields = (
        'user__username', 'title', 'message',
        'related_conversation__subject'
    )

    readonly_fields = ('created_at',)

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        (_('Liens'), {
            'fields': ('related_conversation', 'related_message', 'related_ad'),
            'classes': ('collapse',)
        }),
        (_('Statut'), {
            'fields': ('is_read', 'is_important')
        }),
        (_('Action'), {
            'fields': ('action_url', 'action_text', 'expires_at')
        }),
        (_('Dates'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # ✅ actions doit être une liste
    actions = ['mark_as_read', 'mark_as_unread', 'mark_as_important', 'mark_as_unimportant']

    def user_username(self, obj):
        return obj.user.username
    user_username.short_description = _('Utilisateur')
    user_username.admin_order_field = 'user__username'

    def title_preview(self, obj):
        return obj.title[:50] + ('...' if len(obj.title) > 50 else '')
    title_preview.short_description = _('Titre')

    # Actions
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, _(f'{updated} notifications ont été marquées comme lues.'))
    mark_as_read.short_description = _('Marquer comme lu')

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, _(f'{updated} notifications ont été marquées comme non lues.'))
    mark_as_unread.short_description = _('Marquer comme non lu')

    def mark_as_important(self, request, queryset):
        updated = queryset.update(is_important=True)
        self.message_user(request, _(f'{updated} notifications ont été marquées comme importantes.'))
    mark_as_important.short_description = _('Marquer comme important')

    def mark_as_unimportant(self, request, queryset):
        updated = queryset.update(is_important=False)
        self.message_user(request, _(f'{updated} notifications ont été marquées comme non importantes.'))
    mark_as_unimportant.short_description = _('Marquer comme non important')

    def has_add_permission(self, request):
        # Permettre l'ajout manuel pour le support
        return request.user.is_superuser

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserMessageSettings)
class UserMessageSettingsAdmin(admin.ModelAdmin):
    """Administration des paramètres de messagerie"""

    list_display = (
        'user_username', 'email_notifications',
        'allow_messages_from', 'show_online_status',
        'updated_at'
    )

    list_filter = (
        'email_notifications', 'push_notifications',
        'desktop_notifications', 'allow_messages_from',
        'show_online_status'
    )

    search_fields = ('user__username', 'user__email')

    readonly_fields = ('updated_at',)

    fieldsets = (
        (_('Notifications'), {
            'fields': (
                'email_notifications', 'push_notifications',
                'desktop_notifications'
            )
        }),
        (_('Confidentialité'), {
            'fields': ('allow_messages_from',)
        }),
        (_('Gestion automatique'), {
            'fields': (
                'auto_archive_conversations', 'archive_after_days',
                'auto_delete_messages', 'delete_after_days'
            )
        }),
        (_('Apparence'), {
            'fields': ('show_online_status', 'show_read_receipts')
        }),
        (_('Sécurité'), {
            'fields': ('block_spam_messages', 'filter_profanity')
        }),
        (_('Métadonnées'), {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    # ✅ actions doit être une liste (vide si pas d'actions)
    actions = []

    def user_username(self, obj):
        return obj.user.username
    user_username.short_description = _('Utilisateur')
    user_username.admin_order_field = 'user__username'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    """Administration des utilisateurs bloqués"""

    list_display = (
        'blocker_username', 'blocked_username',
        'reason_preview', 'created_at'
    )

    list_filter = ('created_at',)

    search_fields = (
        'blocker__username', 'blocked__username',
        'reason'
    )

    readonly_fields = ('created_at',)

    fieldsets = (
        (_('Utilisateurs'), {
            'fields': ('blocker', 'blocked')
        }),
        (_('Raison'), {
            'fields': ('reason',)
        }),
        (_('Dates'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # ✅ actions doit être une liste
    actions = ['unblock_users']

    def blocker_username(self, obj):
        return obj.blocker.username
    blocker_username.short_description = _('Bloqueur')
    blocker_username.admin_order_field = 'blocker__username'

    def blocked_username(self, obj):
        return obj.blocked.username
    blocked_username.short_description = _('Bloqué')
    blocked_username.admin_order_field = 'blocked__username'

    def reason_preview(self, obj):
        return obj.reason[:50] if obj.reason else '-'
    reason_preview.short_description = _('Raison')

    # Actions
    def unblock_users(self, request, queryset):
        deleted_count, _ = queryset.delete()
        self.message_user(request, _(f'{deleted_count} blocages ont été supprimés.'))
    unblock_users.short_description = _('Débloquer les utilisateurs')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('blocker', 'blocked')


@admin.register(ConversationArchive)
class ConversationArchiveAdmin(admin.ModelAdmin):
    """Administration des archives de conversations"""

    list_display = (
        'user_username', 'conversation_subject',
        'archived_at'
    )

    list_filter = ('archived_at',)

    search_fields = (
        'user__username', 'conversation__subject',
        'conversation__uuid'
    )

    readonly_fields = ('archived_at',)

    # ✅ actions doit être une liste
    actions = ['unarchive_conversations']

    def user_username(self, obj):
        return obj.user.username
    user_username.short_description = _('Utilisateur')
    user_username.admin_order_field = 'user__username'

    def conversation_subject(self, obj):
        return obj.conversation.subject[:50] if obj.conversation.subject else str(obj.conversation.uuid)[:8]
    conversation_subject.short_description = _('Conversation')
    conversation_subject.admin_order_field = 'conversation__subject'

    # Actions
    def unarchive_conversations(self, request, queryset):
        deleted_count, _ = queryset.delete()
        self.message_user(request, _(f'{deleted_count} archives ont été supprimées.'))
    unarchive_conversations.short_description = _('Désarchiver')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'conversation')


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    """Administration des signalements de messages"""

    list_display = (
        'reporter_username', 'message_preview',
        'reason', 'status', 'created_at'
    )

    list_filter = ('reason', 'status', 'created_at')

    search_fields = (
        'reporter__username', 'message__content',
        'description', 'admin_notes'
    )

    readonly_fields = ('created_at', 'resolved_at')

    list_editable = ('status',)

    fieldsets = (
        (_('Signalement'), {
            'fields': ('reporter', 'message', 'reason', 'description', 'evidence')
        }),
        (_('Traitement'), {
            'fields': ('status', 'admin_notes', 'resolved_by', 'resolved_at')
        }),
        (_('Dates'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # ✅ actions doit être une liste
    actions = ['mark_as_resolved', 'mark_as_dismissed']

    def reporter_username(self, obj):
        return obj.reporter.username
    reporter_username.short_description = _('Signaleur')
    reporter_username.admin_order_field = 'reporter__username'

    def message_preview(self, obj):
        return obj.message.content[:100] if obj.message.content else '-'
    message_preview.short_description = _('Message')

    # Actions
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(
            status='RESOLVED',
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} signalements ont été résolus.'))
    mark_as_resolved.short_description = _('Marquer comme résolu')

    def mark_as_dismissed(self, request, queryset):
        updated = queryset.update(
            status='DISMISSED',
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} signalements ont été rejetés.'))
    mark_as_dismissed.short_description = _('Marquer comme rejeté')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'reporter', 'message', 'message__sender',
            'message__recipient', 'resolved_by'
        )