from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Conversation, Message, MessagePin, MessageReaction, MessageStatus, ConversationParticipant
from .serializers import (
    ConversationSerializer, MessageSerializer, MessagePinSerializer,
    MessageReactionSerializer, MessageStatusSerializer, ConversationListSerializer
)
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

# Create your views here.

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only conversations the user participates in
        return Conversation.objects.filter(participants__user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer  # for detail, create, etc.

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        messages = conversation.messages.filter(is_archived=False).order_by('created_at')
        page = self.paginate_queryset(messages)
        context = self.get_serializer_context()
        if page is not None:
            serializer = MessageSerializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)
        serializer = MessageSerializer(messages, many=True, context=context)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pins(self, request, pk=None):
        conversation = self.get_object()
        pins = conversation.pinned_messages.all()
        context = self.get_serializer_context()
        serializer = MessagePinSerializer(pins, many=True, context=context)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def files(self, request, pk=None):
        conversation = self.get_object()
        files = conversation.messages.exclude(file='').exclude(file=None)
        context = self.get_serializer_context()
        serializer = MessageSerializer(files, many=True, context=context)
        return Response(serializer.data)

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(conversation__participants__user=self.request.user)

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        # Pin logic here
        pass

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        # Unpin logic here
        pass

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        # React logic here
        pass

    @action(detail=True, methods=['post'])
    def status(self, request, pk=None):
        # Status update logic here
        pass

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        file = request.FILES.get('file')
        conversation_id = request.data.get('conversation_id')
        reply_to_id = request.data.get('reply_to_id')
        temp_id = request.data.get('temp_id')  # Get temp_id from frontend

        if not file or not conversation_id:
            return Response({'error': 'Missing file or conversation_id'}, status=400)
        
        conversation = get_object_or_404(Conversation, id=conversation_id)
        reply_to = get_object_or_404(Message, id=reply_to_id) if reply_to_id else None

        # Create the message
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            file=file,
            reply_to=reply_to,
        )

        # Broadcast via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{conversation_id}",
            {
                "type": "file_uploaded",
                "file_url": request.build_absolute_uri(message.file.url),
                "message_id": message.id,
                "temp_id": temp_id,
                "sender_id": request.user.id,
                "conversation_id": conversation_id,
                "name": file.name,
                "reply_to": {
                    "id": reply_to.id if reply_to else None,
                    "content": reply_to.content if reply_to else None,
                    "sender": {
                        "id": reply_to.sender.id if reply_to else None,
                        "username": reply_to.sender.username if reply_to else None,
                    },
                } if reply_to else None,
            }
        )

        return Response({
            'file_url': request.build_absolute_uri(message.file.url),
            'message_id': message.id,
            'temp_id': temp_id,
            'name': file.name,
        })

    @action(detail=True, methods=['post'])
    def delete_for_me(self, request, pk=None):
        message = self.get_object()
        message.is_deleted_for_me.add(request.user)
        message.save()
        return Response({'status': 'deleted_for_me'})

    @action(detail=True, methods=['post'])
    def delete_for_everyone(self, request, pk=None):
        message = self.get_object()
        if message.sender != request.user:
            return Response({'error': 'Only the sender can delete for everyone'}, status=403)
        message.is_deleted_for_everyone = True
        message.save()
        
        # Notify via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{message.conversation.id}",
            {
                "type": "message_deleted",
                "message_id": message.id,
                "deleted_for_everyone": True,
            }
        )
        return Response({'status': 'deleted_for_everyone'})

@api_view(['POST'])
def create_conversation_and_send_message(request):
    user1 = request.user
    user2_id = request.data['user2_id']
    text = request.data['text']
    # Check if conversation exists
    conv = Conversation.objects.filter(
        is_group=False,
        participants__user=user1
    ).filter(
        participants__user__id=user2_id
    ).first()
    if not conv:
        conv = Conversation.objects.create(is_group=False)
        ConversationParticipant.objects.create(conversation=conv, user=user1)
        ConversationParticipant.objects.create(conversation=conv, user_id=user2_id)
    msg = Message.objects.create(conversation=conv, sender=user1, content=text)
    return Response({
        'conversation': ConversationSerializer(conv).data,
        'message': MessageSerializer(msg).data
    })


from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Conversation, ConversationParticipant  # adjust import as needed

@api_view(['POST'])
def start_conversation(request):
    sender_id = request.data.get('sender_id')
    recipient_id = request.data.get('recipient_id')
    
    print("Incoming request data:", request.data)
    print("Sender ID:", sender_id)
    print("Recipient ID:", recipient_id)

    if not sender_id or not recipient_id:
        print("Missing user IDs.")
        return Response({'error': 'Missing user ids'}, status=400)

    # Check for existing conversation
    print("Checking for existing conversation...")
    conv_qs = Conversation.objects.filter(
        is_group=False,
        participants__user_id=sender_id
    ).filter(
        participants__user_id=recipient_id
    ).distinct()

    print("QuerySet SQL:", str(conv_qs.query))  # Optional: shows the SQL query
    conv = conv_qs.first()

    if conv:
        print("Found existing conversation:", conv.id)
        return Response({'conversation_id': conv.id, 'is_temporary': conv.is_temporary})

    # Create new temporary conversation
    print("No existing conversation found. Creating a new one...")
    conv = Conversation.objects.create(is_group=False, is_temporary=True)
    ConversationParticipant.objects.create(conversation=conv, user_id=sender_id)
    ConversationParticipant.objects.create(conversation=conv, user_id=recipient_id)

    print("New conversation created:", conv.id)
    return Response({'conversation_id': conv.id, 'is_temporary': True})



