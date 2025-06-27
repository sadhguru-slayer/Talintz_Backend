from django.core.management.base import BaseCommand
from OBSP.models import OBSPTemplate, OBSPCriteria

class Command(BaseCommand):
    help = 'Populate OBSP criteria for all templates and levels'

    def handle(self, *args, **options):
        templates = OBSPTemplate.objects.filter(is_active=True)
        
        for template in templates:
            for level in ['easy', 'medium', 'hard']:
                criteria, created = OBSPCriteria.objects.get_or_create(
                    template=template,
                    level=level,
                    defaults={
                        'min_completed_projects': 2 if level == 'easy' else (3 if level == 'medium' else 5),
                        'min_avg_rating': 4.0 if level == 'easy' else (4.2 if level == 'medium' else 4.5),
                        'min_skill_match_percentage': 60.0 if level == 'easy' else (70.0 if level == 'medium' else 80.0),
                        'required_skills': ['Python', 'Django'] if template.category == 'web-development' else ['JavaScript', 'React'],
                        'core_skills': ['Python'] if template.category == 'web-development' else ['JavaScript'],
                        'optional_skills': ['PostgreSQL', 'Redis'] if template.category == 'web-development' else ['Node.js', 'MongoDB'],
                        'min_project_budget': 1000.0 if level == 'easy' else (5000.0 if level == 'medium' else 10000.0),
                        'required_domains': [template.category],
                        'min_project_duration_days': 7 if level == 'easy' else (14 if level == 'medium' else 30),
                        'min_obsp_completed': 0 if level == 'easy' else (2 if level == 'medium' else 3),
                        'min_deadline_compliance': 80.0 if level == 'easy' else (85.0 if level == 'medium' else 90.0),
                        'scoring_weights': {
                            'project_experience': 0.25,
                            'skill_match': 0.35,
                            'rating': 0.25,
                            'deadline_compliance': 0.15
                        },
                        'bonus_criteria': {
                            'certification_bonus': 5,
                            'portfolio_bonus': 3,
                            'client_feedback_bonus': 2
                        },
                        'penalty_criteria': {
                            'late_delivery_penalty': -10,
                            'low_rating_penalty': -5
                        }
                    }
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created criteria for {template.title} - {level}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Criteria already exists for {template.title} - {level}')
                    ) 