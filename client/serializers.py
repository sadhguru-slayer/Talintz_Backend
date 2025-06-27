from rest_framework import serializers
from .models import Event,Activity
from Profile.models import VerificationDocument, FreelancerProfile, Skill
from core.models import User

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields='__all__'

from core.serializers import SkillSerializer
class FreelancerProfileListSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = FreelancerProfile
        fields = [
            'bio', 'hourly_rate', 'total_projects_completed',
            'response_time_avg', 'success_rate', 'skills'
        ]

class FreelancerUserListSerializer(serializers.ModelSerializer):
    freelancer_profile = FreelancerProfileListSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'freelancer_profile']

