from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from OBSP.models import OBSPTemplate, OBSPResponse, OBSPApplication
from freelancer.models import FreelancerOBSPEligibility, OBSPEligibilityManager
from django.db.models import Prefetch
from django.db.models import Min, Max
import json
import traceback

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_list_with_eligibility(request):
    """
    Get all OBSP templates with freelancer's eligibility status
    This is the main view for freelancers to see available OBSPs
    """
    try:
        freelancer = request.user
        
        # Get all active OBSP templates
        obsp_templates = OBSPTemplate.objects.filter(is_active=True).prefetch_related(
            'levels', 'criteria'
        )
        
        # Get freelancer's eligibility data
        eligibility_data = {}
        freelancer_eligibility = FreelancerOBSPEligibility.objects.filter(
            freelancer=freelancer
        ).select_related('obsp_template')
        
        
        for eligibility in freelancer_eligibility:
            eligibility_data[eligibility.obsp_template.id] = eligibility
        
        # Get freelancer's applications to check applied status
        freelancer_applications = OBSPApplication.objects.filter(
            freelancer=freelancer
        ).values_list('obsp_template_id', 'selected_level')
        
        # Create a set of applied template-level combinations
        applied_combinations = set()
        for template_id, level in freelancer_applications:
            applied_combinations.add(f"{template_id}_{level}")
        
        # Build response
        obsp_list = []
        for obsp_template in obsp_templates:
            try:
                
                # Get eligibility for this OBSP
                eligibility = eligibility_data.get(obsp_template.id)
                
                # Calculate price range
                levels = obsp_template.levels.all()
                
                if not levels.exists():
                    continue
                
                min_price = min([level.price for level in levels]) if levels else 0
                max_price = max([level.price for level in levels]) if levels else 0
                
                # Build level information with eligibility and applied status
                level_info = []
                for level in levels:
                    try:
                        
                        # Check if this level is applied
                        is_applied = f"{obsp_template.id}_{level.level}" in applied_combinations
                        
                        level_data = {
                            'id': level.id,
                            'name': level.name,
                            'level': level.level,
                            'price': float(level.price),
                            'duration': level.duration,
                            'is_applied': is_applied,  # Add applied status
                        }
                        
                        # Add eligibility data if available
                        if eligibility:
                            try:
                                # Use level.level instead of level.name.lower()
                                level_eligibility = eligibility.get_level_eligibility(level.level)
                                level_data.update({
                                    'is_eligible': level_eligibility.get('is_eligible', False),
                                    'score': level_eligibility.get('score', 0),
                                    'last_calculated': level_eligibility.get('last_calculated', None)
                                })
                            except Exception as e:
                                # Fallback if eligibility calculation fails
                                level_data.update({
                                    'is_eligible': False,
                                    'score': 0,
                                    'last_calculated': None
                                })
                        else:
                            level_data.update({
                                'is_eligible': False,
                                'score': 0,
                                'last_calculated': None
                            })
                        
                        level_info.append(level_data)
                        
                    except Exception as e:
                        # Add basic level data without eligibility
                        level_info.append({
                            'id': level.id,
                            'name': level.name,
                            'level': level.level,
                            'price': float(level.price),
                            'duration': level.duration,
                            'is_eligible': False,
                            'score': 0,
                            'last_calculated': None,
                            'is_applied': f"{obsp_template.id}_{level.level}" in applied_combinations,
                        })
                
                # Get overall eligibility summary
                if eligibility:
                    try:
                        eligible_levels = eligibility.get_all_eligible_levels()
                        highest_level = eligibility.get_highest_eligible_level()
                    except Exception as e:
                        eligible_levels = []
                        highest_level = None
                else:
                    eligible_levels = []
                    highest_level = None
                
                obsp_data = {
                    'id': obsp_template.id,
                    'title': obsp_template.title,
                    'category': {
                        'id': obsp_template.category.id,
                        'name': obsp_template.category.name
                    },
                    'industry': obsp_template.industry,
                    'industry_display': obsp_template.get_industry_display(),
                    'description': obsp_template.description,
                    'price_range': {
                        'min': float(min_price),
                        'max': float(max_price)
                    },
                    'levels': level_info,
                    'eligibility_summary': {
                        'eligible_levels': eligible_levels,
                        'highest_eligible_level': highest_level,
                        'total_levels': len(levels),
                        'is_any_eligible': len(eligible_levels) > 0
                    },
                    'is_active': obsp_template.is_active
                }
                
                obsp_list.append(obsp_data)
                
            except Exception as e:
                # Continue with next OBSP instead of failing completely
                continue
        
        # Sort by eligibility (eligible first, then by title)
        obsp_list.sort(key=lambda x: (not x['eligibility_summary']['is_any_eligible'], x['title']))
        
        return Response({
            'success': True,
            'data': {
                'obsps': obsp_list,
                'total_count': len(obsp_list),
                'eligible_count': sum(1 for obsp in obsp_list if obsp['eligibility_summary']['is_any_eligible'])
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obsp_detail_with_eligibility(request, obsp_id):
    """
    Get detailed OBSP information with full eligibility analysis and budget range.
    """
    try:
        freelancer = request.user
        
        # Get OBSP template
        obsp_template = OBSPTemplate.objects.get(id=obsp_id, is_active=True)
        template_levels = obsp_template.levels.values_list('level', flat=True).distinct()
        
        # Calculate budget range
        budget_range = {
            'min': obsp_template.levels.aggregate(min_price=Min('price'))['min_price'],
            'max': obsp_template.levels.aggregate(max_price=Max('price'))['max_price']
        }
        
        # Get detailed analysis for all levels
        detailed_analysis = {}
        applied_levels = set(
            OBSPApplication.objects.filter(
                freelancer=freelancer,
                obsp_template=obsp_template
            ).values_list('selected_level', flat=True)
        )

        # Get existing eligibility data
        try:
            freelancer_eligibility = FreelancerOBSPEligibility.objects.get(
                freelancer=freelancer,
                obsp_template=obsp_template
            )
            
            for level in template_levels:
                level_data = freelancer_eligibility.get_level_eligibility(level)
                
                # Check if there's valid proof data
                proof_data = level_data.get('proof', {})
                if isinstance(proof_data, dict) and 'error' in proof_data:
                    # If there's an error in proof, provide default data
                    detailed_analysis[level] = {
                        'is_eligible': False,
                        'is_applied': level in applied_levels,
                        'score': 0,
                        'proof': {
                            'level': level,
                            'proof': {
                                'rating': {'min_required': 4.0, 'average_rating': 0},
                                'skill_match': {'min_required': 60.0, 'required_match_percentage': 0},
                                'project_experience': {'required_projects': 1, 'completed_projects_count': 0},
                                'deadline_compliance': {'min_required': 90.0, 'compliance_rate': 0}
                            },
                            'reasons': [f"Level {level} criteria not configured yet"]
                        },
                        'reasons': [f"Level {level} criteria not configured yet"]
                    }
                else:
                    # Use the valid data
                    detailed_analysis[level] = {
                        'is_eligible': level_data.get('is_eligible', False),
                        'is_applied': level in applied_levels,
                        'score': level_data.get('score', 0),
                        'proof': proof_data,
                        'reasons': proof_data.get('reasons', [])
                    }
                    
        except FreelancerOBSPEligibility.DoesNotExist:
            # Create default analysis for each level
            for level in template_levels:
                detailed_analysis[level] = {
                    'is_eligible': False,
                    'is_applied': level in applied_levels,
                    'score': 0,
                    'proof': {
                        'level': level,
                        'proof': {
                            'rating': {'min_required': 4.0, 'average_rating': 0},
                            'skill_match': {'min_required': 60.0, 'required_match_percentage': 0},
                            'project_experience': {'required_projects': 1, 'completed_projects_count': 0},
                            'deadline_compliance': {'min_required': 90.0, 'compliance_rate': 0}
                        },
                        'reasons': ["Initial eligibility calculation needed"]
                    },
                    'reasons': ["Initial eligibility calculation needed"]
                }
        
        # Build response
        response_data = {
            'obsp': {
                'id': obsp_template.id,
                'title': obsp_template.title,
                'category': obsp_template.category.name,
                'industry': obsp_template.get_industry_display(),
                'description': obsp_template.description,
                'is_active': obsp_template.is_active,
                'budget_range': budget_range
            },
            'eligibility_analysis': detailed_analysis,
            'recommendations': _generate_recommendations(detailed_analysis)
        }
        
        return Response({
            'success': True,
            'data': response_data
        })
        
    except OBSPTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': 'OBSP not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _generate_recommendations(analysis):
    """Generate improvement recommendations based on eligibility analysis"""
    recommendations = []
    
    for level, data in analysis.items():
        if not data['is_eligible']:
            proof = data.get('proof', {})
            
            # Project experience recommendations
            if 'project_experience' in proof:
                project_data = proof['project_experience']
                if project_data.get('completed_projects_count', 0) < project_data.get('required_projects', 0):
                    recommendations.append({
                        'level': level,
                        'type': 'project_experience',
                        'message': f'Complete {project_data["required_projects"] - project_data["completed_projects_count"]} more projects in {", ".join(project_data.get("required_domains", []))}',
                        'priority': 'high'
                    })
            
            # Skill recommendations
            if 'skill_match' in proof:
                skill_data = proof['skill_match']
                if skill_data.get('required_match_percentage', 0) < skill_data.get('min_required', 60):
                    missing_skills = set(skill_data.get('required_skills', [])) - set(skill_data.get('required_matches', []))
                    if missing_skills:
                        recommendations.append({
                            'level': level,
                            'type': 'skill_match',
                            'message': f'Learn or add these skills: {", ".join(missing_skills)}',
                            'priority': 'medium'
                        })
            
            # Rating recommendations
            if 'rating' in proof:
                rating_data = proof['rating']
                if rating_data.get('average_rating', 0) < rating_data.get('min_required', 4):
                    recommendations.append({
                        'level': level,
                        'type': 'rating',
                        'message': f'Improve your average rating to at least {rating_data["min_required"]} (current: {rating_data["average_rating"]})',
                        'priority': 'medium'
                    })
    
    return recommendations

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_for_obsp(request):
    """Apply for an OBSP template level"""
    try:
        freelancer = request.user
        
        # Add debugging to see what's being received (but don't access request.body)
        
        # Validate request data
        obsp_template_id = request.data.get('obsp_template_id')
        selected_level = request.data.get('selected_level')
        pitch = request.data.get('pitch', '')
        
        if not all([obsp_template_id, selected_level]):
            return Response({
                'success': False,
                'message': 'Missing required fields: obsp_template_id, selected_level'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get OBSP template
        try:
            obsp_template = OBSPTemplate.objects.get(id=obsp_template_id, is_active=True)
        except OBSPTemplate.DoesNotExist:
            return Response({
                'success': False,
                'message': 'OBSP template not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already applied
        existing_application = OBSPApplication.objects.filter(
            freelancer=freelancer,
            obsp_template=obsp_template,
            selected_level=selected_level
        ).first()
        
        if existing_application:
            return Response({
                'success': False,
                'message': 'You have already applied for this OBSP level'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create eligibility data
        eligibility_obj = FreelancerOBSPEligibility.objects.filter(
            freelancer=freelancer,
            obsp_template=obsp_template
        ).first()
        
        # If no eligibility data exists, create it
        if not eligibility_obj:
            # This will trigger eligibility calculation
            eligibility_obj = OBSPEligibilityManager.get_or_create_eligibility(freelancer, obsp_template)
        
        # Check if freelancer is eligible for the selected level
        level_eligibility = eligibility_obj.get_level_eligibility(selected_level)
        if not level_eligibility.get('is_eligible', False):
            return Response({
                'success': False,
                'message': f'You are not eligible for {selected_level} level. Please check the requirements.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create application
        application = OBSPApplication.objects.create(
            freelancer=freelancer,
            obsp_template=obsp_template,
            selected_level=selected_level,
            pitch=pitch,
            eligibility_reference=eligibility_obj  # Store the eligibility reference
        )
        
        return Response({
            'success': True,
            'message': 'Application submitted successfully',
            'data': {
                'application_id': application.id,
                'status': application.status,
                'applied_at': application.applied_at,
                'eligibility_score': application.get_eligibility_score()
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'message': f'Error submitting application: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_applications(request):
    """Get freelancer's OBSP applications"""
    try:
        freelancer = request.user
        
        applications = OBSPApplication.objects.filter(
            freelancer=freelancer
        ).select_related(
            'obsp_template',
            'reviewed_by'
        ).order_by('-applied_at')
        
        applications_data = []
        for app in applications:
            applications_data.append({
                'id': app.id,
                'project_title': app.obsp_template.title,
                'selected_level': app.selected_level,
                'level_display': app.get_selected_level_display(),
                'status': app.status,
                'applied_at': app.applied_at,
                'reviewed_at': app.reviewed_at,
                'project_value': float(app.project_value),
                'eligibility_score': app.get_eligibility_score(),
                'pitch': app.pitch,
                'rejection_reason': app.rejection_reason if app.status == 'rejected' else None
            })
        
        return Response({
            'success': True,
            'data': {
                'applications': applications_data,
                'total_count': len(applications_data)
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error fetching applications: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)