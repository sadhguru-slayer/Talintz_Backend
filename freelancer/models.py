from django.db import models
from financeapp.models import PaymentMethod,Transaction
class Event(models.Model):
    title = models.CharField(max_length=255)
    start = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class FreelancerActivity(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    ACTIVITY_TYPES = [
        # Project-related activities
        ('bid_submitted', 'Bid Submitted'),
        ('project_awarded', 'Project Awarded'),
        ('project_started', 'Project Started'),
        ('milestone_completed', 'Milestone Completed'),
        ('project_completed', 'Project Completed'),
        ('project_feedback', 'Project Feedback Received'),
        ('project_rejected', 'Project Rejected'),
        ('client_message', 'Client Message Received'),
        
        # Financial activities
        ('payment_received', 'Payment Received'),
        ('payment_pending', 'Payment Pending'),
        ('payment_disputed', 'Payment Disputed'),
        ('payment_released', 'Payment Released'),
        ('invoice_sent', 'Invoice Sent'),
        ('invoice_paid', 'Invoice Paid'),
        ('withdrawal_initiated', 'Withdrawal Initiated'),
        ('withdrawal_completed', 'Withdrawal Completed'),
        
        # Profile/Account activities
        ('profile_updated', 'Profile Updated'),
        ('skill_added', 'Skill Added'),
        ('portfolio_updated', 'Portfolio Updated'),
        ('certification_added', 'Certification Added'),
        ('verification_completed', 'Verification Completed'),
        ('rating_received', 'Rating Received'),
        
        # System activities
        ('login', 'User Logged In'),
        ('login_failed', 'Login Failed'),
        ('account_security', 'Account Security Alert'),
        ('preferences_updated', 'Preferences Updated'),
    ]
    
    VISIBILITY_CHOICES = [
        ('private', 'Private - Only Me'),
        ('clients', 'Clients - Visible to Current Clients'),
        ('public', 'Public - Visible on Profile'),
    ]
    
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='freelancer_activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    description = models.CharField(max_length=255, blank=True, null=True)
    detailed_description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Related objects
    related_model = models.CharField(max_length=100, null=True, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    client = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='client_activities_with_freelancer')
    project = models.ForeignKey('core.Project', on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey('core.Task', on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Advanced features
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='private')
    changes_detail = models.JSONField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    action_required = models.BooleanField(default=False)
    action_taken = models.BooleanField(default=False)
    action_deadline = models.DateTimeField(null=True, blank=True)
    
    # Analytics fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    
    # Notification settings
    email_sent = models.BooleanField(default=False)
    push_notification_sent = models.BooleanField(default=False)
    in_app_notification_sent = models.BooleanField(default=False)
    
    # Add the missing bid field
    bid = models.ForeignKey('core.Bid', on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Freelancer Activity'
        verbose_name_plural = 'Freelancer Activities'
        indexes = [
            models.Index(fields=['freelancer', 'timestamp']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['is_read']),
            models.Index(fields=['action_required']),
        ]

    def __str__(self):
        return f'{self.freelancer.username} - {self.get_activity_type_display()} - {self.timestamp}'
    
    @property
    def formatted_changes(self):
        """Returns a formatted string of changes for display"""
        if self.changes_detail:
            return " | ".join(self.changes_detail.get('changes', []))
        return self.description
    
    @property
    def time_since(self):
        """Returns a human-readable string of time since the activity occurred"""
        now = timezone.now()
        diff = now - self.timestamp
        
        if diff.days > 365:
            return f"{diff.days // 365} year{'s' if diff.days // 365 != 1 else ''} ago"
        if diff.days > 30:
            return f"{diff.days // 30} month{'s' if diff.days // 30 != 1 else ''} ago"
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        if diff.seconds > 3600:
            return f"{diff.seconds // 3600} hour{'s' if diff.seconds // 3600 != 1 else ''} ago"
        if diff.seconds > 60:
            return f"{diff.seconds // 60} minute{'s' if diff.seconds // 60 != 1 else ''} ago"
        return "Just now"
    
    def mark_as_read(self):
        """Mark the activity as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    def mark_action_taken(self):
        """Mark that action has been taken for this activity"""
        self.action_taken = True
        self.save(update_fields=['action_taken'])
    
    @classmethod
    def log_activity(cls, freelancer, activity_type, description=None, **kwargs):
        """
        Convenience method to log an activity with additional data
        Usage: FreelancerActivity.log_activity(freelancer, 'payment_received', 'Payment for Project X', project=project_obj, payment=payment_obj)
        """
        # Handle the details parameter by mapping it to changes_detail
        if 'details' in kwargs:
            kwargs['changes_detail'] = kwargs.pop('details')
            
        activity = cls(
            freelancer=freelancer,
            activity_type=activity_type,
            description=description,
            **kwargs
        )
        activity.save()
        return activity
    




# OBSP related

from django.db import models
from django.conf import settings
from OBSP.models import OBSPTemplate, OBSPLevel
from freelancer.obsp_eligibility import OBSPEligibilityCalculator

class FreelancerOBSPEligibility(models.Model):
    """
    Scalable eligibility storage - only stores when eligibility is calculated
    Uses JSON for flexible scoring and proof storage
    """
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='obsp_eligibility')
    obsp_template = models.ForeignKey(OBSPTemplate, on_delete=models.CASCADE)
    
    # Store all levels in a single JSON field for efficiency
    eligibility_data = models.JSONField(default=dict, help_text="Stores eligibility for all levels")
    # Format: {
    #   'easy': {
    #     'is_eligible': True, 
    #     'score': 85.5, 
    #     'last_calculated': '2024-01-01T10:00:00Z', 
    #     'proof': {
    #       'skill_analysis': {...},
    #       'project_analysis': {...},
    #       'rating_analysis': {...},
    #       'deadline_analysis': {...},
    #       'eligibility_reasons': [...],
    #       'disqualification_reasons': [...],
    #       'improvement_suggestions': [...]
    #     }
    #   },
    #   'medium': {...},
    #   'hard': {...}
    # }
    
    # Overall metadata
    last_updated = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=20, default='1.0')
    
    class Meta:
        unique_together = ('freelancer', 'obsp_template')
        indexes = [
            models.Index(fields=['freelancer', 'obsp_template']),
            models.Index(fields=['last_updated']),
        ]
        ordering = ['-last_updated']

    def __str__(self):
        return f"{self.freelancer.username} - {self.obsp_template.title}"

    def get_level_eligibility(self, level):
        """Get eligibility for a specific level"""
        return self.eligibility_data.get(level, {
            'is_eligible': False,
            'score': 0,
            'last_calculated': None,
            'proof': {}
        })

    def set_level_eligibility(self, level, is_eligible, score, proof):
        """Set eligibility for a specific level with detailed analysis"""
        if level not in self.eligibility_data:
            self.eligibility_data[level] = {}
        
        # Ensure proof is JSON serializable
        def serialize_proof(data):
            """Recursively serialize proof data for JSON storage"""
            from decimal import Decimal
            from datetime import datetime, date
            from django.utils import timezone
            
            if isinstance(data, dict):
                return {k: serialize_proof(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [serialize_proof(item) for item in data]
            elif isinstance(data, set):
                return list(data)
            elif isinstance(data, Decimal):
                return float(data)
            elif isinstance(data, (datetime, date)):
                return data.isoformat()
            elif isinstance(data, timezone.datetime):
                return data.isoformat()
            else:
                return data
        
        serialized_proof = serialize_proof(proof)
        
        self.eligibility_data[level].update({
            'is_eligible': is_eligible,
            'score': score,
            'last_calculated': timezone.now().isoformat(),
            'proof': serialized_proof
        })
        self.save()

    def get_detailed_analysis(self, level):
        """Get detailed analysis for a specific level"""
        level_data = self.eligibility_data.get(level, {})
        return level_data.get('proof', {})

    def get_all_eligible_levels(self):
        """Get all levels where freelancer is eligible"""
        return [
            level for level, data in self.eligibility_data.items()
            if data.get('is_eligible', False)
        ]

    def get_highest_eligible_level(self):
        """Get the highest level where freelancer is eligible"""
        level_order = {'easy': 1, 'medium': 2, 'hard': 3}
        eligible_levels = self.get_all_eligible_levels()
        
        if not eligible_levels:
            return None
        
        return max(eligible_levels, key=lambda x: level_order.get(x, 0))

class FreelancerEligibilityCache(models.Model):
    """
    Cache for frequently accessed eligibility data
    Stores aggregated data for fast lookups
    """
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eligibility_cache')
    
    # Aggregated data for quick access
    total_eligible_obsp = models.IntegerField(default=0)
    total_obsp_checked = models.IntegerField(default=0)
    average_score = models.FloatField(default=0)
    
    # Level breakdown stored as JSON for flexibility
    level_breakdown = models.JSONField(default=dict)
    # Format: {
    #   'easy': {'eligible_count': 5, 'total_count': 10, 'average_score': 75.5},
    #   'medium': {'eligible_count': 3, 'total_count': 8, 'average_score': 65.2},
    #   'hard': {'eligible_count': 1, 'total_count': 5, 'average_score': 45.1}
    # }
    
    # Cache metadata
    last_calculated = models.DateTimeField(auto_now=True)
    cache_version = models.CharField(max_length=20, default='1.0')
    
    class Meta:
        unique_together = ('freelancer',)
        indexes = [
            models.Index(fields=['total_eligible_obsp', 'average_score']),
            models.Index(fields=['last_calculated']),
        ]

    def __str__(self):
        return f"{self.freelancer.username} - Eligibility Cache"

# Updated OBSPEligibilityManager
class OBSPEligibilityManager:
    """
    Manager class for efficient eligibility operations
    """
    
    @staticmethod
    def calculate_and_store_eligibility(freelancer, obsp_template, levels=None):
        """
        Calculate eligibility for specified levels and store efficiently
        """
        if levels is None:
            levels = ['easy', 'medium', 'hard']
        
        # Get or create eligibility record
        eligibility_obj, created = FreelancerOBSPEligibility.objects.get_or_create(
            freelancer=freelancer,
            obsp_template=obsp_template,
            defaults={'eligibility_data': {}}
        )
        
        # Calculate for each level
        for level in levels:
            try:
                is_eligible, overall_score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                    freelancer, obsp_template, level
                )
                
                # Store everything in the JSON field - NO separate records!
                eligibility_obj.set_level_eligibility(level, is_eligible, overall_score, analysis)
            except Exception as e:
                print(f"Error calculating eligibility for {level}: {str(e)}")
                # Set default values if calculation fails
                eligibility_obj.set_level_eligibility(level, False, 0, {'error': str(e)})
        
        # Update cache
        OBSPEligibilityManager.update_freelancer_cache(freelancer)
        
        return eligibility_obj
    
    @staticmethod
    def get_eligibility(freelancer, obsp_template, level):
        """
        Get eligibility for a specific freelancer, OBSP, and level
        """
        try:
            eligibility_obj = FreelancerOBSPEligibility.objects.get(
                freelancer=freelancer,
                obsp_template=obsp_template
            )
            return eligibility_obj.get_level_eligibility(level)
        except FreelancerOBSPEligibility.DoesNotExist:
            # Calculate on-demand if not cached
            return OBSPEligibilityManager.calculate_and_store_eligibility(
                freelancer, obsp_template, [level]
            ).get_level_eligibility(level)
    
    @staticmethod
    def get_freelancer_summary(freelancer):
        """
        Get comprehensive eligibility summary for a freelancer
        """
        try:
            cache = FreelancerEligibilityCache.objects.get(freelancer=freelancer)
            return {
                'freelancer': freelancer.username,
                'total_eligible_obsp': cache.total_eligible_obsp,
                'total_obsp_checked': cache.total_obsp_checked,
                'average_score': cache.average_score,
                'level_breakdown': cache.level_breakdown,
                'last_updated': cache.last_calculated.isoformat()
            }
        except FreelancerEligibilityCache.DoesNotExist:
            # Calculate cache if it doesn't exist
            OBSPEligibilityManager.update_freelancer_cache(freelancer)
            return OBSPEligibilityManager.get_freelancer_summary(freelancer)
    
    @staticmethod
    def update_freelancer_cache(freelancer):
        """
        Update the freelancer's eligibility cache
        """
        all_eligibility = FreelancerOBSPEligibility.objects.filter(freelancer=freelancer)
        
        total_eligible = 0
        total_checked = all_eligibility.count()
        level_counts = {'easy': {'eligible': 0, 'total': 0, 'scores': []},
                       'medium': {'eligible': 0, 'total': 0, 'scores': []},
                       'hard': {'eligible': 0, 'total': 0, 'scores': []}}
        
        all_scores = []  # This should include ALL scores, not just eligible ones
        
        for eligibility in all_eligibility:
            for level, data in eligibility.eligibility_data.items():
                if level in level_counts:
                    level_counts[level]['total'] += 1
                    score = data.get('score', 0)
                    level_counts[level]['scores'].append(score)
                    all_scores.append(score)  # Add ALL scores to overall average
                    
                    if data.get('is_eligible', False):
                        level_counts[level]['eligible'] += 1
                        total_eligible += 1
        
        # Calculate averages
        level_breakdown = {}
        for level, counts in level_counts.items():
            avg_score = sum(counts['scores']) / len(counts['scores']) if counts['scores'] else 0
            level_breakdown[level] = {
                'eligible_count': counts['eligible'],
                'total_count': counts['total'],
                'average_score': round(avg_score, 2)
            }
        
        # Calculate overall average from ALL scores (not just eligible ones)
        overall_average_score = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Update or create cache
        cache, created = FreelancerEligibilityCache.objects.update_or_create(
            freelancer=freelancer,
            defaults={
                'total_eligible_obsp': total_eligible,
                'total_obsp_checked': total_checked,
                'average_score': round(overall_average_score, 2),  # Use overall average
                'level_breakdown': level_breakdown
            }
        )
        
        return cache

    @classmethod
    def get_or_create_eligibility(cls, freelancer, obsp_template):
        """Get existing eligibility or create new one"""
        eligibility, created = FreelancerOBSPEligibility.objects.get_or_create(
            freelancer=freelancer,
            obsp_template=obsp_template,
            defaults={
                'eligibility_data': {},
                'calculation_version': '1.0'
            }
        )
        
        if created or not eligibility.eligibility_data:
            # Calculate eligibility for all levels
            eligibility_data = {}
            for level in ['easy', 'medium', 'hard']:
                level_eligibility = cls.get_eligibility(freelancer, obsp_template, level)
                eligibility_data[level] = level_eligibility
            
            eligibility.eligibility_data = eligibility_data
            eligibility.save()
        
        return eligibility

# Batch processing for scalability
class OBSPEligibilityBatchProcessor:
    """
    Handles batch eligibility calculations for better performance
    """
    
    @staticmethod
    def process_freelancer_batch(freelancer_ids, obsp_template_ids=None):
        """
        Process eligibility for a batch of freelancers
        """
        from django.db import transaction
        
        with transaction.atomic():
            for freelancer_id in freelancer_ids:
                freelancer = User.objects.get(id=freelancer_id)
                
                if obsp_template_ids:
                    templates = OBSPTemplate.objects.filter(id__in=obsp_template_ids)
                else:
                    templates = OBSPTemplate.objects.filter(is_active=True)
                
                for template in templates:
                    OBSPEligibilityManager.calculate_and_store_eligibility(
                        freelancer, template
                    )
    
    @staticmethod
    def update_all_caches():
        """
        Update all freelancer caches (can be run as a background task)
        """
        freelancer_ids = User.objects.filter(role='freelancer').values_list('id', flat=True)
        
        for freelancer_id in freelancer_ids:
            freelancer = User.objects.get(id=freelancer_id)
            OBSPEligibilityManager.update_freelancer_cache(freelancer)

# Legacy function for backward compatibility
def calculate_and_store_eligibility(freelancer, obsp_template, level):
    """
    Legacy function - now uses the new scalable manager
    """
    return OBSPEligibilityManager.calculate_and_store_eligibility(freelancer, obsp_template, [level])

def get_freelancer_eligibility_summary(freelancer, obsp_template=None):
    """
    Legacy function - now uses the new scalable manager
    """
    return OBSPEligibilityManager.get_freelancer_summary(freelancer)
