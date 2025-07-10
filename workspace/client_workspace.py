# Client Workspace

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from workspace.models import Workspace,WorkspaceBox
from OBSP.models import OBSPLevel
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from workspace.models import Workspace, WorkspaceParticipant, WorkspaceAttachment, WorkspaceDispute, WorkspaceRevision
from core.models import Milestone, Notification, ProjectMilestoneNote
from django.contrib.contenttypes.models import ContentType
from OBSP.models import OBSPMilestone, OBSPLevel, OBSPAssignment, OBSPCriteria, OBSPAssignmentNote  # Import additional OBSP models
from django.utils import timezone
from datetime import datetime, date, timedelta
import re
from django.db import models
from financeapp.models import Transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from workspace.models import WorkspaceActivity
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models import Project
from OBSP.models import OBSPResponse, OBSPAssignmentNote


def get_workspace_payment_summary(workspace):
    content_object = workspace.content_object

    if hasattr(content_object, 'template'):  # OBSP
        from financeapp.services.payment_service import PaymentService
        obsp_response = content_object
        payment_summary = PaymentService.get_obsp_payment_summary(obsp_response)
        # You can return only the brief info you want
        return {
            "total_due": payment_summary.get("total_due"),
            "total_paid": payment_summary.get("total_paid"),
            "remaining": payment_summary.get("remaining"),
            "transactions_count": payment_summary.get("transactions_count"),
            "last_payment": payment_summary.get("last_payment"),
        }
    else:  # Project
        project = content_object
        transactions = Transaction.objects.filter(project=project)
        completed_transactions = transactions.filter(status='completed')
        total_paid = sum(tx.amount for tx in completed_transactions)
        return {
            "total_due": float(project.budget),
            "total_paid": float(total_paid),
            "remaining": float(project.budget - total_paid),
            "transactions_count": transactions.count(),
            "completed_transactions_count": completed_transactions.count(),
            "last_payment": completed_transactions.first().completed_at.isoformat() if completed_transactions.exists() else None,
        }




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_overview(request, workspace_id):
    user = request.user

    try:
        workspace = Workspace.objects.get(
            id=workspace_id,
            participants__user=user,
            participants__role='client'
        )
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found or access denied"}, status=404)

    # 2. Get the content object (Project or OBSPResponse)
    content_object = workspace.content_object

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
        files.append({
            "id": attachment.id,
            "name": attachment.file.name if attachment.file else "Link",
            "url": request.build_absolute_uri(attachment.file.url) if attachment.file else request.build_absolute_uri(attachment.link) if attachment.link else None,
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
            assigned_at = assignment.assigned_at  # Ensure this is a datetime
            try:
                duration_days = int(duration.split('-')[1].split()[0]) if '-' in duration else 14
                deadline = assigned_at + timezone.timedelta(days=duration_days)  # This should be a datetime
            except:
                deadline = assigned_at + timezone.timedelta(days=14)  # Fallback
        else:
            assigned_at = None
            deadline = None  # Explicitly set to None

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
        
        for milestone in level_milestones:
            milestone_id_str = str(milestone.id)
            status = milestone_progress.get(milestone_id_str, {}).get('status', milestone.status)  # Fetch status from progress
            deadline = milestone_progress.get(milestone_id_str, {}).get('deadline', None)  # Fetch deadline from progress (as string)
            
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
            
            milestones.append({
                "id": milestone.id,
                "title": milestone.title,
                "description": milestone.description,
                "milestone_type": milestone.milestone_type,
                "estimated_days": milestone.estimated_days,
                "deadline": deadline,  # Use the string directly, no .isoformat()
                "payout_percentage": float(milestone.payout_percentage),
                "deliverables": milestone.deliverables,
                "status": status,  # Fetched from milestone_progress
                "order": milestone.order,
                "activities": activities,
                "activity_count": len(activities),
            })

        project_details = {
            "title": obsp_level.name,  # Use level name instead of template title
            "description": template.description,
            "start_date": assigned_at.isoformat() if assigned_at and isinstance(assigned_at, (datetime, date)) else assigned_at,
            "complexity_level": selected_level,
            "category_name": template.category.name if template.category else None,
            "skills_required": {
                "core_skills": core_skills,
                "optional_skills": optional_skills,
                "required_skills": required_skills,
            },
            "budget": float(obsp_response.total_price) if obsp_response.total_price else 0,
            "deadline": deadline.isoformat() if deadline and isinstance(deadline, (datetime, date)) else deadline,  # Safe check
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

    payments = get_workspace_payment_summary(workspace)

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
        "payments": payments,
        "disputes": disputes,
        "activities": activities,  # Add activity history
        "activity_summary": {
            "total_activities": workspace.activities.count(),  # Use direct count
            "last_activity": workspace.activities.order_by('-timestamp').first().timestamp.isoformat() if workspace.activities.exists() else None,
        }
    }

    return Response(data)


def serialize_history(act, request_user):
    # Filter or check privacy before serializing
    if act.activity_type == 'note_added':
        if act.related_object:  # Check if there's a linked object (e.g., a note)
            note = act.related_object  # This could be ProjectMilestoneNote or OBSPAssignmentNote
            if getattr(note, 'is_private', False) and note.created_by != request_user:
                return None  # Skip this activity if it's private and not created by the user
    return {
        "action": act.get_activity_type_display(),
        "by": act.user.username,
        "details": act.description or act.title,
        "time": act.timestamp.strftime("%Y-%m-%d %H:%M"),
    }

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_milestones(request, workspace_id):
    user = request.user
    # 1. Get the workspace where the user is a client participant
    try:
        workspace = Workspace.objects.get(id=workspace_id, participants__user=user, participants__role='client')
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
            
            # Fetch attachments for this milestone
            milestone_attachments = WorkspaceAttachment.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),
                object_id=m.id
            ).order_by('-uploaded_at')
            
            # First, fetch boxes for this milestone to get their attachments
            boxes = WorkspaceBox.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),
                object_id=m.id
            ).prefetch_related('attachments')
            
            box_attachment_ids = set(attachment.id for box in boxes for attachment in box.attachments.all())
            
            # Now filter regular submissions to exclude attachments in boxes
            regular_submissions = [
                {
                    "id": att.id,
                    "name": att.file.name.split('/')[-1] if att.file else att.link.split('/')[-1] if att.link else "Link",
                    "type": "file" if att.file else "link",
                    "url": request.build_absolute_uri(att.file.url) if att.file else request.build_absolute_uri(att.link) if att.link else None,
                    "submittedAt": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                    "uploadedBy": att.uploaded_by.username
                }
                for att in milestone_attachments if att.id not in box_attachment_ids
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
                    "status": box.status,  # Added: Include the box's status
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
                "history": [serialize_history(a, user) for a in milestone_activities],
                "submissions": regular_submissions,  # Only non-box attachments
                "boxes": serialized_boxes  # Boxes remain separate
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
            assigned_by=user
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
                    milestone=m,
                    is_private=False
                ).values('id', 'content', 'created_at')),
                # Internal notes only visible to admins/freelancer who created them
                "internal_notes": list(obsp_response.notes.filter(
                    note_type='internal_note',
                    milestone=m,
                    created_by=user  # Filter by current user
                ).values('id', 'content', 'created_at')) if user.role == 'client' else []
            }
            
            # Fetch attachments and separate boxes from regular submissions
            milestone_attachments = WorkspaceAttachment.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),
                object_id=m.id
            ).order_by('-uploaded_at')
            
            boxes = WorkspaceBox.objects.filter(
                workspace=workspace,
                content_type=ContentType.objects.get_for_model(m),  # Use actual content_type
                object_id=m.id  # Use object_id
            ).prefetch_related('attachments')  # Use prefetch_related for ManyToMany
            
            box_attachment_ids = set(attachment.id for box in boxes for attachment in box.attachments.all())
            
            regular_submissions = [
                {
                    "id": att.id,
                    "name": att.file.name.split('/')[-1] if att.file else att.link.split('/')[-1] if att.link else "Link",
                    "type": "file" if att.file else "link",
                    "url": request.build_absolute_uri(att.file.url) if att.file else request.build_absolute_uri(att.link) if att.link else None,
                    "submittedAt": att.uploaded_at.strftime("%Y-%m-%d %H:%M"),
                    "uploadedBy": att.uploaded_by.username
                }
                for att in milestone_attachments if att.id not in box_attachment_ids  # Exclude attachments in boxes
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
                    "status": box.status,  # Added: Include the box's status
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
            status = milestone_progress.get(milestone_id_str, {}).get('status', m.status)  # Fetch status from progress
            deadline = milestone_progress.get(milestone_id_str, {}).get('deadline', None)  # Fetch deadline from progress (as string)
            
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
                "history": [serialize_history(a, user) for a in milestone_activities],
                  # Add history if available
                # OBSP-specific fields
                "milestone_type": m.milestone_type,
                "description": m.description,
                "estimated_days": m.estimated_days,
                "deadline": deadline,
                "payout_percentage": float(m.payout_percentage),
                "notes": milestone_notes,
                "submissions": regular_submissions,  # Only non-box attachments
                "boxes": serialized_boxes  # Boxes remain separate
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
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not workspace.participants.filter(user=request.user).exists():
        return Response({"error": "Access denied"}, status=403)

    content_object = workspace.content_object

    if hasattr(content_object, 'template'):  # OBSP
        from financeapp.services.payment_service import PaymentService
        obsp_response = content_object
        payment_summary = PaymentService.get_obsp_payment_summary(obsp_response)
        transactions = Transaction.objects.filter(
            obsp_response=obsp_response
        ).order_by('-created_at')

        # Milestone payments with client actions
        milestone_payments = []
        for milestone in obsp_response.template.template_milestones.filter(level__level=obsp_response.selected_level):
            milestone_tx = Transaction.objects.filter(
                obsp_response=obsp_response,
                obsp_milestone=milestone,
                status='completed'
            ).first()
            # Example logic for next_action
            if milestone_tx:
                next_action = None
            elif milestone.status == "submitted":
                next_action = "Release Payment"
            elif milestone.status == "in_progress":
                next_action = "Wait for Submission"
            else:
                next_action = None

            milestone_payments.append({
                'id': milestone.id,
                'title': milestone.title,
                'amount': float(milestone.get_payout_amount(obsp_response.total_price)),
                'percentage': float(milestone.payout_percentage),
                'status': 'Paid' if milestone_tx else 'Pending',
                'paid_at': milestone_tx.completed_at.isoformat() if milestone_tx else None,
                'can_release': milestone.status == "submitted" and not milestone_tx,
                'next_action': next_action,
            })

        return Response({
            'type': 'obsp',
            'summary': {
                **payment_summary,
                'transactions_count': len(transactions),
            },
            'milestone_payments': milestone_payments,
            'transactions': [
                {
                    'id': str(tx.id),
                    'amount': float(tx.amount),
                    'status': tx.status.capitalize(),
                    'created_at': tx.created_at.isoformat(),
                    'completed_at': tx.completed_at.isoformat() if tx.completed_at else None,
                    'description': tx.description,
                    'payment_type': tx.payment_type,
                    'milestone_id': tx.obsp_milestone.id if tx.obsp_milestone else None,
                    'milestone_title': tx.obsp_milestone.title if tx.obsp_milestone else None,
                    'from_user': {
                        'username': tx.from_user.username,
                        'role': getattr(tx.from_user, 'role', None)
                    },
                    'to_user': {
                        'username': tx.to_user.username,
                        'role': getattr(tx.to_user, 'role', None)
                    },
                    'currency': tx.currency,
                    'platform_fee': float(tx.platform_fee_amount) if tx.platform_fee_amount else 0,
                    'net_amount': float(tx.net_amount) if tx.net_amount else 0,
                    'refundable': tx.status == 'completed' and (timezone.now() - tx.completed_at).days < 7 if tx.completed_at else False,
                    'disputable': tx.status == 'completed' and (timezone.now() - tx.completed_at).days < 14 if tx.completed_at else False,
                }
                for tx in transactions
            ]
        })

    else:  # Project
        project = content_object
        transactions = Transaction.objects.filter(
            project=project
        ).order_by('-created_at')
        completed_transactions = transactions.filter(status='completed')
        total_paid = sum(tx.amount for tx in completed_transactions)

        # Milestone payments with client actions
        milestone_payments = []
        for milestone in project.milestones.all():
            milestone_tx = Transaction.objects.filter(
                project=project,
                milestone=milestone,
                status='completed'
            ).first()
            if milestone_tx:
                next_action = None
            elif milestone.status == "submitted":
                next_action = "Release Payment"
            elif milestone.status == "in_progress":
                next_action = "Wait for Submission"
            else:
                next_action = None

            milestone_payments.append({
                'id': milestone.id,
                'title': milestone.title,
                'amount': float(milestone.amount) if milestone.amount else 0,
                'status': 'Paid' if milestone_tx else 'Pending',
                'paid_at': milestone_tx.completed_at.isoformat() if milestone_tx else None,
                'can_release': milestone.status == "submitted" and not milestone_tx,
                'next_action': next_action,
            })

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
            'milestone_payments': milestone_payments,
            'transactions': [
                {
                    'id': str(tx.id),
                    'amount': float(tx.amount),
                    'status': tx.status.capitalize(),
                    'created_at': tx.created_at.isoformat(),
                    'completed_at': tx.completed_at.isoformat() if tx.completed_at else None,
                    'description': tx.description,
                    'payment_type': tx.payment_type,
                    'milestone_id': tx.milestone.id if tx.milestone else None,
                    'milestone_title': tx.milestone.title if tx.milestone else None,
                    'from_user': {
                        'username': tx.from_user.username,
                        'role': getattr(tx.from_user, 'role', None)
                    },
                    'to_user': {
                        'username': tx.to_user.username,
                        'role': getattr(tx.to_user, 'role', None)
                    },
                    'currency': tx.currency,
                    'platform_fee': float(tx.platform_fee_amount) if tx.platform_fee_amount else 0,
                    'net_amount': float(tx.net_amount) if tx.net_amount else 0,
                    'refundable': tx.status == 'completed' and (timezone.now() - tx.completed_at).days < 7 if tx.completed_at else False,
                    'disputable': tx.status == 'completed' and (timezone.now() - tx.completed_at).days < 14 if tx.completed_at else False,
                }
                for tx in transactions
            ]
        })

class WorkspaceRevisionsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, workspace_id):
        """
        Fetch all revisions for a workspace.
        """
        # 1. Verify workspace access
        workspace = get_object_or_404(
            Workspace,
            id=workspace_id,
            participants__user=request.user,
            participants__role='client'
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

        obsp_response = None
        max_revisions = 1
        if hasattr(workspace.content_object, 'get_max_revisions'):
            obsp_response = workspace.content_object
            max_revisions = obsp_response.get_max_revisions() or 1

        # Calculate used revisions (all milestones, or just for the current one if you want)
        used_revisions = len(data)
        remaining_revisions = max(0, max_revisions - used_revisions)

        return Response({
            "count": len(data),
            "results": data,
            "next_revision": serialize_revision(next_revision) if next_revision else None,
            "max_revisions": max_revisions,
            "used_revisions": used_revisions,
            "remaining_revisions": remaining_revisions,
        }, status=status.HTTP_200_OK)

    def post(self, request, workspace_id):
        """
        Create a new revision request for a milestone in this workspace.
        """
        try:
            workspace = get_object_or_404(
                Workspace,
                id=workspace_id,
                participants__user=request.user,
                participants__role='client'
            )

            description = request.data.get('description', '').strip()
            milestone_id = request.data.get('milestone_id')
            if not description or not milestone_id:
                return Response({"detail": "Description and milestone_id are required."}, status=400)

            # Find the milestone (OBSP or Project)
            milestone = None
            # Try OBSPMilestone first
            from OBSP.models import OBSPMilestone, OBSPResponse
            try:
                milestone = OBSPMilestone.objects.get(id=milestone_id)
            except OBSPMilestone.DoesNotExist:
                # TODO: Add support for Project Milestone if needed
                return Response({"detail": "Milestone not found."}, status=404)

            # Get the OBSPResponse from the workspace's content_object
            obsp_response = None
            if hasattr(workspace.content_object, 'max_revisions'):
                obsp_response = workspace.content_object
            else:
                return Response({"detail": "Workspace is not linked to an OBSPResponse."}, status=400)

            max_revisions = obsp_response.get_max_revisions() or 1

            # Count existing revisions for this milestone in this workspace
            existing_revisions = WorkspaceRevision.objects.filter(
                workspace=workspace,
                milestone_content_type=ContentType.objects.get_for_model(milestone),
                milestone_object_id=milestone.id,
            ).count()

            if existing_revisions >= max_revisions:
                # Optionally, get the latest revision for this milestone
                latest_revision = WorkspaceRevision.objects.filter(
                    workspace=workspace,
                    milestone_content_type=ContentType.objects.get_for_model(milestone),
                    milestone_object_id=milestone.id,
                ).order_by('-created_at').first()

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
                    } if revision else None

                return Response({
                    "detail": f"You have already used all {max_revisions} allowed revision(s) for this milestone.",
                    "max_revisions": max_revisions,
                    "used_revisions": existing_revisions,
                    "can_create": False,
                    "latest_revision": serialize_revision(latest_revision),
                }, status=200)

            # Create the revision
            revision = WorkspaceRevision.objects.create(
                workspace=workspace,
                milestone_content_type=ContentType.objects.get_for_model(milestone),
                milestone_object_id=milestone.id,
                requested_by=request.user,
                description=description,
                type='adhoc',
                revision_number=existing_revisions + 1,
                status='open'
            )

            # Optionally handle file upload, scope, etc.
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                WorkspaceAttachment.objects.create(
                    workspace=workspace,
                    file=uploaded_file,
                    uploaded_by=request.user,
                    content_object=revision,  # or the milestone, depending on your model
                )

            # Return the new revision (serialized)
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

            return Response(serialize_revision(revision), status=201)
        except Exception as e:
            import traceback
            print("Exception in WorkspaceRevisionsAPIView POST:", e)
            traceback.print_exc()
            return Response({"detail": str(e)}, status=400)

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



# Actions

# Create a API view for Box actions as requested
class BoxActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, box_id, action):
        """
        Handle approve or reject actions for a specific box.
        Endpoint: /api/workspace/client/box/{box_id}/{action} where action is 'approve' or 'reject'.
        """
        user = request.user
        try:
            box = WorkspaceBox.objects.get(id=box_id)
            workspace = box.workspace  # Get the associated workspace
            
            # Ensure the user is a client participant in the workspace
            if not workspace.participants.filter(user=user, role='client').exists():
                return Response({"error": "Access denied. You must be a client in this workspace."}, status=403)
            
            if action not in ['approve', 'viewed']:
                return Response({"error": "Invalid action. Use 'approve' or 'reject'."}, status=400)
            
            if action == 'approve':
                box.status = 'approved'
            elif action == 'viewed':
                box.status = 'viewed'
            
            box.save()
            
            return Response({
                "success": True,
                "box_id": box.id,
                "new_status": box.status,
                "message": f"Box has been {action}d successfully."
            }, status=200)
        
        except WorkspaceBox.DoesNotExist:
            return Response({"error": "Box not found."}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500) 
        

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_milestone(request, workspace_id, milestone_id):
    user = request.user  # Assuming authentication is handled via middleware
    
    try:
        # 1. Fetch the workspace and verify user access
        workspace = Workspace.objects.get(id=workspace_id, participants__user=user, participants__role='client')
        content_object = workspace.content_object  # This could be Project or OBSPResponse
        
        # 2. Fetch feedback from the request body
        feedback = request.data.get('data').get('feedback', '').strip()  # Expecting JSON body with 'feedback' key
        
        if isinstance(content_object, Project):  # For Projects
            milestone = Milestone.objects.get(id=milestone_id, project=content_object)
            milestone.status = 'completed'  # Update status
            milestone.completed_at = timezone.now()  # Set completion time
            milestone.save()
            
            # Handle feedback
            if feedback:
                ProjectMilestoneNote.objects.create(
                    milestone=milestone,
                    created_by=user,
                    note_type='client_feedback',
                    content=feedback,
                    is_aknowledged=False  # Can be updated later
                )
            
            # New logic: Check for the next milestone and update if pending
            next_milestones = Milestone.objects.filter(project=content_object, id__gt=milestone.id).order_by('id').first()
            if next_milestones and next_milestones.status == 'pending':
                next_milestones.status = 'in_progress'
                next_milestones.save()  # Optionally, add a timestamp or other fields here
            
        elif isinstance(content_object, OBSPResponse):  # For OBSP
            milestone_progress = content_object.milestone_progress  # JSON field, e.g., {"1": "in_progress"}
            
            # Ensure milestone_id is a string key in milestone_progress
            milestone_key = str(milestone_id)  # Assuming keys are strings like "1"
            if milestone_key in milestone_progress:
                milestone_progress[milestone_key] = 'completed'  # Update status
                content_object.milestone_progress = milestone_progress
                content_object.save()
                
                # Handle feedback
                if feedback:
                    OBSPAssignmentNote.objects.create(
                        response=content_object,
                        milestone=OBSPMilestone.objects.get(id=milestone_id),  # Link to the specific milestone
                        created_by=user,
                        note_type='client_feedback',
                        content=feedback,
                        is_aknowledged=False
                    )
                
                # New logic: Check for the next milestone in the dictionary and update if pending
                keys = sorted(milestone_progress.keys())  # Sort keys to determine sequence (e.g., ["1", "2", "3"])
                current_index = keys.index(milestone_key) if milestone_key in keys else -1
                if current_index != -1 and current_index + 1 < len(keys):
                    next_key = keys[current_index + 1]  # Get the next key
                    if milestone_progress.get(next_key) == 'pending':
                        milestone_progress[next_key] = 'in_progress'
                        content_object.milestone_progress = milestone_progress
                        content_object.save()
            else:
                return Response({"error": "Milestone not found in progress tracking."}, status=404)
        
        return Response({"success": True, "message": "Milestone accepted successfully."}, status=200)
    
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found or access denied."}, status=404)
    except Milestone.DoesNotExist:
        return Response({"error": "Milestone not found."}, status=404)
    except OBSPMilestone.DoesNotExist:
        return Response({"error": "OBSP Milestone not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

def raise_dispute(request, workspace_id, milestone_id):
    pass

def extend_milestone_deadline(request, workspace_id, milestone_id):
    pass