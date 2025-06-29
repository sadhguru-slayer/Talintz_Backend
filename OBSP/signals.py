from django.db.models.signals import post_save
from django.dispatch import receiver
from OBSP.models import OBSPCriteria
from django.contrib.auth import get_user_model
from freelancer.models import OBSPEligibilityManager
from django.db import transaction
from django.utils import timezone

User = get_user_model()

@receiver(post_save, sender=OBSPCriteria)
def recalculate_eligibility_on_criteria_change(sender, instance, created, **kwargs):
    """
    Trigger recalculation of OBSP eligibility for all freelancers when criteria changes
    """
    if not created:  # Only trigger on updates, not on creation
        template = instance.template
        level = instance.level
        
        # Log the criteria change
        print(f"Criteria updated for {template.title} - {level} at {timezone.now()}")
        
        # Get all freelancers
        freelancers = User.objects.filter(role='freelancer')
        total_freelancers = freelancers.count()
        
        print(f"Recalculating eligibility for {total_freelancers} freelancers...")
        
        success_count = 0
        error_count = 0
        
        with transaction.atomic():
            for i, freelancer in enumerate(freelancers, 1):
                try:
                    # Recalculate eligibility for this template and level
                    OBSPEligibilityManager.calculate_and_store_eligibility(
                        freelancer=freelancer,
                        obsp_template=template,
                        levels=[level]
                    )
                    success_count += 1
                    print(f"({i}/{total_freelancers}) Updated eligibility for {freelancer.email}")
                except Exception as e:
                    error_count += 1
                    print(f"({i}/{total_freelancers}) Error updating eligibility for {freelancer.email}: {str(e)}")
        
        print(f"Recalculation complete. Success: {success_count}, Failed: {error_count}") 