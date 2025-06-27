from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'password']
        extra_kwargs = {'password': {'write_only': True}}


class ConnectionSerializer(serializers.ModelSerializer):
    from_user = serializers.StringRelatedField()

    to_user = serializers.StringRelatedField()

    class Meta:
        model = Connection
        fields = ['from_user', 'to_user', 'status']

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Optional: Include additional user fields in the JWT token, e.g., role
        user = self.user
        data['role'] = user.role  # Add role to the response payload
        return data
    

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = '__all__'  # Assuming Skill has fields 'id' and 'name'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'  # Assuming Category has fields 'id' and 'name'

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'  # Assuming User has fields 'id', 'username', 'email'

class MilestoneCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['title', 'milestone_type', 'amount', 'due_date', 'is_automated']
        extra_kwargs = {
            'due_date': {
                'required': False,
                'allow_null': True
            }
        }

    def validate_due_date(self, value):
        """Set default to 1 week from now if not provided"""
        if not value:
            return timezone.now() + timezone.timedelta(weeks=1)
        return value

class MilestoneSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        print(f"Serializing milestone: {instance.id} - {instance.title}")
        return super().to_representation(instance)

    class Meta:
        model = Milestone
        fields = ['title', 'milestone_type', 'amount', 'due_date', 'is_automated', 'status']

class ProjectSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        print("ProjectSerializer initialized")  # Debug
        super().__init__(*args, **kwargs)
    
    domain = serializers.StringRelatedField()
    skills_required = SkillSerializer(many=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    tasks = serializers.SerializerMethodField()
    

    def to_representation(self, instance):
        print(f"Serializing project: {instance.id} - {instance.title}")
        print(f"Project skills: {instance.skills_required.all()}")
        print(f"Project milestones: {instance.milestones.all()}")
        print(f"Project tasks: {instance.tasks.all()}")
        return super().to_representation(instance)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'budget', 'deadline', 
            'domain', 'is_collaborative', 'skills_required', 
            'milestones', 'tasks', 'payment_strategy', 'status'
        ]

    def get_tasks(self, obj):
        print(f"Getting tasks for project: {obj.id}")
        tasks = obj.tasks.all()
        print(f"Found {tasks.count()} tasks")
        return TaskSerializer(tasks, many=True, context=self.context).data

class TaskSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        print("TaskSerializer initialized")  # Debug
        super().__init__(*args, **kwargs)
    skills_required_for_task = SkillSerializer(many=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False
    )

    def to_representation(self, instance):
        print(f"Serializing task: {instance.id} - {instance.title}")
        print(f"Task skills: {instance.skills_required_for_task.all()}")
        print(f"Assigned users: {instance.assigned_to.all()}")
        return super().to_representation(instance)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'budget', 'deadline', 
            'assigned_to', 'status', 'payment_status', 
            'skills_required_for_task'
        ]
        read_only_fields = ['status', 'payment_status']


class TaskCreateSerializer(serializers.ModelSerializer):
    skills_required_for_task = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True)
    milestones = serializers.PrimaryKeyRelatedField(queryset=Milestone.objects.all(), many=True, required=False)

    class Meta:
        model = Task
        fields = ['title', 'description', 'budget', 'deadline', 'status', 
                 'skills_required_for_task', 'milestones']



class ProjectCreateSerializer(serializers.ModelSerializer):
    tasks = TaskCreateSerializer(many=True, required=False)
    skills_required = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    milestones = MilestoneCreateSerializer(many=True, required=False)

    class Meta:
        model = Project
        fields = ['title', 'description', 'budget', 'deadline', 'domain', 
                'is_collaborative', 'skills_required', 'milestones', 'tasks']
        extra_kwargs = {
            'domain': {'required': True}
        }

    def create(self, validated_data):
        # Convert domain ID to Category instance
        validated_data['domain'] = Category.objects.get(id=validated_data['domain'])
        return super().create(validated_data)

class SpendingDistributionByProjectSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.title')  # Get the project title
    task_title = serializers.CharField(source='task.title', required=False)  # Get the task title (may not exist)
    task_id = serializers.IntegerField(source='task.id', required=False)  # Get the task ID (may not exist)
    project_id = serializers.IntegerField(source='project.id')  # Get the project ID
    
    from_user = serializers.StringRelatedField()  # or use PrimaryKeyRelatedField if only ID is needed
    to_user = serializers.StringRelatedField()    # same as above
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    status = serializers.ChoiceField(choices=Payment.STATUS_CHOICES)
    payment_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")  # Customize as needed
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=10)
    installment_period = serializers.CharField(max_length=50, required=False)
    discount_promo = serializers.CharField(max_length=50, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Payment
        fields = [
            'from_user', 'to_user', 'project_name', 'task_title', 'task_id', 'project_id', 'amount', 
            'payment_method', 'status', 'payment_date', 'currency', 'installment_period', 'discount_promo', 
            'notes', 'invoice_number', 'transaction_id'
        ]



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title','type', 'related_model_id', 'notification_text', 'is_read', 'created_at']

# Basic serializers for nested objects
class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class SimpleSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

# Response serializers (for returning data after creation)
class MilestoneResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['id', 'title', 'milestone_type', 'amount', 'due_date', 'is_automated', 'status']

class TaskResponseSerializer(serializers.ModelSerializer):
    skills_required_for_task = SimpleSkillSerializer(many=True, read_only=True)
    assigned_to = SimpleUserSerializer(many=True, read_only=True)
    milestones = MilestoneResponseSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'budget', 'deadline', 
            'assigned_to', 'status', 'payment_status', 
            'skills_required_for_task', 'milestones'
        ]

class ProjectResponseSerializer(serializers.ModelSerializer):
    domain = CategorySerializer(read_only=True)
    skills_required = SimpleSkillSerializer(many=True, read_only=True)
    milestones = MilestoneResponseSerializer(many=True, read_only=True)
    tasks = TaskResponseSerializer(many=True, read_only=True, source='tasks.all')
    client = SimpleUserSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'budget', 'deadline', 
            'domain', 'is_collaborative', 'skills_required', 
            'milestones', 'tasks', 'payment_strategy', 'client','pricing_strategy',
            'status', 'created_at',"max_hours","estimated_hours","hourly_rate",'complexity_level'
        ]

class ProjectPricingSerializer(serializers.ModelSerializer):
    pricing_display = serializers.ReadOnlyField(source='get_pricing_display')
    estimated_cost = serializers.ReadOnlyField(source='get_estimated_cost')
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'budget', 'deadline', 'client',
            'pricing_strategy', 'hourly_rate_min', 'hourly_rate_max', 'estimated_hours',
            'fixed_price', 'milestone_budget', 'currency', 'payment_terms',
            'pricing_display', 'estimated_cost', 'status', 'created_at',
            'domain', 'skills_required', 'is_talentrise_friendly', 'complexity_level',
            'is_multi_freelancer', 'estimated_time_saved'
        ]
        read_only_fields = ['id', 'created_at', 'pricing_display', 'estimated_cost']

    def validate(self, data):
        """Custom validation for pricing strategy"""
        pricing_strategy = data.get('pricing_strategy')
        
        if pricing_strategy == 'hourly':
            if not data.get('hourly_rate_min') or not data.get('hourly_rate_max'):
                raise serializers.ValidationError("Hourly rate min and max are required for hourly projects")
            if data.get('hourly_rate_min', 0) > data.get('hourly_rate_max', 0):
                raise serializers.ValidationError("Minimum hourly rate cannot be greater than maximum hourly rate")
            if not data.get('estimated_hours'):
                raise serializers.ValidationError("Estimated hours are required for hourly projects")
                
        elif pricing_strategy == 'fixed':
            if not data.get('fixed_price'):
                raise serializers.ValidationError("Fixed price is required for fixed price projects")
                
        elif pricing_strategy == 'milestone':
            if not data.get('milestone_budget'):
                raise serializers.ValidationError("Milestone budget is required for milestone projects")
        
        return data

class InvitationSerializer(serializers.ModelSerializer):
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)
    related_object_type = serializers.CharField(source='content_type.model', read_only=True)
    related_object_id = serializers.IntegerField(source='object_id', read_only=True)
    
    class Meta:
        model = Invitation
        fields = [
            'id', 'invitation_type', 'status', 'from_user', 'to_user',
            'from_user_name', 'to_user_name', 'title', 'message', 'terms',
            'expires_at', 'created_at', 'updated_at', 'responded_at',
            'response_message', 'response_terms', 'is_urgent', 'priority_level',
            'related_object_type', 'related_object_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'responded_at']

