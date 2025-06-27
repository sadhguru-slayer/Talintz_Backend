from django.shortcuts import render,get_object_or_404
# Create your views here.
from .serializers import EventSerializer,ActivitySerializer
from core.serializers import ProjectSerializer,TaskSerializer,SpendingDistributionByProjectSerializer,ProjectResponseSerializer,TaskResponseSerializer
from .models import Event,Activity
from core.models import Project,Task,Payment
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authentication import TokenAuthentication
from rest_framework.views import APIView
from rest_framework import viewsets,status,generics
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncWeek, TruncYear,ExtractWeekDay
import calendar
from datetime import timedelta
from collaborations.models import *
from collaborations.serializers import *
from collections import defaultdict
from core.models import Bid, BidNegotiationLog
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from core.models import Invitation, Notification
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


from collections import defaultdict
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from .models import Event, Activity
from .serializers import EventSerializer
from django.shortcuts import get_object_or_404


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    # Override the `get_queryset` method to filter events by the authenticated user
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user)

    def check_if_client(self, user):
        # Check if the user has a 'client' role
        if user.role != 'client':
            return False
        return True

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def create_event(self, request):
        user = request.user

        # Check if user is a client
        if not self.check_if_client(user):
            return Response({'error': 'You are not authorized to create an event'}, status=403)

        event_data = request.data.copy()
        event_data['user'] = user.id

        # Make sure notification_time is present and properly handled
        notification_time = event_data.get('notification_time')
        if notification_time:
            event_data['notification_time'] = int(notification_time)  # Ensure it's an integer in minutes
        
        serializer = self.get_serializer(data=event_data)
        if serializer.is_valid():
            serializer.save()

            # Create Activity for event creation
            Activity.objects.create(
                user=user,
                activity_type='event_created',
                description=f'Created Event: {serializer.validated_data["title"]}',
                related_model='event',
                related_object_id=serializer.instance.id
            )

            return Response(serializer.data, status=201)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def get_events(self, request):
        user = request.user

        # Check if user is a client
        if not self.check_if_client(user):
            return Response({'error': 'You are not authorized to view events'}, status=403)

        events = self.get_queryset()  # Get user-specific events
        
        # Group events by type
        grouped_events = defaultdict(list)
        for event in events:
            grouped_events[event.type].append(event)
    
        # Convert grouped events to a list of dictionaries
        response_data = {
            'Meeting': [event for event in grouped_events.get('Meeting', [])],
            'Deadline': [event for event in grouped_events.get('Deadline', [])],
            'Others': [event for event in grouped_events.get('Others', [])],
        }

        # Serialize the grouped events
        serializer = self.get_serializer(response_data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated])
    def update_event(self, request):
        user = request.user

        # Check if user is a client
        if not self.check_if_client(user):
            return Response({'error': 'You are not authorized to update this event'}, status=403)

        event = get_object_or_404(Event, id=request.data.get('id'))
        
        if event.user != user:
            return Response({'error': 'You are not the owner of this event'}, status=403)

        event_data = request.data.copy()

        # Make sure notification_time is present and properly handled
        notification_time = event_data.get('notification_time')
        if notification_time:
            event_data['notification_time'] = int(notification_time)  # Ensure it's an integer in minutes

        serializer = EventSerializer(event, data=event_data, partial=True)
        
        if serializer.is_valid():
            serializer.save()

            # Create Activity for event update
            Activity.objects.create(
                user=user,
                activity_type='event_updated',
                description=f'Updated Event: {serializer.validated_data["title"]}',
                related_model='event',
                related_object_id=serializer.instance.id
            )

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post', 'delete'], permission_classes=[IsAuthenticated])
    def delete_event(self, request):
        user = request.user

        # Check if user is a client
        if not self.check_if_client(user):
            return Response({'error': 'You are not authorized to delete this event'}, status=403)

        event = get_object_or_404(Event, id=request.data.get('id'))

        if event.user != user:
            return Response({'error': 'You are not the owner of this event'}, status=403)

        # Create Activity for event deletion before deleting
        Activity.objects.create(
            user=user,
            activity_type='event_deleted',
            description=f'Deleted Event: {event.title}',
            related_model='event',
            related_object_id=event.id
        )

        event.delete()

        return Response({'message': 'Event deleted successfully'}, status=status.HTTP_200_OK)


class RecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch the most recent activities for the authenticated user
        activities = Activity.objects.filter(user=request.user).all()[:5]
        
        # Create the response data based on the activities fetched
        activity_data = [
            {
                'activity_type': activity.activity_type,
                'description': activity.description,
                'timestamp': activity.timestamp,
                'related_model': activity.related_model,
                'related_object_id': activity.related_object_id
            }
            for activity in activities
        ]
        
        # Return the data in a Response object
        return Response(activity_data, status=200)


class ActivityListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivitySerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = Activity.objects.filter(user=self.request.user)
        
        # Exclude activities with activity_type 'project' or 'payment'
        queryset = queryset.exclude(related_model__in=['project', 'payment']).order_by('-timestamp')

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class SpecifiedActivityListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ActivitySerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = Activity.objects.filter(user=self.request.user)
        # Filter by activity type if specified
        activity_type = self.request.query_params.get('activity_type', None)
        if activity_type:
            queryset = queryset.filter(related_model=activity_type).order_by('-timestamp')
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    

class PostedProjects(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        projects = Project.objects.filter(client=user).order_by('-created_at')
        
        serialized_projects = ProjectSerializer(projects, many=True)
        
        return Response(serialized_projects.data, status=200)
    
class DashBoard_Overview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Fetch the projects related to the user (client)
        projects = Project.objects.filter(client=user).order_by('-created_at')
        
        # Serialize project data
        project_summary = ProjectSerializer(projects[:8], many=True).data 
        
        # Initialize counters
        pending_tasks_count = 0
        total_spent = 0
        total_projects_last_month = 0
        completed_ahead_of_deadline = 0
        today = timezone.now()
        
        # Get the start of the week and the range for last month
        start_of_week = today - timedelta(days=today.weekday())
        start_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        end_of_last_month = today.replace(day=1) - timedelta(days=1)
        
        for project in projects:
            # Ensure that you're calling the methods, not passing the method reference
            pending_tasks_count += project.get_pending_tasks()  # Call the method with ()
            total_spent += project.total_spent        
            
            # Get tasks completed last month for each project
            tasks_last_month = Task.objects.filter(
                project=project, 
                deadline__gte=start_of_last_month, 
                deadline__lte=end_of_last_month,
                status='completed'
            )
            
            total_projects_last_month += 1
            
            for task in tasks_last_month:
                # Check if task was completed ahead of the deadline
                if task.completed_date and task.completed_date < task.deadline:
                    completed_ahead_of_deadline += 1
        
        if total_projects_last_month > 0:
            projects_ahead_percentage = (completed_ahead_of_deadline / total_projects_last_month) * 100
        else:
            projects_ahead_percentage = 0
        
        # Call the method correctly to get the count of active projects
        active_projects_count = Project.objects.filter(status='ongoing', client=user).count()

        
        # Get other data as needed
        nearest_deadlines = get_nearest_deadlines(user)
        recent_activities = get_recent_activities(user, 5)
        
        client_username = {
            'username': user.username,
        }        
        
        # Prepare the response data
        data = {
            'active_projects': active_projects_count,  # Correct: Method called
            'pending_tasks': pending_tasks_count,
            'total_spent': total_spent,
            'project_summary': project_summary,
            'nearest_deadlines': nearest_deadlines,
            'recent_activities': recent_activities,
            'tasks_due_this_week': Task.objects.filter(
                project__client=user, 
                deadline__gte=start_of_week, 
                deadline__lte=start_of_week + timedelta(days=7)
            ).count(),
            'projects_completed_ahead_last_month': projects_ahead_percentage,
            'client_username': client_username,
        }
        
        # Return the response with the data
        return Response(data)

# Get nearest deadlines function
def get_nearest_deadlines(client):
    projects_with_deadlines = Project.objects.filter(
    client=client, 
    deadline__gte=timezone.now(), 
    assigned_to__isnull=False
    ).order_by('deadline').values('id', 'title', 'deadline').distinct()[:4]
    tasks_with_deadlines = Task.objects.filter(
        project__client=client,
        deadline__gte=timezone.now(),
    assigned_to__isnull=False

    ).order_by('deadline').values('id', 'title', 'deadline').distinct()[:4]
    
    deadlines = []

    if projects_with_deadlines:
        for project in projects_with_deadlines:
            deadlines.append({
                'id': project['id'],
                'title': project['title'],
                'deadline': project['deadline'],
                'type': 'project',
            })
    
    if tasks_with_deadlines:
        for task in tasks_with_deadlines:
            deadlines.append({
                'id': task['id'],
                'title': task['title'],
                'deadline': task['deadline'],
                'type': 'task',
            })

    deadlines.sort(key=lambda x: x['deadline'])
    return deadlines

# Get recent activities function
def get_recent_activities(user, limit=None):
    if limit:
        recent_activities = Activity.objects.filter(user=user).order_by('-timestamp')[:limit]
    else:
        recent_activities = Activity.objects.filter(user=user).order_by('-timestamp')
    
    activities_data = []
    for activity in recent_activities:
        activities_data.append(ActivitySerializer(activity).data)
    
    return activities_data


class SpendingDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        user = request.user
        time_frame = request.GET.get('time_frame', 'monthly')
        data = get_spending_data(user, time_frame)
        return Response(data)
    
class SpendingDistributionByProject(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SpendingDistributionByProjectSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        user = self.request.user
        return Payment.objects.filter(from_user=user).order_by('-payment_date')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=200)

class CollaborationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, *args, **kwargs):
        user = self.request.user

        # Get all collaboration memberships for the user
        user_collaborations = CollaborationMembership.objects.filter(user=user)

        # Group collaborations by status
        active_collaborations = [membership.collaboration for membership in user_collaborations if membership.collaboration.STATUS == 'active']
        inactive_collaborations = [membership.collaboration for membership in user_collaborations if membership.collaboration.STATUS == 'inactive']
        completed_collaborations = [membership.collaboration for membership in user_collaborations if membership.collaboration.STATUS == 'completed']
        removed_collaborations = [membership.collaboration for membership in user_collaborations if membership.collaboration.STATUS == 'removed']

        # Get collaborations where the user is an admin
        admin_collaborations = Collaboration.objects.filter(admin=user)

        serialized_active = CollaborationSerializer(active_collaborations, many=True)
        serialized_inactive = CollaborationSerializer(inactive_collaborations, many=True)
        serialized_completed = CollaborationSerializer(completed_collaborations, many=True)
        serialized_removed = CollaborationSerializer(removed_collaborations, many=True)
        serialized_admin = CollaborationSerializer(admin_collaborations, many=True)

        # Return a structured response with different collaboration categories
        return Response({
            'active_collaborations': serialized_active.data,
            'inactive_collaborations': serialized_inactive.data,
            'completed_collaborations': serialized_completed.data,
            'removed_collaborations': serialized_removed.data,
            'admin_collaborations': serialized_admin.data,
        })




def get_spending_data(user, time_frame='monthly'):
    if time_frame == 'weekly':
        start_of_week = timezone.now() - timezone.timedelta(days=timezone.now().weekday())
        payments = Payment.objects.filter(from_user=user, payment_date__gte=start_of_week)

        spending_data = (
            payments.annotate(weekday=ExtractWeekDay('payment_date'))
                    .values('weekday')
                    .annotate(total_spent=Sum('amount')) 
                    .order_by('weekday')
        )

        labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        chart_data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Spend Over Time',
                    'data': [0] * 7, 
                    'borderColor': 'rgba(75,192,192,1)',
                    'fill': False,
                },
            ],
        }

        for entry in spending_data:
            day_index = entry['weekday'] - 1
            chart_data['datasets'][0]['data'][day_index] = entry['total_spent'] or 0

        weekly = chart_data

        return weekly

    elif time_frame == 'monthly':
        payments = Payment.objects.filter(from_user=user)

        spending_data = (
            payments.annotate(month=TruncMonth('payment_date'))
                    .values('month')
                    .annotate(total_spent=Sum('amount'))
                    .order_by('month')
        )

        months = [calendar.month_name[i] for i in range(1, 13)]

        chart_data = {
            'labels': months,
            'datasets': [
                {
                    'label': 'Spend Over Time',
                    'data': [0] * 12, 
                    'borderColor': 'rgba(75,192,192,1)',
                    'fill': False,
                },
            ],
        }

        for entry in spending_data:
            month_name = entry['month'].strftime('%B')
            month_index = months.index(month_name)
            chart_data['datasets'][0]['data'][month_index] = entry['total_spent'] or 0

        monthly = chart_data

        return monthly


    elif time_frame == 'yearly':
        payments = Payment.objects.filter(from_user=user)

        spending_data = (
            payments.annotate(year=TruncYear('payment_date')) 
                    .values('year')
                    .annotate(total_spent=Sum('amount'))  # Sum the payment amounts for each year
                    .order_by('year')
        )
        # Extract the starting year and the current year as integers
        start_year = min([entry['year'].year for entry in spending_data])  # Extract year from datetime
        current_year = timezone.now().year  # Get the current year
        labels = [str(year) for year in range(start_year, current_year + 1)]  # Use year range

    else:
        return {'error': 'Invalid time frame. Choose from "weekly", "monthly", or "yearly."'}

    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Spend Over Time',
                'data': [entry['total_spent'] or 0 for entry in spending_data],
                'borderColor': 'rgba(75,192,192,1)',
                'fill': False,
            },
        ],
    }

    return chart_data



# views.py
from Profile.models import FreelancerProfile
class ProjectDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, format=None):
        try:
            # Fetch the project by id
            project = Project.objects.get(id=project_id)
            tasks = Task.objects.filter(project=project)
            
            # Serialize the project and task data
            project_data = ProjectResponseSerializer(project).data
            tasks_data = TaskResponseSerializer(tasks, many=True).data
            
            # Add the tasks to the project data
            project_data['tasks'] = tasks_data
            
            # NEW: Add assignment status
            project_data['is_assigned'] = project.assigned_to.exists()
            
            project_data['assigned_freelancers'] = [
                {
                    'id': user.id,
                    'name': user.username,
                    'avatar': profile_user.profile_picture.url if profile_user.profile_picture else None,
                    'rating': profile_user.average_rating if profile_user.average_rating else 0
                }
                for user in project.assigned_to.all()
                if (profile_user := FreelancerProfile.objects.filter(user=user).first())  # Using walrus operator (Python 3.8+)
            ]

            
            return Response(project_data)
        except Project.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)


class BidsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, projectId):
        """
        Get all bids for a specific project with comprehensive details
        """
        try:
            # Verify the project belongs to the current user (client)
            project = Project.objects.get(id=projectId, client=request.user)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found or does not belong to you'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Get all bids for the project with optimized queries
        bids = Bid.objects.filter(
            project_id=projectId
        ).select_related(
            'freelancer', 
            'project',
            'freelancer__freelancer_profile'  # Optimize profile access
        ).prefetch_related(
            'attachments', 
            'items',
            'freelancer__freelancer_profile__addresses',  # Prefetch addresses
            'freelancer__freelancer_profile__skills'      # Prefetch skills
        )
        
        # Optional filter by state
        state = request.query_params.get('state')
        if state:
            bids = bids.filter(state=state)
        
        # Compute bid statistics
        from django.db.models import Avg, Min, Max, Count
        stats = {
            'totalBids': bids.count(),
            'averageBid': bids.aggregate(avg=Avg('total_value'))['avg'] or 0,
            'lowestBid': bids.aggregate(min=Min('total_value'))['min'] or 0,
            'highestBid': bids.aggregate(max=Max('total_value'))['max'] or 0,
            'bidsByState': {
                'submitted': bids.filter(state='submitted').count(),
                'under_review': bids.filter(state='under_review').count(),
                'interview_requested': bids.filter(state='interview_requested').count(),
                'interview_accepted': bids.filter(state='interview_accepted').count(),
                'interview_declined': bids.filter(state='interview_declined').count(),
                'accepted': bids.filter(state='accepted').count(),
                'rejected': bids.filter(state='rejected').count(),
                'withdrawn': bids.filter(state='withdrawn').count()
            }
        }
        
        # Structure the response data with priority sorting
        result = []
        for bid in bids.order_by('-created_at'):
            # Skip withdrawn bids unless specifically requested
            if bid.state == 'withdrawn' and not state:
                continue
                
            # Get freelancer profile data with proper error handling
            freelancer = bid.freelancer
            try:
                profile = freelancer.freelancer_profile
            except:
                # Handle case where profile doesn't exist
                profile = None
            
            # Get primary address for country
            country = None
            if profile and profile.addresses.exists():
                primary_address = profile.addresses.filter(is_primary=True).first()
                if primary_address:
                    country = primary_address.country
            
            # Get bid attachments
            attachments = []
            for attachment in bid.attachments.all():
                item = {
                    'id': attachment.id,
                    'uploaded_at': attachment.uploaded_at,
                }
                
                if attachment.file:
                    item['file_url'] = request.build_absolute_uri(attachment.file.url)
                    item['filename'] = attachment.file.name.split('/')[-1]
                    item['type'] = 'file'
                
                if attachment.url:
                    item['url'] = attachment.url
                    item['type'] = 'link'
                    
                attachments.append(item)
            
            # Check for pending invitations
            pending_invitation = None
            try:
                pending_invitation = Invitation.objects.filter(
                    content_type=ContentType.objects.get_for_model(bid),
                    object_id=bid.id,
                    status='pending',
                    from_user=request.user
                ).first()
            except:
                pass
            
            # Calculate priority score for sorting
            priority_score = 0
            if bid.state == 'interview_accepted':
                priority_score = 100  # Highest priority
            elif bid.state == 'interview_requested':
                priority_score = 50   # Medium priority
            elif bid.state == 'under_review':
                priority_score = 25   # Lower priority
            
            # Construct the bid data with proper profile information
            bid_data = {
                'id': bid.id,
                'priority_score': priority_score,
                'freelancer': {
                    'id': freelancer.id,
                    'name': freelancer.get_full_name() or freelancer.username,
                    'username': freelancer.username,
                    'avatar': request.build_absolute_uri(profile.profile_picture.url) if profile and profile.profile_picture else None,
                    'rating': profile.average_rating if profile else 0.0,
                    'country': country,  # From primary address
                    'completedProjects': profile.total_projects_completed if profile else 0,
                    'memberSince': freelancer.date_joined.strftime('%Y-%m-%d'),
                    'title': profile.title if profile else None,
                    'experienceYears': profile.experience_years if profile else None,
                    'hourlyRate': float(profile.hourly_rate) if profile and profile.hourly_rate else None,
                    'availabilityStatus': profile.availability_status if profile else 'available',
                    'profileCompletion': profile.profile_completion_percentage if profile else 0,
                    'successRate': profile.success_rate if profile else 0.0,
                    'onTimeCompletionRate': profile.on_time_completion_rate if profile else 0.0,
                    'responseRate': profile.response_rate if profile else 0.0,
                    'bio': profile.bio if profile else None,
                    'description': profile.description if profile else None,
                    'isTalentRise': profile.is_talentrise if profile else False,
                    'institution': profile.institution.name if profile and profile.institution else None,
                    'specialization': profile.specialization if profile else None,
                    'cgpa': float(profile.cgpa) if profile and profile.cgpa else None,
                },
                'bid_type': bid.bid_type,
                'state': bid.state,
                'total_value': float(bid.total_value),
                'currency': bid.currency,
                'proposed_start': bid.proposed_start,
                'proposed_end': bid.proposed_end,
                'duration': f"{(bid.proposed_end - bid.proposed_start).days} days",
                'created_at': bid.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': bid.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                'attachments': attachments,
                'version': bid.version,
                'has_pending_invitation': pending_invitation is not None,
                'invitation_type': pending_invitation.invitation_type if pending_invitation else None,
                'invitation_expires_at': pending_invitation.expires_at.isoformat() if pending_invitation else None
            }
            
            # Get bid items (notes and services)
            if bid.items.exists():
                notes = bid.items.filter(item_type='service').first()
                if notes:
                    bid_data['proposal'] = notes.description
            
            # Get freelancer skills from profile
            if profile and profile.skills.exists():
                skills = profile.skills.all()
                bid_data['skills'] = [skill.name for skill in skills[:5]]  # Limit to top 5 skills
            else:
                bid_data['skills'] = []
            
            result.append(bid_data)
        
        # Sort by priority score (highest first) then by creation date
        result.sort(key=lambda x: (-x['priority_score'], x['created_at']), reverse=True)
        
        return Response({
            'bids': result,
            'stats': stats,
            'project': {
                'id': project.id,
                'title': project.title,
                'is_collaborative': project.is_collaborative
            }
        })

# Base class for bid state changes
class BidStateChangeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        bid_id = request.data.get('bid_id')
        if not bid_id:
            return Response({'error': 'bid_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Find the bid and ensure it belongs to a project owned by this client
        bid = get_object_or_404(Bid, id=bid_id)
        
        if bid.project.client != request.user:
            return Response(
                {'error': 'You do not have permission to modify this bid'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            self.process_bid(bid, request)
            return Response({'status': 'success'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def process_bid(self, bid, request):
        # To be implemented by subclasses
        raise NotImplementedError


class AcceptBidView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        bid.accept()
        
        # Log the state change
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='bid_accepted',
            previous_state=previous_state,
            new_state='accepted',
            note=request.data.get('note', '')
        )


class RejectBidView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        bid.reject()
        
        # Log the state change
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='bid_rejected',
            previous_state=previous_state,
            new_state='rejected',
            note=request.data.get('note', '')
        )


class BidUnderReviewView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        bid.mark_under_review()
        
        # Log the state change
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='bid_under_review',
            previous_state=previous_state,
            new_state='under_review',
            note=request.data.get('note', '')
        )


class NegotiateBidView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        counter_offer = request.data.get('counter_offer')
        message = request.data.get('message', '')
        
        if not counter_offer:
            raise ValueError('Counter offer amount is required')
        
        # Set the bid state to negotiation
        bid.state = 'negotiation'
        bid.save()
        
        # Log the negotiation
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='counter_offer',
            previous_state=previous_state,
            new_state='negotiation',
            note=f"Counter offer: {counter_offer}. Message: {message}"
        )


# Add this new view class
class BidSubmittedView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        bid.mark_submitted()  # You'll need to add this method to your Bid model
        
        # Log the state change
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='bid_submitted',
            previous_state=previous_state,
            new_state='submitted',
            note=request.data.get('note', '')
        )


class BidInterviewRequestView(BidStateChangeView):
    def process_bid(self, bid, request):
        previous_state = bid.state
        bid.request_interview()
        
        # Log the state change
        BidNegotiationLog.objects.create(
            bid=bid,
            user=request.user,
            event_type='interview_requested',
            previous_state=previous_state,
            new_state='interview_requested',
            note=request.data.get('message', '')
        )

from core.serializers import InvitationSerializer
class InvitationViewSet(viewsets.ModelViewSet):
    """
    Handle invitation operations
    """
    permission_classes = [IsAuthenticated]
    serializer_class = InvitationSerializer

    def get_queryset(self):
        user = self.request.user
        return Invitation.objects.filter(
            models.Q(from_user=user) | models.Q(to_user=user)
        ).select_related(
            'from_user', 'to_user', 'content_type'
        ).prefetch_related(
            'content_type'
        )

    @action(detail=False, methods=['post'])
    def create_project_assignment(self, request):
        """Create project assignment invitation"""
        bid_id = request.data.get('bid_id')
        message = request.data.get('message', '')
        expires_in_hours = request.data.get('expires_in_hours', 24)
        
        try:
            bid = Bid.objects.get(id=bid_id)
            
            # Verify the client owns the project
            if bid.project.client != request.user:
                return Response(
                    {'error': 'You do not have permission to assign this project'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if invitation already exists
            existing_invitation = Invitation.objects.filter(
                invitation_type='project_assignment',
                content_type=ContentType.objects.get_for_model(bid),
                object_id=bid.id,
                status='pending'
            ).first()
            
            if existing_invitation:
                return Response(
                    {'error': 'An invitation for this bid already exists'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create invitation (notification will be created by signal)
            invitation = Invitation.create_project_assignment_invitation(
                bid=bid,
                message=message,
                expires_in_hours=expires_in_hours
            )
            
            return Response({
                'status': 'success',
                'invitation_id': invitation.id,
                'message': 'Project assignment invitation sent successfully'
            })
            
        except Bid.DoesNotExist:
            return Response(
                {'error': 'Bid not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def create_interview_request(self, request):
        """Create interview request invitation"""
        bid_ids = request.data.get('bid_ids', [])
        message = request.data.get('message', '')
        expires_in_hours = request.data.get('expires_in_hours', 48)
        
        created_invitations = []
        updated_bids = []
        
        try:
            for bid_id in bid_ids:
                bid = Bid.objects.get(id=bid_id)
                
                # Verify the client owns the project
                if bid.project.client != request.user:
                    continue
                
                # Check if invitation already exists
                existing_invitation = Invitation.objects.filter(
                    invitation_type='interview_request',
                    content_type=ContentType.objects.get_for_model(bid),
                    object_id=bid.id,
                    status='pending'
                ).first()
                
                if existing_invitation:
                    continue
                
                # Update bid state to interview_requested
                if bid.state == 'under_review':
                    bid.request_interview()  # This updates the bid state
                    updated_bids.append(bid.id)
                
                # Create invitation (notification will be created by signal)
                invitation = Invitation.create_interview_invitation(
                    bid=bid,
                    message=message,
                    expires_in_hours=expires_in_hours
                )
                
                created_invitations.append(invitation.id)
            
            return Response({
                'status': 'success',
                'created_invitations': len(created_invitations),
                'updated_bids': len(updated_bids),
                'message': f'Interview requests sent to {len(created_invitations)} candidates'
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Respond to an invitation (accept/decline)"""
        invitation = self.get_object()
        action = request.data.get('action')  # 'accept' or 'decline'
        response_message = request.data.get('message', '')
        response_terms = request.data.get('terms', {})
        
        try:
            if action == 'accept':
                invitation.accept(response_message, response_terms)
                return Response({
                    'status': 'success',
                    'message': 'Invitation accepted successfully'
                })
            elif action == 'decline':
                invitation.decline(response_message, response_terms)
                return Response({
                    'status': 'success',
                    'message': 'Invitation declined'
                })
            else:
                return Response(
                    {'error': 'Invalid action. Use "accept" or "decline"'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def my_invitations(self, request):
        """Get user's invitations"""
        invitation_type = request.query_params.get('type')
        status_filter = request.query_params.get('status')
        
        queryset = self.get_queryset().filter(to_user=request.user)
        
        if invitation_type:
            queryset = queryset.filter(invitation_type=invitation_type)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def sent_invitations(self, request):
        """Get invitations sent by user"""
        invitation_type = request.query_params.get('type')
        status_filter = request.query_params.get('status')
        
        queryset = self.get_queryset().filter(from_user=request.user)
        
        if invitation_type:
            queryset = queryset.filter(invitation_type=invitation_type)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@receiver(post_save, sender=Invitation)
def create_invitation_notification(sender, instance, created, **kwargs):
    """
    REMOVED: This notification creation is now handled in freelancer/signals.py
    to avoid duplicate notifications and ensure proper real-time delivery.
    """
    pass  # Remove this entire function


