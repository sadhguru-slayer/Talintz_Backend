from celery import shared_task
from freelancer.models import OBSPEligibilityManager
from OBSP.models import OBSPTemplate

@shared_task
def update_freelancer_obsp_eligibility(freelancer_id):
    """Background task to update freelancer's OBSP eligibility"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        freelancer = User.objects.get(id=freelancer_id, role='freelancer')
        obsp_templates = OBSPTemplate.objects.filter(is_active=True)
        
        for obsp_template in obsp_templates:
            OBSPEligibilityManager.calculate_and_store_eligibility(
                freelancer, obsp_template
            )
        
        OBSPEligibilityManager.update_freelancer_cache(freelancer)
        return f"Updated eligibility for freelancer {freelancer.username}"
    except Exception as e:
        return f"Error updating eligibility: {str(e)}"

@shared_task
def update_all_freelancers_eligibility():
    """Background task to update all freelancers' eligibility"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    freelancer_ids = User.objects.filter(role='freelancer').values_list('id', flat=True)
    
    for freelancer_id in freelancer_ids:
        update_freelancer_obsp_eligibility.delay(freelancer_id) 