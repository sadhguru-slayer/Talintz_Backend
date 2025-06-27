from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from freelancer.models import OBSPEligibilityManager
from OBSP.models import OBSPTemplate

User = get_user_model()

class Command(BaseCommand):
    help = 'Update OBSP eligibility for freelancers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--freelancer-id',
            type=int,
            help='Update for specific freelancer only'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update for all freelancers'
        )

    def handle(self, *args, **options):
        if options['freelancer_id']:
            freelancers = User.objects.filter(id=options['freelancer_id'], role='freelancer')
        elif options['all']:
            freelancers = User.objects.filter(role='freelancer')
        else:
            self.stdout.write(self.style.ERROR('Please specify --freelancer-id or --all'))
            return

        total = freelancers.count()
        self.stdout.write(f'Updating eligibility for {total} freelancers...')

        for i, freelancer in enumerate(freelancers, 1):
            self.stdout.write(f'[{i}/{total}] Updating {freelancer.username}...')
            
            try:
                obsp_templates = OBSPTemplate.objects.filter(is_active=True)
                
                for obsp_template in obsp_templates:
                    OBSPEligibilityManager.calculate_and_store_eligibility(
                        freelancer, obsp_template
                    )
                
                OBSPEligibilityManager.update_freelancer_cache(freelancer)
                self.stdout.write(f'  ✅ Updated successfully')
                
            except Exception as e:
                self.stdout.write(f'  ❌ Error: {str(e)}')

        self.stdout.write(self.style.SUCCESS('Eligibility update completed!')) 