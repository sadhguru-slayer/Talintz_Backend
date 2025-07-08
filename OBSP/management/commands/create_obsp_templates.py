# manage.py shell script to create OBSP templates, levels, milestones, criteria, and fields

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Category, Skill
from OBSP.models import (
    OBSPTemplate, OBSPLevel, OBSPMilestone, OBSPCriteria, OBSPField
)
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create OBSP templates with levels, milestones, criteria, and fields'

    def handle(self, *args, **kwargs):
        # Get or create a system user for OBSP creation
        system_user, _ = User.objects.get_or_create(
            username='system_obsp',
            defaults={
                'email': 'system@talintz.com',
                'role': 'client',
                'is_active': True
            }
        )

        # Create Categories and Skills for Technology and Creativity
        tech_category, _ = Category.objects.get_or_create(
            name='Technology',
            defaults={'description': 'Technology-related projects and services'}
        )
        creativity_category, _ = Category.objects.get_or_create(
            name='Creativity',
            defaults={'description': 'Creative projects and services'}
        )

        # Skills for Technology
        tech_skills = [
            Skill.objects.get_or_create(
                category=tech_category,
                name=name,
                defaults={'description': f'{name} skill for technology projects'}
            )[0] for name in [
                'Web Development', 'Mobile Development', 'UI/UX Design',
                'Backend Development', 'DevOps', 'Data Science'
            ]
        ]

        # Skills for Creativity
        creativity_skills = [
            Skill.objects.get_or_create(
                category=creativity_category,
                name=name,
                defaults={'description': f'{name} skill for creative projects'}
            )[0] for name in [
                'Graphic Design', 'Video Editing', 'Content Writing',
                'Illustration', 'Animation', 'Photography'
            ]
        ]

        # Create Technology OBSP Template
        tech_obsp = OBSPTemplate.objects.create(
            title='Technology Project Template',
            category=tech_category,
            industry='tech',
            description='A comprehensive template for technology projects including web and mobile development.',
            base_price=1000,
            currency='INR',
            created_by=system_user
        )

        # Create Creativity OBSP Template
        creativity_obsp = OBSPTemplate.objects.create(
            title='Creative Project Template',
            category=creativity_category,
            industry='creativity',
            description='A template for creative projects like design, video editing, and content creation.',
            base_price=800,
            currency='INR',
            created_by=system_user
        )

        # Define levels for both templates
        levels = [
            {'level': 'easy', 'name': 'Basic', 'price': 1000, 'duration': '1-2 weeks'},
            {'level': 'medium', 'name': 'Standard', 'price': 2500, 'duration': '2-4 weeks'},
            {'level': 'hard', 'name': 'Premium', 'price': 5000, 'duration': '4-6 weeks'}
        ]

        # Create levels for Technology OBSP
        tech_levels = []
        for level_data in levels:
            tech_level = OBSPLevel.objects.create(
                template=tech_obsp,
                **level_data,
                features=['Basic features', 'Standard support', '1 revision'],
                deliverables=['Source code', 'Documentation', '1 month support']
            )
            tech_levels.append(tech_level)

        # Create levels for Creativity OBSP
        creativity_levels = []
        for level_data in levels:
            creativity_level = OBSPLevel.objects.create(
                template=creativity_obsp,
                **level_data,
                features=['Basic design', 'Standard edits', '1 revision'],
                deliverables=['Final designs', 'Source files', '1 month support']
            )
            creativity_levels.append(creativity_level)

        # Define milestones for each level
        milestones = [
            {
                'milestone_type': 'requirement_review',
                'title': 'Requirement Review',
                'description': 'Initial review and confirmation of project requirements.',
                'estimated_days': 3,
                'payout_percentage': 20,
                'deliverables': ['Approved requirements document'],
                'quality_checklist': ['All requirements documented', 'Client approval received']
            },
            {
                'milestone_type': 'development_progress',
                'title': 'Development Progress',
                'description': 'Mid-project progress review and feedback.',
                'estimated_days': 10,
                'payout_percentage': 40,
                'deliverables': ['Progress report', 'Demo'],
                'quality_checklist': ['Core features implemented', 'Client feedback incorporated']
            },
            {
                'milestone_type': 'final_delivery',
                'title': 'Final Delivery',
                'description': 'Project completion and handover.',
                'estimated_days': 20,
                'payout_percentage': 40,
                'deliverables': ['Final product', 'Documentation'],
                'quality_checklist': ['All features tested', 'Client sign-off received']
            }
        ]

        # Create milestones for Technology OBSP levels
        for level in tech_levels:
            for milestone_data in milestones:
                OBSPMilestone.objects.create(
                    template=tech_obsp,
                    level=level,
                    **milestone_data
                )

        # Create milestones for Creativity OBSP levels
        for level in creativity_levels:
            for milestone_data in milestones:
                OBSPMilestone.objects.create(
                    template=creativity_obsp,
                    level=level,
                    **milestone_data
                )

        # Define criteria for each level
        criteria = [
            {
                'level': 'easy',
                'min_completed_projects': 1,
                'min_avg_rating': 3.5,
                'min_skill_match_percentage': 50,
                'required_skills': ['Web Development', 'Graphic Design'],
                'core_skills': ['Web Development'],
                'optional_skills': ['UI/UX Design'],
                'min_project_budget': 500,
                'required_domains': ['tech', 'creativity'],
                'min_project_duration_days': 5,
                'min_obsp_completed': 0,
                'min_deadline_compliance': 70,
                'scoring_weights': {
                    'project_experience': 0.3,
                    'skill_match': 0.4,
                    'rating': 0.2,
                    'deadline_compliance': 0.1
                }
            },
            {
                'level': 'medium',
                'min_completed_projects': 3,
                'min_avg_rating': 4.0,
                'min_skill_match_percentage': 70,
                'required_skills': ['Web Development', 'UI/UX Design', 'Backend Development'],
                'core_skills': ['Web Development', 'Backend Development'],
                'optional_skills': ['UI/UX Design', 'DevOps'],
                'min_project_budget': 1000,
                'required_domains': ['tech'],
                'min_project_duration_days': 10,
                'min_obsp_completed': 1,
                'min_deadline_compliance': 80,
                'scoring_weights': {
                    'project_experience': 0.4,
                    'skill_match': 0.3,
                    'rating': 0.2,
                    'deadline_compliance': 0.1
                }
            },
            {
                'level': 'hard',
                'min_completed_projects': 5,
                'min_avg_rating': 4.5,
                'min_skill_match_percentage': 90,
                'required_skills': ['Web Development', 'UI/UX Design', 'Backend Development', 'DevOps'],
                'core_skills': ['Web Development', 'Backend Development', 'DevOps'],
                'optional_skills': ['UI/UX Design', 'Data Science'],
                'min_project_budget': 2000,
                'required_domains': ['tech'],
                'min_project_duration_days': 15,
                'min_obsp_completed': 2,
                'min_deadline_compliance': 90,
                'scoring_weights': {
                    'project_experience': 0.5,
                    'skill_match': 0.3,
                    'rating': 0.1,
                    'deadline_compliance': 0.1
                }
            }
        ]
        
                # Create criteria for Creativity OBSP
        for level_data in criteria:
            # Adjust criteria for creativity domain
            creativity_level_data = level_data.copy()
            creativity_level_data['required_skills'] = ['Graphic Design', 'Content Writing']
            creativity_level_data['core_skills'] = ['Graphic Design']
            creativity_level_data['optional_skills'] = ['Illustration', 'Animation']
            creativity_level_data['required_domains'] = ['creativity']

            OBSPCriteria.objects.create(
                template=creativity_obsp,
                **creativity_level_data
            )

        # Define fields for both templates
        fields = [
            {
                'label': 'Project Name',
                'field_type': 'text',
                'placeholder': 'Enter your project name',
                'help_text': 'The name of your project',
                'is_required': True,
                'has_price_impact': False,
                'order': 1,
                'visibility_rule': 'generic',
                'phase': 'basic'
            },
            {
                'label': 'Project Description',
                'field_type': 'textarea',
                'placeholder': 'Describe your project in detail',
                'help_text': 'Detailed description of what you need',
                'is_required': True,
                'has_price_impact': False,
                'order': 2,
                'visibility_rule': 'generic',
                'phase': 'basic'
            },
            {
                'label': 'Preferred Technology Stack',
                'field_type': 'select',
                'placeholder': 'Select your tech stack',
                'help_text': 'Choose the technologies you want to use',
                'is_required': False,
                'has_price_impact': True,
                'price_impact': 200,
                'order': 3,
                'options': [
                    {'text': 'React + Node.js', 'price': 200},
                    {'text': 'Angular + Django', 'price': 150},
                    {'text': 'Vue.js + Laravel', 'price': 100}
                ],
                'visibility_rule': 'generic',
                'phase': 'core_features'
            },
            {
                'label': 'Design Style Preference',
                'field_type': 'radio',
                'placeholder': '',
                'help_text': 'Select your preferred design style',
                'is_required': True,
                'has_price_impact': True,
                'price_impact': 100,
                'order': 4,
                'options': [
                    {'text': 'Minimalist', 'price': 100},
                    {'text': 'Modern', 'price': 150},
                    {'text': 'Vintage', 'price': 200}
                ],
                'visibility_rule': 'mid_high',
                'phase': 'core_features'
            },
            {
                'label': 'Additional Features',
                'field_type': 'checkbox',
                'placeholder': '',
                'help_text': 'Select any additional features you need',
                'is_required': False,
                'has_price_impact': True,
                'order': 5,
                'options': [
                    {'text': 'Admin Dashboard', 'price': 300},
                    {'text': 'Mobile App', 'price': 500},
                    {'text': 'API Integration', 'price': 200}
                ],
                'visibility_rule': 'high',
                'phase': 'add_ons'
            },
            {
                'label': 'File Uploads',
                'field_type': 'file',
                'placeholder': 'Upload any reference files',
                'help_text': 'Upload design mockups or other references',
                'is_required': False,
                'has_price_impact': False,
                'order': 6,
                'visibility_rule': 'generic',
                'phase': 'review'
            }
        ]

        # Create fields for Technology OBSP
        for field_data in fields:
            OBSPField.objects.create(
                template=tech_obsp,
                **field_data
            )

        # Create fields for Creativity OBSP (with adjusted options)
        creativity_fields = [
            {
                'label': 'Project Name',
                'field_type': 'text',
                'placeholder': 'Enter your project name',
                'help_text': 'The name of your project',
                'is_required': True,
                'has_price_impact': False,
                'order': 1,
                'visibility_rule': 'generic',
                'phase': 'basic'
            },
            {
                'label': 'Project Description',
                'field_type': 'textarea',
                'placeholder': 'Describe your project in detail',
                'help_text': 'Detailed description of what you need',
                'is_required': True,
                'has_price_impact': False,
                'order': 2,
                'visibility_rule': 'generic',
                'phase': 'basic'
            },
            {
                'label': 'Design Style Preference',
                'field_type': 'radio',
                'placeholder': '',
                'help_text': 'Select your preferred design style',
                'is_required': True,
                'has_price_impact': True,
                'price_impact': 100,
                'order': 3,
                'options': [
                    {'text': 'Minimalist', 'price': 100},
                    {'text': 'Modern', 'price': 150},
                    {'text': 'Vintage', 'price': 200}
                ],
                'visibility_rule': 'generic',
                'phase': 'core_features'
            },
            {
                'label': 'Color Palette',
                'field_type': 'select',
                'placeholder': 'Select your color palette',
                'help_text': 'Choose the colors for your project',
                'is_required': False,
                'has_price_impact': True,
                'price_impact': 50,
                'order': 4,
                'options': [
                    {'text': 'Warm Colors', 'price': 50},
                    {'text': 'Cool Colors', 'price': 50},
                    {'text': 'Custom Palette', 'price': 100}
                ],
                'visibility_rule': 'mid_high',
                'phase': 'core_features'
            },
            {
                'label': 'Additional Services',
                'field_type': 'checkbox',
                'placeholder': '',
                'help_text': 'Select any additional services you need',
                'is_required': False,
                'has_price_impact': True,
                'order': 5,
                'options': [
                    {'text': 'Social Media Kit', 'price': 200},
                    {'text': 'Brand Guidelines', 'price': 300},
                    {'text': 'Animated Logo', 'price': 400}
                ],
                'visibility_rule': 'high',
                'phase': 'add_ons'
            },
            {
                'label': 'Reference Files',
                'field_type': 'file',
                'placeholder': 'Upload any reference files',
                'help_text': 'Upload images or documents for reference',
                'is_required': False,
                'has_price_impact': False,
                'order': 6,
                'visibility_rule': 'generic',
                'phase': 'review'
            }
        ]

        for field_data in creativity_fields:
            OBSPField.objects.create(
                template=creativity_obsp,
                **field_data
            )

        