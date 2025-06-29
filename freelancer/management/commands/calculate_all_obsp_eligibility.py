from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from OBSP.models import OBSPTemplate
from freelancer.models import OBSPEligibilityManager
from Profile.models import FreelancerProfile
from freelancer.obsp_eligibility import OBSPEligibilityCalculator
from django.db import transaction

User = get_user_model()

class Command(BaseCommand):
    help = 'Calculate OBSP eligibility for all freelancers'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting OBSP eligibility calculation for all freelancers...')
        
        # Get all freelancer users
        freelancers = User.objects.filter(role='freelancer')
        total = freelancers.count()
        
        self.stdout.write(f'Found {total} freelancers')
        
        # Get all active OBSP templates
        templates = OBSPTemplate.objects.filter(is_active=True)
        
        success_count = 0
        error_count = 0
        
        with transaction.atomic():
            for i, user in enumerate(freelancers, 1):
                try:
                    # Process each template for the freelancer
                    for template in templates:
                        # Calculate for all levels
                        for level in ['easy', 'medium', 'hard']:
                            try:
                                # Use the static method correctly
                                is_eligible, score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                                    freelancer=user,
                                    obsp_template=template,
                                    level=level
                                )
                                
                                # Store the results using OBSPEligibilityManager
                                OBSPEligibilityManager.calculate_and_store_eligibility(
                                    freelancer=user,
                                    obsp_template=template,
                                    levels=[level]
                                )
                                
                                self.stdout.write(
                                    f'  - {template.title} ({level}): Score={score}, Eligible={is_eligible}'
                                )
                            
                            except Exception as e:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'  - Error calculating {level} level for {template.title}: {str(e)}'
                                    )
                                )
                    
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'({i}/{total}) Calculated eligibility for {user.email}'
                        )
                    )
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'({i}/{total}) Error calculating eligibility for {user.email}: {str(e)}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted OBSP eligibility calculation.\n'
                f'Successful: {success_count}\n'
                f'Failed: {error_count}\n'
                f'Total processed: {total}'
            )
        ) 