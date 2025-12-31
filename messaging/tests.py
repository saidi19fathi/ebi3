# ~/ebi3/messaging/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import (
    Conversation, Message, Notification,
    UserMessageSettings, BlockedUser,
    ConversationArchive, MessageReport
)

User = get_user_model()

class MessagingModelsTest(TestCase):
    """Tests des modèles de messagerie"""

    def setUp(self):
        # Créer des utilisateurs
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='password123'
        )

        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='password123'
        )

        # Créer des paramètres de messagerie
        UserMessageSettings.objects.create(user=self.user1)
        UserMessageSettings.objects.create(user=self.user2)

    def test_conversation_creation(self):
        """Test la création d'une conversation"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        self.assertEqual(conversation.conversation_type, Conversation.ConversationType.PRIVATE)
        self.assertEqual(conversation.participants.count(), 2)
        self.assertTrue(conversation.is_active)
        self.assertFalse(conversation.is_blocked)

    def test_conversation_str_method(self):
        """Test la méthode __str__ de Conversation"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            subject="Test Conversation"
        )
        conversation.participants.add(self.user1, self.user2)

        self.assertEqual(str(conversation), "Test Conversation (Privé)")

    def test_message_creation(self):
        """Test la création d'un message"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        message = Message.objects.create(
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2,
            content="Hello, this is a test message."
        )

        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.recipient, self.user2)
        self.assertEqual(message.content, "Hello, this is a test message.")
        self.assertFalse(message.is_read)
        self.assertFalse(message.is_deleted)

    def test_message_mark_as_read(self):
        """Test le marquage d'un message comme lu"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        message = Message.objects.create(
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2,
            content="Test message"
        )

        self.assertFalse(message.is_read)
        self.assertIsNone(message.read_at)

        message.mark_as_read()
        message.refresh_from_db()

        self.assertTrue(message.is_read)
        self.assertIsNotNone(message.read_at)

    def test_conversation_get_other_participant(self):
        """Test la méthode get_other_participant de Conversation"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        other = conversation.get_other_participant(self.user1)
        self.assertEqual(other, self.user2)

        other = conversation.get_other_participant(self.user2)
        self.assertEqual(other, self.user1)

    def test_conversation_get_or_create(self):
        """Test la méthode get_or_create_conversation"""
        # Première création
        conversation1 = Conversation.get_or_create_conversation(
            self.user1, self.user2
        )
        self.assertIsNotNone(conversation1)
        self.assertEqual(conversation1.participants.count(), 2)

        # Récupération de la même conversation
        conversation2 = Conversation.get_or_create_conversation(
            self.user1, self.user2
        )
        self.assertEqual(conversation1.id, conversation2.id)

    def test_notification_creation(self):
        """Test la création d'une notification"""
        notification = Notification.objects.create(
            user=self.user1,
            notification_type=Notification.NotificationType.MESSAGE_RECEIVED,
            title="Test Notification",
            message="This is a test notification"
        )

        self.assertEqual(notification.user, self.user1)
        self.assertEqual(notification.notification_type, Notification.NotificationType.MESSAGE_RECEIVED)
        self.assertFalse(notification.is_read)
        self.assertFalse(notification.is_expired())

    def test_blocked_user_creation(self):
        """Test la création d'un blocage d'utilisateur"""
        blocked = BlockedUser.objects.create(
            blocker=self.user1,
            blocked=self.user2,
            reason="Test reason"
        )

        self.assertEqual(blocked.blocker, self.user1)
        self.assertEqual(blocked.blocked, self.user2)
        self.assertEqual(blocked.reason, "Test reason")

    def test_message_settings_creation(self):
        """Test la création des paramètres de messagerie"""
        settings = UserMessageSettings.objects.get(user=self.user1)

        self.assertEqual(settings.user, self.user1)
        self.assertTrue(settings.email_notifications)
        self.assertEqual(settings.allow_messages_from, 'EVERYONE')


class MessagingViewsTest(TestCase):
    """Tests des vues de messagerie"""

    def setUp(self):
        self.client = Client()

        # Créer des utilisateurs
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@test.com',
            password='testpass123'
        )

        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@test.com',
            password='testpass123'
        )

        # Créer des paramètres
        UserMessageSettings.objects.create(user=self.user1)
        UserMessageSettings.objects.create(user=self.user2)

        # Créer une conversation
        self.conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        self.conversation.participants.add(self.user1, self.user2)

    def test_inbox_view_authenticated(self):
        """Test la vue de la boîte de réception pour un utilisateur authentifié"""
        self.client.login(username='testuser1', password='testpass123')
        response = self.client.get(reverse('messaging:inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'messaging/inbox.html')

    def test_inbox_view_unauthenticated(self):
        """Test la redirection pour un utilisateur non authentifié"""
        response = self.client.get(reverse('messaging:inbox'))
        # Devrait rediriger vers la page de connexion
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_conversation_detail_view(self):
        """Test la vue de détail d'une conversation"""
        self.client.login(username='testuser1', password='testpass123')

        response = self.client.get(reverse('messaging:conversation_detail',
                                         kwargs={'uuid': self.conversation.uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'messaging/conversation_detail.html')

    def test_new_conversation_view_get(self):
        """Test la vue de nouvelle conversation (GET)"""
        self.client.login(username='testuser1', password='testpass123')

        response = self.client.get(reverse('messaging:new_conversation'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'messaging/new_conversation.html')

    def test_new_conversation_view_post(self):
        """Test la vue de nouvelle conversation (POST)"""
        self.client.login(username='testuser1', password='testpass123')

        data = {
            'recipient': 'testuser2',
            'subject': 'Test Subject',
            'message': 'This is a test message.'
        }

        response = self.client.post(reverse('messaging:new_conversation'), data)

        # Devrait rediriger vers la conversation créée
        self.assertEqual(response.status_code, 302)

        # Vérifier que la conversation a été créée
        conversation = Conversation.objects.filter(
            participants=self.user1
        ).filter(
            participants=self.user2
        ).first()

        self.assertIsNotNone(conversation)

        # Vérifier que le message a été créé
        message = Message.objects.filter(
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2
        ).first()

        self.assertIsNotNone(message)
        self.assertEqual(message.content, 'This is a test message.')

    def test_send_message_view(self):
        """Test la vue d'envoi de message"""
        self.client.login(username='testuser1', password='testpass123')

        data = {
            'content': 'This is a reply message.'
        }

        response = self.client.post(
            reverse('messaging:send_message', kwargs={'uuid': self.conversation.uuid}),
            data
        )

        # Devrait retourner JSON pour AJAX
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        # Vérifier que le message a été créé
        message = Message.objects.filter(
            conversation=self.conversation,
            sender=self.user1,
            recipient=self.user2
        ).last()

        self.assertIsNotNone(message)
        self.assertEqual(message.content, 'This is a reply message.')


class MessagingFormsTest(TestCase):
    """Tests des formulaires de messagerie"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='password123'
        )

        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='password123'
        )

        UserMessageSettings.objects.create(user=self.user1)
        UserMessageSettings.objects.create(user=self.user2)

    def test_new_conversation_form_valid(self):
        """Test le formulaire de nouvelle conversation avec des données valides"""
        form_data = {
            'recipient': 'user2',
            'subject': 'Test Subject',
            'message': 'Hello!'
        }

        form = NewConversationForm(data=form_data, user=self.user1)
        self.assertTrue(form.is_valid())

    def test_new_conversation_form_invalid_self_message(self):
        """Test le formulaire de nouvelle conversation avec envoi à soi-même"""
        form_data = {
            'recipient': 'user1',
            'subject': 'Test Subject',
            'message': 'Hello!'
        }

        form = NewConversationForm(data=form_data, user=self.user1)
        self.assertFalse(form.is_valid())
        self.assertIn('recipient', form.errors)

    def test_new_conversation_form_invalid_recipient(self):
        """Test le formulaire avec un destinataire invalide"""
        form_data = {
            'recipient': 'nonexistent',
            'subject': 'Test Subject',
            'message': 'Hello!'
        }

        form = NewConversationForm(data=form_data, user=self.user1)
        self.assertFalse(form.is_valid())
        self.assertIn('recipient', form.errors)

    def test_message_form_valid(self):
        """Test le formulaire de message avec des données valides"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        form_data = {
            'content': 'This is a test message.'
        }

        form = MessageForm(
            data=form_data,
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2
        )

        self.assertTrue(form.is_valid())

    def test_message_form_invalid_empty(self):
        """Test le formulaire de message vide"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        form_data = {}

        form = MessageForm(
            data=form_data,
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2
        )

        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)

    def test_message_form_with_attachment(self):
        """Test le formulaire de message avec pièce jointe"""
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        # Créer un faux fichier
        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            file_content,
            content_type="text/plain"
        )

        form_data = {
            'content': 'Message with attachment',
            'attachment': uploaded_file
        }

        form = MessageForm(
            data=form_data,
            conversation=conversation,
            sender=self.user1,
            recipient=self.user2
        )

        self.assertTrue(form.is_valid())

    def test_block_user_form_valid(self):
        """Test le formulaire de blocage d'utilisateur"""
        form_data = {
            'reason': 'Test reason for blocking'
        }

        form = BlockUserForm(
            data=form_data,
            blocker=self.user1,
            blocked=self.user2
        )

        self.assertTrue(form.is_valid())

    def test_block_user_form_self_block(self):
        """Test le formulaire de blocage avec soi-même"""
        form_data = {
            'reason': 'Test reason'
        }

        form = BlockUserForm(
            data=form_data,
            blocker=self.user1,
            blocked=self.user1
        )

        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)


class MessagingAPITest(TestCase):
    """Tests pour les endpoints API"""

    def setUp(self):
        self.client = Client()

        self.user1 = User.objects.create_user(
            username='apiuser1',
            email='api1@test.com',
            password='password123'
        )

        self.user2 = User.objects.create_user(
            username='apiuser2',
            email='api2@test.com',
            password='password123'
        )

        UserMessageSettings.objects.create(user=self.user1)

    def test_unread_count_api(self):
        """Test l'API du nombre de messages non lus"""
        self.client.login(username='apiuser1', password='password123')

        response = self.client.get(reverse('messaging:api_unread_count'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = response.json()
        self.assertIn('unread_count', data)
        self.assertEqual(data['unread_count'], 0)

    def test_mark_as_read_api(self):
        """Test l'API de marquage comme lu"""
        self.client.login(username='apiuser1', password='password123')

        # Créer une conversation et un message
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        conversation.participants.add(self.user1, self.user2)

        message = Message.objects.create(
            conversation=conversation,
            sender=self.user2,
            recipient=self.user1,
            content="Unread message"
        )

        # Marquer comme lu via API
        response = self.client.post(
            reverse('messaging:api_mark_as_read', kwargs={'message_uuid': message.uuid})
        )

        self.assertEqual(response.status_code, 200)

        # Vérifier que le message est marqué comme lu
        message.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertIsNotNone(message.read_at)