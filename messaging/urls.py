# ~/ebi3/messaging/urls.py
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'messaging'

urlpatterns = [
    # Vues principales
    path('inbox/', views.InboxView.as_view(), name='inbox'),
    path('conversation/<uuid:uuid>/', views.ConversationDetailView.as_view(), name='conversation_detail'),
    path('new/', views.NewConversationView.as_view(), name='new_conversation'),
    path('new/<str:username>/', views.NewConversationWithUserView.as_view(), name='new_conversation_with_user'),
    path('conversation/<uuid:uuid>/send/', views.SendMessageView.as_view(), name='send_message'),
    path('conversation/<uuid:uuid>/archive/', views.ArchiveConversationView.as_view(), name='archive_conversation'),
    path('conversation/<uuid:uuid>/unarchive/', views.UnarchiveConversationView.as_view(), name='unarchive_conversation'),
    path('conversation/<uuid:uuid>/delete/', views.DeleteConversationView.as_view(), name='delete_conversation'),

    # Gestion des messages
    path('message/<uuid:message_uuid>/read/', views.MarkMessageAsReadView.as_view(), name='mark_message_read'),
    path('message/<uuid:message_uuid>/delete/', views.DeleteMessageView.as_view(), name='delete_message'),

    # Blocage d'utilisateurs
    path('block/<str:username>/', views.BlockUserView.as_view(), name='block_user'),
    path('unblock/<str:username>/', views.UnblockUserView.as_view(), name='unblock_user'),

    # Notifications
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.MarkNotificationAsReadView.as_view(), name='mark_notification_read'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_notifications_read'),

    # Signalements
    path('message/<uuid:message_uuid>/report/', views.ReportMessageView.as_view(), name='report_message'),

    # Paramètres
    path('settings/', views.MessageSettingsView.as_view(), name='settings'),

    # Vues spéciales
    path('sent/', views.SentMessagesView.as_view(), name='sent_messages'),
    path('archived/', views.ArchivedConversationsView.as_view(), name='archived_conversations'),
    path('unread/', views.UnreadMessagesView.as_view(), name='unread_messages'),
    path('with-attachments/', views.MessagesWithAttachmentsView.as_view(), name='messages_with_attachments'),
    path('blocked-users/', views.BlockedUsersView.as_view(), name='blocked_users'),
    path('my-reports/', views.MyReportsView.as_view(), name='my_reports'),

    # API endpoints (AJAX)
    path('api/unread-count/', views.UnreadCountAPIView.as_view(), name='api_unread_count'),
    path('api/message/<uuid:message_uuid>/mark-read/', views.MarkAsReadAPIView.as_view(), name='api_mark_read'),
    path('api/check-new-messages/', views.CheckNewMessagesAPIView.as_view(), name='api_check_new_messages'),
    path('api/upload-attachment/', views.UploadAttachmentAPIView.as_view(), name='api_upload_attachment'),
]