from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Project
from Profile.models import FreelancerProfile, Feedback, FreelancerReview, BankDetails, VerificationDocument
from OBSP.models import OBSPAssignment, OBSPResponse

@receiver(post_save, sender=Project)
def update_freelancer_points_on_project_complete(sender, instance, **kwargs):
    if instance.status in ['completed', 'Completed']:
        for freelancer in instance.assigned_to.filter(role='freelancer'):
            if hasattr(freelancer, 'freelancer_profile'):
                freelancer.freelancer_profile.recalculate_points()

@receiver(post_save, sender=OBSPAssignment)
def update_freelancer_points_on_obsp_assignment_complete(sender, instance, **kwargs):
    if instance.status == 'completed':
        freelancer = instance.assigned_freelancer
        if hasattr(freelancer, 'freelancer_profile'):
            freelancer.freelancer_profile.recalculate_points()

@receiver(post_save, sender=OBSPResponse)
def update_freelancer_points_on_obsp_response_complete(sender, instance, **kwargs):
    if instance.status == 'completed':
        # Find all freelancers assigned to this OBSP (if applicable)
        from core.models import User
        assigned_freelancers = User.objects.filter(
            obsp_assignments__obsp_response=instance
        ).distinct()
        for freelancer in assigned_freelancers:
            if hasattr(freelancer, 'freelancer_profile'):
                freelancer.freelancer_profile.recalculate_points()

@receiver(post_save, sender=Feedback)
def update_freelancer_points_on_feedback(sender, instance, created, **kwargs):
    if created and instance.to_user and instance.to_user.role == 'freelancer':
        if hasattr(instance.to_user, 'freelancer_profile'):
            instance.to_user.freelancer_profile.recalculate_points()

@receiver(post_save, sender=FreelancerReview)
def update_freelancer_points_on_review(sender, instance, created, **kwargs):
    if created and instance.to_freelancer:
        if hasattr(instance.to_freelancer, 'freelancer_profile'):
            instance.to_freelancer.freelancer_profile.recalculate_points()

@receiver(post_save, sender=BankDetails)
def update_freelancer_points_on_bank_update(sender, instance, **kwargs):
    # Find all freelancer profiles using this bank detail
    from Profile.models import FreelancerProfile
    profiles = FreelancerProfile.objects.filter(bank_details=instance)
    for profile in profiles:
        profile.recalculate_points()

@receiver(post_save, sender=VerificationDocument)
def update_freelancer_points_on_document_update(sender, instance, **kwargs):
    # Find all freelancer profiles using this document
    from Profile.models import FreelancerProfile
    profiles = FreelancerProfile.objects.filter(verification_documents=instance)
    for profile in profiles:
        profile.recalculate_points()
