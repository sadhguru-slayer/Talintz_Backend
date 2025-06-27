# Serializers of chat models

from rest_framework import serializers
from .models import Conversation, Message, ConversationParticipant
from django.contrib.auth import get_user_model
from Profile.models import ClientProfile,FreelancerProfile
from .models import *

User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'avatar']

    def get_avatar(self, obj):
        # Try to get client profile picture
        if hasattr(obj, 'client_profile') and obj.client_profile and obj.client_profile.profile_picture:
            return self._build_url(obj.client_profile.profile_picture.url)
        # Try to get freelancer profile picture
        if hasattr(obj, 'freelancer_profile') and obj.freelancer_profile and obj.freelancer_profile.profile_picture:
            return self._build_url(obj.freelancer_profile.profile_picture.url)
        # Fallback: generate avatar from initials
        name = (obj.first_name or '') + ' ' + (obj.last_name or '')
        if not name.strip():
            name = obj.username
        # ui-avatars.com API
        return f"https://ui-avatars.com/api/?name={name.strip().replace(' ', '+')}&background=random"

    def _build_url(self, path):
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(path)
        return path

class LastMessageSerializer(serializers.ModelSerializer):
    sender = UserShortSerializer()
    class Meta:
        model = Message
        fields = ['id', 'content', 'created_at', 'sender']

class ConversationListSerializer(serializers.ModelSerializer):
    # For 1-to-1, show the other user; for group, show group name/avatar
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    lastMessage = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    lastActive = serializers.SerializerMethodField()
    isGroup = serializers.BooleanField(source='is_group')

    class Meta:
        model = Conversation
        fields = ['id', 'name', 'avatar', 'lastMessage', 'unread', 'lastActive', 'isGroup']

    def get_name(self, obj):
        user = self.context['request'].user
        if obj.is_group:
            return getattr(obj, 'group_name', 'Group Chat')
        # 1-to-1: show the other participant's name
        other = obj.participants.exclude(user=user).first()
        if other:
            return other.user.get_full_name() or other.user.username
        return "Unknown"

    def get_avatar(self, obj):
        user = self.context['request'].user
        if obj.is_group:
            return getattr(obj, 'group_avatar', None)
        # 1-to-1: show the other participant's avatar using UserShortSerializer logic
        other = obj.participants.exclude(user=user).first()
        if other:
            # Use the same serializer to get the avatar (with context for absolute URL)
            return UserShortSerializer(other.user, context=self.context).data.get('avatar')
        return None

    def get_lastMessage(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                "id": last_msg.id,
                "content": last_msg.content,
                "created_at": last_msg.created_at,
                "sender": {
                    "id": last_msg.sender.id,
                    "username": last_msg.sender.username,
                }
            }
        return None

    def get_unread(self, obj):
        user = self.context['request'].user
        # Count messages that are NOT from the current user,
        # and for which a 'seen' status does NOT exist for the current user.
        unread_count = Message.objects.filter(
            conversation=obj
        ).exclude(
            sender=user
        ).exclude(
            statuses__user=user,
            statuses__status='seen'
        ).count()
        return unread_count

    def get_lastActive(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return last_msg.created_at
        return obj.updated_at

class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    isGroup = serializers.BooleanField(source='is_group')

    class Meta:
        model = Conversation
        fields = [
            'id',
            'isGroup',
            'participants',
            'created_at',
            'updated_at',
            'is_archived',
        ]

    def get_participants(self, obj):
        # Return a list of User objects for all participants
        users = [cp.user for cp in obj.participants.all()]
        return UserShortSerializer(users, many=True, context=self.context).data

class MessageSerializer(serializers.ModelSerializer):
    sender = UserShortSerializer(read_only=True)
    reply_to = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'conversation',
            'sender',
            'content',
            'file',
            'reply_to',
            'type',
            'created_at',
            'updated_at',
            'is_deleted_for_everyone',
            'is_archived',
            'archived_at',
            'status',
        ]
        read_only_fields = ['id', 'sender', 'created_at', 'updated_at']

    def get_status(self, obj):
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return 'sent'

        if obj.sender == user:
            # For messages sent by the user, check if all recipients have seen it
            other_participants = obj.conversation.participants.exclude(user=user)
            if not other_participants.exists():
                return 'sent'
            # If all have seen
            seen_by_all = all(
                MessageStatus.objects.filter(message=obj, user=p.user, status='seen').exists()
                for p in other_participants
            )
            if seen_by_all:
                return 'seen'
            # If at least one has delivered but not seen, return 'delivered'
            delivered_to_any = any(
                MessageStatus.objects.filter(message=obj, user=p.user).exists()
                for p in other_participants
            )
            if delivered_to_any:
                return 'delivered'
            return 'sent'
        else:
            # For messages received by the user, check if they have seen it
            has_seen = MessageStatus.objects.filter(message=obj, user=user, status='seen').exists()
            return 'seen' if has_seen else 'delivered'

    def get_reply_to(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'content': obj.reply_to.content,
                'file': obj.reply_to.file.url if obj.reply_to.file else None,
                'sender': {
                    'id': obj.reply_to.sender.id,
                    'username': obj.reply_to.sender.username,
                    'first_name': obj.reply_to.sender.first_name,
                    'last_name': obj.reply_to.sender.last_name,
                },
            }
        return None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def to_representation(self, instance):
        request = self.context.get('request')
        if request and (instance.is_deleted_for_everyone or request.user in instance.is_deleted_for_me.all()):
            return None  # Skip serialization for deleted messages
        return super().to_representation(instance)

class MessagePinSerializer(serializers.ModelSerializer):
    message = MessageSerializer(read_only=True)
    pinned_by = UserShortSerializer(read_only=True)
    class Meta:
        model = MessagePin
        fields = ['id', 'conversation', 'message', 'pinned_by', 'pinned_at']

class MessageReactionSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'emoji', 'reacted_at']

class MessageStatusSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    class Meta:
        model = MessageStatus
        fields = ['id', 'message', 'user', 'status', 'updated_at']

class ConversationParticipantSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    class Meta:
        model = ConversationParticipant
        fields = ['id', 'conversation', 'user', 'joined_at', 'last_read_at', 'is_deleted', 'role']