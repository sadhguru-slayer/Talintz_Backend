from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib import admin
from django.forms import Textarea
import re
from core.models import Category, Skill
from django.utils import timezone
from django.contrib.auth import get_user_model

class OBSPTemplate(models.Model):
    """Main OBSP template created by Talintz"""
    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category,on_delete=models.CASCADE)
    industry = models.CharField(max_length=100, choices=[
        ('tech', 'Technology'),
        ('creativity', 'Creativity'),
        
    ])
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='INR')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_field_count(self):
        return self.fields.count()
    get_field_count.short_description = "Fields"

class OBSPLevel(models.Model):
    """Level-specific configuration for OBSP templates"""
    LEVEL_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'), 
        ('hard', 'Hard')
    ]
    
    template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='levels')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    name = models.CharField(max_length=255, help_text="Display name for this level (e.g., 'Basic E-commerce')")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    duration = models.CharField(max_length=50, help_text="Delivery timeline (e.g., '2-3 weeks')")
    features = models.JSONField(default=list, help_text="List of features included in this level")
    deliverables = models.JSONField(default=list, help_text="List of deliverables for this level")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order (1=first, 2=second, etc.)")
    max_revisions = models.PositiveIntegerField(default=2, help_text="Maximum number of revisions allowed for this level")
    
    class Meta:
        unique_together = ['template', 'level']
        ordering = ['template', 'order']

    def __str__(self):
        return f"{self.template.title} - {self.get_level_display()}"

    def get_level_display_name(self):
        return self.name or self.get_level_display()

class OBSPField(models.Model):
    """Individual fields/questions in OBSP template"""
    FIELD_TYPE_CHOICES = [
        ('text', 'Text Input'),
        ('textarea', 'Text Area'),
        ('number', 'Number Input'),
        ('email', 'Email Input'),
        ('phone', 'Phone Input'),
        ('date', 'Date Input'),
        ('radio', 'Radio Buttons'),
        ('checkbox', 'Checkboxes'),
        ('select', 'Dropdown Select'),
        ('file', 'File Upload')
    ]
    
    FIELD_VISIBILITY_CHOICES = [
        ('generic', 'Generic - All Levels'),
        ('low', 'Low Level Only'),
        ('mid', 'Mid Level Only'),
        ('high', 'High Level Only'),
        ('lmid', 'Low + Mid Levels'),
        ('mhigh', 'Mid + High Levels'),
        ('low_mid', 'Low + Mid Levels'),
        ('mid_high', 'Mid + High Levels')
    ]
    
    FIELD_PHASE_CHOICES = [
        ('basic', 'Basic Info - Tell us about your business'),
        ('core_features', 'Core Features - Choose your essential features'),
        ('add_ons', 'Add-ons - Enhance your package'),
        ('review', 'Review & Purchase - Finalize your order')
    ]
    
    is_active = models.BooleanField(default=True)
    template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='fields')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    label = models.CharField(max_length=255)
    placeholder = models.CharField(max_length=255, blank=True, help_text="Placeholder text for input fields")
    help_text = models.CharField(max_length=500, blank=True, help_text="Help text to guide users")
    is_required = models.BooleanField(default=False)
    has_price_impact = models.BooleanField(default=False)
    price_impact = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)
    options = models.JSONField(default=list, help_text="Options for radio/checkbox/select fields")
    visibility_rule = models.CharField(
        max_length=20, 
        choices=FIELD_VISIBILITY_CHOICES, 
        default='generic',
        help_text="Which levels can see this field"
    )
    phase = models.CharField(
        max_length=20,
        choices=FIELD_PHASE_CHOICES,
        default='basic',
        help_text="Which phase/step this field belongs to"
    )
    
    class Meta:
        ordering = ['template', 'phase', 'order']

    def __str__(self):
        return f"{self.template.title} - {self.label}"

    def get_phase_display_name(self):
        """Get the display name for the phase"""
        phase_names = {
            'basic': 'Basic Info',
            'core_features': 'Core Features', 
            'add_ons': 'Add-ons',
            'review': 'Review & Purchase'
        }
        return phase_names.get(self.phase, self.phase)

    def get_phase_description(self):
        """Get the description for the phase"""
        phase_descriptions = {
            'basic': 'Tell us about your business or project',
            'core_features': 'Choose your essential features',
            'add_ons': 'Enhance your package',
            'review': 'Finalize your order'
        }
        return phase_descriptions.get(self.phase, '')

    def get_options_with_pricing(self):
        """Return options with pricing information"""
        if not self.options:
            return []
        
        result = []
        for option in self.options:
            if isinstance(option, dict):
                display_text = option.get('text', '')
                if option.get('description'):
                    display_text += f" | {option['description']}"
                result.append({
                    'text': option.get('text', ''),
                    'price': option.get('price', 0),
                    'description': option.get('description', ''),
                    'display': display_text
                })
            else:
                result.append({
                    'text': option,
                    'price': 0,
                    'description': '',
                    'display': option
                })
        return result

    def get_total_price_impact(self):
        """Calculate total price impact for all options"""
        if not self.options:
            return 0
        
        total = 0
        for option in self.options:
            if isinstance(option, dict):
                total += option.get('price', 0)
        return total

    def is_visible_for_level(self, level):
        """Check if field should be visible for given level"""
        try:
            visibility_map = {
                'easy': ['generic', 'low', 'lmid', 'low_mid'],
                'medium': ['generic', 'mid', 'lmid', 'mhigh', 'low_mid', 'mid_high'],
                'hard': ['generic', 'high', 'mhigh', 'mid_high']
            }
            
            # Handle case where level might be None or invalid
            if not level or level not in visibility_map:
                return self.visibility_rule in visibility_map.get('easy', [])
            return self.visibility_rule in visibility_map.get(level, [])
        except Exception:
            return False

class OBSPResponse(models.Model):
    """Client response to OBSP template"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded')
    ]
    
    template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='responses')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='obsp_responses', null=True)
    selected_level = models.CharField(max_length=20, choices=OBSPLevel.LEVEL_CHOICES,null=True)
    responses = models.JSONField(default=dict,null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft',null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    current_milestone = models.ForeignKey("OBSP.OBSPMilestone", on_delete=models.SET_NULL, null=True, blank=True)
    milestone_progress = models.JSONField(default=dict, help_text="Progress tracking for each milestone")
    max_revisions = models.PositiveIntegerField(null=True, blank=True, help_text="Override max revisions for this order (default from level)")
    
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['template', 'client', 'selected_level', 'status']
    
    def __str__(self):
        return f"{self.client.username} - {self.template.title} ({self.get_selected_level_display()})"
    
    def get_selected_level_display(self):
        return dict(OBSPLevel.LEVEL_CHOICES).get(self.selected_level, self.selected_level)

    def save(self, *args, **kwargs):
        if not self.pk:  # This is a new instance
            self.initialize_milestone_progress()
        super().save(*args, **kwargs)

    def initialize_milestone_progress(self):
        """
        Initialize milestone_progress when OBSPResponse is created.
        Sets each milestone based on OBSPMilestone.order with status 'pending', deadline as empty string, and deadline_type as 'Default'.
        """
        milestones = OBSPMilestone.objects.filter(
            template=self.template,
            level__level=self.selected_level
        ).order_by('order')  # Order by milestone order
        
        milestone_progress = {}
        for milestone in milestones:
            milestone_id = str(milestone.id)
            milestone_progress[milestone_id] = {
                'status': 'pending',
                'deadline': '',  # Empty string as specified
                'deadline_type': 'Default'
            }
        self.milestone_progress = milestone_progress

    def calculate_and_set_milestone_deadlines(self):
        """
        Calculate and set deadlines for milestones based on the OBSPAssignment's assigned_at date.
        After setting deadlines, update the first milestone's status to 'in_progress'.
        """
        try:
            assignment = self.assignments.filter(status__in=['assigned', 'in_progress']).first()
            if not assignment:
                return  # No assignment, so no deadlines to calculate
            
            assigned_at = assignment.assigned_at
            milestones = OBSPMilestone.objects.filter(
                template=self.template,
                level__level=self.selected_level
            ).order_by('order')
            
            milestone_progress = self.milestone_progress or {}
            current_date = assigned_at
            
            for milestone in milestones:
                estimated_days = milestone.estimated_days
                deadline_date = current_date + timezone.timedelta(days=estimated_days)
                
                milestone_id = str(milestone.id)
                if milestone_id in milestone_progress and isinstance(milestone_progress[milestone_id], dict):
                    milestone_progress[milestone_id]['deadline'] = deadline_date.strftime('%Y-%m-%d')
                else:
                    milestone_progress[milestone_id] = {
                        'deadline': deadline_date.strftime('%Y-%m-%d'),
                        'status': milestone_progress.get(milestone_id, {}).get('status', 'pending'),
                        'deadline_type': milestone_progress.get(milestone_id, {}).get('deadline_type', 'Default')
                    }
                
                current_date = deadline_date  # Chain to the next milestone
            
            # After setting deadlines, update the first milestone's status to 'in_progress'
            if milestones.exists():
                first_milestone_id = str(milestones.first().id)
                if first_milestone_id in milestone_progress:
                    milestone_progress[first_milestone_id]['status'] = 'in_progress'  # Set first to 'in_progress'
            
            self.milestone_progress = milestone_progress
            self.save()
        except Exception as e:
            print(f"Error calculating deadlines: {e}")

    def assign_freelancer(self, freelancer, assigned_by=None, freelancer_payout=None, platform_fee=None):
        """Assign a freelancer to this OBSP response"""
        from django.utils import timezone
        
        # Calculate payout if not provided
        if freelancer_payout is None:
            # Default to 80% of total price for freelancer
            freelancer_payout = self.total_price * 0.8
        
        if platform_fee is None:
            # Default to 20% platform fee
            platform_fee = self.total_price * 0.2
        
        # Create assignment
        assignment = OBSPAssignment.objects.create(
            obsp_response=self,
            assigned_freelancer=freelancer,
            assigned_by=assigned_by,
            freelancer_payout=freelancer_payout,
            platform_fee=platform_fee,
            status='assigned'
        )
        
        # Update OBSP response status
        self.status = 'processing'
        self.save()
        
        # Call the updated method to calculate deadlines and set statuses
        self.calculate_and_set_milestone_deadlines()
        
        return assignment

    def get_assignments(self):
        """Get all assignments for this response"""
        return self.assignments.all()

    def get_active_assignment(self):
        """Get the currently active assignment"""
        return self.assignments.filter(status__in=['assigned', 'in_progress', 'review']).first()

    def is_fully_assigned(self):
        """Check if all work is assigned"""
        return self.assignments.filter(status__in=['assigned', 'in_progress', 'review', 'completed']).exists()
    def update_milestone_progress(self, milestone_name, percentage, notes=""):
        """Update progress for a specific milestone"""
        if not self.milestone_progress:
            self.milestone_progress = {}
        
        self.milestone_progress[milestone_name] = {
            'percentage': percentage,
            'notes': notes,
            'updated_at': timezone.now().isoformat()
        }
        self.save()

    def set_current_milestone(self, milestone):
        """Set the current milestone for the response"""
        self.current_milestone = milestone
        self.save() 
    def get_max_revisions(self):
        """Return the max revisions for this response (override or from level)"""
        if self.max_revisions is not None:
            return self.max_revisions
        level_obj = self.template.levels.filter(level=self.selected_level).first()
        return level_obj.max_revisions if level_obj else 0

class OBSPMilestone(models.Model):
    """Pre-defined milestones for OBSP templates"""
    MILESTONE_TYPE_CHOICES = [
        ('requirement_review', 'Requirement Review'),
        ('design_approval', 'Design Approval'),
        ('development_progress', 'Development Progress'),
        ('testing_qa', 'Testing & QA'),
        ('final_delivery', 'Final Delivery'),
        ('post_launch', 'Post-Launch Support')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered')
    ]
    
    template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='template_milestones')
    level = models.ForeignKey(OBSPLevel, on_delete=models.CASCADE, related_name='level_milestones')
    
    # Milestone details
    milestone_type = models.CharField(max_length=50, choices=MILESTONE_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Timeline & Progress
    
    estimated_days = models.PositiveIntegerField(help_text="Estimated days from project start")
    payout_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of total payment released"
    )
    
    # Quality & Deliverables
    deliverables = models.JSONField(default=list, help_text="What client receives at this milestone")
    quality_checklist = models.JSONField(default=list, help_text="QA checklist for this milestone")
    client_approval_required = models.BooleanField(default=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['template', 'level', 'milestone_type']
        ordering = ['template', 'level', 'order']

    def __str__(self):
        return f"{self.template.title} - {self.level.name} - {self.title}"

    def get_payout_amount(self, level_price):
        """Calculate actual payout amount based on level price"""
        return (level_price * self.payout_percentage) / 100

class OBSPCriteria(models.Model):
    """
    Stores specific criteria requirements for each OBSP level
    This creates 200 OBSPs × 3 levels = 600 records with detailed requirements
    """
    template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='criteria')
    level = models.CharField(max_length=10, choices=OBSPLevel.LEVEL_CHOICES)
    
    # Core Requirements
    min_completed_projects = models.PositiveIntegerField(default=2, help_text="Minimum completed projects required")
    min_avg_rating = models.FloatField(default=4.0, help_text="Minimum average rating required")
    min_skill_match_percentage = models.FloatField(default=60.0, help_text="Minimum skill match percentage")
    
    # Skill Requirements (JSON for flexibility)
    required_skills = models.ManyToManyField(
        Skill,
        related_name='required_in_criteria',
        blank=True,
        help_text="Required skills for this criteria"
    )
    core_skills = models.ManyToManyField(
        Skill,
        related_name='core_in_criteria',
        blank=True,
        help_text="Core skills for this criteria"
    )
    optional_skills = models.ManyToManyField(
        Skill,
        related_name='optional_in_criteria',
        blank=True,
        help_text="Optional skills for this criteria"
    )
    required_domains = models.ManyToManyField(
        Category,  # Assuming Category is the model for domains
        related_name='required_in_criteria',
        blank=True,
        help_text="Required domains for this criteria"
    )
    # Project Experience Requirements
    min_project_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum project budget experience")
    min_project_duration_days = models.PositiveIntegerField(default=7, help_text="Minimum project duration experience")
    
    # OBSP-Specific Requirements (for higher levels)
    min_obsp_completed = models.PositiveIntegerField(default=0, help_text="Minimum OBSPs completed at previous level")
    min_deadline_compliance = models.FloatField(default=80.0, help_text="Minimum deadline compliance percentage")
    
    # Scoring Weights (JSON for flexibility)
    scoring_weights = models.JSONField(default=dict, help_text="Weights for different scoring components")
    # Format: {
    #   "project_experience": 0.25,
    #   "skill_match": 0.35,
    #   "rating": 0.25,
    #   "deadline_compliance": 0.15
    # }
    
    # Bonus Criteria
    bonus_criteria = models.JSONField(default=dict, help_text="Bonus points criteria")
    # Format: {
    #   "certification_bonus": 5,
    #   "portfolio_bonus": 3,
    #   "client_feedback_bonus": 2
    # }
    
    # Penalty Criteria
    penalty_criteria = models.JSONField(default=dict, help_text="Penalty criteria")
    # Format: {
    #   "late_delivery_penalty": -10,
    #   "low_rating_penalty": -5
    # }
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('template', 'level')
        ordering = ['template', 'level']
        indexes = [
            models.Index(fields=['template', 'level']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.template.title} - {self.level} - Criteria"

    def get_scoring_breakdown(self):
        """Get detailed scoring breakdown for this criteria"""
        return {
            'min_completed_projects': self.min_completed_projects,
            'min_avg_rating': self.min_avg_rating,
            'min_skill_match_percentage': self.min_skill_match_percentage,
            'required_skills': list(self.required_skills.values_list('name', flat=True)),
            'core_skills': list(self.core_skills.values_list('name', flat=True)),
            'optional_skills': list(self.optional_skills.values_list('name', flat=True)),
            'min_project_budget': float(self.min_project_budget),
            'required_domains': list(self.required_domains.values_list('name', flat=True)),
            'min_project_duration_days': self.min_project_duration_days,
            'min_obsp_completed': self.min_obsp_completed,
            'min_deadline_compliance': self.min_deadline_compliance,
            'scoring_weights': self.scoring_weights,
            'bonus_criteria': self.bonus_criteria,
            'penalty_criteria': self.penalty_criteria
        }

class OBSPAssignment(models.Model):
    """Handles assignment of freelancers to OBSP projects"""
    ASSIGNMENT_STATUS_CHOICES = [
        ('pending', 'Pending Assignment'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed')
    ]
    
    # Core relationships
    obsp_response = models.ForeignKey(OBSPResponse, on_delete=models.CASCADE, related_name='assignments')
    assigned_freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='obsp_assignments')
    
    # Assignment details
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='obsp_assignments_made')
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Status and progress
    status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS_CHOICES, default='pending')
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Financial details
    freelancer_payout = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount to be paid to freelancer")
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Platform commission")
    

    # Communication and feedback
    quality_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    deadline_met = models.BooleanField(null=True, blank=True)
    
    class Meta:
        unique_together = ['obsp_response', 'assigned_freelancer']
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['status', 'assigned_freelancer']),
            models.Index(fields=['assigned_at']),
            models.Index(fields=['obsp_response', 'status']),
        ]

    def __str__(self):
        return f"{self.obsp_response.template.title} - {self.assigned_freelancer.username}"

    def get_total_payout(self):
        """Get total payout including platform fee"""
        return self.freelancer_payout + self.platform_fee


    def start_work(self):
        """Mark assignment as started"""
        if self.status == 'assigned':
            self.status = 'in_progress'
            self.started_at = timezone.now()
            self.save()

    def complete_assignment(self):
        """Mark assignment as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100
        self.save()

    def get_estimated_completion_date(self):
        """Calculate estimated completion date based on milestones"""
        if not self.current_milestone:
            return None
        
        # Calculate remaining days based on current milestone and progress
        remaining_days = self.current_milestone.estimated_days * (100 - self.progress_percentage) / 100
        return timezone.now() + timezone.timedelta(days=remaining_days)

    def update_from_freelancer_changes(self):
        """
        Update assignment details based on freelancer's current profile
        """
        from freelancer.signals import (
            update_assignment_from_freelancer,
            update_assignment_from_project,
            update_assignment_from_feedback
        )
        
        freelancer = self.assigned_freelancer
        
        # Update based on freelancer profile
        update_assignment_from_freelancer(self, freelancer)
        
        # Update based on recent projects
        from core.models import Project
        recent_projects = Project.objects.filter(
            assigned_to=freelancer,
            status__in=['completed', 'Completed'],
            updated_at__gte=timezone.now() - timezone.timedelta(days=30)
        )
        
        for project in recent_projects:
            update_assignment_from_project(self, project)
        
        # Update based on recent feedback
        from Profile.models import Feedback
        recent_feedback = Feedback.objects.filter(
            to_user=freelancer,
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        )
        
        for feedback in recent_feedback:
            update_assignment_from_feedback(self, feedback)
    
    def recalculate_pricing(self):
        """
        Recalculate pricing based on current market conditions and freelancer profile
        """
        from freelancer.signals import calculate_freelancer_payout, calculate_platform_fee
        
        new_payout = calculate_freelancer_payout(self, self.assigned_freelancer)
        new_platform_fee = calculate_platform_fee(new_payout)
        
        old_payout = float(self.freelancer_payout)
        old_platform_fee = float(self.platform_fee)
        
        self.freelancer_payout = new_payout
        self.platform_fee = new_platform_fee
        
        # Add note about the recalculation
        if not self.internal_notes:
            self.internal_notes = ""
        self.internal_notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Pricing recalculated: Payout {old_payout}→{new_payout}, Platform fee {old_platform_fee}→{new_platform_fee}"
        
        self.save()
        
        return {
            'old_payout': old_payout,
            'new_payout': new_payout,
            'old_platform_fee': old_platform_fee,
            'new_platform_fee': new_platform_fee
        }
    
    def update_quality_score(self):
        """
        Update quality score based on recent performance
        """
        from freelancer.signals import calculate_quality_score_from_feedback
        
        from Profile.models import Feedback
        recent_feedback = Feedback.objects.filter(
            to_user=self.assigned_freelancer,
            created_at__gte=timezone.now() - timezone.timedelta(days=90)
        )
        
        if recent_feedback.exists():
            new_score = calculate_quality_score_from_feedback(self, recent_feedback.first())
            
            if new_score and new_score != self.quality_score:
                old_score = self.quality_score
                self.quality_score = new_score
                
                # Add note about the update
                if not self.internal_notes:
                    self.internal_notes = ""
                self.internal_notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] Quality score updated: {old_score}→{new_score}"
                
                self.save()
                return {'old_score': old_score, 'new_score': new_score}
        
        return None

    def get_client_feedback(self):
        """Get all client feedback notes"""
        return self.notes.filter(note_type='client_feedback').order_by('-created_at')
    
    def get_freelancer_notes(self):
        """Get all freelancer notes"""
        return self.notes.filter(note_type='freelancer_note').order_by('-created_at')
    
    def get_internal_notes(self):
        """Get all internal notes"""
        return self.notes.filter(note_type='internal_note').order_by('-created_at')
    
    
    def add_note(self, note_type, content, created_by, milestone=None, **kwargs):
        """Helper method to add a note"""
        return self.notes.create(
            note_type=note_type,
            content=content,
            created_by=created_by,
            milestone=milestone,
            **kwargs
        )

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new instance
        super().save(*args, **kwargs)  # Save the instance first
        
        if is_new or self.status == 'assigned':  # Only run if new or status is set to 'assigned'
            if self.obsp_response:
                self.obsp_response.calculate_and_set_milestone_deadlines()

class OBSPApplication(models.Model):
    """Freelancer application to work on an OBSP template level"""
    APPLICATION_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('assigned', 'Assigned to Project'),
        ('completed', 'Completed')
    ]
    
    # Core relationships - freelancer applies to template level
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='obsp_applications')
    obsp_template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE, related_name='applications')
    selected_level = models.CharField(max_length=20, choices=OBSPLevel.LEVEL_CHOICES)
    
    # Application details
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='obsp_applications_reviewed')
    
    # Freelancer's pitch
    pitch = models.TextField(help_text="Freelancer's proposal/pitch for this project")
    
    # Eligibility reference
    eligibility_reference = models.ForeignKey('freelancer.FreelancerOBSPEligibility', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    
    # Admin notes
    admin_notes = models.TextField(blank=True, help_text="Internal notes for Talintz team")
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if applicable")
    
    class Meta:
        unique_together = ['freelancer', 'obsp_template', 'selected_level']
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['status', 'applied_at']),
            models.Index(fields=['freelancer', 'status']),
            models.Index(fields=['obsp_template', 'status']),
        ]

    def __str__(self):
        return f"{self.freelancer.username} - {self.obsp_template.title} ({self.get_selected_level_display()})"

    def get_eligibility_data(self):
        """Get eligibility data for this application level"""
        if self.eligibility_reference:
            return self.eligibility_reference.get_level_eligibility(self.selected_level)
        return None

    def get_eligibility_score(self):
        """Get eligibility score for this application"""
        eligibility_data = self.get_eligibility_data()
        return eligibility_data.get('score', 0) if eligibility_data else 0

    def is_eligible_for_level(self):
        """Check if freelancer is eligible for the selected level"""
        eligibility_data = self.get_eligibility_data()
        return eligibility_data.get('is_eligible', False) if eligibility_data else False

    def approve(self, reviewed_by_user):
        """Approve the application"""
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by_user
        self.save()

    def reject(self, reviewed_by_user, reason=""):
        """Reject the application"""
        self.status = 'rejected'
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by_user
        self.rejection_reason = reason
        self.save()

    def assign_to_project(self):
        """Assign the application to a project (creates OBSPAssignment)"""
        if self.status == 'approved':
            # Note: This would need to be updated when a client actually purchases this template
            # For now, we'll create a placeholder assignment
            # In a real scenario, you'd need to link this to an actual OBSPResponse when a client purchases
            
            # Create a placeholder OBSPResponse for this template
            # This is a simplified approach - in production you might handle this differently
            User = get_user_model()
            
            # Get or create a system user for placeholder responses
            system_user, created = User.objects.get_or_create(
                username='system_obsp',
                defaults={'email': 'system@talintz.com', 'role': 'client'}
            )
            
            # Create OBSP response for this template
            obsp_response, created = OBSPResponse.objects.get_or_create(
                template=self.obsp_template,
                client=system_user,
                selected_level=self.selected_level,
                defaults={
                    'total_price': self.project_value,
                    'status': 'processing'
                }
            )
            
            # Create OBSP assignment
            assignment = OBSPAssignment.objects.create(
                obsp_response=obsp_response,
                assigned_freelancer=self.freelancer,
                assigned_by=self.reviewed_by,
                status='assigned'
            )
            self.status = 'assigned'
            self.save()
            return assignment
        return None

    @property
    def project_value(self):
        """Get the project value for the selected level"""
        level_obj = self.obsp_template.levels.filter(level=self.selected_level).first()
        return level_obj.price if level_obj else 0

    @property
    def days_since_applied(self):
        """Get days since application was submitted"""
        return (timezone.now() - self.applied_at).days

class OBSPAssignmentNote(models.Model):
    """Notes and feedback for OBSP assignments with milestone tracking"""
    NOTE_TYPE_CHOICES = [
        ('client_feedback', 'Client Feedback'),
        ('freelancer_note', 'Freelancer Note'),
        ('internal_note', 'Internal Note'),
        ('milestone_feedback', 'Milestone Feedback'),
        ('quality_review', 'Quality Review'),
        ('deadline_update', 'Deadline Update')
    ]
    
    # Core relationships
    response = models.ForeignKey(OBSPResponse, on_delete=models.CASCADE, related_name='notes')
    milestone = models.ForeignKey(OBSPMilestone, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Note details
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_private = models.BooleanField(default=False, help_text="Internal notes only visible to admins")
    
    # For milestone-specific feedback
    milestone_status = models.CharField(max_length=20, choices=OBSPMilestone.STATUS_CHOICES, blank=True)
    quality_rating = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    is_aknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['response', 'note_type']),
            models.Index(fields=['milestone', 'note_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_note_type_display()} - {self.response} - {self.created_at.strftime('%Y-%m-%d')}"

    def get_note_type_display_name(self):
        """Get display name with milestone context"""
        if self.milestone:
            return f"{self.get_note_type_display()} - {self.milestone.title}"
        return self.get_note_type_display()

    def is_visible_to_user(self, user):
        """Check if note is visible to specific user"""
        if self.is_private and user.role != 'admin':
            return False
        
        # Client can see client feedback and milestone feedback
        if user.role == 'client' and self.note_type in ['client_feedback', 'milestone_feedback']:
            return True
        
        # Freelancer can see their own notes and milestone feedback
        if user.role == 'freelancer' and self.created_by == user:
            return True
        
        # Admins can see all notes
        if user.role == 'admin':
            return True
        
        return False

class OBSPAssignmentHistory(models.Model):
    """Tracks all status changes and important actions"""
    ACTION_CHOICES = [
        ('status_change', 'Status Changed'),
        ('note_added', 'Note Added'),
        ('file_uploaded', 'File Uploaded'),
        ('payout_processed', 'Payout Processed')
    ]
    
    assignment = models.ForeignKey(OBSPAssignment, on_delete=models.CASCADE)
    milestone = models.ForeignKey(OBSPMilestone, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict)  # {from: 'pending', to: 'in_progress'}
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

