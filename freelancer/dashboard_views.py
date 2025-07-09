from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import Project, User,Bid
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core.models import Project, Task
from Profile.models import FreelancerProfile
from core.serializers import ProjectResponseSerializer, TaskResponseSerializer  # Adjust import as needed
from core.models import Bid
from rest_framework import serializers
from workspace.models import Workspace, WorkspaceParticipant

class BidHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bid
        fields = [
            'id', 'bid_type', 'state', 'total_value', 'currency',
            'estimated_hours', 'hourly_rate', 'proposed_start', 'proposed_end', 'created_at'
        ]

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def assigned_projects(request):
    user = request.user
    projects = Project.objects.filter(assigned_to=user).select_related('client')
    data = []
    for project in projects:
        data.append({
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "deadline": project.deadline.isoformat() if project.deadline else None,
            "status": project.status,
            "client": {
                "id": project.client.id,
                "username": project.client.username,
            }
        })
    return Response(data, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def freelancer_workspaces(request):
    user = request.user
    workspaces = Workspace.objects.filter(participants__user=user).distinct().order_by('-created_at')
    data = []
    for ws in workspaces:
        content_object = ws.content_object
        # Default values
        title = None
        workspace_type = None
        status = None
        budget = None
        deadline = None

        # Project workspace
        if hasattr(content_object, 'milestones'):
            title = getattr(content_object, "title", None)
            workspace_type = "project"
            status = getattr(content_object, "status", None)
            budget = getattr(content_object, "budget", None)
            deadline = getattr(content_object, "deadline", None)
        # OBSP workspace
        elif hasattr(content_object, 'template'):
            try:
                obsp_level = content_object.template.levels.get(level=content_object.selected_level)
                title = obsp_level.name
            except Exception:
                title = getattr(content_object.template, "title", None)
            workspace_type = "obsp"
            status = getattr(content_object, "status", None)
            budget = getattr(content_object, "total_price", None)
            assignment = content_object.get_active_assignment() if hasattr(content_object, "get_active_assignment") else None
            if assignment and hasattr(assignment, "assigned_at"):
                deadline = assignment.assigned_at
            else:
                deadline = None

        # Participants
        participants = [
            {
                "id": p.user.id,
                "username": p.user.username,
                "role": p.role,
            }
            for p in ws.participants.all()
        ]

        data.append({
            "id": ws.id,
            "content_type": ws.content_type.model,
            "object_id": ws.object_id,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
            "is_active": ws.is_active,
            "title": title,
            "type": workspace_type,
            "status": status,
            "budget": float(budget) if budget is not None else None,
            "deadline": deadline.isoformat() if deadline else None,
            "participants": participants,
        })
    return Response(data, status=200)


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
            
            # Add bidding history for this freelancer
            bids = Bid.objects.filter(project=project, freelancer=request.user).order_by('-created_at')
            bidding_history = BidHistorySerializer(bids, many=True).data
            project_data['bidding_history'] = bidding_history

            # Add assignment status and assigned freelancers
            project_data['is_assigned'] = project.assigned_to.exists()
            project_data['assigned_freelancers'] = [
                {
                    'id': user.id,
                    'name': user.username,
                    'avatar': profile_user.profile_picture.url if profile_user.profile_picture else None,
                    'rating': profile_user.average_rating if profile_user.average_rating else 0
                }
                for user in project.assigned_to.all()
                if (profile_user := FreelancerProfile.objects.filter(user=user).first())
            ]
            
            # Workspace logic
            is_workspace_available = False
            workspace_id = None

            if project.status in ["ongoing", "completed"]:
                has_accepted_bid = Bid.objects.filter(
                    project=project,
                    freelancer=request.user,
                    state="accepted"
                ).exists()
                if has_accepted_bid:
                    workspaces = Workspace.objects.filter(
                        object_id=project.id,
                        content_type__model="project",
                        participants__user=request.user
                    ).distinct()
                    if workspaces.exists():
                        is_workspace_available = True
                        workspace_id = workspaces.first().id

            project_data["is_workspace_available"] = is_workspace_available
            project_data["workspace_id"] = workspace_id

            return Response(project_data)
        except Project.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

