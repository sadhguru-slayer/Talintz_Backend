from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from OBSP.models import OBSPTemplate
from freelancer.models import OBSPEligibilityManager,FreelancerOBSPEligibility
from freelancer.obsp_eligibility import OBSPEligibilityCalculator
from django.db import transaction
import time
import json
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Calculate OBSP eligibility for all freelancers and all OBSP templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--freelancer-id',
            type=int,
            help='Calculate for specific freelancer only'
        )
        parser.add_argument(
            '--obsp-id', 
            type=int,
            help='Calculate for specific OBSP only'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if already calculated'
        )

    def serialize_for_json(self, obj):
        """Convert objects to JSON-serializable format"""
        def _convert(value):
            if isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, (datetime, date)):
                return value.isoformat()
            elif isinstance(value, timezone.datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_convert(item) for item in value]
            elif isinstance(value, set):
                return list(value)
            else:
                return value
        
        return _convert(obj)

    def handle(self, *args, **options):
        start_time = time.time()
        
        # Get freelancers
        if options['freelancer_id']:
            freelancers = User.objects.filter(id=options['freelancer_id'], role='freelancer')
        else:
            freelancers = User.objects.filter(role='freelancer')
        
        # Get OBSP templates
        if options['obsp_id']:
            obsp_templates = OBSPTemplate.objects.filter(id=options['obsp_id'], is_active=True)
        else:
            obsp_templates = OBSPTemplate.objects.filter(is_active=True)
        
        total_freelancers = freelancers.count()
        total_obsps = obsp_templates.count()
        total_calculations = total_freelancers * total_obsps
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting eligibility calculation for {total_freelancers} freelancers and {total_obsps} OBSPs '
                f'(Total: {total_calculations} calculations)'
            )
        )
        
        processed = 0
        successful = 0
        failed = 0
        
        for freelancer in freelancers:
            self.stdout.write(f'Processing freelancer: {freelancer.username}')
            
            for obsp_template in obsp_templates:
                try:
                    with transaction.atomic():
                        # Calculate eligibility for all levels
                        eligibility_obj, created = FreelancerOBSPEligibility.objects.get_or_create(
                            freelancer=freelancer,
                            obsp_template=obsp_template,
                            defaults={'eligibility_data': {}}
                        )
                        
                        # Calculate for each level
                        for level in ['easy', 'medium', 'hard']:
                            is_eligible, overall_score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                                freelancer, obsp_template, level
                            )
                            
                            # Ensure analysis is JSON serializable
                            serialized_analysis = self.serialize_for_json(analysis)
                            
                            # Store everything in the JSON field
                            eligibility_obj.set_level_eligibility(level, is_eligible, overall_score, serialized_analysis)
                        
                        # Get eligibility summary
                        easy_eligible = eligibility_obj.get_level_eligibility('easy')['is_eligible']
                        medium_eligible = eligibility_obj.get_level_eligibility('medium')['is_eligible']
                        hard_eligible = eligibility_obj.get_level_eligibility('hard')['is_eligible']
                        
                        self.stdout.write(
                            f'  ✅ {obsp_template.title}: Easy={easy_eligible}, Medium={medium_eligible}, Hard={hard_eligible}'
                        )
                        
                        successful += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ {obsp_template.title}: {str(e)}'
                        )
                    )
                    failed += 1
                
                processed += 1
                
                # Progress update every 10 calculations
                if processed % 10 == 0:
                    progress = (processed / total_calculations) * 100
                    self.stdout.write(f'Progress: {progress:.1f}% ({processed}/{total_calculations})')
        
        # Update all caches
        self.stdout.write('Updating freelancer caches...')
        for freelancer in freelancers:
            try:
                OBSPEligibilityManager.update_freelancer_cache(freelancer)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to update cache for {freelancer.username}: {str(e)}')
                )
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Eligibility calculation completed!\n'
                f'Total processed: {processed}\n'
                f'Successful: {successful}\n'
                f'Failed: {failed}\n'
                f'Duration: {duration:.2f} seconds'
            )
        ) 