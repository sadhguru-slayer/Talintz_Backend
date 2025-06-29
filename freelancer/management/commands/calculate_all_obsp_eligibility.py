from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from OBSP.models import OBSPTemplate
from freelancer.models import OBSPEligibilityManager,FreelancerOBSPEligibility
from Profile.models import FreelancerProfile
from freelancer.obsp_eligibility import OBSPEligibilityCalculator
from django.db import transaction
import time
import json
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Calculate OBSP eligibility for all freelancers'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting OBSP eligibility calculation for all freelancers...')
        
        # Get all freelancer users
        freelancers = User.objects.filter(role='freelancer')
        total = freelancers.count()
        
        self.stdout.write(f'Found {total} freelancers')
        
        success_count = 0
        error_count = 0
        
        with transaction.atomic():
            for i, user in enumerate(freelancers, 1):
                try:
                    calculator = OBSPEligibilityCalculator(user)
                    eligibility = calculator.calculate_eligibility()
                    
                    # Update the freelancer profile
                    FreelancerProfile.objects.filter(user=user).update(
                        obsp_eligibility=eligibility
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