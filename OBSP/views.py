from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import OBSPTemplate, OBSPLevel, OBSPField, OBSPResponse, OBSPMilestone
from .serializers import (
    OBSPTemplateSerializer, 
    OBSPTemplateDetailSerializer,
    OBSPLevelSerializer,
    OBSPFieldSerializer,
OBSPResponseSerializer
)
from django.db import models
from financeapp.models.wallet import Wallet
from django.db import transaction
from decimal import Decimal
from freelancer.models import FreelancerOBSPEligibility
from core.models import User
import datetime
from django.utils import timezone  # For timezone handling
import datetime  # For date manipulations
from OBSP.models import OBSPResponse, OBSPLevel, OBSPCriteria, OBSPMilestone  # Adjust based on your models
from core.models import User  # If needed, based on your imports
from workspace.models import Workspace  # Assuming this is where Workspace is defined, if relevant
from django.contrib.contenttypes.models import ContentType # Added for generic foreign key check
from OBSP.models import OBSPAssignment # Added for OBSPAssignment check

# Create your views here.

# Create a client purchased OBSPs means OBSPResponses


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_response_list(request):
    """Get a list of OBSPResponses for the authenticated user with custom fields"""
    try:
        responses = OBSPResponse.objects.filter(client=request.user).order_by('-created_at')
        
        # Manually construct the response data
        response_data = []
        for response in responses:
            # Fetch the OBSPLevel instance for the selected level
            level_obj = OBSPLevel.objects.filter(
                template=response.template,
                level=response.selected_level
            ).first()
            
            level_name = level_obj.name if level_obj and level_obj.name else response.get_selected_level_display() or 'Unknown'
            milestone_count = OBSPMilestone.objects.filter(template = response.template,level=level_obj).count()
            if response.milestone_progress:  # Ensure milestone_progress exists and is not empty
                milestone_keys = sorted(response.milestone_progress.keys(), key=int)  # Sort keys as integers
                if milestone_keys:  # Check if there are any keys
                    last_key = milestone_keys[-1]  # Get the last key
                    last_milestone_deadline = response.milestone_progress[last_key].get('deadline')  # Extract deadline
                else:
                    last_milestone_deadline = None  # Fallback if no milestones
            else:
                last_milestone_deadline = None  # Fallback if milestone_progress is empty
            
            data = {
                'id': response.id,
                'title': f"{response.template.title} - {level_name}" if response.template else 'Untitled',
                'level': response.selected_level,
                'features':level_obj.features,
                'created_at':response.created_at,
                'deadline':last_milestone_deadline,
                'status': response.status,
                'price': str(response.total_price) if response.total_price else '0.00',
                'milestones_count': milestone_count if response.template and response.selected_level else 0,  # Filtered by selected level
            }
            response_data.append(data)
        
        return Response({
            'success': True,
            'data': response_data
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_response_detail(request, response_id):
    """Get details of a specific OBSPResponse with custom processing from client_workspace"""
    try:
        obsp_response = get_object_or_404(OBSPResponse, id=response_id, client=request.user)
        
        # Check for OBSPAssignment
        has_obsp_assignment = OBSPAssignment.objects.filter(obsp_response=obsp_response).exists()
        
        # Check for Workspace (assuming Workspace is linked to OBSPResponse via generic foreign key)
        workspace_content_type = ContentType.objects.get_for_model(OBSPResponse)
        has_workspace = Workspace.objects.filter(
            content_type=workspace_content_type,
            object_id=obsp_response.id
        ).exists()
        
        # Set workspace_ready based on both conditions
        workspace_ready = has_obsp_assignment and has_workspace
        
        # If workspace exists, fetch the first one (assuming one per OBSPResponse)
        workspace_id = None
        if has_workspace:
            workspace = Workspace.objects.filter(
                content_type=workspace_content_type,
                object_id=obsp_response.id
            ).first()
            workspace_id = workspace.id  # This will be included in the response if workspace_ready is True
        
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
        assignment = obsp_response.get_active_assignment()  # Assuming this method exists
        if assignment:
            assigned_at = assignment.assigned_at  # Ensure this is a datetime
            try:
                duration_days = int(duration.split('-')[1].split()[0]) if '-' in duration else 14
                deadline = assigned_at + timezone.timedelta(days=duration_days)
            except:
                deadline = assigned_at + timezone.timedelta(days=14)  # Fallback
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
        for milestone in level_milestones:
            milestone_id_str = str(milestone.id)
            status_value = milestone_progress.get(milestone_id_str, {})
            status = status_value.get('status', milestone.status) if isinstance(status_value, dict) else milestone.status
            deadline_milestone = status_value.get('deadline', None) if isinstance(status_value, dict) else None
            
            # Get activities (assuming this is from Workspace or related model)
            # Adjust based on your actual model; this might need integration from workspace
            milestone_activities = []  # Placeholder; replace with actual query if needed
            # Example: milestone_activities = Workspace.objects.filter(obsp_milestone=milestone).select_related('user').order_by('-timestamp')[:20]
            
            milestones.append({
                "id": milestone.id,
                "title": milestone.title,
                "description": milestone.description,
                "milestone_type": milestone.milestone_type,
                "estimated_days": milestone.estimated_days,
                "deadline": deadline_milestone,
                "payout_percentage": float(milestone.payout_percentage),
                "deliverables": milestone.deliverables,
                "status": status,
                "order": milestone.order,
                "activities": [],  # Populate if needed
                "activity_count": 0,  # Or actual count
            })

        phases_data = obsp_response.responses.get('phases', {})
        client_selections = {}
        summary = {
            'total_price': float(obsp_response.total_price) if obsp_response.total_price else 0,
            'selected_level': selected_level,
            'phase_count': len(phases_data),
            'key_selections': [],
        }

        for phase_key, phase in phases_data.items():
            selections = phase.get('selections', [])
            unique_selections = {}
            for sel in selections:
                if sel.get('field_label') not in unique_selections:
                    unique_selections[sel.get('field_label')] = sel
            
            client_selections[phase_key] = {
                'phase_display': phase.get('phase_display', phase_key),
                'selected_fields': [
                    {
                        'field_label': sel.get('field_label'),
                        'selected_value': sel.get('selected_value'),
                        'price_impact': sel.get('price_impact', 0),
                    } for sel in unique_selections.values() if sel.get('selected_value')
                ],
            }
            
            key_selections_for_phase = []
            for sel in selections:
                if sel.get('is_required', False):
                    key_selections_for_phase.append({
                        'field_label': sel.get('field_label'),
                        'selected_value': sel.get('selected_value'),
                    })
            summary['key_selections'].extend(key_selections_for_phase)

        project_details = {
            "title": obsp_level.name,
            "status":obsp_response.status,
            "description": template.description,
            "start_date": assigned_at.isoformat() if assigned_at and isinstance(assigned_at, (datetime.datetime, datetime.date)) else assigned_at,
            "complexity_level": selected_level,
            "category_name": template.category.name if template.category else None,
            "skills_required": {
                "core_skills": [skill.name for skill in (core_skills.all() if hasattr(core_skills, 'all') else core_skills)],
                "optional_skills": [skill.name for skill in (optional_skills.all() if hasattr(optional_skills, 'all') else optional_skills)],
                "required_skills": [skill.name for skill in (required_skills.all() if hasattr(required_skills, 'all') else required_skills)],
            },
            "budget": float(obsp_response.total_price) if obsp_response.total_price else 0,
            "deadline": deadline.isoformat() if deadline and isinstance(deadline, (datetime.datetime, datetime.date)) else deadline,
            "features": features,
            "deliverables": deliverables,
            "client_selections": client_selections,
            "milestones": milestones,  # Include milestones
            "summary": summary,  # Include the summary
            "workspace_ready": workspace_ready,  # Add the new field here
            "workspace_id": workspace_id if workspace_ready else None,  # New field, only if workspace_ready is True
        }
        
        return Response({
            'success': True,
            'data': project_details  # Return the fully constructed project_details
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@staff_member_required
def obsp_preview(request, obsp_id):
    """Preview OBSP template in admin"""
    obsp = get_object_or_404(OBSPTemplate, id=obsp_id)
    return render(request, 'admin/OBSP/obsp_preview.html', {'obsp': obsp})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_list(request):
    """Get list of active OBSP templates with optimized data"""
    try:
        
        # Get active OBSP templates with minimal data
        obsps = OBSPTemplate.objects.filter(is_active=True).prefetch_related('levels')
        
        # Calculate statistics
        total_obsps = obsps.count()
        unique_industries = obsps.values_list('industry', flat=True).distinct().count()
        
        # Calculate price range
        all_prices = []
        for obsp in obsps:
            for level in obsp.levels.filter(is_active=True):
                all_prices.append(float(level.price))
        
        min_price = min(all_prices) if all_prices else 0
        max_price = max(all_prices) if all_prices else 0
        
        # Get completed projects count (submitted responses)
        completed_count = OBSPResponse.objects.filter(
            status__in=['submitted', 'processing', 'completed']
        ).count()
        
        # Prepare minimal data for list view
        obsp_list_data = []
        for obsp in obsps:
            # Get price range for this OBSP
            obsp_prices = [float(level.price) for level in obsp.levels.filter(is_active=True)]
            obsp_min_price = min(obsp_prices) if obsp_prices else 0
            obsp_max_price = max(obsp_prices) if obsp_prices else 0
            level_count = obsp.levels.filter(is_active=True).count()
            
            obsp_data = {
                'id': obsp.id,
                'title': obsp.title,
                'category': {
                    'id': obsp.category.id,
                    'name': obsp.category.name
                },
                'category_display': obsp.category.name,
                'industry': obsp.industry,
                'industry_display': obsp.get_industry_display(),
                'description': obsp.description,
                'price_range': {
                    'min': obsp_min_price,
                    'max': obsp_max_price
                },
                'level_count': level_count,
                'is_active': obsp.is_active
            }
            obsp_list_data.append(obsp_data)
        
        # Prepare header statistics
        header_stats = {
            'total_obsps': total_obsps,
            'unique_industries': unique_industries,
            'completed_projects': completed_count,
            'price_range': {
                'min': min_price,
                'max': max_price
            }
        }
        
        return Response({
            'success': True,
            'data': {
                'obsps': obsp_list_data,
                'header_stats': header_stats
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_detail(request, obsp_id):
    """Get detailed OBSP template with levels, milestones, and draft information"""
    try:
        obsp = get_object_or_404(OBSPTemplate, id=obsp_id, is_active=True)
        
        # Get levels ordered by order field
        levels = obsp.levels.filter(is_active=True).order_by('order')
        
        # Get all draft responses for this user and template
        draft_responses = OBSPResponse.objects.filter(
            template=obsp,
            client=request.user,
            status='draft'
        ).values('selected_level', 'id', 'total_price', 'created_at')
        
        # Create a lookup dictionary for draft responses
        draft_lookup = {draft['selected_level']: draft for draft in draft_responses}
        
        # Prepare the response data
        response_data = {
            'id': obsp.id,
            'title': obsp.title,
            'category': {
                'id': obsp.category.id,
                'name': obsp.category.name
            },
            'category_display': obsp.category.name,
            'industry': obsp.industry,
            'industry_display': obsp.get_industry_display(),
            'description': obsp.description,
            'base_price': float(obsp.base_price),
            'currency': obsp.currency,
            'is_active': obsp.is_active,
            'created_at': obsp.created_at,
            'updated_at': obsp.updated_at,
            'levels': {}
        }
        
        # Add levels data with milestones and draft information
        for level in levels:
            # Get milestones for this level
            milestones = level.level_milestones.filter(is_active=True).order_by('order')
            
            # Check if there's a draft for this level
            draft_info = draft_lookup.get(level.level)
            
            level_data = {
                'id': level.id,
                'level': level.level,
                'level_display': level.get_level_display(),
                'name': level.name,
                'price': float(level.price),
                'duration': level.duration,
                'features': level.features,
                'deliverables': level.deliverables,
                'is_active': level.is_active,
                'order': level.order,
                'milestones': [],
                'draft_info': None  # Will be populated if draft exists
            }
            
            # Add draft information if exists
            if draft_info:
                level_data['draft_info'] = {
                    'draft_id': draft_info['id'],
                    'draft_price': float(draft_info['total_price']),
                    'draft_created_at': draft_info['created_at'],
                    'has_draft': True
                }
            else:
                level_data['draft_info'] = {
                    'has_draft': False
                }
            
            # Add milestones data
            for milestone in milestones:
                milestone_data = {
                    'id': milestone.id,
                    'milestone_type': milestone.milestone_type,
                    'milestone_type_display': milestone.get_milestone_type_display(),
                    'title': milestone.title,
                    'description': milestone.description,
                    'estimated_days': milestone.estimated_days,
                    'payout_percentage': float(milestone.payout_percentage),
                    'payout_amount': float(milestone.get_payout_amount(level.price)),
                    'deliverables': milestone.deliverables,
                    'quality_checklist': milestone.quality_checklist,
                    'client_approval_required': milestone.client_approval_required,
                    'status': milestone.status,
                    'status_display': milestone.get_status_display(),
                    'order': milestone.order
                }
                level_data['milestones'].append(milestone_data)
            
            response_data['levels'][level.level] = level_data
        
        return Response({
            'success': True,
            'data': response_data
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
def obsp_fields(request, obsp_id, level=None):
    """Get OBSP fields for a specific level, grouped by phase with draft data"""
    try:
        obsp = get_object_or_404(OBSPTemplate, id=obsp_id, is_active=True)
        
        # Get fields that are visible for the specified level
        fields = obsp.fields.filter(is_active=True).order_by('phase', 'order')  # Already ordered by phase and order
        if level:
            # Filter fields based on level visibility
            fields = fields.filter(
                models.Q(visibility_rule='generic') |
                models.Q(visibility_rule=level) |
                models.Q(visibility_rule__contains=level)
            )
        
        # Check for existing draft response for this user and level
        draft_response = OBSPResponse.objects.filter(
            template=obsp,
            client=request.user,
            selected_level=level,
            status='draft'
        ).first()
        
        # Group fields by phase
        phases = {}
        for field in fields:
            phase = field.phase
            if phase not in phases:
                phases[phase] = {
                    'phase': phase,
                    'phase_display': field.get_phase_display_name(),
                    'phase_description': field.get_phase_description(),
                    'fields': [],
                    'draft_data': None
                }
            
            # Add field to phase
            field_data = {
                'id': field.id,
                'label': field.label,
                'field_type': field.field_type,
                'is_required': field.is_required,
                'has_price_impact': field.has_price_impact,
                'price_impact': field.price_impact,
                'placeholder': field.placeholder,
                'help_text': field.help_text,
                'options': field.get_options_with_pricing()
            }
            phases[phase]['fields'].append(field_data)
        
        # Add draft data to each phase if exists
        if draft_response:
            draft_responses_data = draft_response.responses or {}
            for phase_key, phase_data in phases.items():
                phase_responses = {}
                phase_impacts = {}
                
                if 'phases' in draft_responses_data:
                    phase_info = draft_responses_data['phases'].get(phase_key, {})
                    selections = phase_info.get('selections', [])
                    
                    for selection in selections:
                        field_id = selection.get('field_id')
                        selected_value = selection.get('selected_value')
                        price_impact = selection.get('price_impact', 0)
                        
                        if field_id and selected_value is not None:
                            phase_responses[field_id] = selected_value
                            if price_impact > 0:
                                phase_impacts[field_id] = price_impact
                
                total_phase_impact = sum(phase_impacts.values())
                phases[phase_key]['draft_data'] = {
                    'has_draft': True,
                    'draft_id': draft_response.id,
                    'draft_price': draft_response.total_price,
                    'responses': phase_responses,
                    'phaseImpacts': {phase_key: total_phase_impact}
                }
        
        # Define the desired phase order
        DESIRED_PHASE_ORDER = ['basic', 'core_features', 'add_ons']  # Only these three phases
        
        # Sort phases based on DESIRED_PHASE_ORDER
        sorted_phases = {phase: phases[phase] for phase in DESIRED_PHASE_ORDER if phase in phases}
        
        # Convert to list in the desired order
        phases_list = [sorted_phases[phase] for phase in DESIRED_PHASE_ORDER if phase in sorted_phases]
        
        return Response({
            'success': True,
            'data': {
                'phases': phases_list,  # Now in the correct order
                'has_draft': draft_response is not None,
                'draft_id': draft_response.id if draft_response else None,
                'draft_price': draft_response.total_price if draft_response else None
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_obsp_response(request, obsp_id):
    """Submit OBSP response with atomic wallet balance checking"""
    try:
        
        obsp = get_object_or_404(OBSPTemplate, id=obsp_id, is_active=True)
        
        # Extract data from request
        selected_level = request.data.get('selected_level')
        dynamic_responses = request.data.get('dynamicResponses', {})
        phase_data = request.data.get('phaseData', {})
        total_price = request.data.get('totalPrice', 0)
        wallet_payment = request.data.get('wallet_payment', False)
        response_status = request.data.get('status', 'submitted')
        draft_id = request.data.get('draft_id')
        
        # Check for existing OBSP responses for this client and template
        existing_responses = OBSPResponse.objects.filter(
            template=obsp,
            client=request.user
        ).order_by('-created_at')
        
        # Check if client already has a response for the same level with processing/submitted status
        existing_same_level = existing_responses.filter(
            selected_level=selected_level,
            status__in=['submitted', 'processing']
        ).first()
        
        
        if existing_same_level:
            return Response({
                'success': False,
                'error': f'You have already purchased the {existing_same_level.get_selected_level_display()} level of this package. Please try a different level or visit your workspace.',
                'existing_response_id': existing_same_level.id,
                'existing_status': existing_same_level.status,
                'blocked': True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if client has any active responses (submitted/processing) for this template
        active_responses = existing_responses.filter(
            status__in=['submitted', 'processing']
        )
        
        # If client has active responses, check if they're for different levels
        if active_responses.exists():
            active_levels = set(response.selected_level for response in active_responses)
            if selected_level in active_levels:
                return Response({
                    'success': False,
                    'error': f'You already have an active {active_responses.filter(selected_level=selected_level).first().get_selected_level_display()} level purchase. Please complete or cancel it before purchasing again.',
                    'blocked': True
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for existing draft response for the same level, client, template
        existing_draft = existing_responses.filter(
            selected_level=selected_level,
            status='draft'
        ).first()
        
        # Build detailed response structure
        detailed_responses = {
            'selected_level': selected_level,
            'total_price': float(total_price),
            'phases': {},
            'summary': {
                'base_price': 0,
                'add_ons_total': 0,
                'phase_breakdown': {}
            }
        }
        
        # Get base price for selected level
        if selected_level:
            try:
                level = obsp.levels.get(level=selected_level, is_active=True)
                detailed_responses['summary']['base_price'] = float(level.price)
            except OBSPLevel.DoesNotExist:
                pass
        
        # Process each phase
        for phase_key, phase_info in phase_data.items():
            phase_responses = phase_info.get('responses', {})
            phase_impacts = phase_info.get('phaseImpacts', {})
            
            # Find phase display info
            phase_display = "Unknown Phase"
            phase_description = ""
            
            # Get fields for this specific phase
            phase_fields_query = obsp.fields.filter(phase=phase_key, is_active=True)
            if phase_fields_query.exists():
                phase_display = phase_fields_query.first().get_phase_display_name()
                phase_description = phase_fields_query.first().get_phase_description()
            
            phase_detail = {
                'phase_key': phase_key,
                'phase_display': phase_display,
                'phase_description': phase_description,
                'selections': [],
                'phase_total': float(phase_impacts.get(phase_key, 0)),
                'has_selections': len(phase_responses) > 0
            }
            
            
            # Process each field response in this phase, but only if it belongs to this phase
            unique_fields = {}  # Use a dict to ensure uniqueness by field_id
            for field_id, field_value in phase_responses.items():
                try:
                    field = obsp.fields.get(id=field_id, is_active=True)
                    
                    # Add check: Only include if the field's phase matches the current phase_key
                    if field.phase == phase_key:
                        field_detail = {
                            'field_id': field_id,
                            'field_label': field.label,
                            'field_type': field.field_type,
                            'field_help_text': field.help_text,
                            'is_required': field.is_required,
                            'has_price_impact': field.has_price_impact,
                            'selected_value': field_value,
                            'price_impact': 0,
                            'options_detail': []
                        }
                        
                        # Handle different field types and their pricing
                        if field.field_type in ['radio', 'select']:
                            if field.options and isinstance(field_value, str):
                                for option in field.options:
                                    if isinstance(option, dict):
                                        if option.get('text') == field_value:
                                            field_detail['selected_value'] = option.get('text', field_value)
                                            field_detail['price_impact'] = float(option.get('price', 0))
                                            field_detail['options_detail'] = [{
                                                'text': option.get('text', ''),
                                                'description': option.get('description', ''),
                                                'price': float(option.get('price', 0)),
                                                'selected': True
                                            }]
                                            break
                                    elif option == field_value:
                                        field_detail['options_detail'] = [{
                                            'text': option,
                                            'description': '',
                                            'price': 0,
                                            'selected': True
                                        }]
                                        break
                        
                        elif field.field_type == 'checkbox':
                            if field.options and isinstance(field_value, list):
                                selected_options = []
                                total_field_impact = 0
                                
                                for option in field.options:
                                    if isinstance(option, dict):
                                        is_selected = option.get('text') in field_value
                                        option_detail = {
                                            'text': option.get('text', ''),
                                            'description': option.get('description', ''),
                                            'price': float(option.get('price', 0)),
                                            'selected': is_selected
                                        }
                                        selected_options.append(option_detail)
                                        if is_selected:
                                            total_field_impact += float(option.get('price', 0))
                                    else:
                                        is_selected = option in field_value
                                        selected_options.append({
                                            'text': option,
                                            'description': '',
                                            'price': 0,
                                            'selected': is_selected
                                        })
                                
                                field_detail['options_detail'] = selected_options
                                field_detail['price_impact'] = total_field_impact
                        
                        else:
                            field_detail['price_impact'] = float(field.price_impact) if field.has_price_impact else 0
                        
                        # Add to unique fields to prevent duplicates in this phase
                        unique_fields[field_id] = field_detail  # Use field_id as key for uniqueness
                        
                        
                except OBSPField.DoesNotExist:
                    print(f"Field {field_id} not found for phase {phase_key}")
            
            # Now add the unique fields to phase_detail
            phase_detail['selections'] = [detail for field_id, detail in unique_fields.items()]
            
            # Add phase to detailed responses
            detailed_responses['phases'][phase_key] = phase_detail
            
            # Update summary
            if phase_detail['phase_total'] > 0:
                detailed_responses['summary']['phase_breakdown'][phase_key] = {
                    'phase_display': phase_display,
                    'amount': phase_detail['phase_total']
                }
                detailed_responses['summary']['add_ons_total'] += phase_detail['phase_total']
        
        # Handle wallet payment with atomic balance checking
        if wallet_payment and response_status == 'submitted':
            try:
                # Atomic transaction for wallet operations
                with transaction.atomic():
                    # Get user's wallet with row lock
                    wallet = Wallet.objects.select_for_update().get(user=request.user)
        
                    # Fresh balance check (atomic)
                    available_balance = wallet.available_balance
        
                    if available_balance < total_price:
                        return Response({
                            'success': False,
                            'error': f'Insufficient wallet balance. Available: ₹{available_balance}, Required: ₹{total_price}',
                            'insufficient_funds': True,
                            'available_balance': float(available_balance),
                            'required_amount': float(total_price)
                        }, status=status.HTTP_400_BAD_REQUEST)
        
                    # Use new method instead of withdraw
                    wallet_tx = wallet.process_obsp_purchase(
                        total_price,
                        f"OBSP Purchase: {obsp.title} - {selected_level} level"
                    )
            except Wallet.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Wallet not found for the user.'
                }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'An unexpected error occurred: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # After creating or updating the response
        if existing_draft:
            # Update existing draft response
            existing_draft.responses = detailed_responses
            existing_draft.total_price = detailed_responses['total_price']
            existing_draft.status = response_status
            existing_draft.save()
            response = existing_draft
        elif draft_id:
            # Update specific draft by ID
            try:
                response = OBSPResponse.objects.get(id=draft_id, client=request.user, status='draft')
                response.responses = detailed_responses
                response.total_price = detailed_responses['total_price']
                response.status = response_status
                response.save()
            except OBSPResponse.DoesNotExist:
                # Draft not found, create new
                response = OBSPResponse.objects.create(
                    template=obsp,
                    client=request.user,
                    selected_level=selected_level,
                    responses=detailed_responses,
                    total_price=detailed_responses['total_price'],
                    status=response_status
                )
        else:
            # Create new response
            response = OBSPResponse.objects.create(
                template=obsp,
                client=request.user,
                selected_level=selected_level,
                responses=detailed_responses,
                total_price=detailed_responses['total_price'],
                status=response_status
            )
        
        # New logic: Check for eligible freelancers
        if selected_level:  # Ensure selected_level is defined
            eligible_freelancers = FreelancerOBSPEligibility.objects.filter(
                obsp_template=obsp,  # Match the OBSP template
                eligibility_data__has_key=selected_level  # Ensure the level exists in eligibility_data
            ).filter(  # Dynamically filter for is_eligible
                **{f'eligibility_data__{selected_level}__is_eligible': True}
            ).values('freelancer__id', 'freelancer__username')  # Get freelancer IDs and usernames
            
            eligible_list = list(eligible_freelancers)  # Convert queryset to list for response
        else:
            eligible_list = []  # Default to empty list if selected_level is not set
        
        return Response({
            'success': True,
            'data': {
                'response_id': response.id,
                'total_price': float(response.total_price),
                'status': response.status,
                'detailed_response': detailed_responses,
                'wallet_payment_processed': wallet_payment,
                'updated_existing_draft': existing_draft is not None,
                'eligible_freelancers': eligible_list,  # Include the list of eligible freelancers
            }
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
def check_purchase_eligibility(request, obsp_id, level=None):
    """Check if client can purchase a specific OBSP level"""
    try:
        obsp = get_object_or_404(OBSPTemplate, id=obsp_id, is_active=True)
        
        if not level:
            return Response({
                'success': False,
                'error': 'Level parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get existing responses for this client and template
        existing_responses = OBSPResponse.objects.filter(
            template=obsp,
            client=request.user
        ).order_by('-created_at')
        
        # Check for same level with active status
        same_level_active = existing_responses.filter(
            selected_level=level,
            status__in=['submitted', 'processing']
        ).first()
        
        if same_level_active:
            return Response({
                'success': False,
                'eligible': False,
                'reason': 'already_purchased_same_level',
                'message': f'You have already purchased the {same_level_active.get_selected_level_display()} level of this package. Please try a different level or visit your workspace.',
                'existing_response': {
                    'id': same_level_active.id,
                    'status': same_level_active.status,
                    'created_at': same_level_active.created_at
                }
            })
        
        # Check for any active responses (different levels)
        active_responses = existing_responses.filter(
            status__in=['submitted', 'processing']
        )
        
        if active_responses.exists():
            active_levels = [response.selected_level for response in active_responses]
            return Response({
                'success': True,
                'eligible': True,
                'warning': True,
                'message': f'You have active purchases for levels: {", ".join(active_levels)}. You can purchase this {level} level as well.',
                'active_responses': [
                    {
                        'id': response.id,
                        'level': response.selected_level,
                        'status': response.status,
                        'created_at': response.created_at
                    } for response in active_responses
                ]
            })
        
        # All good - can purchase
        return Response({
            'success': True,
            'eligible': True,
            'message': 'You can purchase this package level.'
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
def get_draft_response(request, obsp_id, level=None):
    """Get draft response data for form pre-filling"""
    try:
        obsp = get_object_or_404(OBSPTemplate, id=obsp_id, is_active=True)
        
        if not level:
            return Response({
                'success': False,
                'error': 'Level parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get draft response for this user, template, and level
        draft_response = OBSPResponse.objects.filter(
            template=obsp,
            client=request.user,
            selected_level=level,
            status='draft'
        ).first()
        
        if not draft_response:
            return Response({
                'success': False,
                'error': 'No draft found for this level',
                'has_draft': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Extract form data from the detailed responses
        detailed_responses = draft_response.responses or {}
        
        # Extract field responses for form pre-filling
        form_data = {}
        phase_data = {}
        
        # Process each phase
        for phase_key, phase_info in detailed_responses.get('phases', {}).items():
            phase_responses = {}
            phase_impacts = {}
            
            # Extract field responses from this phase
            for selection in phase_info.get('selections', []):
                field_id = selection.get('field_id')
                selected_value = selection.get('selected_value')
                
                if field_id and selected_value is not None:
                    phase_responses[field_id] = selected_value
                    
                    # Also extract price impact if available
                    price_impact = selection.get('price_impact', 0)
                    if price_impact > 0:
                        phase_impacts[field_id] = price_impact
            
            # Add to phase data
            if phase_responses:
                phase_data[phase_key] = {
                    'responses': phase_responses,
                    'phaseImpacts': {phase_key: sum(phase_impacts.values())}
                }
                
                # Also add to main form data for backward compatibility
                form_data.update(phase_responses)
        
        return Response({
            'success': True,
            'data': {
                'draft_id': draft_response.id,
                'selected_level': draft_response.selected_level,
                'total_price': float(draft_response.total_price),
                'created_at': draft_response.created_at.isoformat(),
                'updated_at': draft_response.updated_at.isoformat(),
                'form_data': form_data,  # Flattened for easy form filling
                'phase_data': phase_data,  # Structured by phase
                'detailed_responses': detailed_responses,  # Full response data
                'has_draft': True
            }
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_freelancer_to_obsp(request, response_id):
    """Assign a freelancer to an OBSP response (Talintz admin only)"""
    try:
        # Check if user is Talintz admin
        if request.user.role != 'admin' and not request.user.is_staff:
            return Response({
                'success': False,
                'error': 'Only Talintz administrators can assign freelancers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        obsp_response = get_object_or_404(OBSPResponse, id=response_id)
        
        # Extract data
        freelancer_id = request.data.get('freelancer_id')
        freelancer_payout = request.data.get('freelancer_payout')
        platform_fee = request.data.get('platform_fee')
        
        if not freelancer_id:
            return Response({
                'success': False,
                'error': 'freelancer_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get freelancer
        freelancer = get_object_or_404(User, id=freelancer_id, role='freelancer')
        
        # Check if already assigned
        existing_assignment = obsp_response.assignments.filter(
            assigned_freelancer=freelancer,
            status__in=['assigned', 'in_progress', 'review']
        ).first()
        
        if existing_assignment:
            return Response({
                'success': False,
                'error': 'Freelancer is already assigned to this project'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create assignment
        assignment = obsp_response.assign_freelancer(
            freelancer=freelancer,
            assigned_by=request.user,
            freelancer_payout=freelancer_payout,
            platform_fee=platform_fee
        )
        
        return Response({
            'success': True,
            'data': {
                'assignment_id': assignment.id,
                'freelancer_name': freelancer.username,
                'status': assignment.status,
                'payout': float(assignment.freelancer_payout)
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_obsp_assignments(request, response_id):
    """Get all assignments for an OBSP response"""
    try:
        obsp_response = get_object_or_404(OBSPResponse, id=response_id)
        
        # Check permissions
        if request.user.role == 'client':
            # Client can only see their own responses
            if obsp_response.client != request.user:
                return Response({
                    'success': False,
                    'error': 'Access denied'
                }, status=status.HTTP_403_FORBIDDEN)
        elif request.user.role == 'freelancer':
            # Freelancer can only see their own assignments
            assignments = obsp_response.assignments.filter(assigned_freelancer=request.user)
        else:
            # Admin can see all assignments
            assignments = obsp_response.assignments.all()
        
        assignments_data = []
        for assignment in assignments:
            assignments_data.append({
                'id': assignment.id,
                'freelancer_name': assignment.assigned_freelancer.username,
                'status': assignment.status,
                'progress_percentage': assignment.progress_percentage,
                'assigned_at': assignment.assigned_at.isoformat(),
                'started_at': assignment.started_at.isoformat() if assignment.started_at else None,
                'completed_at': assignment.completed_at.isoformat() if assignment.completed_at else None,
                'freelancer_payout': float(assignment.freelancer_payout),
                'current_milestone': assignment.current_milestone.title if assignment.current_milestone else None,
                'quality_score': assignment.quality_score,
                'deadline_met': assignment.deadline_met
            })
        
        return Response({
            'success': True,
            'data': {
                'obsp_title': obsp_response.template.title,
                'client_name': obsp_response.client.username,
                'selected_level': obsp_response.selected_level,
                'total_price': float(obsp_response.total_price),
                'assignments': assignments_data
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


