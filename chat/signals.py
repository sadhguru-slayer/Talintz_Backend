from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from .models import Message
from .consumers import UserConsumer
from django.contrib.auth import get_user_model
from django.conf import settings
from .serializers import UserShortSerializer
from django.dispatch import Signal

User = get_user_model()

# Custom signal for file uploads
file_uploaded = Signal()

@database_sync_to_async
def get_conversation_details_for_user(conversation_id, user_id):
    def build_absolute_uri(path):
        base = getattr(settings, "BASE_URL", "http://127.0.0.1:8000")
        if not path:
            return None
        if path.startswith("http"):
            return path
        return base + path

    from .models import Conversation
    conv = Conversation.objects.get(id=conversation_id)
    user = User.objects.get(id=user_id)
    if conv.is_group:
        name = getattr(conv, 'group_name', 'Group Chat')
        avatar = getattr(conv, 'group_avatar', None)
        avatar = build_absolute_uri(avatar)
    else:
        other = conv.participants.exclude(user=user).first()
        if other:
            name = other.user.get_full_name() or other.user.username
            avatar = UserShortSerializer(other.user, context={'request': None}).data.get('avatar')
            avatar = build_absolute_uri(avatar)
        else:
            name = "Unknown"
            avatar = "https://ui-avatars.com/api/?name=Unknown"
    last_msg = conv.messages.order_by('-created_at').first()
    last_message = {
        'id': last_msg.id,
        'content': getattr(last_msg, 'content', None) or getattr(last_msg, 'content_creator', ''),
        'created_at': last_msg.created_at.isoformat(),
        'sender': {
            'id': last_msg.sender.id,
            'username': last_msg.sender.username,
        }
    } if last_msg else None

    unread_count = (
        conv.messages.exclude(sender=user)
        .exclude(statuses__user=user, statuses__status='seen')
        .count()
    )

    return {
        'conversation_id': conv.id,
        'name': name,
        'avatar': avatar,
        'is_group': conv.is_group,
        'last_message': last_message,
        'participants': [
            {'id': p.user.id, 'username': p.user.username}
            for p in conv.participants.all()
        ],
        'timestamp': last_msg.created_at.isoformat() if last_msg else conv.updated_at.isoformat(),
        'unread': unread_count,
    }

@receiver(post_save, sender=Message)
def message_post_save(sender, instance, created, **kwargs):
    if created:
        print(f"✅ SIGNAL: New message {instance.id} saved. Triggering conversation update.")
        channel_layer = get_channel_layer()
        conversation = instance.conversation
        
        participant_user_ids = [p.user.id for p in conversation.participants.all()]
        print(f"✅ SIGNAL: Found participants {participant_user_ids} for conversation {conversation.id}.")

        for user_id in participant_user_ids:
            print(f"✅ SIGNAL: Preparing update for user {user_id}.")
            # We run this synchronously for simplicity in a signal handler
            conv_details = async_to_sync(get_conversation_details_for_user)(conversation.id, user_id)
            
            print(f"✅ SIGNAL: Sending 'conversation_update' to user's channel (user_{user_id}).")
            # Send the update to the user's personal channel
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    'type': 'conversation_update',
                    **conv_details,
                    'sender_id': instance.sender.id,
                }
            )

@receiver(post_save, sender=Message)
def notify_file_upload(sender, instance, created, **kwargs):
    if created and instance.file:  # Only for new messages with files
        file_uploaded.send(
            sender=Message,
            message=instance,
            conversation_id=instance.conversation.id,
            sender_id=instance.sender.id
        )
