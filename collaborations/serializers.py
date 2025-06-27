from rest_framework import serializers
from .models import Collaboration, CollaborationMembership, CollaborationInvitation
from core.models import User  # Assuming User is in the 'core' app

class CollaborationSerializer(serializers.ModelSerializer):
    admin = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all(), many=True)  # to get a list of usernames

    class Meta:
        model = Collaboration
        fields = ['id', 'collaboration_name', 'collaboration_description', 'collaboration_type', 'STATUS', 'admin', 'created_at']

    def validate_status(self, value):
        """Ensure that the status is one of the valid choices."""
        if value not in dict(Collaboration.STATUS_CHOICES):
            raise serializers.ValidationError("Invalid status choice")
        return value
class CollaborationMembershipSerializer(serializers.ModelSerializer):
    collaboration_name = serializers.CharField(source='collaboration.collaboration_name')
    user_username = serializers.CharField(source='user.username')  # To get username instead of user id
    role = serializers.CharField()

    class Meta:
        model = CollaborationMembership
        fields = ['id', 'collaboration_name', 'user_username', 'role', 'join_date']

    def validate_role(self, value):
        """Ensure that the role is either 'admin' or 'collaborator'."""
        if value not in ['admin', 'collaborator']:
            raise serializers.ValidationError("Role must be either 'admin' or 'collaborator'")
        return value
    
class CollaborationInvitationSerializer(serializers.ModelSerializer):
    collaboration_name = serializers.CharField(source='collaboration.collaboration_name')
    sender_username = serializers.CharField(source='sender.username')  # Sender's username
    receiver_username = serializers.CharField(source='receiver.username')  # Receiver's username

    class Meta:
        model = CollaborationInvitation
        fields = ['id', 'collaboration_name', 'sender_username', 'receiver_username', 'status', 'created_at']

    def validate_status(self, value):
        """Ensure that the status is one of the valid choices."""
        if value not in dict(CollaborationInvitation.STATUS_CHOICES):
            raise serializers.ValidationError("Invalid status choice")
        return value
