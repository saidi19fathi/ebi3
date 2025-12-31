# ~/ebi3/colis/utils/signal_helpers.py
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

def create_conversation_for_offer(offer):
    """Crée une conversation pour une offre (gère les imports circulaires)"""
    try:
        from messaging.models import Conversation, Message

        # Votre logique de création de conversation
        conversation, created = Conversation.objects.get_or_create(
            package=offer.package,
            carrier=offer.carrier,
            defaults={
                'subject': f"Offre pour le colis #{offer.package.id}",
                'last_message_at': timezone.now()
            }
        )

        if created:
            # Créer le premier message
            Message.objects.create(
                conversation=conversation,
                sender=offer.carrier.user,
                content=f"Bonjour, je vous propose de transporter votre colis pour {offer.price} {offer.currency}.",
                is_read=False
            )

        return conversation

    except ImportError as e:
        logger.error(f"Could not import messaging models: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return None