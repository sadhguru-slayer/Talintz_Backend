from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from core.models import Project, User, Invitation, Notification
from Profile.models import Feedback, FreelancerReview
from freelancer.models import OBSPEligibilityManager
from freelancer.obsp_eligibility import OBSPEligibilityCalculator
from django.db import transaction
import threading
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from OBSP.models import OBSPAssignment

# Thread-local storage to prevent recursive updates
_thread_local = threading.local()

logger = logging.getLogger(__name__)

@receiver(m2m_changed, sender=Project.assigned_to.through)
def update_obsp_eligibility_on_project_assignment(sender, instance, action, pk_set, **kwargs):
    """
    Update OBSP eligibility when freelancers are assigned/unassigned from projects
    """
    # Only process when freelancers are added or removed
    if action not in ['post_add', 'post_remove']:
        return
    
    # Prevent recursive updates
    if hasattr(_thread_local, 'updating_eligibility'):
        return
    
    _thread_local.updating_eligibility = True
    
    try:
        with transaction.atomic():
            User = get_user_model()
            
            # Get the freelancers that were affected
            if pk_set:
                affected_freelancers = User.objects.filter(
                    id__in=pk_set, 
                    role='freelancer'
                )
                
                for freelancer in affected_freelancers:
                    # Only update if project status is relevant
                    if instance.status in ['completed', 'ongoing', 'cancelled']:
                        from OBSP.models import OBSPTemplate
                        obsp_templates = OBSPTemplate.objects.filter(is_active=True)
                        
                        for obsp_template in obsp_templates:
                            try:
                                from freelancer.models import FreelancerOBSPEligibility
                                eligibility_obj, created = FreelancerOBSPEligibility.objects.get_or_create(
                                    freelancer=freelancer,
                                    obsp_template=obsp_template,
                                    defaults={'eligibility_data': {}}
                                )
                                for level in ['easy', 'medium', 'hard']:
                                    is_eligible, overall_score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                                        freelancer, obsp_template, level
                                    )
                                    eligibility_obj.set_level_eligibility(level, is_eligible, overall_score, analysis)
                            except Exception as e:
                                print(f"Error in eligibility calculation for template {obsp_template.title}: {str(e)}")
                        OBSPEligibilityManager.update_freelancer_cache(freelancer)
    finally:
        if hasattr(_thread_local, 'updating_eligibility'):
            delattr(_thread_local, 'updating_eligibility')
    
@receiver(post_save, sender=Project)
def update_obsp_eligibility_on_project_status_change(sender, instance, created, **kwargs):
    """
    Update OBSP eligibility when project status changes
    """
    if instance.status not in ['completed', 'Completed', 'ongoing', 'Ongoing', 'cancelled', 'Cancelled']:
        return
    
    if hasattr(_thread_local, 'updating_eligibility'):
        return
    
    _thread_local.updating_eligibility = True
    
    try:
        with transaction.atomic():
            assigned_freelancers = instance.assigned_to.filter(role='freelancer')
            for freelancer in assigned_freelancers:
                from OBSP.models import OBSPTemplate
                obsp_templates = OBSPTemplate.objects.filter(is_active=True)
                
                for obsp_template in obsp_templates:
                    try:
                        from freelancer.models import FreelancerOBSPEligibility
                        eligibility_obj, created = FreelancerOBSPEligibility.objects.get_or_create(
                            freelancer=freelancer,
                            obsp_template=obsp_template,
                            defaults={'eligibility_data': {}}
                        )
                        for level in ['easy', 'medium', 'hard']:
                            is_eligible, overall_score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                                freelancer, obsp_template, level
                            )
                            eligibility_obj.set_level_eligibility(level, is_eligible, overall_score, analysis)
                    except Exception as e:
                        print(f"Error in eligibility calculation for template {obsp_template.title}: {str(e)}")
                OBSPEligibilityManager.update_freelancer_cache(freelancer)
                
    finally:
        if hasattr(_thread_local, 'updating_eligibility'):
            delattr(_thread_local, 'updating_eligibility')
            
@receiver(post_save, sender=Feedback)
def update_obsp_eligibility_on_feedback_change(sender, instance, created, **kwargs):
    """Update OBSP eligibility when feedback/rating is added"""
    if not instance.to_user or instance.to_user.role != 'freelancer':
        return
    _thread_local.updating_eligibility = True
    try:
        with transaction.atomic():
            freelancer = instance.to_user
            from OBSP.models import OBSPTemplate
            obsp_templates = OBSPTemplate.objects.filter(is_active=True)
            for obsp_template in obsp_templates:
                try:
                    OBSPEligibilityManager.calculate_and_store_eligibility(
                        freelancer, obsp_template
                    )
                except Exception:
                    pass
            OBSPEligibilityManager.update_freelancer_cache(freelancer)
    finally:
        if hasattr(_thread_local, 'updating_eligibility'):
            delattr(_thread_local, 'updating_eligibility')

@receiver(post_save, sender=FreelancerReview)
def update_obsp_eligibility_on_review_change(sender, instance, created, **kwargs):
    """Update OBSP eligibility when freelancer review is added"""
    if not instance.to_freelancer:
        return
    _thread_local.updating_eligibility = True
    try:
        with transaction.atomic():
            freelancer = instance.to_freelancer
            from OBSP.models import OBSPTemplate
            obsp_templates = OBSPTemplate.objects.filter(is_active=True)
            for obsp_template in obsp_templates:
                try:
                    OBSPEligibilityManager.calculate_and_store_eligibility(
                        freelancer, obsp_template
                    )
                except Exception:
                    pass
            OBSPEligibilityManager.update_freelancer_cache(freelancer)
    finally:
        if hasattr(_thread_local, 'updating_eligibility'):
            delattr(_thread_local, 'updating_eligibility')

@receiver(post_save, sender=User)
def update_obsp_assignments_on_freelancer_change(sender, instance, created, **kwargs):
    """
    Update OBSP assignments when freelancer profile changes
    """
    if instance.role != 'freelancer' or created:
        return
    if hasattr(_thread_local, 'updating_assignments'):
        return
    _thread_local.updating_assignments = True
    try:
        with transaction.atomic():
            from OBSP.models import OBSPAssignment
            assignments = OBSPAssignment.objects.filter(
                assigned_freelancer=instance,
                status__in=['assigned', 'in_progress', 'review']
            )
            for assignment in assignments:
                try:
                    update_assignment_from_freelancer(assignment, instance)
                except Exception:
                    pass
    finally:
        if hasattr(_thread_local, 'updating_assignments'):
            delattr(_thread_local, 'updating_assignments')

@receiver(post_save, sender=Project)
def update_obsp_assignments_on_project_change(sender, instance, created, **kwargs):
    """
    Update OBSP assignments when freelancer's projects change
    """
    if instance.status not in ['completed', 'Completed', 'ongoing', 'Ongoing', 'cancelled', 'Cancelled']:
        return
    if hasattr(_thread_local, 'updating_assignments'):
        return
    _thread_local.updating_assignments = True
    try:
        with transaction.atomic():
            from OBSP.models import OBSPAssignment
            assigned_freelancers = instance.assigned_to.filter(role='freelancer')
            for freelancer in assigned_freelancers:
                assignments = OBSPAssignment.objects.filter(
                    assigned_freelancer=freelancer,
                    status__in=['assigned', 'in_progress', 'review']
                )
                for assignment in assignments:
                    try:
                        update_assignment_from_project(assignment, instance)
                    except Exception:
                        pass
    finally:
        if hasattr(_thread_local, 'updating_assignments'):
            delattr(_thread_local, 'updating_assignments')

@receiver(post_save, sender=Feedback)
def update_obsp_assignments_on_feedback_change(sender, instance, created, **kwargs):
    """
    Update OBSP assignments when freelancer receives feedback
    """
    if not instance.to_user or instance.to_user.role != 'freelancer':
        return
    if hasattr(_thread_local, 'updating_assignments'):
        return
    _thread_local.updating_assignments = True
    try:
        with transaction.atomic():
            from OBSP.models import OBSPAssignment
            freelancer = instance.to_user
            assignments = OBSPAssignment.objects.filter(
                assigned_freelancer=freelancer,
                status__in=['assigned', 'in_progress', 'review']
            )
            for assignment in assignments:
                try:
                    update_assignment_from_feedback(assignment, instance)
                except Exception:
                    pass
    finally:
        if hasattr(_thread_local, 'updating_assignments'):
            delattr(_thread_local, 'updating_assignments')

# Helper functions for updating assignments

def update_assignment_from_freelancer(assignment, freelancer):
    """
    Update OBSP assignment based on freelancer profile changes
    """
    from OBSP.models import OBSPResponse
    
    # Get the OBSP response to recalculate pricing
    obsp_response = assignment.obsp_response
    
    # Recalculate freelancer payout based on current market rates
    new_payout = calculate_freelancer_payout(assignment, freelancer)
    
    # Update assignment if payout changed significantly (>5%)
    if abs(new_payout - float(assignment.freelancer_payout)) / float(assignment.freelancer_payout) > 0.05:
        assignment.freelancer_payout = new_payout
        assignment.platform_fee = calculate_platform_fee(new_payout)
        
        # Add note about the update
        if not assignment.internal_notes:
            assignment.internal_notes = ""
        assignment.internal_notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Payout updated due to freelancer profile changes. New payout: ₹{new_payout}"
        
        assignment.save()

def update_assignment_from_project(assignment, project):
    """
    Update OBSP assignment based on project changes
    """
    freelancer = assignment.assigned_freelancer
    
    # Check if this project affects the freelancer's workload
    if project.assigned_to.filter(id=freelancer.id).exists():
        # Update quality score if project is completed
        if project.status in ['completed', 'Completed']:
            # Calculate new quality score based on project completion
            new_quality_score = calculate_quality_score_from_project(assignment, project)
            
            if new_quality_score and new_quality_score != assignment.quality_score:
                assignment.quality_score = new_quality_score
                
                # Add note about the update
                if not assignment.internal_notes:
                    assignment.internal_notes = ""
                assignment.internal_notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Quality score updated to {new_quality_score} based on project '{project.title}' completion"
                
                assignment.save()

def update_assignment_from_feedback(assignment, feedback):
    """
    Update OBSP assignment based on feedback changes
    """
    freelancer = assignment.assigned_freelancer
    
    # Only update if feedback is for the assigned freelancer
    if feedback.to_user != freelancer:
        return
    
    # Update quality score based on new feedback
    new_quality_score = calculate_quality_score_from_feedback(assignment, feedback)
    
    if new_quality_score and new_quality_score != assignment.quality_score:
        assignment.quality_score = new_quality_score
        
        # Add note about the update
        if not assignment.internal_notes:
            assignment.internal_notes = ""
        assignment.internal_notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Quality score updated to {new_quality_score} based on new feedback (rating: {feedback.rating})"
        
        assignment.save()

# Calculation helper functions

def calculate_freelancer_payout(assignment, freelancer):
    """
    Calculate freelancer payout based on current market rates and freelancer profile
    """
    from OBSP.models import OBSPLevel
    
    # Get the level for this assignment
    level_name = assignment.obsp_response.selected_level
    try:
        level = OBSPLevel.objects.get(
            template=assignment.obsp_response.template,
            level=level_name
        )
        base_price = float(level.price)
    except OBSPLevel.DoesNotExist:
        base_price = float(assignment.freelancer_payout)
    
    # Calculate adjustment factors
    experience_factor = calculate_experience_factor(freelancer)
    rating_factor = calculate_rating_factor(freelancer)
    demand_factor = calculate_demand_factor(freelancer)
    
    # Apply factors to base price
    adjusted_price = base_price * experience_factor * rating_factor * demand_factor
    
    # Round to nearest 100
    return round(adjusted_price / 100) * 100

def calculate_platform_fee(payout):
    """
    Calculate platform fee based on payout amount
    """
    if payout <= 5000:
        return payout * 0.15  # 15% for small projects
    elif payout <= 20000:
        return payout * 0.12  # 12% for medium projects
    else:
        return payout * 0.10  # 10% for large projects

def calculate_experience_factor(freelancer):
    """
    Calculate experience factor based on freelancer's project history
    """
    from core.models import Project
    
    # Count completed projects
    completed_projects = Project.objects.filter(
        assigned_to=freelancer,
        status__in=['completed', 'Completed']
    ).count()
    
    # Experience factor: 1.0 for 0-5 projects, 1.1 for 6-15, 1.2 for 16-30, 1.3 for 30+
    if completed_projects <= 5:
        return 1.0
    elif completed_projects <= 15:
        return 1.1
    elif completed_projects <= 30:
        return 1.2
    else:
        return 1.3

def calculate_rating_factor(freelancer):
    """
    Calculate rating factor based on freelancer's average rating
    """
    from Profile.models import Feedback
    
    # Get average rating
    feedbacks = Feedback.objects.filter(to_user=freelancer)
    if not feedbacks.exists():
        return 1.0
    
    avg_rating = feedbacks.aggregate(avg=models.Avg('rating'))['avg']
    
    # Rating factor: 0.9 for <3.5, 1.0 for 3.5-4.0, 1.1 for 4.0-4.5, 1.2 for 4.5+
    if avg_rating < 3.5:
        return 0.9
    elif avg_rating < 4.0:
        return 1.0
    elif avg_rating < 4.5:
        return 1.1
    else:
        return 1.2

def calculate_demand_factor(freelancer):
    """
    Calculate demand factor based on freelancer's current workload
    """
    from core.models import Project
    
    # Count ongoing projects
    ongoing_projects = Project.objects.filter(
        assigned_to=freelancer,
        status__in=['ongoing', 'Ongoing']
    ).count()
    
    # Demand factor: 1.2 for 0-1 projects, 1.1 for 2-3, 1.0 for 4-5, 0.9 for 6+
    if ongoing_projects <= 1:
        return 1.2  # High demand
    elif ongoing_projects <= 3:
        return 1.1  # Medium demand
    elif ongoing_projects <= 5:
        return 1.0  # Normal demand
    else:
        return 0.9  # Low demand (overloaded)

def calculate_quality_score_from_project(assignment, project):
    """
    Calculate quality score based on project completion
    """
    # Get project feedback
    from Profile.models import Feedback
    
    feedbacks = Feedback.objects.filter(
        project=project,
        to_user=assignment.assigned_freelancer
    )
    
    if not feedbacks.exists():
        return None
    
    # Calculate average rating
    avg_rating = feedbacks.aggregate(avg=models.Avg('rating'))['avg']
    
    # Convert rating to quality score (1-5 scale)
    return min(5.0, max(1.0, avg_rating))

def calculate_quality_score_from_feedback(assignment, feedback):
    """
    Calculate quality score based on new feedback
    """
    from Profile.models import Feedback
    
    # Get all feedback for this freelancer
    all_feedbacks = Feedback.objects.filter(to_user=assignment.assigned_freelancer)
    
    if not all_feedbacks.exists():
        return None
    
    # Calculate weighted average (recent feedback has more weight)
    total_weight = 0
    weighted_sum = 0
    
    for fb in all_feedbacks:
        # Weight based on recency (1-3 months ago = 1.0, 3-6 months = 0.8, 6+ months = 0.6)
        days_ago = (timezone.now() - fb.created_at).days
        if days_ago <= 90:
            weight = 1.0
        elif days_ago <= 180:
            weight = 0.8
        else:
            weight = 0.6
        
        total_weight += weight
        weighted_sum += fb.rating * weight
    
    if total_weight > 0:
        avg_rating = weighted_sum / total_weight
        return min(5.0, max(1.0, avg_rating))
    
    return None

@receiver(post_save, sender=Invitation)
def create_freelancer_invitation_notification(sender, instance, created, **kwargs):
    """
    Create comprehensive notification when an invitation is sent to a freelancer
    """
    if not created or instance.to_user.role not in ['freelancer', 'student']:
        return
    
    try:
        # Get project information
        project = None
        if instance.invitation_type in ['project_assignment', 'interview_request'] and hasattr(instance, 'bid'):
            project = instance.bid.project
        elif instance.invitation_type == 'bid_invitation' and hasattr(instance, 'project'):
            project = instance.project
        else:
            # Fallback: try to get project from related object
            if hasattr(instance, 'related_object'):
                if hasattr(instance.related_object, 'project'):
                    project = instance.related_object.project
                elif hasattr(instance.related_object, 'id') and hasattr(instance.related_object, 'title'):
                    project = instance.related_object
        
        # Prepare notification content based on invitation type
        if instance.invitation_type == 'project_assignment':
            title = "🎯 Project Assignment Invitation"
            if project:
                project_name = project.title[:30] + "..." if len(project.title) > 30 else project.title
                client_name = project.client.username[:20] + "..." if len(project.client.username) > 20 else project.client.username
                notification_text = f"You have been invited to accept the project assignment for <strong><a href='/freelancer/browse-projects/project-view/{project.id}' style='color: #00D4AA; text-decoration: none; cursor: pointer;'>{project_name}</a></strong> by <strong>{client_name}</strong>. Please review the terms and respond within the specified time."
            else:
                notification_text = f"You have been invited to accept a project assignment. Please review the terms and respond within the specified time."
                
        elif instance.invitation_type == 'interview_request':
            title = "📞 Interview Request"
            if project:
                project_name = project.title[:30] + "..." if len(project.title) > 30 else project.title
                client_name = project.client.username[:20] + "..." if len(project.client.username) > 20 else project.client.username
                notification_text = f"You have received an interview request for project <strong><a href='/freelancer/browse-projects/project-view/{project.id}' style='color: #00D4AA; text-decoration: none; cursor: pointer;'>{project_name}</a></strong> by <strong>{client_name}</strong>. Please respond to schedule the interview."
            else:
                notification_text = f"You have received an interview request. Please respond to schedule the interview."
                
        elif instance.invitation_type == 'bid_invitation':
            title = "💼 Bid Invitation"
            if project:
                project_name = project.title[:30] + "..." if len(project.title) > 30 else project.title
                client_name = project.client.username[:20] + "..." if len(project.client.username) > 20 else project.client.username
                notification_text = f"You have been invited to submit a bid for project <strong><a href='/freelancer/browse-projects/project-view/{project.id}' style='color: #00D4AA; text-decoration: none; cursor: pointer;'>{project_name}</a></strong> by <strong>{client_name}</strong>. Please review the project details and submit your proposal."
            else:
                notification_text = f"You have been invited to submit a bid for a project. Please review the project details and submit your proposal."
                
        else:
            # Generic invitation
            title = "📨 New Invitation"
            if project:
                project_name = project.title[:30] + "..." if len(project.title) > 30 else project.title
                client_name = project.client.username[:20] + "..." if len(project.client.username) > 20 else project.client.username
                notification_text = f"You have received an invitation for project <strong><a href='/freelancer/browse-projects/project-view/{project.id}' style='color: #00D4AA; text-decoration: none; cursor: pointer;'>{project_name}</a></strong> by <strong>{client_name}</strong>. Please review and respond."
            else:
                notification_text = f"You have received a new invitation. Please review and respond."
        
        # Create notification for the freelancer
        notification = Notification.objects.create(
            user=instance.to_user,
            title=title,
            notification_text=notification_text,
            type=instance.invitation_type,
            related_model_id=instance.id,
            is_read=False
        )
        
        # Send real-time notification via WebSocket
        channel_layer = get_channel_layer()
        
        # Send notification count update
        async_to_sync(channel_layer.group_send)(
            f"freelancer_{instance.to_user.id}",
            {
                "type": "send_notification_count",
                "notifications_count": Notification.objects.filter(
                    user=instance.to_user, 
                    is_read=False,
                    type__in=['project_assignment', 'interview_request', 'bid_invitation', 'bid_update', 'payment_received', 'project_update']
                ).count()
            }
        )
        
        # Send individual notification with HTML content
        async_to_sync(channel_layer.group_send)(
            f"freelancer_notification_{instance.to_user.id}",
            {
                "type": "send_notification",
                "notification": {
                    "id": notification.id,
                    "title": notification.title,
                    "notification_text": notification_text,  # This contains HTML
                    "created_at": notification.created_at.isoformat(),
                    "related_model_id": notification.related_model_id,
                    "type": notification.type,
                    "project_id": project.id if project else None
                }
            }
        )
        
        logger.info(f"Created comprehensive invitation notification for freelancer {instance.to_user.username} - Type: {instance.invitation_type}")
    except Exception as e:
        logger.error(f"Error creating freelancer invitation notification: {str(e)}")

@receiver(post_save, sender=Project)
def create_freelancer_project_notification(sender, instance, created, **kwargs):
    """
    Create notifications for freelancers when project status changes
    """
    if not instance.assigned_to.exists():
        return
    
    try:
        # Get all assigned freelancers
        assigned_freelancers = instance.assigned_to.filter(role__in=['freelancer', 'student'])
        
        for freelancer in assigned_freelancers:
            # Create notification based on project status
            if instance.status == 'completed':
                title = "Project Completed"
                message = f"Your project '{instance.title}' has been marked as completed."
                notification_type = "project_update"
            elif instance.status == 'cancelled':
                title = "Project Cancelled"
                message = f"Your project '{instance.title}' has been cancelled."
                notification_type = "project_update"
            else:
                continue
            
            notification = Notification.objects.create(
                user=freelancer,
                title=title,
                notification_text=message,
                type=notification_type,
                related_model_id=instance.id,
                is_read=False
            )
            
            # Send real-time notification
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"freelancer_{freelancer.id}",
                {
                    "type": "send_notification_count",
                    "notifications_count": Notification.objects.filter(
                        user=freelancer, 
                        is_read=False,
                        type__in=['project_assignment', 'interview_request', 'bid_update', 'payment_received', 'project_update']
                    ).count()
                }
            )
            
            async_to_sync(channel_layer.group_send)(
                f"freelancer_notification_{freelancer.id}",
                {
                    "type": "send_notification",
                    "notification": {
                        "id": notification.id,
                        "title": notification.title,
                        "notification_text": notification.notification_text,
                        "created_at": notification.created_at.isoformat(),
                        "related_model_id": notification.related_model_id,
                        "type": notification.type
                    }
                }
            )
            
            logger.info(f"Created project notification for freelancer {freelancer.username}")
    except Exception as e:
        logger.error(f"Error creating freelancer project notification: {str(e)}")

@receiver(post_save, sender=OBSPAssignment)
def update_eligibility_on_assignment_change(sender, instance, **kwargs):
    if instance.status == 'completed':
        freelancer = instance.assigned_freelancer
        template = instance.obsp_response.template
        OBSPEligibilityManager.calculate_and_store_eligibility(freelancer, template) 

# Import all other signal modules to ensure they are registered
from freelancer.obsp.obspsignals import *  # Project/OBSP/Feedback/Bank/Doc scoring signals

# If you create more, import them here:
# from .bank_signals import *
# from .document_signals import *



