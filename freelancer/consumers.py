from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from core.models import Notification, User
from asgiref.sync import async_to_sync
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
from django.core.paginator import Paginator
from django.core.cache import cache
from Profile.models import FreelancerProfile
import logging

logger = logging.getLogger(__name__)

class FreelancerNotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for freelancer notification counts"""
    async def connect(self):
        try:
            # Extract the user from the token
            token = self.scope['query_string'].decode().split('=')[-1]
            user_id = await self.get_user_from_token(token)

            if user_id:
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                
                # Verify user is a freelancer
                if self.user.role not in ['freelancer', 'student']:
                    logger.warning(f"User {self.user.username} is not a freelancer, closing connection")
                    await self.close()
                    return
                    
                self.group_name = f"freelancer_{self.user.id}"

                # Join the user to their group
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()

                # Send initial notification count and unread messages
                unread_count = await self.get_unread_notification_count(self.user)
                unread_messages = await self.get_unread_message_count(self.user)
                
                await self.send(text_data=json.dumps({
                    "notifications_count": unread_count,
                    "unread_messages": unread_messages
                }))
                
                logger.info(f"Freelancer {self.user.username} connected successfully")
            else:
                logger.error("Invalid token, closing connection")
                await self.close()
        except Exception as e:
            logger.error(f"Error in freelancer notification connect: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        # Leave the group when disconnected
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"Freelancer disconnected with code: {close_code}")

    async def receive(self, text_data):
        # Handle incoming messages (if needed, like marking notifications as read)
        pass

    async def send_notification_count(self, event):
        """Send notification count updates to the client"""
        try:
            if 'notifications_count' in event:
                await self.send(text_data=json.dumps({
                    'notifications_count': event['notifications_count']
                }))
            elif 'unread_messages' in event:
                await self.send(text_data=json.dumps({
                    'unread_messages': event['unread_messages']
                }))
            elif 'message' in event:
                await self.send(text_data=json.dumps(event['message']))
        except Exception as e:
            logger.error(f"Error sending notification count: {str(e)}")

    @database_sync_to_async
    def get_unread_notification_count(self, user):
        """Get count of unread notifications for freelancer"""
        try:
            return Notification.objects.filter(
                user=user, 
                is_read=False,
                type__in=['project_assignment', 'interview_request', 'bid_update', 'payment_received', 'project_update']
            ).count()
        except Exception as e:
            logger.error(f"Error getting notification count: {str(e)}")
            return 0

    @database_sync_to_async
    def get_unread_message_count(self, user):
        """Get count of unread messages for freelancer"""
        # This would integrate with your messaging system
        # For now, return 0 - you can implement this based on your message model
        return 0

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Extract user ID from JWT token"""
        try:
            decoded_token = AccessToken(token)
            return decoded_token['user_id']
        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            return None


class FreelancerNotificationShowConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for freelancer individual notifications"""
    async def connect(self):
        try:
            # Extract the user from the token
            query_string = parse_qs(self.scope['query_string'].decode())
            token = query_string.get('token', [None])[0]

            if token:
                user_id = await self.get_user_from_token(token)

                if user_id:
                    self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                    
                    # Verify user is a freelancer
                    if self.user.role not in ['freelancer', 'student']:
                        logger.warning(f"User {self.user.username} is not a freelancer, closing connection")
                        await self.close()
                        return
                        
                    self.group_name = f"freelancer_notification_{self.user.id}"

                    # Join the user to their group
                    await self.channel_layer.group_add(
                        self.group_name,
                        self.channel_name
                    )
                    await self.accept()

                    # Send initial notifications only once
                    notifications = await self.get_user_notification(self.user)
                    if notifications:
                        # Send only the first notification
                        await self.send(text_data=json.dumps({
                            "notifications": [notifications[0]]
                        }))
                    
                    logger.info(f"Freelancer notification consumer connected for {self.user.username}")
                else:
                    logger.error("Invalid token, closing connection")
                    await self.close()
            else:
                logger.error("No token provided, closing connection")
                await self.close()
        except Exception as e:
            logger.error(f"Error in freelancer notification show connect: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        # Leave the group when disconnected
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"Freelancer notification consumer disconnected with code: {close_code}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        pass

    async def send_notification(self, event):
        """Send a single notification to the WebSocket client"""
        try:
            notification = event['notification']
            if notification:
                await self.send(text_data=json.dumps({
                    'notification_id': notification['id'],
                    'title': notification['title'],
                    'notification_text': notification['notification_text'],
                    'created_at': notification['created_at'],
                    'related_model_id': notification['related_model_id'],
                    'type': notification['type']
                }))
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

    @database_sync_to_async
    def get_user_notification(self, user):
        """Fetch the unread notifications for the freelancer"""
        try:
            notifications = Notification.objects.filter(
                user=user, 
                is_read=False,
                type__in=['project_assignment', 'interview_request', 'bid_update', 'payment_received', 'project_update']
            ).order_by('-created_at')
            
            return [{
                "id": notification.id,
                "title": notification.title or "New Notification",
                "notification_text": notification.notification_text,
                "created_at": notification.created_at.isoformat(),
                "related_model_id": notification.related_model_id,
                "type": notification.type
            } for notification in notifications]
        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}")
            return []

    @database_sync_to_async
    def get_user_from_token(self, token):
        """Extract user ID from JWT token"""
        try:
            decoded_token = AccessToken(token)
            return decoded_token['user_id']
        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            return None
