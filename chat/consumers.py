import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message, MessageStatus
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from .serializers import UserShortSerializer
from django.conf import settings
from datetime import datetime

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Validate token
        query_string = parse_qs(self.scope['query_string'].decode())
        token = query_string.get('token', [None])[0]
        if not token:
            await self.close()
            return

        try:
            user_id = await self.get_user_from_token(token)
            self.user = await database_sync_to_async(User.objects.get)(id=user_id)
        except Exception as e:
            print(f"Token validation failed: {e}")
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        print("WebSocket received:", text_data)
        data = json.loads(text_data)
        if data.get("type") == "seen":
            message_ids = [mid for mid in data.get("message_ids", []) if mid is not None]
            if not message_ids:
                return
            user_id = self.user.id
            await self.mark_messages_as_seen(user_id, message_ids)
            # Broadcast seen status to all participants
            for msg_id in message_ids:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_seen",
                        "message_id": msg_id,
                        "user_id": user_id,
                    }
                )
            # Send conversation update to all participants
            
            conv_id = await self.get_conversation_id_from_message_id(message_ids[0])
            participant_user_ids = await self.get_participant_user_ids(conv_id)
            for uid in participant_user_ids:
                conv_details = await self.get_conversation_details_for_user(conv_id, uid)
                await self.channel_layer.group_send(
                    f"user_{uid}",
                    {
                        'type': 'user_conversation_update',
                        **conv_details,
                        'sender_id': user_id,
                    }
                )
        elif data.get("message"):
            message = data['message']
            temp_id = data.get('temp_id')
            reply_to_id = data.get('reply_to_id')
            user_id = self.user.id
            print("-------------------------------", reply_to_id)
            # Save message to DB with reply_to
            msg = await self.create_message(user_id, self.conversation_id, message, reply_to_id)

            # Update is_temporary to false if it's the first message
            await self.update_conversation_temporary_status(self.conversation_id)

            # Get reply_to details for WebSocket broadcast
            reply_to = await self.get_reply_to_details(reply_to_id) if reply_to_id else None

            # Broadcast message to group
            sender_user = self.user
            avatar = await self.get_avatar_for_user_sync(sender_user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': msg.id,
                        'sender': {
                            'id': msg.sender.id,
                            'username': msg.sender.username,
                            'avatar': avatar,
                        },
                        'avatar': avatar,
                        'content': msg.content,
                        'created_at': msg.created_at.isoformat(),
                        'temp_id': temp_id,
                        'reply_to': reply_to,
                    }
                }
            )

            # After broadcasting the message to the chat group
            participant_user_ids = await self.get_participant_user_ids(msg.conversation.id)
            for user_id in participant_user_ids:
                conv_details = await self.get_conversation_details_for_user(msg.conversation.id, user_id)
                await self.channel_layer.group_send(
                    f"user_{user_id}",
                    {
                        'type': 'user_conversation_update',
                        **conv_details,
                        'sender_id': msg.sender.id,
                    }
                )

    # Receive message from room group
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def create_message(self, user_id, conversation_id, content, reply_to_id=None):
        user = User.objects.get(id=user_id)
        conversation = Conversation.objects.get(id=conversation_id)
        reply_to = Message.objects.get(id=reply_to_id) if reply_to_id else None
        return Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content,
            reply_to=reply_to,
        )

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            decoded_token = AccessToken(token)
            return decoded_token['user_id']
        except Exception:
            return None

    @database_sync_to_async
    def mark_messages_as_seen(self, user_id, message_ids):
        for msg_id in message_ids:
            try:
                msg = Message.objects.get(id=msg_id)
                obj, created = MessageStatus.objects.get_or_create(
                    message=msg, user_id=user_id,
                    defaults={"status": "seen"}
                )
                if not created and obj.status == "seen":
                    # Already seen, skip update
                    continue
                obj.status = "seen"
                obj.save()
                print(f"MessageStatus {'created' if created else 'updated'} for message {msg_id}, user {user_id}")
            except Exception as e:
                print(f"Error in mark_messages_as_seen: {e}, message_id={msg_id}, user_id={user_id}")

    async def message_seen(self, event):
        # Send seen status to all clients in the group
        await self.send(text_data=json.dumps({
            "type": "seen",
            "message_id": event["message_id"],
            "user_id": event["user_id"],
        }))

    @database_sync_to_async
    def get_conversation_details(self, conversation_id):
        conv = Conversation.objects.get(id=conversation_id)
        if conv.is_group:
            name = getattr(conv, 'group_name', 'Group Chat')
            avatar = getattr(conv, 'group_avatar', None)
        else:
            other = conv.participants.exclude(user=self.user).first()
            if other:
                name = other.user.get_full_name() or other.user.username
                avatar = UserShortSerializer(other.user, context={'request': None}).data.get('avatar')
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
            },
            'type':'seen'
        } if last_msg else None
        return {
            'conversation_id': conv.id,
            'name': name,
            'avatar': avatar,
            'is_group': conv.is_group,
            'lastMessage': last_message,
            'participants': [
                {
                    'id': p.user.id,
                    'username': p.user.username,
                }
                for p in conv.participants.all()
            ],
            'timestamp': last_msg.created_at.isoformat() if last_msg else conv.updated_at.isoformat(),
            # Optionally add unread_count here
        }

    @database_sync_to_async
    def get_conversation_id_from_message_id(self, msg_id):
        try:
            return Message.objects.get(id=msg_id).conversation.id
        except (Message.DoesNotExist, AttributeError):
            return None

    @database_sync_to_async
    def get_participant_user_ids(self, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id)
            return [p.user.id for p in conv.participants.all()]
        except Conversation.DoesNotExist:
            return []

    @database_sync_to_async
    def get_conversation_details_for_user(self, conversation_id, user_id):
        def build_absolute_uri(path):
            base = getattr(settings, "BASE_URL", "http://127.0.0.1:8000")
            if not path:
                return None
            if path.startswith("http"):
                return path
            return base + path

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

        # --- UNREAD COUNT LOGIC ---
        # Count messages in this conversation not sent by this user and not seen by this user
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
            'lastMessage': last_message,
            'participants': [
                {
                    'id': p.user.id,
                    'username': p.user.username,
                }
                for p in conv.participants.all()
            ],
            'timestamp': last_msg.created_at.isoformat() if last_msg else conv.updated_at.isoformat(),
            'unread': unread_count,
        }

    @database_sync_to_async
    def update_conversation_temporary_status(self, conversation_id):
        conversation = Conversation.objects.get(id=conversation_id)
        if conversation.is_temporary:
            conversation.is_temporary = False
            conversation.save()

    async def file_uploaded(self, event):
        sender_user = await database_sync_to_async(User.objects.get)(id=event["sender_id"])
        avatar = await self.get_avatar_for_user_sync(sender_user)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": {
                    "id": event["message_id"],
                    "file_url": event["file_url"],
                    "name": event.get("name"),
                    "sender": {
                        "id": event["sender_id"],
                        "username": sender_user.username,
                        "avatar": avatar,
                    },
                    "avatar": avatar,
                    "created_at": datetime.now().isoformat(),
                    "reply_to": event.get("reply_to"),
                    "type": "file_uploaded",
                    "conversation_id": event["conversation_id"],
                    "content": "",
                    "temp_id": event.get("temp_id"),
                }
            }
        )

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"],
            "deleted_for_everyone": event["deleted_for_everyone"],
        }))

    @database_sync_to_async
    def get_reply_to_details(self, reply_to_id):
        if not reply_to_id:
            return None
        reply_to = Message.objects.get(id=reply_to_id)
        return {
            "id": reply_to.id,
            "content": reply_to.content,
            "sender": {
                "id": reply_to.sender.id,
                "username": reply_to.sender.username,
            },
        }

    async def user_conversation_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_conversation_update",
            "conversation_id": event["conversation_id"],
            "name": event["name"],
            "avatar": event["avatar"],
            "is_group": event["is_group"],
            "lastMessage": event["lastMessage"],
            "participants": event["participants"],
            "timestamp": event["timestamp"],
            "unread": event["unread"],
            "sender_id": event["sender_id"],
        }))

    @database_sync_to_async
    def get_avatar_for_user_sync(self, user):
        from Profile.models import ClientProfile, FreelancerProfile

        # Try to get client profile picture
        if user.role == "client":
            client_profile = ClientProfile.objects.filter(user=user).first()
            if client_profile and client_profile.profile_picture:
                return self.build_absolute_uri(client_profile.profile_picture.url)

        # Try to get freelancer profile picture
        if user.role == "freelancer":
            freelancer_profile = FreelancerProfile.objects.filter(user=user).first()
            if freelancer_profile and freelancer_profile.profile_picture:
                return self.build_absolute_uri(freelancer_profile.profile_picture.url)

        # Fallback: generate avatar from initials
        name = (user.first_name or '') + ' ' + (user.last_name or '')
        if not name.strip():
            name = user.username
        return f"https://ui-avatars.com/api/?name={name.strip().replace(' ', '+')}&background=random"

    def build_absolute_uri(self, path):
        base = getattr(settings, "BASE_URL", "http://127.0.0.1:8000")
        if not path:
            return None
        if path.startswith("http"):
            return path
        return base + path

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.user_group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

    async def conversation_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_conversation_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "conversation_update",
            **event
        }))

class FileUploadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["user"].id
        self.group_name = f"user_{self.user_id}"

        # Join the user's group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the user's group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def file_uploaded(self, event):
        # Send the file upload notification to the client
        sender_user = await database_sync_to_async(User.objects.get)(id=event["sender_id"])
        avatar = await self.get_avatar_for_user_sync(sender_user)
        await self.send(text_data=json.dumps({
            "type": "file_uploaded",
            "file_url": event["file_url"],
            "message_id": event["message_id"],
            "sender_id": event["sender_id"],
            "conversation_id": event["conversation_id"],
        }))
