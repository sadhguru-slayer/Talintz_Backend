# consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from core.models import Notification, User
from asgiref.sync import async_to_sync
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
from django.core.paginator import Paginator
from django.core.cache import cache
from Profile.models import ClientProfile, FreelancerProfile  # Ensure correct import
from core.serializers import ProjectSerializer, CategorySerializer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the user from the token
        token = self.scope['query_string'].decode().split('=')[-1]  # Assuming token is passed via query params
        user_id = await self.get_user_from_token(token)  # Get user based on the token

        if user_id:
            self.user = await database_sync_to_async(User.objects.get)(id=user_id)
            self.group_name = f"user_{self.user.id}"

            # Join the user to their group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()

            # Send initial notification count
            unread_count = await self.get_unread_notification_count(self.user)
            await self.send(text_data=json.dumps({
                "notifications_count": unread_count
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Leave the group when disconnected
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Handle incoming messages (if needed, like marking notifications as read)
        pass

    async def send_notification_count(self, event):
        
        if 'notifications_count' in event:
            await self.send(text_data=json.dumps({
                'notifications_count': event['notifications_count']
            }))
        elif 'message' in event:
            await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def get_unread_notification_count(self, user):
        return Notification.objects.filter(user=user, is_read=False).count()

    @database_sync_to_async
    def get_user_from_token(self, token):
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            decoded_token = AccessToken(token)
            return decoded_token['user_id']
        except Exception:
            return None


class NotificationShowConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the user from the token
        query_string = parse_qs(self.scope['query_string'].decode())
        token = query_string.get('token', [None])[0]  # Extract token safely

        if token:
            user_id = await self.get_user_from_token(token)

            if user_id:
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                self.group_name = f"user_notification_{self.user.id}"

                # Join the user to their group
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()

                # Send initial notifications only once
                notifications = await self.get_user_notification(self.user)
                if notifications:  # If there are notifications to send
                    # Send only the first notification (or none if no notifications)
                    await self.send(text_data=json.dumps({
                        "notifications": [notifications[0]]  # Send just one notification
                    }))
            else:
                await self.close()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Leave the group when disconnected
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages (e.g., mark notifications as read)."""
        pass

    async def send_notification(self, event):
        """Send a single notification to the WebSocket client."""
        notification = event['notification']
        if notification:  # Send the notification if there's one
            await self.send(text_data=json.dumps({
                'notification_id': notification['id'],
                'title': notification['title'],
                'notification_text': notification['notification_text'],
                'created_at': notification['created_at'],
                'related_model_id': notification['related_model_id'],
                'type': notification['type']
            }))

    @database_sync_to_async
    def get_user_notification(self, user):
        """Fetch the unread notifications for the user."""
        notifications = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')
        return [{
            "id": notification.id,
            "notification_text": notification.notification_text,
            "created_at": notification.created_at.isoformat(),
            "related_model_id": notification.related_model_id,
            "type": notification.type
        } for notification in notifications]

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Extract user ID from JWT token."""
        try:
            decoded_token = AccessToken(token)
            return decoded_token['user_id']
        except Exception:
            return None

