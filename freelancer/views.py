from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from core.models import Project, Task, Bid, BidItem, BidAttachment, Invitation, ContentType
from core.serializers import ProjectResponseSerializer, TaskResponseSerializer
from .serializers import BidSerializer, BidItemSerializer
from Profile.serializers import FreelancerProfileSerializer
from Profile.models import FreelancerProfile
from core.serializers import ProjectSerializer, TaskSerializer
from django.http import Http404
from django.db import connection, transaction
from django.utils import timezone
import datetime
from django.db import models
import types
from django.db.models import Q
from collections import Counter
from django.db.models.functions import TruncMonth
from django.db.models import Avg, Count, Max, Min, Q, Sum
from Profile.models import FreelancerProfile
from django.contrib.auth import get_user_model
from .models import FreelancerActivity
from freelancer.obsp_eligibility import OBSPEligibilityEvaluator
from freelancer.models import FreelancerOBSPEligibility
from OBSP.models import OBSPTemplate, OBSPCriteria
User = get_user_model()

# Create your views here.

class ProjectManagementViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return both assigned projects and bid projects for the current user"""
        user = self.request.user
        
        # Get projects directly assigned to the user (Type 1)
        assigned_projects = Project.objects.filter(assigned_to=user)
        
        # Get projects where the user has submitted bids (Type 2)
        project_bid_projects = Project.objects.filter(project_bids__freelancer=user)
        task_bid_projects = Project.objects.filter(tasks__task_bids__freelancer=user)
        
        # Combine all projects and remove duplicates
        return (assigned_projects | project_bid_projects | task_bid_projects).distinct().order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def assigned_projects(self, request):
        """Get only projects assigned to the current user"""
        user = request.user
        assigned_projects = Project.objects.filter(assigned_to=user).order_by('-created_at')
        
        page = self.paginate_queryset(assigned_projects)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(assigned_projects, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def bid_projects(self, request):
        """Get only projects where the current user has submitted bids, including bid details"""
        user = request.user
        
        # Get projects where the user has submitted bids
        project_bid_projects = Project.objects.filter(project_bids__freelancer=user)
        task_bid_projects = Project.objects.filter(tasks__task_bids__freelancer=user)
        bid_projects = (project_bid_projects | task_bid_projects).distinct().order_by('-created_at')
        
        # Serialize the projects
        serializer = self.get_serializer(bid_projects, many=True)
        result = serializer.data
        
        # Add bid information to each project
        for project_data in result:
            project_id = project_data['id']
            
            # Get project bids
            project_bids = Bid.objects.filter(
                project_id=project_id,
                freelancer=user,
            ).order_by('-created_at')
            
            # Get task bids for this project
            task_bids = Bid.objects.filter(
                tasks__project_id=project_id,
                freelancer=user
            ).order_by('-created_at')
            
            # Add basic bid info
            if project_bids.exists():
                latest_bid = project_bids.first()
                project_data['bid_info'] = {
                    'id': latest_bid.id,
                    'state': latest_bid.state,
                    'total_value': float(latest_bid.total_value),
                    'created_at': latest_bid.created_at.strftime('%Y-%m-%d'),
                    'is_task_bid': False
                }
            elif task_bids.exists():
                project_data['bid_info'] = {
                    'state': 'multiple',
                    'is_task_bid': True,
                    'task_count': task_bids.count()
                }
                
                # Add brief task bid details
                task_bid_details = []
                for bid in task_bids:
                    tasks = list(bid.tasks.all())
                    if tasks:
                        task_bid_details.append({
                            'id': bid.id,
                            'task_id': tasks[0].id,
                            'task_name': tasks[0].title,
                            'state': bid.state,
                            'total_value': float(bid.total_value)
                        })
                project_data['task_bids'] = task_bid_details
        
        page = self.paginate_queryset(bid_projects)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(result)
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def latest_bid_project(self, request):
        """Get the latest project with bids from the current user"""
        user = request.user
        
        # Get projects where the user has submitted bids
        project_bid_projects = Project.objects.filter(project_bids__freelancer=user)
        task_bid_projects = Project.objects.filter(tasks__task_bids__freelancer=user)
        bid_projects = (project_bid_projects | task_bid_projects).distinct().order_by('-created_at')
        
        latest_project = bid_projects.first()
        
        if not latest_project:
            return Response({"error": "No projects found with your bids"}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        # Serialize the project
        serializer = self.get_serializer(latest_project)
        data = serializer.data
        
        # Add a flag to indicate if this is an assigned project
        data['is_assigned'] = Project.objects.filter(id=latest_project.id, assigned_to=user).exists()
        
        # If this is a collaborative project with tasks, only include tasks with user's bids
        if latest_project.is_collaborative:
            # Get only tasks from this project that have bids from the current user
            bid_tasks = Task.objects.filter(
                project=latest_project,
                task_bids__freelancer=user
            ).distinct()
            
            task_serializer = TaskResponseSerializer(bid_tasks, many=True)
            data['tasks'] = task_serializer.data
        else:
            data['tasks'] = []
            
        return Response(data)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific project with bid status and history"""
        try:
            pk = int(kwargs.get('pk'))
            
            project = Project.objects.get(id=pk)
            
            if pk == 'undefined' or not pk:
                return Response(
                    {"error": "Invalid project ID provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = self.get_serializer(project)
            data = serializer.data
            
            # Add a flag to indicate if this is an assigned project
            data['is_assigned'] = Project.objects.filter(id=project.id, assigned_to=request.user).exists()
            
            # Check for existing bid and get bid status
            existing_bid = Bid.objects.filter(
                project=project,
                freelancer=request.user,
            ).order_by('-version').first()
            
            if existing_bid:
                data['existing_bid'] = {
                    'id': existing_bid.id,
                    'state': existing_bid.state,
                    'total_value': float(existing_bid.total_value),
                    'created_at': existing_bid.created_at.isoformat(),
                    'version': existing_bid.version,
                    'can_resubmit': existing_bid.state == 'withdrawn',
                    'show_bid_button': existing_bid.state == 'withdrawn',
                    'status_message': self._get_bid_status_message(existing_bid.state)
                }
                
                # Get bid history for this project
                bid_history = Bid.objects.filter(
                    project=project,
                    freelancer=request.user
                ).order_by('-version')
                
                data['bid_history'] = [
                    {
                        'id': bid.id,
                        'version': bid.version,
                        'state': bid.state,
                        'total_value': float(bid.total_value),
                        'created_at': bid.created_at.isoformat(),
                        'status_message': self._get_bid_status_message(bid.state)
                    }
                    for bid in bid_history
                ]
            else:
                data['existing_bid'] = None
                data['bid_history'] = []
                data['show_bid_button'] = True
            
            # Check for pending assignment invitation
            pending_assignment = Invitation.objects.filter(
                invitation_type='project_assignment',
                to_user=request.user,
                status='pending',
                content_type=ContentType.objects.get_for_model(Bid),
                object_id__in=Bid.objects.filter(project=project, freelancer=request.user).values_list('id', flat=True)
            ).first()
            
            if pending_assignment:
                data['pending_assignment'] = {
                    'id': pending_assignment.id,
                    'title': pending_assignment.title,
                    'message': pending_assignment.message,
                    'expires_at': pending_assignment.expires_at.isoformat(),
                    'terms': pending_assignment.terms
                }
            else:
                data['pending_assignment'] = None

            return Response(data)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_bid_status_message(self, state):
        """Get user-friendly status message for bid state"""
        status_messages = {
            'draft': 'Draft - Not submitted yet',
            'submitted': 'Submitted - Under client review',
            'under_review': 'Under Review - Client is evaluating your proposal',
            'interview_requested': 'Interview Requested - Client wants to discuss further',
            'interview_accepted': 'Interview Accepted - You accepted the interview',
            'interview_declined': 'Interview Declined - You declined the interview',
            'accepted': 'Accepted - Congratulations! Your bid was selected',
            'withdrawn': 'Withdrawn - You can submit a new bid',
        }
        return status_messages.get(state, state.title())

class BidViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing project and task bids
    """
    serializer_class = BidSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return bids submitted by the current user"""
        return Bid.objects.filter(freelancer=self.request.user)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Submit a new bid - project-level bidding only"""
        # Basic validation
        if 'project' not in request.data:
            return Response({'error': 'Project ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        project_id = int(request.data.get('project'))
        print(f"Project ID from request: {project_id}")
        
        try:
            # Get the project
            project = Project.objects.get(id=project_id)
            
            # Validate bid type matches project pricing strategy
            project_pricing_strategy = project.pricing_strategy
            bid_type = request.data.get('bid_type', project_pricing_strategy)
            
            # Ensure bid type matches project pricing strategy
            if bid_type != project_pricing_strategy:
                return Response({
                    'error': f'Bid type must match project pricing strategy. Project is {project_pricing_strategy}, but bid is {bid_type}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate required fields based on pricing strategy
            if project_pricing_strategy == 'hourly':
                if 'hourly_rate' not in request.data:
                    return Response({'error': 'Hourly rate is required for hourly projects'}, status=status.HTTP_400_BAD_REQUEST)
                if 'estimated_hours' not in request.data:
                    return Response({'error': 'Estimated hours is required for hourly projects'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Calculate total value for hourly projects
                hourly_rate = float(request.data.get('hourly_rate'))
                estimated_hours = int(request.data.get('estimated_hours'))
                total_value = hourly_rate * estimated_hours
            else:
                # Fixed price project
                if 'total_value' not in request.data:
                    return Response({'error': 'Bid amount is required for fixed price projects'}, status=status.HTTP_400_BAD_REQUEST)
                total_value = float(request.data.get('total_value'))
                hourly_rate = None
                estimated_hours = None
            
            if 'proposed_start' not in request.data or 'proposed_end' not in request.data:
                return Response({'error': 'Start and end dates are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if there's an existing active bid for this project
            existing_bid = self.get_queryset().filter(
                project_id=project_id,
                freelancer=request.user,
                state__in=['draft', 'submitted', 'under_review', 'negotiation']
            ).first()
            
            if existing_bid:
                serializer = self.get_serializer(existing_bid)
                return Response(serializer.data, status=status.HTTP_200_OK)
            
            # Get the latest version for this project and freelancer
            latest_bid = self.get_queryset().filter(
                project_id=project_id,
                freelancer=request.user
            ).order_by('-version').first()
            
            version = 1
            if latest_bid:
                version = latest_bid.version + 1
            
            # Print debug information
            print(f"Creating {project_pricing_strategy} bid with version: {version}")
            print(f"Project ID: {project_id}")
            print(f"Freelancer ID: {request.user.id}")
            print(f"Total value: {total_value}")
            if project_pricing_strategy == 'hourly':
                print(f"Hourly rate: {hourly_rate}")
                print(f"Estimated hours: {estimated_hours}")

            # Create bid using Django ORM
            with transaction.atomic():
                # Create the bid data dictionary
                bid_data = {
                    'freelancer': request.user,
                    'project': project,
                    'bid_type': project_pricing_strategy,
                    'version': version,
                    'state': request.data.get('state', 'submitted'),
                    'total_value': total_value,
                    'currency': request.data.get('currency', 'INR'),
                    'proposed_start': request.data.get('proposed_start'),
                    'proposed_end': request.data.get('proposed_end'),
                    'delivery_buffer_days': int(request.data.get('delivery_buffer_days', 0)),
                    'last_edited_by': request.user,
                    'is_archived': False
                }
                
                # Add hourly-specific fields
                if project_pricing_strategy == 'hourly':
                    bid_data['hourly_rate'] = hourly_rate
                    bid_data['estimated_hours'] = estimated_hours
                
                # Override clean method temporarily
                original_clean = Bid.clean
                Bid.clean = lambda self: None
                
                # Save without validation
                bid = Bid(**bid_data)
                bid.save(force_insert=True)
                
                # Restore original clean method
                Bid.clean = original_clean
                
                # Create a bid item for notes if provided
                notes = request.data.get('notes')
                if notes:
                    BidItem.objects.create(
                        bid=bid,
                        item_type='service',
                        description=notes,
                        quantity=1,
                        unit_price=total_value,
                        tax_rate=0,
                        delivery_days=30
                    )
                
                # Process file attachments (max 5 files)
                files = request.FILES.getlist('files')
                print(f"Received {len(files)} file(s)")
                
                # Validate file count
                if len(files) > 5:
                    return Response({'error': 'Maximum 5 files allowed'}, status=status.HTTP_400_BAD_REQUEST)
                
                for file in files:
                    # Validate file size (10MB limit)
                    if file.size > 10 * 1024 * 1024:  # 10MB in bytes
                        return Response({'error': f'File {file.name} is too large. Maximum size is 10MB'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    print(f"Creating attachment for file: {file.name}")
                    BidAttachment.objects.create(
                        bid=bid,
                        file=file,
                        uploaded_at=timezone.now()
                    )
                
                # Process link attachments (max 5 links)
                links = request.data.get('links', [])
                if isinstance(links, str):
                    try:
                        import json
                        links = json.loads(links)
                        print(f"Parsed links from JSON: {links}")
                    except:
                        print("Failed to parse links JSON")
                        links = []
                
                # Validate link count
                if len(links) > 5:
                    return Response({'error': 'Maximum 5 links allowed'}, status=status.HTTP_400_BAD_REQUEST)
                
                if links and isinstance(links, list):
                    for link in links:
                        if link and isinstance(link, str) and link.strip():
                            print(f"Creating attachment for link: {link}")
                            BidAttachment.objects.create(
                                bid=bid,
                                url=link.strip(),
                                uploaded_at=timezone.now()
                            )
                
                # Return the created bid with attachment data
                serializer = self.get_serializer(bid)
                response_data = serializer.data
                
                # Add attachment data to the response
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
                
                response_data['attachments'] = attachments

                # Log activity for bid submission
                description = f"Submitted a {project_pricing_strategy} bid for project '{project.title}'"
                
                FreelancerActivity.log_activity(
                    freelancer=request.user,
                    activity_type='bid_submitted',
                    description=description,
                    bid=bid,
                    project=project,
                    details={
                        'bid_type': bid.bid_type,
                        'total_value': float(bid.total_value),
                        'currency': bid.currency,
                        'proposed_start': str(bid.proposed_start),
                        'proposed_end': str(bid.proposed_end),
                        'has_attachments': bid.attachments.exists(),
                        'file_count': len(files),
                        'link_count': len([l for l in links if l and l.strip()]),
                        'hourly_rate': float(bid.hourly_rate) if bid.hourly_rate else None,
                        'estimated_hours': bid.estimated_hours,
                    }
                )
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Project.DoesNotExist:
            return Response({
                'error': f'Project with ID {project_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw a submitted bid"""
        try:
            bid = self.get_object()
            
            # Check if bid can be withdrawn
            if bid.state not in ['draft', 'submitted', 'under_review', 'negotiation']:
                return Response({
                    'error': 'This bid cannot be withdrawn in its current state'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Override clean method temporarily
            original_clean = Bid.clean
            original_save = Bid.save
            
            # Replace the clean method with a no-op function
            def no_op_clean(self):
                pass
            
            # Replace the save method to skip full_clean
            def save_without_validation(self, *args, **kwargs):
                kwargs.pop('validate', None)  # Remove our custom parameter
                super(Bid, self).save(*args, **kwargs)
            
            try:
                # Monkey patch the methods
                Bid.clean = no_op_clean
                Bid.save = save_without_validation
                
                # Handle either project or task bid withdrawal
                bid.state = 'withdrawn'
                bid.save()
                
            finally:
                # Restore original methods
                Bid.clean = original_clean
                Bid.save = original_save
            
            # Add to response whether this was a task or project bid
            serializer = self.get_serializer(bid)
            data = serializer.data
            data['is_task_bid'] = bid.tasks.exists()
            
            # Include task IDs in the response for task bids
            if data['is_task_bid']:
                data['task_ids'] = list(bid.tasks.values_list('id', flat=True))
            
            # Log activity for bid withdrawal
            if data['is_task_bid']:
                task = bid.tasks.first()
                description = f"Withdrew bid for task '{task.title}' in project '{bid.project.title}'"
                
                FreelancerActivity.log_activity(
                    freelancer=request.user,
                    activity_type='bid_withdrawn',
                    description=description,
                    bid=bid,
                    project=bid.project,
                    task=task,
                    details={
                        'bid_id': bid.id,
                        'task_id': task_id,
                        'reason': request.data.get('reason', 'Not specified'),
                    }
                )
            else:
                description = f"Withdrew bid for project '{bid.project.title}'"
                
                FreelancerActivity.log_activity(
                    freelancer=request.user,
                    activity_type='bid_withdrawn',
                    description=description,
                    bid=bid,
                    project=bid.project,
                    details={
                        'bid_id': bid.id,
                        'reason': request.data.get('reason', 'Not specified'),
                        'total_value': float(bid.total_value),
                    }
                )
            
            return Response(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def for_project(self, request):
        """Get all bids for a specific project, including task-specific bids"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({'error': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a query that gets bids either directly related to the project
        # or related via a task from the project
        from django.db.models import Q
        
        # Get all bids for the project, either directly or via tasks
        bids = self.get_queryset().filter(
            # Either project_id matches OR tasks belong to this project
            Q(project_id=project_id) | Q(tasks__project_id=project_id)
        ).distinct()
        
        # Optionally filter by task
        task_id = request.query_params.get('task_id')
        if task_id:
            bids = bids.filter(tasks__id=task_id)
        
        # Optionally filter by state
        state = request.query_params.get('state')
        if state:
            bids = bids.filter(state=state)
        
        # Order by newest first
        bids = bids.order_by('-created_at')
        
        # Include task information in the response
        serializer = self.get_serializer(bids, many=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        """Resubmit a withdrawn bid with a new version"""
        try:
            old_bid = self.get_object()
            
            # Check if bid can be resubmitted
            if old_bid.state != 'withdrawn':
                return Response({
                    'error': 'Only withdrawn bids can be resubmitted'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the latest version for this project/freelancer
            latest_version = Bid.objects.filter(
                project=old_bid.project,
                freelancer=old_bid.freelancer
            ).order_by('-version').first().version
            
            # Create a new bid with incremented version
            now = timezone.now()
            new_bid = Bid(
                project=old_bid.project,
                freelancer=old_bid.freelancer,
                bid_type=request.data.get('bid_type', old_bid.bid_type),
                version=latest_version + 1,
                state='submitted',
                total_value=request.data.get('total_value', old_bid.total_value),
                currency=request.data.get('currency', old_bid.currency),
                proposed_start=request.data.get('proposed_start', old_bid.proposed_start),
                proposed_end=request.data.get('proposed_end', old_bid.proposed_end),
                delivery_buffer_days=request.data.get('delivery_buffer_days', old_bid.delivery_buffer_days),
                created_at=now,
                updated_at=now,
                last_edited_by=request.user,
                is_archived=False,
                parent_bid=old_bid
            )
            
            # Override the clean method temporarily
            original_clean = Bid.clean
            Bid.clean = lambda self: None
            
            # Save without validation
            new_bid.save(force_insert=True)
            
            # Restore the original clean method
            Bid.clean = original_clean
            
            # Copy bid items if no new notes provided
            if not request.data.get('notes'):
                # Copy items from old bid
                for old_item in old_bid.items.all():
                    BidItem.objects.create(
                        bid=new_bid,
                        item_type=old_item.item_type,
                        task=old_item.task,
                        description=old_item.description,
                        quantity=old_item.quantity,
                        unit_price=old_item.unit_price,
                        tax_rate=old_item.tax_rate,
                        delivery_days=old_item.delivery_days
                    )
            else:
                # Create a new bid item for the notes
                BidItem.objects.create(
                    bid=new_bid,
                    item_type='project',
                    description=request.data.get('notes'),
                    quantity=1,
                    
                    unit_price=float(new_bid.total_value),
                    tax_rate=0,
                    delivery_days=30  # Default value
                )
            
            # Return the created bid
            serializer = self.get_serializer(new_bid)
            
            # Log activity for bid resubmission
            description = f"Resubmitted bid for project '{new_bid.project.title}' with updated terms"
            
            FreelancerActivity.log_activity(
                freelancer=request.user,
                activity_type='bid_resubmitted',
                description=description,
                bid=new_bid,
                project=new_bid.project,
                details={
                    'original_bid_id': old_bid.id,
                    'new_bid_id': new_bid.id,
                    'previous_value': float(old_bid.total_value),
                    'new_value': float(new_bid.total_value),
                    'changes': [
                        {'field': 'total_value', 'old': float(old_bid.total_value), 'new': float(new_bid.total_value)},
                        {'field': 'proposed_start', 'old': str(old_bid.proposed_start), 'new': str(new_bid.proposed_start)},
                        {'field': 'proposed_end', 'old': str(old_bid.proposed_end), 'new': str(new_bid.proposed_end)},
                    ],
                }
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def withdraw_task_bid(self, request):
        """Withdraw a bid for a specific task"""
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': 'Task ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find the active bid for this task
            bid = self.get_queryset().filter(
                tasks__id=task_id,
                state__in=['draft', 'submitted', 'under_review', 'negotiation']
            ).first()
            
            if not bid:
                return Response({'error': 'No active bid found for this task'}, 
                               status=status.HTTP_404_NOT_FOUND)
            
            # Override clean method temporarily to bypass validation
            original_clean = Bid.clean
            original_save = Bid.save
            
            # Replace the clean method with a no-op function
            def no_op_clean(self):
                pass
            
            # Replace the save method to skip full_clean
            def save_without_validation(self, *args, **kwargs):
                kwargs.pop('validate', None)  # Remove our custom parameter
                super(Bid, self).save(*args, **kwargs)
            
            try:
                # Monkey patch the methods
                Bid.clean = no_op_clean
                Bid.save = save_without_validation
                
                # Withdraw the bid
                bid.state = 'withdrawn'
                bid.save()
                
            finally:
                # Restore original methods
                Bid.clean = original_clean
                Bid.save = original_save
            
            serializer = self.get_serializer(bid)
            data = serializer.data
            data['task_id'] = int(task_id)
            
            # Log activity for task bid withdrawal
            task = Task.objects.get(id=task_id)  # Get the task
            description = f"Withdrew bid for task '{task.title}' in project '{bid.project.title}'"
            
            FreelancerActivity.log_activity(
                freelancer=request.user,
                activity_type='bid_withdrawn',
                description=description,
                bid=bid,
                project=bid.project,
                task=task,
                details={
                    'bid_id': bid.id,
                    'task_id': task_id,
                    'reason': request.data.get('reason', 'Not specified'),
                }
            )
            
            return Response(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """Get all attachments for a specific bid"""
        bid = self.get_object()
        attachments = bid.attachments.all()
        
        data = []
        for attachment in attachments:
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
                
            data.append(item)
        
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def add_attachment(self, request, pk=None):
        """Add an attachment to a bid"""
        bid = self.get_object()
        
        # Check if the bid belongs to the current user
        if bid.freelancer != request.user:
            return Response(
                {'error': 'You can only add attachments to your own bids'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if the bid is in an editable state
        if bid.state not in ['draft', 'submitted']:
            return Response(
                {'error': 'You can only add attachments to draft or submitted bids'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process file upload
        file = request.FILES.get('file')
        url = request.data.get('url')
        
        if not file and not url:
            return Response(
                {'error': 'You must provide either a file or a URL'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attachment = BidAttachment()
        attachment.bid = bid
        
        if file:
            attachment.file = file
        if url:
            attachment.url = url
        
        attachment.save()
        
        # Log activity for adding attachment
        description = f"Added attachment to bid for project '{bid.project.title}'"
        
        FreelancerActivity.log_activity(
            freelancer=request.user,
            activity_type='bid_updated',
            description=description,
            bid=bid,
            project=bid.project,
            details={
                'action': 'add_attachment',
                'attachment_type': 'file' if file else 'link',
                'attachment_name': file.name if file else url,
            }
        )
        
        if attachment.file:
            return Response({
                'id': attachment.id,
                'file_url': request.build_absolute_uri(attachment.file.url),
                'filename': attachment.file.name.split('/')[-1],
                'uploaded_at': attachment.uploaded_at,
                'type': 'file'
            })
        else:
            return Response({
                'id': attachment.id,
                'url': attachment.url,
                'uploaded_at': attachment.uploaded_at,
                'type': 'link'
            })
    
    @action(detail=True, methods=['delete'])
    def remove_attachment(self, request, pk=None, attachment_id=None):
        """Remove an attachment from a bid"""
        if not attachment_id:
            attachment_id = request.query_params.get('attachment_id')
            if not attachment_id:
                return Response(
                    {'error': 'attachment_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        bid = self.get_object()
        
        # Check if the bid belongs to the current user
        if bid.freelancer != request.user:
            return Response(
                {'error': 'You can only remove attachments from your own bids'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if the bid is in an editable state
        if bid.state not in ['draft', 'submitted']:
            return Response(
                {'error': 'You can only modify attachments on draft or submitted bids'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            attachment = BidAttachment.objects.get(id=attachment_id, bid=bid)
            
            # Log activity for removing attachment
            description = f"Removed attachment from bid for project '{bid.project.title}'"
            
            FreelancerActivity.log_activity(
                freelancer=request.user,
                activity_type='bid_updated',
                description=description,
                bid=bid,
                project=bid.project,
                details={
                    'action': 'remove_attachment',
                    'attachment_type': 'file' if attachment.file else 'link',
                    'attachment_name': attachment.file.name.split('/')[-1] if attachment.file else attachment.url,
                }
            )
            
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BidAttachment.DoesNotExist:
            return Response(
                {'error': 'Attachment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get comprehensive statistics about the user's bidding history and performance
        """
        user = request.user
        
        # Get all bids submitted by the user
        all_bids = self.get_queryset()
        
        # Basic bid counts by state
        total_bids = all_bids.count()
        pending_bids = all_bids.filter(state__in=['draft', 'submitted', 'under_review', 'negotiation']).count()
        accepted_bids = all_bids.filter(state='accepted').count()
        rejected_bids = all_bids.filter(state='rejected').count()
        withdrawn_bids = all_bids.filter(state='withdrawn').count()
        
        # Calculate acceptance rate
        acceptance_rate = round((accepted_bids / total_bids) * 100) if total_bids > 0 else 0
        
        # Calculate average bid amount
        avg_bid_amount = all_bids.aggregate(avg=Avg('total_value'))['avg'] or 0
        
        # Get recent win rate (last 10 bids)
        # Fix: Filter before slicing
        recent_bids_count = min(10, all_bids.count())
        if recent_bids_count > 0:
            recent_accepted_count = all_bids.filter(state='accepted').order_by('-created_at')[:recent_bids_count].count()
            recent_win_rate = round((recent_accepted_count / recent_bids_count) * 100)
        else:
            recent_win_rate = 0
        
        # Get the 10 most recent bids for display (not for filtering)
        recent_bids_list = list(all_bids.order_by('-created_at')[:10])
        
        # Monthly bid trend
        monthly_trends = (
            all_bids
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                bids=Count('id'),
                accepted=Count('id', filter=Q(state='accepted'))
            )
            .order_by('month')
        )
        
        # Format monthly trends for frontend
        formatted_trends = [
            {
                'month': trend['month'].strftime('%b %Y'),
                'bids': trend['bids'],
                'accepted': trend['accepted'],
                'rate': round((trend['accepted'] / trend['bids']) * 100) if trend['bids'] > 0 else 0
            }
            for trend in monthly_trends
        ]
        
        # Get competitiveness insights
        avg_competitors = 0
        position_data = []
        
        # Calculate average position and competitors for project bids (if available)
        projects_with_multiple_bids = Project.objects.filter(
            Q(project_bids__freelancer=user) | Q(tasks__task_bids__freelancer=user)
        ).annotate(bid_count=Count('project_bids')).filter(bid_count__gt=1)
        
        total_positions = 0
        position_count = 0
        
        for project in projects_with_multiple_bids:
            # Get all bids for this project
            project_bids = project.project_bids.all()
            if project_bids.count() > 1:
                # Sort by amount to determine position
                sorted_bids = sorted(project_bids, key=lambda b: b.total_value)
                try:
                    user_bid = next(b for b in sorted_bids if b.freelancer == user)
                    position = sorted_bids.index(user_bid) + 1
                    total_positions += position
                    position_count += 1
                    position_data.append({
                        'project_name': project.title,
                        'project_id': project.id,
                        'position': position,
                        'total_bids': len(sorted_bids)
                    })
                    avg_competitors = sum(len(sorted_bids) for p in position_data) / len(position_data) if position_data else 0
                except StopIteration:
                    pass
        
        avg_position = total_positions / position_count if position_count > 0 else 0
        
        # Get high demand skills
        skill_counter = Counter()
        
        # Collect skills from projects where bids were accepted
        for bid in all_bids.filter(state='accepted'):
            if bid.project and hasattr(bid.project, 'skills_required'):
                for skill in bid.project.skills_required.all():
                    skill_counter[skill.name] += 1
        
        high_demand_skills = [skill for skill, count in skill_counter.most_common(5)]
        
        # Get optimal bid range
        successful_bids = all_bids.filter(state='accepted')
        min_value = successful_bids.aggregate(min=Min('total_value'))['min'] or 0
        max_value = successful_bids.aggregate(max=Max('total_value'))['max'] or 0
        suggested_range = f"₹{int(min_value)} - ₹{int(max_value)}" if min_value and max_value else "N/A"
        
        # Calculate median response time for accepted bids (in days)
        # This is a simplified calculation - in a real system you'd track when clients respond
        avg_response_time = "N/A"  # Would need more data in a real system
        
        # Assemble the complete statistics response
        statistics = {
            # Basic counts
            'totalBids': total_bids,
            'pendingBids': pending_bids,
            'acceptedBids': accepted_bids,
            'rejectedBids': rejected_bids,
            'withdrawnBids': withdrawn_bids,
            
            # Performance metrics
            'acceptanceRate': acceptance_rate,
            'averageBidAmount': round(avg_bid_amount),
            'recentWinRate': recent_win_rate,
            'totalEarnings': float(sum(bid.total_value for bid in successful_bids)) if successful_bids.exists() else 0,
            
            # Trends
            'monthlyTrend': formatted_trends,
            
            # Competitive analysis
            'competitivePosition': {
                'averagePosition': round(avg_position, 1) if avg_position else "N/A",
                'topPositionRate': round(sum(1 for p in position_data if p['position'] == 1) / len(position_data) * 100) if position_data else 0,
                'improvement': 0  # Would need historical data to calculate improvement
            },
            
            # Bid optimization
            'bidOptimization': {
                'suggestedRange': suggested_range,
                'successRate': acceptance_rate,
                'optimalDuration': "2-3 months"  # Would need more data to determine this accurately
            },
            
            # Market analysis
            'marketAnalysis': {
                'highDemandSkills': high_demand_skills,
                'avgResponseTime': avg_response_time,
                'competitorCount': round(avg_competitors)
            }
        }
        
        # Get recent bids with detailed information
        recent_bids_data = []
        for bid in recent_bids_list:
            # Safely get project title
            project_title = "Unknown"
            if bid.project:
                project_title = bid.project.title
            elif bid.tasks.exists():
                project_title = bid.tasks.first().project.title if bid.tasks.first().project else "Unknown"
            
            # Safely get deadline
            deadline = "N/A"
            if bid.project and hasattr(bid.project, 'deadline'):
                deadline = bid.project.deadline.strftime('%Y-%m-%d')
            
            # Safely get client rating
            client_rating = "N/A"
            if bid.project and hasattr(bid.project, 'client') and hasattr(bid.project.client, 'userprofile'):
                profile = bid.project.client.userprofile
                if hasattr(profile, 'rating') and profile.rating:
                    client_rating = round(profile.rating, 1)
            
            # Safely get skills
            skills = []
            if bid.project and hasattr(bid.project, 'skills_required'):
                skills = [skill.name for skill in bid.project.skills_required.all()]
            
            # Get competing bids and position info
            competing_bids = 0
            bid_position = 0
            for pos_data in position_data:
                if pos_data.get('project') == project_title:
                    competing_bids = pos_data.get('total_bids', 0)
                    bid_position = pos_data.get('position', 0)
                    break
            
            try:
                # Calculate project duration
                duration_days = (bid.proposed_end - bid.proposed_start).days
                project_duration = f"{duration_days} days"
            except:
                project_duration = "N/A"
            
            bid_data = {
                'id': bid.id,
                'projectName': project_title,
                'projectId': project.id,
                'bidAmount': float(bid.total_value),
                'status': bid.state.capitalize(),
                'deadline': deadline,
                'clientRating': client_rating,
                'projectDuration': project_duration,
                'competingBids': competing_bids,
                'bidPosition': bid_position,
                'skills': skills,
                'created_at': bid.created_at.strftime('%Y-%m-%d'),
            }
            recent_bids_data.append(bid_data)
        
        statistics['recentBids'] = recent_bids_data
        
        return Response(statistics)

# Add this new viewset for bid items
class BidItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bid items (notes, services, etc.)
    """
    serializer_class = BidItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return bid items related to the current user's bids"""
        return BidItem.objects.filter(bid__freelancer=self.request.user)
    
    def create(self, request, *args, **kwargs):
        # Ensure the bid belongs to the current user
        bid_id = request.data.get('bid')
        if not bid_id:
            return Response({'error': 'Bid ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            bid = Bid.objects.get(id=bid_id, freelancer=request.user )
        except Bid.DoesNotExist:
            return Response({'error': 'Bid not found or does not belong to you'}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    

class FreelancerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing freelancer data and operations
    """
    serializer_class = FreelancerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FreelancerProfile.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get freelancer's profile data"""
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except FreelancerProfile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def projects(self, request):
        """Get all projects where the freelancer is involved"""
        projects = Project.objects.filter(
            Q(assigned_to=request.user) |
            Q(tasks__assigned_to=request.user)
        ).distinct()
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active_projects(self, request):
        """Get currently active projects"""
        projects = Project.objects.filter(
            Q(assigned_to=request.user) |
            Q(tasks__assigned_to=request.user),
            status='ongoing'
        ).distinct()
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def completed_projects(self, request):
        """Get completed projects"""
        projects = Project.objects.filter(
            Q(assigned_to=request.user) |
            Q(tasks__assigned_to=request.user),
            status='completed'
        ).distinct()
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tasks(self, request):
        """Get all tasks assigned to the freelancer"""
        tasks = Task.objects.filter(assigned_to=request.user)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active_tasks(self, request):
        """Get currently active tasks"""
        tasks = Task.objects.filter(
            assigned_to=request.user,
            status='ongoing'
        )
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def bids(self, request):
        """Get all bids submitted by the freelancer"""
        bids = Bid.objects.filter(freelancer=request.user)
        serializer = BidSerializer(bids, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get freelancer's statistics with direct calculations"""
        from django.db.models import Sum, Avg, Count, F, Case, When, DecimalField, Value
        from django.db.models.functions import Coalesce
        
        try:
            # Get project statistics by direct calculation
            total_projects = Project.objects.filter(
                Q(assigned_to=request.user) |
                Q(tasks__assigned_to=request.user)
            ).distinct().count()
            
            completed_projects = Project.objects.filter(
                Q(assigned_to=request.user) |
                Q(tasks__assigned_to=request.user),
                status='completed'
            ).distinct().count()
            
            active_projects = Project.objects.filter(
                Q(assigned_to=request.user) |
                Q(tasks__assigned_to=request.user),
                status='ongoing'
            ).distinct().count()
            
            # Calculate total earnings from actual transactions
            from financeapp.models.transaction import Transaction
            
            # Get all completed transactions where the freelancer is the recipient
            earnings_data = Transaction.objects.filter(
                to_user=request.user,
                status='completed'
            ).aggregate(
                total_earnings=Coalesce(Sum('net_amount'), Value(0), output_field=DecimalField()),
                avg_payment=Coalesce(Avg('net_amount'), Value(0), output_field=DecimalField()),
                payment_count=Count('id')
            )
            
            # Get payment type distribution
            payment_types = Transaction.objects.filter(
                to_user=request.user,
                status='completed'
            ).values('payment_type').annotate(
                count=Count('id'),
                total=Sum('net_amount')
            ).order_by('-count')
            
            # Calculate on-time deliveries
            on_time_tasks = Task.objects.filter(
                assigned_to=request.user,
                status='completed',
                completed_at__lte=F('deadline')
            ).count()
            
            all_completed_tasks = Task.objects.filter(
                assigned_to=request.user,
                status='completed'
            ).count()
            
            on_time_rate = (on_time_tasks / all_completed_tasks * 100) if all_completed_tasks > 0 else 0
            
            # Get bid statistics
            total_bids = Bid.objects.filter(freelancer=request.user).count()
            accepted_bids = Bid.objects.filter(
                freelancer=request.user,
                state='accepted'
            ).count()
            
            # Calculate success rates
            bid_success_rate = (accepted_bids / total_bids * 100) if total_bids > 0 else 0
            project_completion_rate = (completed_projects / total_projects * 100) if total_projects > 0 else 0
            
            # Get profile for ratings and other details
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Format payment types for response
            payment_type_data = [
                {
                    'type': payment['payment_type'],
                    'count': payment['count'],
                    'total': float(payment['total'])
                }
                for payment in payment_types
            ]
            
            return Response({
                'total_projects': total_projects,
                'completed_projects': completed_projects,
                'active_projects': active_projects,
                'total_earnings': float(earnings_data['total_earnings']),
                'avg_payment': float(earnings_data['avg_payment']),
                'payment_count': earnings_data['payment_count'],
                'payment_types': payment_type_data,
                'average_rating': float(profile.average_rating),
                'total_bids': total_bids,
                'accepted_bids': accepted_bids,
                'bid_success_rate': bid_success_rate,
                'project_completion_rate': project_completion_rate,
                'on_time_completion_rate': float(on_time_rate),
                'response_rate': float(profile.response_rate)
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def earnings(self, request):
        """Get detailed earnings information calculated directly from transactions"""
        from django.db.models import Sum, Count
        from financeapp.models.transaction import Transaction
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        try:
            # Calculate earnings by month (last 6 months)
            end_date = timezone.now()
            start_date = end_date - timedelta(days=180)  # approximately 6 months
            
            # Monthly aggregation - SQLite compatible approach
            monthly_earnings = []
            month_data = {}
            
            # Manually aggregate by month
            for tx in Transaction.objects.filter(
                to_user=request.user,
                status='completed',
                created_at__gte=start_date
            ):
                month_key = tx.created_at.strftime('%b %Y')
                if month_key not in month_data:
                    month_data[month_key] = {
                        'total': 0,
                        'count': 0
                    }
                
                month_data[month_key]['total'] += float(tx.net_amount)
                month_data[month_key]['count'] += 1
            
            # Convert to list and sort by month
            for month, data in month_data.items():
                monthly_earnings.append({
                    'month': month,
                    'total': data['total'],
                    'count': data['count']
                })
            
            # Sort by month
            monthly_earnings.sort(key=lambda x: datetime.strptime(x['month'], '%b %Y'))
            
            # Get project-wise earnings
            project_earnings = []
            completed_projects = Project.objects.filter(
                Q(assigned_to=request.user) |
                Q(tasks__assigned_to=request.user),
                status='completed'
            ).distinct()
            
            for project in completed_projects:
                # Calculate total earnings for this project from transactions
                project_transactions = Transaction.objects.filter(
                    to_user=request.user,
                    project=project,
                    status='completed'
                )
                
                project_total = project_transactions.aggregate(total=Sum('net_amount'))['total'] or 0
                
                project_earnings.append({
                    'project_id': project.id,
                    'project_title': project.title,
                    'earnings': float(project_total),
                    'completion_date': project.deadline,
                    'transaction_count': project_transactions.count()
                })
            
            # Calculate total all-time earnings
            total_earnings = Transaction.objects.filter(
                to_user=request.user,
                status='completed'
            ).aggregate(total=Sum('net_amount'))['total'] or 0
            
            # Calculate average project value
            avg_project_value = total_earnings / len(project_earnings) if project_earnings else 0
            
            return Response({
                'total_earnings': float(total_earnings),
                'project_earnings': project_earnings,
                'monthly_earnings': monthly_earnings,
                'average_project_value': float(avg_project_value)
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Get all transactions associated with the freelancer"""
        from financeapp.models.transaction import Transaction
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        
        # Get all transactions where the freelancer is involved
        transactions = Transaction.objects.filter(
            Q(to_user=request.user) | Q(from_user=request.user)
        ).order_by('-created_at')
        
        # Get summary metrics
        received_payments = Transaction.objects.filter(
            to_user=request.user,
            status='completed'
        )
        
        sent_payments = Transaction.objects.filter(
            from_user=request.user,
            status='completed'
        )
        
        # Calculate summaries
        received_summary = received_payments.aggregate(
            total=Sum('net_amount'),
            count=Count('id')
        )
        
        sent_summary = sent_payments.aggregate(
            total=Sum('net_amount'),
            count=Count('id')
        )
        
        # Get payment type breakdown for visualization
        payment_types = received_payments.values('payment_type').annotate(
            count=Count('id'),
            total=Sum('net_amount')
        ).order_by('-total')
        
        # Get monthly breakdown for charts (last 6 months)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=180)
        
        # SQLite-compatible approach for monthly data
        monthly_data = []
        month_transactions = {}
        
        # Group transactions by month manually
        for tx in received_payments.filter(created_at__gte=start_date):
            month_key = tx.created_at.strftime('%b %Y')
            if month_key not in month_transactions:
                month_transactions[month_key] = {
                    'total': 0,
                    'count': 0
                }
            
            month_transactions[month_key]['total'] += float(tx.net_amount)
            month_transactions[month_key]['count'] += 1
        
        # Convert dictionary to list format
        for month, data in month_transactions.items():
            monthly_data.append({
                'month': month,
                'total': data['total'],
                'count': data['count']
            })
        
        # Sort by month
        monthly_data.sort(key=lambda x: timezone.datetime.strptime(x['month'], '%b %Y'))
        
        # Serialize transaction list (limited to 20 most recent)
        recent_transactions = []
        for tx in transactions[:20]:
            recent_transactions.append({
                'id': str(tx.id),
                'transaction_id': tx.transaction_id,
                'amount': float(tx.amount),
                'net_amount': float(tx.net_amount),
                'payment_type': tx.payment_type,
                'status': tx.status,
                'created_at': tx.created_at.isoformat(),
                'completed_at': tx.completed_at.isoformat() if tx.completed_at else None,
                'is_incoming': tx.to_user.id == request.user.id,
                'other_party': tx.from_user.username if tx.to_user.id == request.user.id else tx.to_user.username,
                'project_title': tx.project.title if tx.project else None,
                'task_title': tx.task.title if tx.task else None
            })
        
        return Response({
            'recent_transactions': recent_transactions,
            'received_summary': {
                'total': float(received_summary['total'] or 0),
                'count': received_summary['count'] or 0
            },
            'sent_summary': {
                'total': float(sent_summary['total'] or 0),
                'count': sent_summary['count'] or 0
            },
            'payment_types': [
                {
                    'type': pt['payment_type'],
                    'count': pt['count'],
                    'total': float(pt['total'])
                } for pt in payment_types
            ],
            'monthly_data': monthly_data
        })

    @action(detail=False, methods=['get'])
    def activities(self, request):
        """Get recent activities for the freelancer"""
        from django.db.models import Q
        
        try:
            # Get most recent 10 activities for this freelancer
            activities = FreelancerActivity.objects.filter(
                freelancer=request.user
            ).order_by('-timestamp')[:10]
            
            # Format for response
            activity_data = []
            for activity in activities:
                activity_data.append({
                    'id': activity.id,
                    'activity_type': activity.activity_type,
                    'description': activity.description,
                    'timestamp': activity.timestamp.isoformat(),
                    'time_since': activity.time_since,
                    'is_read': activity.is_read,
                    'priority': activity.priority,
                    'action_required': activity.action_required,
                    # Include related object info if available
                    'project_title': activity.project.title if activity.project else None,
                    'task_title': activity.task.title if activity.task else None,
                    'bid_id': activity.bid.id if activity.bid else None,
                })
            
            return Response(activity_data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_obsp_eligibility(request, obsp_id, level):
    """Check freelancer eligibility for specific OBSP level"""
    try:
        obsp = OBSPTemplate.objects.get(id=obsp_id, is_active=True)
        
        # Check if user is a freelancer
        if request.user.role != 'freelancer':
            return Response({
                'success': False,
                'error': 'Only freelancers can check OBSP eligibility'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Evaluate eligibility
        evaluator = OBSPEligibilityEvaluator(request.user, obsp, level)
        result = evaluator.evaluate_eligibility()
        
        # Save the result
        eligibility, created = FreelancerOBSPEligibility.objects.update_or_create(
            freelancer=request.user,
            obsp_template=obsp,
            defaults={
                'eligibility_data': result,
                'is_eligible': result['is_eligible'],
                'overall_score': result['overall_score'],
                'calculation_version': '1.0'
            }
        )
        
        return Response({
            'success': True,
            'data': result
        })
        
    except OBSPTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': 'OBSP template not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_obsp_eligibility_summary(request):
    """Get summary of freelancer's OBSP eligibility across all templates"""
    try:
        if request.user.role != 'freelancer':
            return Response({
                'success': False,
                'error': 'Only freelancers can access eligibility summary'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get all eligibility records for this freelancer
        eligibility_records = FreelancerOBSPEligibility.objects.filter(
            freelancer=request.user
        ).select_related('obsp_template')
        
        summary = {
            'total_obsps': 0,
            'eligible_obsps': 0,
            'eligible_levels': {},
            'recent_evaluations': [],
            'recommendations': []
        }
        
        for record in eligibility_records:
            summary['total_obsps'] += 1
            
            if record.is_eligible:
                summary['eligible_obsps'] += 1
                
                # Group by OBSP template
                template_name = record.obsp_template.title
                if template_name not in summary['eligible_levels']:
                    summary['eligible_levels'][template_name] = []
                
                summary['eligible_levels'][template_name].append({
                    'level': record.eligibility_data.get('level', 'unknown'),
                    'score': record.overall_score,
                    'evaluated_at': record.eligibility_data.get('evaluated_at', '')
                })
            
            # Add to recent evaluations
            summary['recent_evaluations'].append({
                'obsp_title': record.obsp_template.title,
                'level': record.eligibility_data.get('level', 'unknown'),
                'is_eligible': record.is_eligible,
                'score': record.overall_score,
                'evaluated_at': record.eligibility_data.get('evaluated_at', '')
            })
        
        # Generate recommendations
        summary['recommendations'] = self._generate_recommendations(request.user)
        
        return Response({
            'success': True,
            'data': summary
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _generate_recommendations(self, freelancer):
    """Generate recommendations for improving eligibility"""
    recommendations = []
    
    # Check project experience
    completed_projects = Project.objects.filter(
        assigned_to=freelancer,
        status='completed'
    ).count()
    
    if completed_projects < 2:
        recommendations.append({
            'type': 'project_experience',
            'message': f'Complete more projects to improve eligibility. Currently: {completed_projects} projects',
            'priority': 'high'
        })
    
    # Check ratings
    avg_rating = freelancer.freelancer_profile.average_rating
    if avg_rating < 4.0:
        recommendations.append({
            'type': 'rating',
            'message': f'Improve your average rating. Currently: {avg_rating}',
            'priority': 'high'
        })
    
    # Check skills
    skill_count = freelancer.freelancer_profile.skills.count()
    if skill_count < 5:
        recommendations.append({
            'type': 'skills',
            'message': f'Add more skills to your profile. Currently: {skill_count} skills',
            'priority': 'medium'
        })
    
    return recommendations

# Add new ViewSet for handling invitation responses
class InvitationResponseViewSet(viewsets.ViewSet):
    """Handle freelancer responses to invitations"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def respond_to_assignment(self, request, pk=None):
        """Respond to project assignment invitation"""
        invitation_id = pk
        action = request.data.get('action')  # 'accept' or 'decline'
        response_message = request.data.get('message', '')
        
        try:
            # Get the invitation
            invitation = Invitation.objects.get(
                id=invitation_id,
                to_user=request.user,
                invitation_type='project_assignment',
                status='pending'
            )
            
            if action == 'accept':
                # Accept the invitation
                invitation.accept(response_message)
                
                # Get the bid and project
                bid = invitation.bid
                project = bid.project
                
                return Response({
                    'status': 'success',
                    'message': f'Project assignment accepted! You are now assigned to "{project.title}"',
                    'project_id': project.id,
                    'project_title': project.title
                })
                
            elif action == 'decline':
                # Decline the invitation
                invitation.decline(response_message)
                
                return Response({
                    'status': 'success',
                    'message': 'Project assignment declined. You can still submit new bids for other projects.',
                })
                
            else:
                return Response(
                    {'error': 'Invalid action. Use "accept" or "decline"'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Invitation.DoesNotExist:
            return Response(
                {'error': 'Invitation not found or already responded to'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    
# Browsing Projects
    