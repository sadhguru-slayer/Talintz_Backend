from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.models import Project, User
from core.models import Skill
from .models import Event
from django.db.models import Count, Avg, Case, When, IntegerField, Q, Value
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from Profile.models import VerificationDocument
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from Profile.serializers import ClientProfilePartialUpdateSerializer
from core.models import Bid
from django.db.models import Min, Max
from OBSP.models import OBSPAssignment, OBSPResponse
from Profile.models import FreelancerProfile
from .serializers import FreelancerProfileListSerializer,FreelancerUserListSerializer

class CHomePageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        active_projects = Project.objects.filter(client=user, status='ongoing').count()
        total_spent = sum(project.total_spent for project in Project.objects.filter(client=user))
        pending_tasks = sum(project.get_pending_tasks() for project in Project.objects.filter(client=user))

        # Fetch trending skills
        trending_skills = Skill.objects.annotate(
            demand=Count('projects') + Count('tasks')  # Count projects and tasks associated with each skill
        ).order_by('-demand')[:5]
        # Fetch top freelancers
        top_freelancers = User.objects.filter(role='freelancer').annotate(avg_rating=Avg('freelancer_profile__average_rating')).order_by('-avg_rating')[:5]

        # Fetch recent success stories
        success_stories = Project.objects.filter(status='completed').order_by('-created_at')[:5]
        
        response_data = {
            'active_projects': active_projects,
            'total_spent': total_spent,
            'pending_tasks': pending_tasks,
            'trending_skills': [{'name': skill.name, 'demand': skill.demand} for skill in trending_skills],
            'top_freelancers': [
                {
                    'id': freelancer.id,
                    'name': freelancer.username,
                    'rating': freelancer.freelancer_profile.average_rating,
                    'avatar': freelancer.freelancer_profile.profile_picture.url if freelancer.freelancer_profile.profile_picture else None
                } for freelancer in top_freelancers
            ],
            'success_stories': [
                {
                    'title': project.title,
                    'description': project.description,
                    'budget': project.budget,
                    'freelancers': [{'id': freelancer.id, 'username': freelancer.username} for freelancer in project.assigned_to.all()]
                } for project in success_stories
            ],
        }

        return Response(response_data)

from core.models import BidItem
class ClientBidsOverviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Fetch all projects posted by this client
        projects = Project.objects.filter(client=user)
        
        response_data = []
        
        for project in projects:
            # Get all bids for this project (direct project bids and task bids)
            project_bids = Bid.objects.filter(
                Q(project=project) | 
                Q(tasks__project=project)
            ).select_related(
                'freelancer', 
                'project'
            ).prefetch_related(
                'tasks', 
                'attachments'
            ).distinct()
            
            if not project_bids.exists():
                continue  # Skip projects with no bids
                
            # Group bids by freelancer
            freelancer_bids = {}
            for bid in project_bids:
                freelancer_id = bid.freelancer.id
                if freelancer_id not in freelancer_bids:
                    completed_projects = bid.freelancer.freelancer_profile.total_projects_completed if hasattr(bid.freelancer, 'freelancer_profile') else 0
                    freelancer_bids[freelancer_id] = {
                        'freelancer': {
                            'id': bid.freelancer.id,
                            'name': bid.freelancer.get_full_name() or bid.freelancer.username,
                            'avatar': bid.freelancer.freelancer_profile.profile_picture.url if hasattr(bid.freelancer, 'freelancer_profile') and bid.freelancer.freelancer_profile.profile_picture else None,
                            'rating': bid.freelancer.freelancer_profile.average_rating if hasattr(bid.freelancer, 'freelancer_profile') else None,
                            'completedProjects': completed_projects,
                            'country': bid.freelancer.freelancer_profile.addresses.first().country if hasattr(bid.freelancer, 'freelancer_profile') and bid.freelancer.freelancer_profile.addresses.exists() else None,
                        },
                        'bids': []
                    }

                duration = bid.proposed_end - bid.proposed_start
                proposal = BidItem.objects.filter(bid=bid).first()
                
                # Get all tasks for this bid
                task_list = []
                if bid.tasks.exists():
                    for task in bid.tasks.all():
                        task_list.append({
                            'id': task.id,
                            'title': task.title,
                            'budget': task.budget
                        })
                
                bid_data = {
                    'id': bid.id,
                    'price': bid.total_value,
                    'days': duration.days,
                    'description': proposal.description if proposal else "",
                    'state': bid.state,
                    'created_at': bid.created_at,
                    'is_task_bid': bid.project.is_collaborative,
                    'tasks': task_list,  # Now sending a list of all tasks
                    'task_count': len(task_list)
                }
                
                freelancer_bids[freelancer_id]['bids'].append(bid_data)
            
            # Calculate project-level statistics
            total_bids = project_bids.count()
            avg_bid = project_bids.aggregate(avg=Avg('total_value'))['avg'] or 0
            min_bid = project_bids.aggregate(min=Min('total_value'))['min'] or 0
            max_bid = project_bids.aggregate(max=Max('total_value'))['max'] or 0
            
            project_data = {
                'id': project.id,
                'name': project.title,
                'description': project.description,
                'deadline': project.deadline,
                'status': project.status,
                'budget': project.budget,
                'created_at': project.created_at,
                'is_collaborative': project.is_collaborative,
                'totalBids': total_bids,
                'avgBid': avg_bid,
                'minBid': min_bid,
                'maxBid': max_bid,
                'freelancer_bids': list(freelancer_bids.values())
            }
            
            response_data.append(project_data)
        
        return Response(response_data)

class FreelancerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tab = request.query_params.get('tab', 'all')
        user = request.user

        if tab == 'previous':
            freelancers = User.objects.filter(
                role='freelancer'
            ).filter(
                Q(projects_assigned__client=user, projects_assigned__status__in=['ongoing', 'completed']) |
                Q(obsp_assignments__obsp_response__client=user, obsp_assignments__status__in=['assigned', 'in_progress', 'review', 'completed'])
            ).distinct()
        else:
            freelancers = User.objects.filter(role='freelancer')

        # Now you can annotate as before
        freelancers = freelancers.annotate(
            has_bio=Case(
                When(freelancer_profile__bio__isnull=False, freelancer_profile__bio__gt='', then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            has_hourly_rate=Case(
                When(freelancer_profile__hourly_rate__isnull=False, freelancer_profile__hourly_rate__gt=0, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            skill_count=Count('freelancer_profile__skills', distinct=True)
        ).annotate(
            is_filled=Case(
                When(
                    has_bio=1,
                    has_hourly_rate=1,
                    skill_count__gt=0,
                    then=Value(1)
                ),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-is_filled', 'id')

        freelancers = freelancers.select_related('freelancer_profile').prefetch_related('freelancer_profile__skills')

        serializer = FreelancerUserListSerializer(freelancers, many=True)
        return Response(serializer.data)