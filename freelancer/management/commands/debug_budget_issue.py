from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Project
from OBSP.models import OBSPTemplate, OBSPCriteria

User = get_user_model()

class Command(BaseCommand):
    help = 'Debug budget filtering issue'

    def add_arguments(self, parser):
        parser.add_argument('--freelancer-id', type=int, required=True)

    def handle(self, *args, **options):
        freelancer_id = options['freelancer_id']
        
        try:
            freelancer = User.objects.get(id=freelancer_id, role='freelancer')
            
            self.stdout.write(f"=== Budget Debug for {freelancer.username} ===")
            
            # Check all projects
            self.stdout.write("\n📋 All Projects:")
            all_projects = Project.objects.filter(assigned_to=freelancer)
            for project in all_projects:
                self.stdout.write(f"  - {project.title}: Budget={project.budget}, Status='{project.status}', Domain={project.domain.name}")
            
            # Check OBSP criteria
            self.stdout.write("\n🎯 OBSP Criteria:")
            obsp_templates = OBSPTemplate.objects.filter(is_active=True)
            for template in obsp_templates:
                self.stdout.write(f"\n  {template.title}:")
                for level in ['easy', 'medium', 'hard']:
                    try:
                        criteria = OBSPCriteria.objects.get(template=template, level=level, is_active=True)
                        self.stdout.write(f"    {level}: Min budget={criteria.min_project_budget}, Min projects={criteria.min_completed_projects}")
                    except OBSPCriteria.DoesNotExist:
                        self.stdout.write(f"    {level}: No criteria found")
            
            # Test budget filtering
            self.stdout.write("\n🔍 Budget Filtering Test:")
            for template in obsp_templates:
                for level in ['easy', 'medium', 'hard']:
                    try:
                        criteria = OBSPCriteria.objects.get(template=template, level=level, is_active=True)
                        
                        # Test domain filter
                        domain_projects = all_projects.filter(
                            status__in=['completed', 'Completed'],
                            domain__name__in=criteria.required_domains
                        )
                        
                        # Test budget filter
                        budget_projects = domain_projects.filter(
                            budget__gte=criteria.min_project_budget
                        )
                        
                        self.stdout.write(f"  {template.title} - {level}:")
                        self.stdout.write(f"    Domain filter: {domain_projects.count()} projects")
                        self.stdout.write(f"    Budget filter: {budget_projects.count()} projects (min: {criteria.min_project_budget})")
                        
                        for p in domain_projects:
                            self.stdout.write(f"      - {p.title}: Budget={p.budget}, Meets budget: {p.budget >= criteria.min_project_budget}")
                        
                    except OBSPCriteria.DoesNotExist:
                        continue
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Freelancer not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}')) 