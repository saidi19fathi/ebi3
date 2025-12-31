# ~/ebi3/messaging/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView,
    UpdateView, DeleteView, TemplateView, View
)
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
import json

from .models import (
    Conversation, Message, Notification,
    UserMessageSettings, BlockedUser,
    ConversationArchive, MessageReport
)
from .forms import (
    NewConversationForm, MessageForm,
    ConversationSearchForm, MessageReportForm,
    BlockUserForm, UserMessageSettingsForm,
    ReplyMessageForm, ArchiveConversationForm
)
from users.models import User


class InboxView(LoginRequiredMixin, ListView):
    """Vue de la boîte de réception"""
    model = Conversation
    template_name = 'messaging/inbox.html'
    context_object_name = 'conversations'
    paginate_by = 20

    def get_queryset(self):
        # Récupérer les conversations où l'utilisateur est participant
        queryset = Conversation.objects.filter(
            participants=self.request.user,
            is_active=True,
            is_blocked=False
        ).annotate(
            unread_count=Count('messages', filter=Q(
                messages__recipient=self.request.user,
                messages__is_read=False,
                messages__is_deleted=False
            )),
            last_message_time=Max('messages__sent_at')
        ).order_by('-last_message_time', '-created_at')

        # Filtrer par recherche
        form = ConversationSearchForm(self.request.GET)
        if form.is_valid():
            search_term = form.cleaned_data.get('q')
            if search_term:
                queryset = queryset.filter(
                    Q(subject__icontains=search_term) |
                    Q(messages__content__icontains=search_term) |
                    Q(participants__username__icontains=search_term)
                ).distinct()

            conversation_type = form.cleaned_data.get('conversation_type')
            if conversation_type:
                queryset = queryset.filter(conversation_type=conversation_type)

            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            if date_from:
                queryset = queryset.filter(messages__sent_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(messages__sent_at__lte=date_to)

            has_attachment = form.cleaned_data.get('has_attachment')
            if has_attachment == 'yes':
                queryset = queryset.filter(messages__attachment__isnull=False).distinct()
            elif has_attachment == 'no':
                queryset = queryset.filter(messages__attachment__isnull=True).distinct()

            is_read = form.cleaned_data.get('is_read')
            if is_read == 'read':
                queryset = queryset.filter(
                    messages__recipient=self.request.user,
                    messages__is_read=True
                ).distinct()
            elif is_read == 'unread':
                queryset = queryset.filter(
                    messages__recipient=self.request.user,
                    messages__is_read=False
                ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ConversationSearchForm(self.request.GET)

        # Statistiques
        context['total_conversations'] = self.get_queryset().count()
        context['unread_messages_count'] = Message.objects.filter(
            recipient=self.request.user,
            is_read=False,
            is_deleted=False
        ).count()

        # Conversations archivées
        context['archived_conversations_count'] = ConversationArchive.objects.filter(
            user=self.request.user
        ).count()

        return context


class ConversationDetailView(LoginRequiredMixin, DetailView):
    """Vue de détail d'une conversation"""
    model = Conversation
    template_name = 'messaging/conversation_detail.html'
    context_object_name = 'conversation'

    def get_object(self):
        # Récupérer la conversation par UUID
        uuid = self.kwargs.get('uuid')
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            uuid=uuid
        )

        # Vérifier les permissions
        if not conversation.can_user_access(self.request.user):
            raise HttpResponseForbidden(_("Vous n'avez pas accès à cette conversation."))

        return conversation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.object

        # Marquer tous les messages comme lus
        conversation.mark_as_read_for_user(self.request.user)

        # Récupérer les messages
        messages = conversation.messages.filter(
            is_deleted=False
        ).select_related('sender', 'recipient', 'parent_message').order_by('sent_at')

        # Pagination
        paginator = Paginator(messages, 50)
        page = self.request.GET.get('page')
        messages_page = paginator.get_page(page)

        # Formulaire de réponse
        context['message_form'] = MessageForm(
            conversation=conversation,
            sender=self.request.user,
            recipient=conversation.get_other_participant(self.request.user)
        )

        # Informations supplémentaires
        context['messages'] = messages_page
        context['other_participant'] = conversation.get_other_participant(self.request.user)
        context['is_blocked'] = BlockedUser.objects.filter(
            blocker=self.request.user,
            blocked=context['other_participant']
        ).exists() if context['other_participant'] else False

        # Vérifier si l'utilisateur peut envoyer des messages
        if context['other_participant']:
            try:
                recipient_settings = context['other_participant'].message_settings
                context['can_send_message'] = recipient_settings.allow_messages_from != 'NOBODY'
            except UserMessageSettings.DoesNotExist:
                context['can_send_message'] = True
        else:
            context['can_send_message'] = True

        return context


class NewConversationView(LoginRequiredMixin, CreateView):
    """Vue pour démarrer une nouvelle conversation"""
    template_name = 'messaging/new_conversation.html'
    form_class = NewConversationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        recipient = form.cleaned_data['recipient']
        subject = form.cleaned_data.get('subject', '')
        message_content = form.cleaned_data['message']

        with transaction.atomic():
            # Obtenir ou créer la conversation
            conversation = Conversation.get_or_create_conversation(
                self.request.user,
                recipient,
                subject=subject
            )

            # Créer le premier message
            Message.objects.create(
                conversation=conversation,
                sender=self.request.user,
                recipient=recipient,
                content=message_content
            )

        messages.success(self.request, _("Message envoyé avec succès !"))
        return redirect('messaging:conversation_detail', uuid=conversation.uuid)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Nouvelle conversation")
        return context


class NewConversationWithUserView(LoginRequiredMixin, View):
    """Vue pour démarrer une conversation avec un utilisateur spécifique"""

    def get(self, request, username):
        recipient = get_object_or_404(User, username=username)

        # Vérifier si l'utilisateur n'est pas bloqué
        if BlockedUser.objects.filter(blocker=request.user, blocked=recipient).exists():
            messages.error(request, _("Vous avez bloqué cet utilisateur."))
            return redirect('messaging:inbox')

        # Vérifier les paramètres de confidentialité
        try:
            recipient_settings = recipient.message_settings
            if recipient_settings.allow_messages_from == 'NOBODY':
                messages.error(request, _("Cet utilisateur n'accepte pas de messages."))
                return redirect('messaging:inbox')
        except UserMessageSettings.DoesNotExist:
            pass

        # Vérifier s'il existe déjà une conversation
        existing_conversation = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=recipient
        ).filter(
            conversation_type=Conversation.ConversationType.PRIVATE,
            is_active=True,
            is_blocked=False
        ).first()

        if existing_conversation:
            return redirect('messaging:conversation_detail', uuid=existing_conversation.uuid)

        # Créer une nouvelle conversation
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(request.user, recipient)

        return redirect('messaging:conversation_detail', uuid=conversation.uuid)


class SendMessageView(LoginRequiredMixin, View):
    """Vue pour envoyer un message dans une conversation"""

    def post(self, request, uuid):
        conversation = get_object_or_404(Conversation, uuid=uuid)

        # Vérifier les permissions
        if not conversation.can_user_access(request.user):
            return JsonResponse({'error': _("Accès refusé.")}, status=403)

        # Vérifier si la conversation est bloquée
        if conversation.is_blocked:
            return JsonResponse({'error': _("Cette conversation est bloquée.")}, status=400)

        # Récupérer le destinataire
        other_participant = conversation.get_other_participant(request.user)
        if not other_participant:
            return JsonResponse({'error': _("Destinataire non trouvé.")}, status=400)

        # Vérifier si l'utilisateur n'est pas bloqué
        if BlockedUser.objects.filter(blocker=other_participant, blocked=request.user).exists():
            return JsonResponse({'error': _("Vous êtes bloqué par cet utilisateur.")}, status=400)

        # Vérifier les paramètres de confidentialité
        try:
            recipient_settings = other_participant.message_settings
            if recipient_settings.allow_messages_from == 'NOBODY':
                return JsonResponse({'error': _("Cet utilisateur n'accepte pas de messages.")}, status=400)
        except UserMessageSettings.DoesNotExist:
            pass

        form = MessageForm(
            request.POST,
            request.FILES,
            conversation=conversation,
            sender=request.user,
            recipient=other_participant
        )

        if form.is_valid():
            message = form.save()

            # Réponse pour AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message_id': message.id,
                    'content': message.content,
                    'sent_at': message.sent_at.strftime('%H:%M'),
                    'sender': message.sender.username
                })

            messages.success(request, _("Message envoyé avec succès !"))
            return redirect('messaging:conversation_detail', uuid=conversation.uuid)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': form.errors.as_json()
                }, status=400)

            messages.error(request, _("Erreur lors de l'envoi du message."))
            return redirect('messaging:conversation_detail', uuid=conversation.uuid)


class ArchiveConversationView(LoginRequiredMixin, View):
    """Vue pour archiver une conversation"""

    def post(self, request, uuid):
        conversation = get_object_or_404(Conversation, uuid=uuid)

        # Vérifier les permissions
        if not conversation.can_user_access(request.user):
            messages.error(request, _("Accès refusé."))
            return redirect('messaging:inbox')

        form = ArchiveConversationForm(
            request.POST,
            user=request.user,
            conversation=conversation
        )

        if form.is_valid():
            # Créer une archive
            ConversationArchive.objects.get_or_create(
                user=request.user,
                conversation=conversation
            )

            messages.success(request, _("Conversation archivée avec succès."))
        else:
            messages.error(request, _("Erreur lors de l'archivage."))

        return redirect('messaging:inbox')


class UnarchiveConversationView(LoginRequiredMixin, View):
    """Vue pour désarchiver une conversation"""

    def post(self, request, uuid):
        conversation = get_object_or_404(Conversation, uuid=uuid)

        # Supprimer l'archive
        ConversationArchive.objects.filter(
            user=request.user,
            conversation=conversation
        ).delete()

        messages.success(request, _("Conversation désarchivée avec succès."))
        return redirect('messaging:inbox')


class DeleteConversationView(LoginRequiredMixin, View):
    """Vue pour supprimer une conversation"""

    def post(self, request, uuid):
        conversation = get_object_or_404(Conversation, uuid=uuid)

        # Vérifier les permissions
        if not conversation.can_user_access(request.user):
            messages.error(request, _("Accès refusé."))
            return redirect('messaging:inbox')

        # Supprimer tous les messages de l'utilisateur dans cette conversation
        Message.objects.filter(
            conversation=conversation,
            recipient=request.user
        ).update(
            is_deleted=True,
            deleted_by=request.user,
            deleted_at=timezone.now()
        )

        # Si l'utilisateur est expéditeur, supprimer aussi ses messages envoyés
        Message.objects.filter(
            conversation=conversation,
            sender=request.user
        ).update(
            is_deleted=True,
            deleted_by=request.user,
            deleted_at=timezone.now()
        )

        messages.success(request, _("Conversation supprimée avec succès."))
        return redirect('messaging:inbox')


class MarkMessageAsReadView(LoginRequiredMixin, View):
    """Vue pour marquer un message comme lu"""

    def post(self, request, message_uuid):
        message = get_object_or_404(Message, uuid=message_uuid)

        # Vérifier les permissions
        if message.recipient != request.user:
            return JsonResponse({'error': _("Accès refusé.")}, status=403)

        message.mark_as_read()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('messaging:conversation_detail', uuid=message.conversation.uuid)


class DeleteMessageView(LoginRequiredMixin, View):
    """Vue pour supprimer un message"""

    def post(self, request, message_uuid):
        message = get_object_or_404(Message, uuid=message_uuid)

        # Vérifier les permissions
        if message.sender != request.user and message.recipient != request.user:
            messages.error(request, _("Accès refusé."))
            return redirect('messaging:inbox')

        message.soft_delete(request.user)

        messages.success(request, _("Message supprimé avec succès."))
        return redirect('messaging:conversation_detail', uuid=message.conversation.uuid)


class BlockUserView(LoginRequiredMixin, View):
    """Vue pour bloquer un utilisateur"""

    def post(self, request, username):
        blocked_user = get_object_or_404(User, username=username)

        # Ne pas permettre de se bloquer soi-même
        if blocked_user == request.user:
            messages.error(request, _("Vous ne pouvez pas vous bloquer vous-même."))
            return redirect('messaging:inbox')

        form = BlockUserForm(
            request.POST,
            blocker=request.user,
            blocked=blocked_user
        )

        if form.is_valid():
            form.save()
            messages.success(request, _("Utilisateur bloqué avec succès."))
        else:
            for error in form.errors.values():
                messages.error(request, error)

        return redirect('messaging:inbox')


class UnblockUserView(LoginRequiredMixin, View):
    """Vue pour débloquer un utilisateur"""

    def post(self, request, username):
        blocked_user = get_object_or_404(User, username=username)

        # Supprimer le blocage
        BlockedUser.objects.filter(
            blocker=request.user,
            blocked=blocked_user
        ).delete()

        messages.success(request, _("Utilisateur débloqué avec succès."))
        return redirect('messaging:inbox')


class NotificationsView(LoginRequiredMixin, ListView):
    """Vue des notifications"""
    model = Notification
    template_name = 'messaging/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).exclude(
            expires_at__lt=timezone.now()
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = self.get_queryset().filter(is_read=False).count()
        return context


class MarkNotificationAsReadView(LoginRequiredMixin, View):
    """Vue pour marquer une notification comme lue"""

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            user=request.user
        )

        notification.mark_as_read()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('messaging:notifications')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    """Vue pour marquer toutes les notifications comme lues"""

    def post(self, request):
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)

        messages.success(request, _("Toutes les notifications ont été marquées comme lues."))
        return redirect('messaging:notifications')


class ReportMessageView(LoginRequiredMixin, CreateView):
    """Vue pour signaler un message"""
    template_name = 'messaging/report_message.html'
    form_class = MessageReportForm

    def dispatch(self, request, *args, **kwargs):
        self.message = get_object_or_404(Message, uuid=kwargs.get('message_uuid'))

        # Vérifier si l'utilisateur a accès au message
        if not self.message.can_user_access(request.user):
            messages.error(request, _("Accès refusé."))
            return redirect('messaging:inbox')

        # Vérifier si l'utilisateur a déjà signalé ce message
        if MessageReport.objects.filter(
            reporter=request.user,
            message=self.message
        ).exists():
            messages.warning(request, _("Vous avez déjà signalé ce message."))
            return redirect('messaging:conversation_detail', uuid=self.message.conversation.uuid)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['reporter'] = self.request.user
        kwargs['message'] = self.message
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message'] = self.message
        return context

    def form_valid(self, form):
        report = form.save()

        messages.success(
            self.request,
            _("Votre signalement a été soumis. Notre équipe l'examinera sous 24 heures.")
        )
        return redirect('messaging:conversation_detail', uuid=self.message.conversation.uuid)


class MessageSettingsView(LoginRequiredMixin, UpdateView):
    """Vue pour les paramètres de messagerie"""
    template_name = 'messaging/settings.html'
    form_class = UserMessageSettingsForm

    def get_object(self):
        # Obtenir ou créer les paramètres
        obj, created = UserMessageSettings.objects.get_or_create(
            user=self.request.user
        )
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Paramètres mis à jour avec succès."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('messaging:settings')


# ============================================================================
# VUES API (AJAX)
# ============================================================================

class UnreadCountAPIView(LoginRequiredMixin, View):
    """API pour obtenir le nombre de messages non lus"""

    def get(self, request):
        unread_count = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted=False
        ).count()

        return JsonResponse({'unread_count': unread_count})


class MarkAsReadAPIView(LoginRequiredMixin, View):
    """API pour marquer un message comme lu"""

    def post(self, request, message_uuid):
        message = get_object_or_404(Message, uuid=message_uuid)

        if message.recipient != request.user:
            return JsonResponse({'error': _("Accès refusé.")}, status=403)

        message.mark_as_read()

        return JsonResponse({'success': True})


class CheckNewMessagesAPIView(LoginRequiredMixin, View):
    """API pour vérifier les nouveaux messages"""

    def get(self, request):
        conversation_uuid = request.GET.get('conversation_uuid')

        if conversation_uuid:
            # Vérifier les nouveaux messages dans une conversation spécifique
            conversation = get_object_or_404(Conversation, uuid=conversation_uuid)

            if not conversation.can_user_access(request.user):
                return JsonResponse({'error': _("Accès refusé.")}, status=403)

            last_message_id = request.GET.get('last_message_id', 0)

            new_messages = conversation.messages.filter(
                id__gt=last_message_id,
                is_deleted=False
            ).order_by('sent_at')

            messages_data = []
            for msg in new_messages:
                messages_data.append({
                    'id': msg.id,
                    'content': msg.content,
                    'sender': msg.sender.username,
                    'sent_at': msg.sent_at.strftime('%H:%M'),
                    'is_own': msg.sender == request.user
                })

            return JsonResponse({
                'has_new': len(messages_data) > 0,
                'messages': messages_data,
                'last_message_id': new_messages.last().id if new_messages.exists() else last_message_id
            })
        else:
            # Vérifier s'il y a de nouvelles conversations
            # (à implémenter selon les besoins)
            return JsonResponse({'has_new': False})


class UploadAttachmentAPIView(LoginRequiredMixin, View):
    """API pour uploader une pièce jointe"""

    def post(self, request):
        if 'file' not in request.FILES:
            return JsonResponse({'error': _("Aucun fichier fourni.")}, status=400)

        file = request.FILES['file']

        # Validation de la taille
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            return JsonResponse({
                'error': _(f"Le fichier est trop volumineux. Taille maximum: {max_size/(1024*1024):.0f}MB")
            }, status=400)

        # Validation du type
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf',
                             '.doc', '.docx', '.xls', '.xlsx', '.zip']
        import os
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in allowed_extensions:
            return JsonResponse({
                'error': _(f"Type de fichier non autorisé. Types autorisés: {', '.join(allowed_extensions)}")
            }, status=400)

        # Pour l'instant, retourner juste le nom du fichier
        # Dans une implémentation réelle, vous sauvegarderiez le fichier
        return JsonResponse({
            'success': True,
            'filename': file.name,
            'size': file.size
        })


# ============================================================================
# VUES SUPPLEMENTAIRES
# ============================================================================

class SentMessagesView(LoginRequiredMixin, ListView):
    """Vue des messages envoyés"""
    template_name = 'messaging/sent.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        return Message.objects.filter(
            sender=self.request.user,
            is_deleted=False
        ).select_related(
            'conversation', 'recipient'
        ).order_by('-sent_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Messages envoyés")
        return context


class ArchivedConversationsView(LoginRequiredMixin, ListView):
    """Vue des conversations archivées"""
    template_name = 'messaging/archived.html'
    context_object_name = 'conversations'
    paginate_by = 20

    def get_queryset(self):
        return Conversation.objects.filter(
            archives__user=self.request.user
        ).annotate(
            last_message_time=Max('messages__sent_at')
        ).order_by('-last_message_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Conversations archivées")
        return context


class UnreadMessagesView(LoginRequiredMixin, ListView):
    """Vue des messages non lus"""
    template_name = 'messaging/unread.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        return Message.objects.filter(
            recipient=self.request.user,
            is_read=False,
            is_deleted=False
        ).select_related(
            'conversation', 'sender'
        ).order_by('-sent_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Messages non lus")
        return context


class MessagesWithAttachmentsView(LoginRequiredMixin, ListView):
    """Vue des messages avec pièces jointes"""
    template_name = 'messaging/with_attachments.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        return Message.objects.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user),
            attachment__isnull=False,
            is_deleted=False
        ).select_related(
            'conversation', 'sender', 'recipient'
        ).order_by('-sent_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Messages avec pièces jointes")
        return context


class BlockedUsersView(LoginRequiredMixin, ListView):
    """Vue des utilisateurs bloqués"""
    template_name = 'messaging/blocked_users.html'
    context_object_name = 'blocked_users'

    def get_queryset(self):
        return BlockedUser.objects.filter(
            blocker=self.request.user
        ).select_related('blocked').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Utilisateurs bloqués")
        return context


class MyReportsView(LoginRequiredMixin, ListView):
    """Vue des signalements de l'utilisateur"""
    template_name = 'messaging/my_reports.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        return MessageReport.objects.filter(
            reporter=self.request.user
        ).select_related(
            'message', 'message__conversation'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Mes signalements")
        return context