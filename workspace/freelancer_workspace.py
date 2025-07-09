# Freelancer Workspace

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from workspace.models import Workspace, WorkspaceParticipant, WorkspaceAttachment, WorkspaceDispute, WorkspaceRevision
from core.models import Milestone, Notification, ProjectMilestoneNote
from django.contrib.contenttypes.models import ContentType
from OBSP.models import OBSPMilestone, OBSPLevel, OBSPAssignment, OBSPCriteria, OBSPAssignmentNote  # Import additional OBSP models
from django.utils import timezone
from datetime import datetime, timedelta
import re
from django.db import models
from financeapp.models import Transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from workspace.models import WorkspaceActivity,WorkspaceBox
from django.contrib.contenttypes.fields import GenericForeignKey

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def freelancer_overview(request, workspace_id):
    user = request.user
    print(f"User: {user.username}, Workspace ID: {workspace_id}")  # Debug log

    # 1. Get the workspace where the user is a freelancer participant
    try:
        workspace = Workspace.objects.get(
            id=workspace_id,
            participants__user=user,
            participants__role='freelancer'
        )
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found or access denied"}, status=404)

    # 2. Get the content object (Project or OBSPResponse)
    content_object = workspace.content_object
    print(f"Content object: {content_object}")  # Debug log

    # 3. Get participants
    participants = []
    for participant in workspace.participants.all():
        participants.append({
            "id": participant.user.id,
            "name": participant.user.username,
            "role": participant.role,
            "joined_at": participant.joined_at.isoformat(),
        })

    # 4. Get files
    files = []
    for attachment in workspace.attachments.all():
        # Use build_absolute_uri for file and link URLs
        if attachment.file:
            url = request.build_absolute_uri(attachment.file.url)
        elif attachment.link:
            url = request.build_absolute_uri(attachment.link)
        else:
            url = None

        files.append({
            "id": attachment.id,
            "name": attachment.file.name if attachment.file else "Link",
            "url": url,
            "uploaded_by": attachment.uploaded_by.username,
            "uploaded_at": attachment.uploaded_at.isoformat(),
        })

    # 5. Get disputes
    disputes = []
    for dispute in workspace.disputes.all():
        disputes.append({
            "id": dispute.id,
            "issue": dispute.issue_description,
            "status": dispute.status,
            "raised_by": dispute.raised_by.username,
            "created_at": dispute.created_at.isoformat(),
        })

    # 6. Get project details and milestones
    project_details = {}
    milestones = []

    if hasattr(content_object, 'milestones'):
        # Case: Project
        milestones_qs = content_object.milestones.all()
        
        for m in milestones_qs:
            # Get activities related to this milestone
            milestone_activities = workspace.activities.filter(
                milestone=m
            ).select_related('user').order_by('-timestamp')[:20]  # Last 20 activities
            
            # Format milestone activities
            activities = []
            for activity in milestone_activities:
                activity_data = {
                    "id": activity.id,
                    "type": activity.activity_type,
                    "type_display": activity.get_activity_type_display(),
                    "user": {
                        "id": activity.user.id,
                        "username": activity.user.username,
                    },
                    "timestamp": activity.timestamp.isoformat(),
                    "title": activity.title,
                    "description": activity.description,
                }
                
                # Add optional fields
                if activity.amount:
                    activity_data["amount"] = float(activity.amount)
                if activity.old_value and activity.new_value:
                    activity_data["status_change"] = {
                        "old": activity.old_value,
                        "new": activity.new_value,
                    }
                
                activities.append(activity_data)
            
            milestones.append({
                "id": m.id,
                "title": m.title,
                "status": m.status,
                "due": m.due_date,
                "summary": getattr(m, "description", ""),
                "instructions": getattr(m, "quality_requirements", ""),
                "deliverables": [],  # Add deliverables if available
                "amount": float(m.amount) if m.amount else 0,
                "milestone_type": m.milestone_type,
                "activities": activities,  # Add milestone-specific activities
                "activity_count": len(activities),
            })
        
        project_details = {
            "title": content_object.title,
            "description": content_object.description,
            "start_date": content_object.start_date.isoformat() if content_object.start_date else None,
            "complexity_level": content_object.complexity_level,
            "category_name": content_object.domain.name if content_object.domain else None,
            "skills_required": [skill.name for skill in content_object.skills_required.all()],
            "budget": float(content_object.budget) if content_object.budget else 0,
            "deadline": content_object.deadline.isoformat() if content_object.deadline else None,
        }

    elif hasattr(content_object, 'template'):
        # Case: OBSPResponse
        obsp_response = content_object
        template = obsp_response.template
        selected_level = obsp_response.selected_level
        
        # Get OBSP level details
        try:
            obsp_level = OBSPLevel.objects.get(template=template, level=selected_level)
            duration = obsp_level.duration
            features = obsp_level.features
            deliverables = obsp_level.deliverables
        except OBSPLevel.DoesNotExist:
            duration = "N/A"
            features = []
            deliverables = []

        # Get assignment details
        assignment = obsp_response.get_active_assignment()
        if assignment:
            assigned_at = assignment.assigned_at
            # Calculate deadline based on assignment date + duration
            try:
                duration_days = int(duration.split('-')[1].split()[0]) if '-' in duration else 14
                deadline = assigned_at + timezone.timedelta(days=duration_days)
            except:
                deadline = assigned_at + timezone.timedelta(days=14)
        else:
            assigned_at = None
            deadline = None

        # Get skills from OBSP criteria
        try:
            obsp_criteria = OBSPCriteria.objects.get(template=template, level=selected_level)
            core_skills = obsp_criteria.core_skills
            optional_skills = obsp_criteria.optional_skills
            required_skills = obsp_criteria.required_skills
        except OBSPCriteria.DoesNotExist:
            core_skills = []
            optional_skills = []
            required_skills = []

        # Get milestones for this level
        level_milestones = OBSPMilestone.objects.filter(
            template=template,
            level=obsp_level
        ).order_by('order')
        milestone_progress = obsp_response.milestone_progress or {}

        milestones = []
        current_date = assigned_at if assigned_at else timezone.now()
        
        for milestone in level_milestones:
            # Calculate deadline based on order and estimated days
            if milestone.order == 1:
                # First milestone starts from assignment date
                milestone_deadline = current_date + timezone.timedelta(days=milestone.estimated_days)
            else:
                # Subsequent milestones start from previous milestone deadline
                previous_milestone = level_milestones.filter(order=milestone.order - 1).first()
                if previous_milestone:
                    # This is simplified - in reality you'd track actual completion dates
                    milestone_deadline = current_date + timezone.timedelta(days=milestone.estimated_days)
                else:
                    milestone_deadline = current_date + timezone.timedelta(days=milestone.estimated_days)

            # Get activities related to this OBSP milestone
            milestone_activities = workspace.activities.filter(
                obsp_milestone=milestone
            ).select_related('user').order_by('-timestamp')[:20]  # Last 20 activities
            
            # Format milestone activities
            activities = []
            for activity in milestone_activities:
                activity_data = {
                    "id": activity.id,
                    "type": activity.activity_type,
                    "type_display": activity.get_activity_type_display(),
                    "user": {
                        "id": activity.user.id,
                        "username": activity.user.username,
                    },
                    "timestamp": activity.timestamp.isoformat(),
                    "title": activity.title,
                    "description": activity.description,
                }
                
                # Add optional fields
                if activity.amount:
                    activity_data["amount"] = float(activity.amount)
                if activity.old_value and activity.new_value:
                    activity_data["status_change"] = {
                        "old": activity.old_value,
                        "new": activity.new_value,
                    }
                
                activities.append(activity_data)
            milestone_id_str = str(milestone.id)
            status = milestone_progress.get(milestone_id_str, milestone.status)  # fallback to model status if not set
            milestones.append({
                "id": milestone.id,
                "title": milestone.title,
                "description": milestone.description,
                "milestone_type": milestone.milestone_type,
                "estimated_days": milestone.estimated_days,
                "deadline": milestone_deadline.isoformat() if milestone_deadline else None,
                "payout_percentage": float(milestone.payout_percentage),
                "deliverables": milestone.deliverables,
                "status": status,
                "order": milestone.order,
                "activities": activities,  # Add milestone-specific activities
                "activity_count": len(activities),
            })

        project_details = {
            "title": obsp_level.name,  # Use level name instead of template title
            "description": template.description,
            "start_date": assigned_at.isoformat() if assigned_at else None,
            "complexity_level": selected_level,
            "category_name": template.category.name if template.category else None,
            "skills_required": {
                "core_skills": core_skills,
                "optional_skills": optional_skills,
                "required_skills": required_skills,
            },
            "budget": float(obsp_response.total_price) if obsp_response.total_price else 0,
            "deadline": deadline.isoformat() if deadline else None,
            "features": features,
            "deliverables": deliverables,
        }

    # 7. Get workspace activity history (general activities)
    activities = []
    workspace_activities = workspace.activities.select_related('user', 'milestone', 'obsp_milestone').order_by('-timestamp')[:50]  # Last 50 activities
    
    for activity in workspace_activities:
        activity_data = {
            "id": activity.id,
            "type": activity.activity_type,
            "type_display": activity.get_activity_type_display(),
            "user": {
                "id": activity.user.id,
                "username": activity.user.username,
            },
            "timestamp": activity.timestamp.isoformat(),
            "title": activity.title,
            "description": activity.description,
        }
        
        # Add optional fields if they exist
        if activity.amount:
            activity_data["amount"] = float(activity.amount)
        if activity.old_value and activity.new_value:
            activity_data["status_change"] = {
                "old": activity.old_value,
                "new": activity.new_value,
            }
        if activity.milestone:
            activity_data["milestone"] = {
                "id": activity.milestone.id,
                "title": activity.milestone.title,
            }
        if activity.obsp_milestone:
            activity_data["obsp_milestone"] = {
                "id": activity.obsp_milestone.id,
                "title": activity.obsp_milestone.title,
            }
        
        activities.append(activity_data)

    # 8. Compose response
    data = {
        "type": "obsp" if hasattr(content_object, 'template') else "project",
        "project": {
            **project_details,
            "milestones": milestones,
        },
        "team": participants,
        "recentMessages": [],  # Empty for now
        "files": files,
        "payments": {},        # Empty for now
        "disputes": disputes,
        "activities": activities,  # Add activity history
        "activity_summary": {
            "total_activities": workspace.activities.count(),  # Use direct count
            "last_activity": workspace.activities.order_by('-timestamp').first().timestamp.isoformat() if workspace.activities.exists() else None,
        }
    }

    print(data)
    return Response(data)


# Milestone
def serialize_history(act):
        return {
            "action": act.get_activity_type_display(),
            "by": act.user.username,
            "details": act.description or act.title,
            "time": act.timestamp.strftime("%Y-%m-%d %H:%M"),
        }

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def freelancer_milestones(request, workspace_id):
    user = request.user
    print(f"User: {user.username}, Workspace ID: {workspace_id}")  # Debug log

    # 1. Get the workspace where the user is a freelancer participant
    try:
        workspace = Workspace.objects.get(id=workspace_id, participants__user=user, participants__role='freelancer')
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found or access denied."}, status=404)

    # 2. Get the project or OBSP assignment
    content_object = workspace.content_object

    # 3. Get milestones based on content type
    milestones = []
    activities = WorkspaceActivity.objects.filter(workspace=workspace).select_related('user')
    
    if hasattr(content_object, 'milestones'):
        # Case: Project
        milestones_qs = content_object.milestones.all()
        for m in milestones_qs:
            milestone_activities = [a for a in activities if a.milestone_id == m.id]
            
            # Fetch attachments for this milestone, excluding those in any box
            milestone_attachments = WorkspaceAttachment.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),
                object_id=m.id
            ).exclude(
                id__in=WorkspaceBox.objects.filter(
                    workspace=workspace,
                    content_type=ContentType.objects.get_for_model(m),
                    object_id=m.id
                ).values('attachments__id')
            ).order_by('-uploaded_at')
            
            regular_submissions = [
                {
                    "id": att.id,
                    "name": att.file.name.split('/')[-1] if att.file else att.link.split('/')[-1] if att.link else "Link",
                    "type": "file" if att.file else "link",
                    "url": request.build_absolute_uri(att.file.url) if att.file else request.build_absolute_uri(att.link) if att.link else None,
                    "submittedAt": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                    "uploadedBy": att.uploaded_by.username
                }
                for att in milestone_attachments  # Now excludes box attachments
            ]
            
            # Fetch boxes for this milestone using content_type and object_id
            boxes = WorkspaceBox.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),  # Use actual content_type
                object_id=m.id  # Use object_id
            ).prefetch_related('attachments')  # Use prefetch_related for ManyToMany
            
            serialized_boxes = [
                {
                    "id": box.id,
                    "title": box.title,
                    "description": box.description,
                    "status":box.status,
                    "files": [
                        {
                            "id": attachment.id,
                            "name": attachment.file.name.split('/')[-1] if attachment.file else attachment.link.split('/')[-1] if attachment.link else "Link",
                            "type": "file" if attachment.file else "link",
                            "url": request.build_absolute_uri(attachment.file.url) if attachment.file else request.build_absolute_uri(attachment.link) if attachment.link else None,
                            "uploadedBy": attachment.uploaded_by.username,
                            "uploadedAt": attachment.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                        } for attachment in box.attachments.all()
                    ]
                } for box in boxes
            ]
            
            milestones.append({
                "id": m.id,
                "title": m.title,
                "status": m.status,
                "due": m.due_date,
                "description": getattr(m, "description", ""),
                "instructions": getattr(m, "quality_requirements", ""),
                "deliverables": [],  # Add deliverables if available
                "comments": [],      # Add comments if available
                "payout": {
                    "percent": 0,   # Fill as needed
                    "status": m.status,
                    "autoPay": False
                },
                "history": [serialize_history(a) for a in milestone_activities],
                "submissions": regular_submissions,  # Only non-box submissions
                "boxes": serialized_boxes  # Add boxes list
            })
        
    elif hasattr(content_object, 'template'):
        # Case: OBSPResponse
        obsp_response = content_object
        template = obsp_response.template
        selected_level = obsp_response.selected_level
        
        # Get OBSP level details
        try:
            obsp_level = OBSPLevel.objects.get(template=template, level=selected_level)
        except OBSPLevel.DoesNotExist:
            return Response({"error": "OBSP level not found."}, status=404)
        
        # Get assignment details for deadline calculation
        assignment = OBSPAssignment.objects.filter(
            obsp_response=obsp_response,
            assigned_freelancer=user
        ).first()
        
        # Get milestones only for this specific level and calculate deadlines
        milestones_qs = OBSPMilestone.objects.filter(
            template=template,
            level=obsp_level
        ).order_by('order')
        
        # Calculate deadlines based on order and estimated_days
        current_date = assignment.assigned_at if assignment else None
        milestone_progress = obsp_response.milestone_progress or {}
        for m in milestones_qs:
            # Calculate deadline based on order and estimated_days
            deadline = None
            milestone_activities = [a for a in activities if a.obsp_milestone_id == m.id]
        
            if current_date:
                if m.order == milestones_qs.aggregate(models.Min('order'))['order__min']:
                    # First milestone: start from assignment date
                    deadline = current_date + timedelta(days=m.estimated_days)
                else:
                    # Subsequent milestones: start from previous milestone's deadline
                    if milestones:  # If we have previous milestones
                        previous_deadline = milestones[-1]['deadline']
                        if previous_deadline:
                            deadline = previous_deadline + timedelta(days=m.estimated_days)
                    else:
                        # Fallback: start from assignment date
                        deadline = current_date + timedelta(days=m.estimated_days)
            
            # Get all related notes for this milestone
            feedbacks = []
            for note in obsp_response.notes.filter(note_type='client_feedback', milestone=m):
                feedbacks.append({
                    "id": note.id,
                    "content": note.content,
                    "created_at": note.created_at.isoformat(),
                    "created_by": note.created_by.username,
                    "isAcknowledged": note.is_aknowledged,
                })
            milestone_notes = {
                "client_feedback": feedbacks,
                "freelancer_notes": list(obsp_response.notes.filter(
                    note_type='freelancer_note', 
                    milestone=m
                ).values('id', 'content', 'created_at')),
                # Internal notes only visible to admins/freelancer who created them
                "internal_notes": list(obsp_response.notes.filter(
                    note_type='internal_note',
                    milestone=m,
                    created_by=user  # Filter by current user
                ).values('id', 'content', 'created_at')) if user.role == 'freelancer' else []
            }
            
            # Fetch attachments for this milestone, excluding those in any box
            milestone_attachments = WorkspaceAttachment.objects.filter(
                    workspace=workspace,
                    content_type=ContentType.objects.get_for_model(m),
                    object_id=m.id
            ).exclude(
                id__in=WorkspaceBox.objects.filter(
                    workspace=workspace,
                    content_type=ContentType.objects.get_for_model(m),
                    object_id=m.id
                ).values('attachments__id')
                ).order_by('-uploaded_at')
                
            regular_submissions = [
                    {
                        "id": att.id,
                        "name": att.file.name.split('/')[-1] if att.file else att.link.split('/')[-1] if att.link else "Link",
                        "type": "file" if att.file else "link",
                        "url": request.build_absolute_uri(att.file.url) if att.file else request.build_absolute_uri(att.link) if att.link else None,
                        "submittedAt": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                        "uploadedBy": att.uploaded_by.username
                    }
                for att in milestone_attachments  # Now excludes box attachments
                ]
            
            # Fetch boxes for this milestone using content_type and object_id
            boxes = WorkspaceBox.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),  # Use actual content_type
                object_id=m.id  # Use object_id
            ).prefetch_related('attachments')  # Use prefetch_related for ManyToMany
            
            serialized_boxes = [
                {
                    "id": box.id,
                    "title": box.title,
                    "description": box.description,
                    "status":box.status,
                    "files": [
                        {
                            "id": attachment.id,
                            "name": attachment.file.name.split('/')[-1] if attachment.file else attachment.link.split('/')[-1] if attachment.link else "Link",
                            "type": "file" if attachment.file else "link",
                            "url": request.build_absolute_uri(attachment.file.url) if attachment.file else request.build_absolute_uri(attachment.link) if attachment.link else None,
                            "uploadedBy": attachment.uploaded_by.username,
                            "uploadedAt": attachment.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                        } for attachment in box.attachments.all()
                    ]
                } for box in boxes
            ]
            
            milestone_id_str = str(m.id)
            status = milestone_progress.get(milestone_id_str, m.status)  # fallback to model status if not set
            
            milestone_data = {
                "id": m.id,
                "title": m.title,
                "status": status,
                "due": deadline,
                "instructions": "",  # Add instructions if available
                "deliverables": m.deliverables,
                "comments": [],      # Add comments if available
                "payout": {
                    "percent": float(m.payout_percentage),
                    "status": status,
                    "autoPay": False
                },
                "history": [serialize_history(a) for a in milestone_activities],
                  # Add history if available
                # OBSP-specific fields
                "milestone_type": m.milestone_type,
                "description": m.description,
                "estimated_days": m.estimated_days,
                "deadline": deadline,
                "payout_percentage": float(m.payout_percentage),
                "notes": milestone_notes,
                "submissions": regular_submissions,  # Only regular submissions
                "boxes": serialized_boxes  # Add boxes list
            }
            milestones.append(milestone_data)

    # 4. Compose response
    data = {
        "type": "obsp" if hasattr(content_object, 'template') else "project",
        "milestones": milestones,
    }
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace_payments(request, workspace_id):
    """Get payment information for workspace"""
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    # Check access
    if not workspace.participants.filter(user=request.user).exists():
        return Response({"error": "Access denied"}, status=403)
    
    content_object = workspace.content_object
    
    if hasattr(content_object, 'template'):  # OBSP
        # Get OBSP payment data using existing PaymentService
        from financeapp.services.payment_service import PaymentService
        
        obsp_response = content_object
        payment_summary = PaymentService.get_obsp_payment_summary(obsp_response)
        
        # Get ALL transactions for this OBSP (all statuses)
        transactions = Transaction.objects.filter(
            obsp_response=obsp_response
        ).order_by('-created_at')
        
        # Get milestone payments for additional info
        milestone_payments = []
        for milestone in obsp_response.template.template_milestones.filter(level__level=obsp_response.selected_level):
            milestone_tx = Transaction.objects.filter(
                obsp_response=obsp_response,
                obsp_milestone=milestone,
                status='completed'
            ).first()
            
            milestone_payments.append({
                'id': milestone.id,
                'title': milestone.title,
                'amount': float(milestone.get_payout_amount(obsp_response.total_price)),
                'percentage': float(milestone.payout_percentage),
                'status': 'paid' if milestone_tx else 'pending',
                'paid_at': milestone_tx.completed_at.isoformat() if milestone_tx else None,
            })
        
        return Response({
            'type': 'obsp',
            'summary': payment_summary,
            'milestone_payments': milestone_payments,
            'transactions': [
                {
                    'id': str(tx.id),
                    'amount': float(tx.amount),
                    'status': tx.status,
                    'created_at': tx.created_at.isoformat(),
                    'completed_at': tx.completed_at.isoformat() if tx.completed_at else None,
                    'description': tx.description,
                    'payment_type': tx.payment_type,
                    'milestone_title': tx.obsp_milestone.title if tx.obsp_milestone else None,
                    'from_user': tx.from_user.username,
                    'to_user': tx.to_user.username,
                    'currency': tx.currency,
                    'platform_fee': float(tx.platform_fee_amount) if tx.platform_fee_amount else 0,
                    'net_amount': float(tx.net_amount) if tx.net_amount else 0,
                }
                for tx in transactions
            ]
        })
    
    else:  # Project
        # Get project payment data
        project = content_object
        # Get ALL transactions for this project (all statuses)
        transactions = Transaction.objects.filter(
            project=project
        ).order_by('-created_at')
        
        # Calculate summary based on completed transactions only
        completed_transactions = transactions.filter(status='completed')
        total_paid = sum(tx.amount for tx in completed_transactions)
        
        return Response({
            'type': 'project',
            'summary': {
                'total_due': float(project.budget),
                'total_paid': float(total_paid),
                'remaining': float(project.budget - total_paid),
                'transactions_count': transactions.count(),
                'completed_transactions_count': completed_transactions.count(),
                'last_payment': completed_transactions.first().completed_at.isoformat() if completed_transactions.exists() else None,
            },
            'transactions': [
                {
                    'id': str(tx.id),
                    'amount': float(tx.amount),
                    'status': tx.status,
                    'created_at': tx.created_at.isoformat(),
                    'completed_at': tx.completed_at.isoformat() if tx.completed_at else None,
                    'description': tx.description,
                    'payment_type': tx.payment_type,
                    'milestone_title': tx.milestone.title if tx.milestone else None,
                    'from_user': tx.from_user.username,
                    'to_user': tx.to_user.username,
                    'currency': tx.currency,
                    'platform_fee': float(tx.platform_fee_amount) if tx.platform_fee_amount else 0,
                    'net_amount': float(tx.net_amount) if tx.net_amount else 0,
                }
                for tx in transactions
            ]
        })

class WorkspaceRevisionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        """
        Fetch all revisions for a workspace.
        """
        # 1. Verify workspace access
        workspace = get_object_or_404(
            Workspace,
            id=workspace_id,
            participants__user=request.user,
            participants__role='freelancer'
        )

        # 2. Fetch revisions with related milestones
        revisions_qs = WorkspaceRevision.objects.filter(
            workspace=workspace
        ).select_related(
            'milestone_content_type',
            'requested_by'
        )
        revisions = list(revisions_qs)

        # Annotate each revision with the milestone order (if OBSPMilestone)
        for rev in revisions:
            milestone = rev.milestone
            if hasattr(milestone, 'order'):
                rev._milestone_order = milestone.order
            else:
                rev._milestone_order = 9999  # fallback for non-OBSPMilestone or missing order

        # Now you can sort
        revisions.sort(key=lambda r: (r._milestone_order, r.revision_number))

        # Find the next scheduled revision (first with status 'open')
        next_revision = next((rev for rev in revisions if rev.status == "open"), None)

        # Serialize next_revision if it exists
        def serialize_revision(revision):
            milestone = revision.milestone
            return {
                "id": revision.id,
                "milestone": {
                    "id": milestone.id if milestone else None,
                    "title": getattr(milestone, "title", "N/A"),
                    "type": getattr(milestone, "milestone_type", "N/A"),
                    "order": getattr(milestone, "order", None),
                } if milestone else None,
                "requested_by": {
                    "id": revision.requested_by.id,
                    "username": revision.requested_by.username,
                },
                "description": revision.description,
                "type": revision.type,
                "status": revision.status,
                "revision_number": revision.revision_number,
                "created_at": revision.created_at.isoformat(),
                "addressed_at": revision.addressed_at.isoformat() if revision.addressed_at else None,
            }

        # Now serialize as before
        data = [serialize_revision(revision) for revision in revisions]

        return Response({
            "count": len(data),
            "results": data,
            "next_revision": serialize_revision(next_revision) if next_revision else None,
        }, status=status.HTTP_200_OK)


class WorkspaceNotificationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        # Ensure user is a participant in the workspace
        workspace = get_object_or_404(
            Workspace,
            id=workspace_id,
            participants__user=request.user
        )

        # Get ContentType for Workspace
        workspace_ct = ContentType.objects.get_for_model(Workspace)

        # Fetch notifications where related_object is this workspace
        notifications = Notification.objects.filter(
            content_type=workspace_ct,
            related_model_id=workspace.id
        ).order_by('-created_at')

        def serialize_notification(n):
            return {
                "id": n.id,
                "type": n.type,
                "subtype": n.subtype,
                "title": n.title,
                "notification_text": n.notification_text,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "priority": n.priority,
                "metadata": n.metadata,
            }

        return Response({
            "count": notifications.count(),
            "results": [serialize_notification(n) for n in notifications]
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, workspace_id, notification_id):
    from core.models import Notification
    from workspace.models import Workspace
    from django.shortcuts import get_object_or_404

    # Ensure user is a participant in the workspace
    workspace = get_object_or_404(
        Workspace,
        id=workspace_id,
        participants__user=request.user
    )

    notification = get_object_or_404(Notification, id=notification_id)
    # Optionally, check that notification is for this workspace
    if notification.related_model_id != workspace.id:
        return Response({"error": "Notification does not belong to this workspace."}, status=403)

    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return Response({"success": True, "id": notification.id, "is_read": True}, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def submit_milestone_deliverables(request, workspace_id, milestone_type, milestone_id):
    user = request.user

    # Get workspace
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not workspace.participants.filter(user=user, role='freelancer').exists():
        return Response({"error": "Not allowed"}, status=403)

    # Get milestone
    if milestone_type == 'obsp':
        milestone = get_object_or_404(OBSPMilestone, id=milestone_id)
    elif milestone_type == 'project':
        milestone = get_object_or_404(Milestone, id=milestone_id)
    else:
        return Response({"error": "Invalid milestone type"}, status=400)

    attachment_type = request.data.get('attachment_type', 'single')  # Default to 'single'
    title = request.data.get('title', None)  # For box title
    description = request.data.get('description', None)  # For box description
    files = request.FILES.getlist('files')

    attachments = []  # List to hold created attachments

    # Create attachments
    for f in files:
        attachment = WorkspaceAttachment.objects.create(
            workspace=workspace,
            content_type=ContentType.objects.get_for_model(milestone),
            object_id=milestone.id,
            file=f,
            uploaded_by=user
        )
        attachments.append(attachment)  # Add to list for later use in box

        # Create activity only if attachment_type is 'single'
        if attachment_type == 'single':
            WorkspaceActivity.objects.create(
                workspace=workspace,
                activity_type='file_uploaded',
                user=user,
                attachment=attachment,
                milestone=milestone if milestone_type == 'project' else None,
                obsp_milestone=milestone if milestone_type == 'obsp' else None,
                title="Deliverable Submitted",
                description=f.name
            )

    if attachment_type == 'box' and title:  # Only create box if attachment_type is 'box' and title is provided
        content_type_model = ContentType.objects.get(model='obspmilestone') if milestone_type == 'obsp' else ContentType.objects.get(model='milestone')
        
        workspace_box = WorkspaceBox.objects.create(
            workspace=workspace,
            title=title,
            description=description,
            content_type=content_type_model,
            object_id=milestone_id  # Link to the milestone
        )
        
        # Associate attachments with the box
        workspace_box.attachments.set(attachments)

        # Create a unified activity for the box
        WorkspaceActivity.objects.create(
            workspace=workspace,
            activity_type='box_uploaded',  # New activity type for boxes
            user=user,
            milestone=milestone if milestone_type == 'project' else None,
            obsp_milestone=milestone if milestone_type == 'obsp' else None,
            title=f"Box Submitted: {title}",
            description=f"Box with {len(attachments)} files submitted for milestone {milestone_id}. Description: {description}"
        )

        return Response({"success": True, "box_id": workspace_box.id})

    return Response({"success": True})  # For single attachments

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_milestone_revision(request, workspace_id, milestone_type, milestone_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not workspace.participants.filter(user=user).exists():
        return Response({"detail": "Not authorized."}, status=403)

    reason = request.data.get('reason', '')

    if milestone_type == 'project':
        milestone = get_object_or_404(Milestone, id=milestone_id)
        # Create a revision
        WorkspaceRevision.objects.create(
            workspace=workspace,
            milestone_content_type=ContentType.objects.get_for_model(Milestone),
            milestone_object_id=milestone.id,
            requested_by=user,
            description=reason,
            type='adhoc',
            revision_number=1  # You may want to increment this based on existing revisions
        )
        # Optionally, add a note
        ProjectMilestoneNote.objects.create(
            milestone=milestone,
            created_by=user,
            note_type='milestone_feedback',
            content=reason
        )
        # Create workspace activity
        WorkspaceActivity.objects.create(
            workspace=workspace,
            activity_type='revision_requested',
            user=user,
            milestone=milestone,
            title="Revision Requested",
            description=reason
        )
    elif milestone_type == 'obsp':
        milestone = get_object_or_404(OBSPMilestone, id=milestone_id)
        # Get the OBSPResponse for the workspace
        obsp_response = workspace.content_object  # assuming this is an OBSPResponse

        # Check if the current milestone matches
        if obsp_response.current_milestone == milestone:
            # Get the assignment for the user
            assignment = OBSPAssignment.objects.filter(
                obsp_response=obsp_response,
                assigned_freelancer=user
            ).first()
        WorkspaceRevision.objects.create(
            workspace=workspace,
            milestone_content_type=ContentType.objects.get_for_model(OBSPMilestone),
            milestone_object_id=milestone.id,
            requested_by=user,
            description=reason,
            type='adhoc',
            revision_number=1
        )
        # Optionally, add a note (if assignment is available)
        if assignment:
            OBSPAssignmentNote.objects.create(
                assignment=assignment,
                milestone=milestone,
                created_by=user,
                note_type='milestone_feedback',
                content=reason
            )
            # Create workspace activity
            WorkspaceActivity.objects.create(
                workspace=workspace,
                activity_type='revision_requested',
                user=user,
                obsp_milestone=milestone,
                title="Revision Requested",
                description=reason
            )
    else:
        return Response({"detail": "Invalid milestone type."}, status=400)

    return Response({"success": True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def acknowledge_milestone_feedback(request, workspace_id, milestone_type, milestone_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not workspace.participants.filter(user=user).exists():
        return Response({"detail": "Not authorized."}, status=403)

    feedback_id = request.data.get('feedback_id')
    if not feedback_id:
        return Response({"detail": "feedback_id is required."}, status=400)

    if milestone_type == 'obsp':
        milestone = get_object_or_404(OBSPMilestone, id=milestone_id)
        from OBSP.models import OBSPAssignmentNote
        try:
            feedback_note = OBSPAssignmentNote.objects.get(id=feedback_id, milestone=milestone, note_type='client_feedback')
            feedback_note.is_aknowledged = True
            feedback_note.save(update_fields=['is_aknowledged'])
        except OBSPAssignmentNote.DoesNotExist:
            return Response({"detail": "Feedback note not found."}, status=404)
        # Optionally, log activity here
        return Response({"success": True})

    elif milestone_type == 'project':
        milestone = get_object_or_404(Milestone, id=milestone_id)
        from core.models import ProjectMilestoneNote
        try:
            feedback_note = ProjectMilestoneNote.objects.get(id=feedback_id, milestone=milestone, note_type='client_feedback')
            feedback_note.is_aknowledged = True
            feedback_note.save(update_fields=['is_aknowledged'])
        except ProjectMilestoneNote.DoesNotExist:
            return Response({"detail": "Feedback note not found."}, status=404)
        # Optionally, log activity here
        WorkspaceActivity.objects.create(
            workspace=workspace,
            activity_type='feedback_given',
            user=user,
            milestone=milestone,
            title="Feedback Acknowledged",
            description="Feedback acknowledged by freelancer."
        )
        return Response({"success": True})

    else:
        return Response({"detail": "Invalid milestone type."}, status=400)

from OBSP.models import OBSPResponse

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_milestone_note(request, workspace_id, milestone_type, milestone_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not workspace.participants.filter(user=user).exists():
        return Response({"detail": "Not authorized."}, status=403)


    content = request.data.get('content', '').strip()
    if not content:
        return Response({"detail": "Note content required."}, status=400)

    if milestone_type == 'project':
        milestone = get_object_or_404(Milestone, id=milestone_id)
        note = ProjectMilestoneNote.objects.create(
            milestone=milestone,
            created_by=user,
            note_type='freelancer_note',
            content=content,
            is_private=True  # Assuming it's private based on context; adjust as needed
        )
        
        # Create workspace activity with link to the note
        WorkspaceActivity.objects.create(
            workspace=workspace,
            activity_type='note_added',
            user=user,
            milestone=milestone,  # Keep existing reference if needed
            title="Freelancer Note Added Privately",
            description=content,
            content_type=ContentType.objects.get_for_model(note),  # Link to the note
            object_id=note.id  # Link to the note's ID
        )
    
    elif milestone_type == 'obsp':

        milestone = get_object_or_404(OBSPMilestone, id=milestone_id)
        workspace = get_object_or_404(Workspace, id=workspace_id)
        response = workspace.content_object

        # reponse = OBSPResponse.objects.get content with worksspace id workspace_id
        if isinstance(response, OBSPResponse):
            note = OBSPAssignmentNote.objects.create(
                response=response,
                milestone=milestone,
                created_by=user,
                note_type='freelancer_note',
                is_private=True,
                content=content
            )
            
            # Create workspace activity with link to the note
            WorkspaceActivity.objects.create(
                workspace=workspace,
                activity_type='note_added',
                user=user,
                obsp_milestone=milestone,
                title="Freelancer Note Added Privately",
                description=content,
                content_type=ContentType.objects.get_for_model(note),  # Link to the note
                object_id=note.id  # Link to the note's ID
            )
        else:
            return Response({"detail": "No assignment found for this milestone and user."}, status=400)
    else:
        return Response({"detail": "Invalid milestone type."}, status=400)

    return Response({"success": True})
