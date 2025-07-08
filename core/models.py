from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db import models, transaction
from decimal import Decimal, ROUND_HALF_UP
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
# User Model
from django.db import models
from django.contrib.auth.models import AbstractUser, User
from django.db.models import Q, Sum
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
import uuid


class User(AbstractUser):
    ROLE_CHOICES = [
        ('freelancer', 'Freelancer'),
        ('client', 'Client'),
        ('student', 'Student'),
    ]
    
    MEMBERSHIP_CHOICES = [
        ('free', 'Free'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', db_index=True)
    membership = models.CharField(max_length=10, choices=MEMBERSHIP_CHOICES, default='free')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_profiled = models.BooleanField(default=False)
    is_talentrise = models.BooleanField(default=True)
    nickname = models.CharField(max_length=150, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    

    def __str__(self):
        return f"{self.id}-{self.username}"
    
    def get_client_connections(self):
        # Get the total number of accepted connections (both sent and received)
        sent_connections = Connection.objects.filter(from_user=self, status='accepted')
        received_connections = Connection.objects.filter(to_user=self, status='accepted')

        return sent_connections.count() + received_connections.count()

class Connection(models.Model):
    from_user = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        ordering = ['-created_at']

    def __str__(self):
        return f"Connection from {self.from_user.username} to {self.to_user.username} ({self.status})"

    def clean(self):
        # Ensure a user cannot connect to themselves
        if self.from_user == self.to_user:
            raise ValidationError("You cannot connect to yourself.")
        
        # Ensure reverse connections do not exist (e.g., A -> B and B -> A)
        if Connection.objects.filter(from_user=self.to_user, to_user=self.from_user, status='pending').exists():
            raise ValidationError("You cannot send a connection request to a user who has already sent you one.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Call the clean method to ensure validation
        super().save(*args, **kwargs)

    def accept(self):
        self.status = 'accepted'
        self.save()

    def reject(self):
        self.status = 'rejected'
        self.save()

    def cancel(self):
        self.delete()  # Cancel and delete the connection request

# Category Model
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True,db_index=True)
    description = models.TextField()

    def __str__(self):
        return self.name
    
# Skill Model
class Skill(models.Model):
    category = models.ForeignKey(Category, related_name='skills', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return f'{self.name} in {self.category.name}' 

class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('not_initiated', 'Not Initiated'),
        ('paid', 'Paid'),
    ]
    
    # New: Clean Pricing Strategy Choices
    PRICING_STRATEGY_CHOICES = [
        ('fixed', 'Fixed Price'),
        ('hourly', 'Hourly Rate'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    deadline = models.DateField()
    is_collaborative = models.BooleanField(default=False)
    domain = models.ForeignKey(Category, on_delete=models.CASCADE)
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_strategy = models.CharField(max_length=20, default='automatic')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='not_initiated')
    
    # New: Pricing Strategy Fields (matching frontend field names)
    pricing_strategy = models.CharField(
        max_length=20, 
        choices=PRICING_STRATEGY_CHOICES, 
        default='fixed'
    )
    hourly_rate = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    max_hours = models.PositiveIntegerField(null=True, blank=True)
    
    # Hourly project management fields
    allow_hour_flexibility = models.BooleanField(default=True)
    require_milestone_approval = models.BooleanField(default=True)
    emergency_hours = models.PositiveIntegerField(default=0)
    
    # Core Fields (keeping existing)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    isSubscribed = models.BooleanField(default=False)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    skills_required = models.ManyToManyField(Skill, related_name='projects', blank=True)
    assigned_to = models.ManyToManyField(User, related_name='projects_assigned', blank=True)

    # Keep existing TalentRise fields
    is_talentrise_friendly = models.BooleanField(
        default=False, 
        help_text="Flag to mark projects suitable for TalentRise students"
    )
    complexity_level = models.CharField(
        max_length=15, 
        choices=[
        ('entry', 'Entry Level'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
        ], 
        default='intermediate', 
        help_text="Project complexity level to match with appropriate freelancers"
    )

    # Keep existing multi-freelancer fields
    is_multi_freelancer = models.BooleanField(
        default=False, 
        help_text="Project designed for multiple freelancers"
    )
    estimated_time_saved = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Estimated days saved using multi-freelancer approach"
    )
    auto_schedule_tasks = models.BooleanField(
        default=True, 
        help_text="Automatically schedule tasks based on dependencies"
    )
    client_skill_level = models.CharField(
        max_length=20, 
        choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert')
        ], 
        default='beginner', 
        help_text="Client's project management experience level"
    )
    show_simplified_ui = models.BooleanField(
        default=True, 
        help_text="Show simplified UI for clients with limited PM knowledge"
    )

    class Meta:
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['description']),
            models.Index(fields=['pricing_strategy']),
            models.Index(fields=['status']),
            models.Index(fields=['client']),
        ]

    def clean(self):
        """Validate pricing strategy specific fields"""
        super().clean()
        
        if self.pricing_strategy == 'hourly':
            if not self.hourly_rate:
                raise ValidationError("Hourly rate is required for hourly projects")
            if not self.estimated_hours:
                raise ValidationError("Estimated hours are required for hourly projects")
                
        elif self.pricing_strategy == 'fixed':
            if not self.budget:
                raise ValidationError("Budget is required for fixed price projects")
                
        elif self.pricing_strategy == 'hourly':
            if not self.max_hours or self.max_hours <= 0:
                raise ValidationError("Hourly projects must have a valid maximum hours")
            if self.max_hours < self.estimated_hours:
                raise ValidationError("Maximum hours cannot be less than estimated hours")

    def save(self, *args, **kwargs):
        """Auto-populate budget field based on pricing strategy"""
        if self.pricing_strategy == 'fixed' and self.budget:
            self.budget = self.budget
        elif self.pricing_strategy == 'hourly' and self.hourly_rate and self.estimated_hours:
            # Set budget as max possible cost for hourly projects
            self.budget = self.hourly_rate * self.estimated_hours
            
        super().save(*args, **kwargs)

    # NEW: Pricing Strategy Methods
    def get_pricing_display(self):
        """Get human-readable pricing information"""
        if self.pricing_strategy == 'fixed':
            return f"Fixed Price: {self.budget:,.2f}"
        elif self.pricing_strategy == 'hourly':
            return f"Hourly Rate: {self.hourly_rate:,.2f}/hr"
        else:
            return "Negotiable"

    def get_estimated_cost(self):
        """Get estimated total cost based on pricing strategy"""
        if self.pricing_strategy == 'fixed':
            return self.budget or 0
        elif self.pricing_strategy == 'hourly':
            if self.hourly_rate and self.estimated_hours:
                return self.hourly_rate * self.estimated_hours
        return 0

    def is_budget_within_range(self, bid_amount):
        """Check if a bid amount is within acceptable range"""
        if self.pricing_strategy == 'hourly':
            min_cost = self.hourly_rate * self.estimated_hours if self.hourly_rate and self.estimated_hours else 0
            max_cost = self.hourly_rate * self.max_hours if self.hourly_rate and self.max_hours else float('inf')
            return min_cost <= bid_amount <= max_cost
        elif self.pricing_strategy == 'fixed':
            # Allow 20% variance for fixed price projects
            variance = self.budget * Decimal('0.2')
            return self.budget - variance <= bid_amount <= self.budget + variance
        return True  # For negotiable projects

    # Keep existing methods
    def get_pending_tasks(self):
        """Returns all tasks that are currently 'pending' and not 'completed' for this project."""
        tasks = Task.objects.filter(project=self.id, status='pending').count()
        return tasks

    def __str__(self):
        return self.title

    def get_pending_projects(self):
        """
        Returns all projects that are currently 'pending' for this client.
        """
        return Project.objects.filter(status='pending', client=self.client)

    def get_upcoming_deadlines(self):
        """
        Returns all projects with deadlines within the next week.
        """
        return Project.objects.filter(deadline__lt=timezone.now() + timezone.timedelta(weeks=1)).order_by('deadline')

    def update_payment_strategy(self):
        """Determine payment handling strategy based on project milestones only"""
        has_project_payment_milestones = self.milestones.filter(
            milestone_type__in=['payment', 'hybrid']
        ).exists()

        if has_project_payment_milestones:
            self.payment_strategy = 'project_milestones'
        else:
            self.payment_strategy = 'lump_sum'
        self.save()

    def get_total_paid(self):
        """Get total paid amount from project milestones only"""
        if self.payment_strategy == 'project_milestones':
            return self.milestones.filter(
                status='paid',
                milestone_type__in=['payment', 'hybrid']
            ).aggregate(total=Sum('amount'))['total'] or 0
        else:
            return self.total_spent if self.status == 'completed' else 0

    def get_progress(self):
        """Calculate progress based on completed project milestones only"""
        total_milestones = self.milestones.filter(milestone_type__in=['progress', 'hybrid']).count()
        completed_milestones = self.milestones.filter(
            status='paid',
            milestone_type__in=['progress', 'hybrid']
        ).count()

        return (completed_milestones / total_milestones * 100) if total_milestones else 0

    def handle_payment(self):
        """Handle automatic payments based on strategy"""
        if self.payment_strategy == 'lump_sum' and self.status == 'completed':
            self._process_lump_sum_payment()
            
    def _process_lump_sum_payment(self):
        """Automatically process final payment for lump-sum projects"""
        if not self.payments.filter(status='paid').exists():
            Payment.objects.create(
                from_user=self.client,
                to_user=self.assigned_to.first(),  # Simplified for example
                payment_for='project',
                project=self,
                amount=self.budget,
                status='paid'
            )
            self.total_spent = self.budget
            self.save()

    @property
    def allows_project_bids(self):
        """Check if bidding on project level is allowed"""
        return True  # Always allow project-level bidding since no tasks

    # New methods
    def get_critical_path(self):
        """Calculate critical path through task dependencies"""
        # Implementation details would go here
        dependencies = TaskDependency.objects.filter(from_task__project=self)
        # Logic to determine critical path
        return []
    
    def generate_task_timeline(self):
        """Generate timeline based on task dependencies and durations"""
        # Implementation would involve analyzing task dependencies
        return {}
    
    def get_parallel_tasks(self):
        """Return sets of tasks that can be worked on simultaneously"""
        # Implementation would identify tasks without blocking dependencies
        return self.tasks.filter(dependencies__isnull=True)
    
    def calculate_time_savings(self):
        """Calculate time saved using multi-freelancer approach vs sequential"""
        # Logic to compare sequential vs parallel execution
        sequential_days = self.tasks.aggregate(total=Sum('estimated_days'))['total'] or 0
        # Parallel time calculation using critical path method
        parallel_days = 0  # Actual implementation would calculate this
        
        self.estimated_time_saved = sequential_days - parallel_days
        self.save()
        return self.estimated_time_saved

# Task Model
class Task(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('not_initiated', 'Not Initiated'),
        ('completed', 'Completed'),
    ]
    
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    deadline = models.DateField()
    assigned_to = models.ManyToManyField(User, related_name='assigned_tasks',  blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='not_initiated')
    is_payment_updated = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    skills_required_for_task = models.ManyToManyField(Skill, related_name='tasks', blank=True)
    is_automated_payment = models.BooleanField(default=False)

    # New fields for better scheduling and dependency management
    estimated_days = models.PositiveIntegerField(default=1, help_text="Estimated days to complete")
    earliest_start_date = models.DateField(null=True, blank=True, help_text="Calculated earliest start date based on dependencies")
    latest_start_date = models.DateField(null=True, blank=True, help_text="Latest date to start without affecting project timeline")
    can_start = models.BooleanField(default=False, help_text="Task has no blocking dependencies and can be started")
    priority_score = models.IntegerField(default=0, help_text="Calculated priority based on dependencies and deadline")
    specialist_required = models.BooleanField(default=True, help_text="Requires specialized skills vs general skills")

    def __str__(self):
        return self.title

    def update_payment_status(self):
        """Update payment status based on milestones or completion"""
        if self.milestones.exists():
            total_due = self.milestones.filter(
                milestone_type__in=['payment', 'hybrid']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            paid_amount = self.milestones.filter(
                status='paid',
                milestone_type__in=['payment', 'hybrid']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            self.payment_status = 'completed' if paid_amount >= total_due else 'not_initiated'
        else:
            # Auto-complete payment if no milestones and task is done
            self.payment_status = 'completed' if self.status == 'completed' else 'not_initiated'
            
        self.save()

    def save(self, *args, **kwargs):
        # Original completion logic
        if self.status == 'completed' and not self.milestones.exists():
            self.completed_at = timezone.now()
            if self.payment_status == 'not_initiated':
                self.payment_status = 'completed'
        
        super().save(*args, **kwargs)
        
        # New payment automation logic
        if self.status == 'completed' and not self.milestones.exists():
            self._process_automatic_payment()
        elif self.milestones.exists():
            # If milestones exist, ensure task payment status matches milestone payments
            total_due = self.milestones.aggregate(total=Sum('amount'))['total'] or 0
            paid_amount = self.milestones.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0
            self.payment_status = 'completed' if paid_amount >= total_due else 'not_initiated'
            self.save()

        self.project.update_payment_strategy()

    def _process_automatic_payment(self):
        """Handle automatic payment when no milestones exist"""
        if self.payment_status == 'completed' and not self.payments.exists():
            Payment.objects.create(
                from_user=self.project.client,
                to_user=self.assigned_to.first(),
                payment_for='task',
                task=self,
                amount=self.budget,
                status='paid'
            )

    @property
    def open_for_bidding(self):
        """Check if task is available for new bids"""
        return not self.bids.filter(
            state__in=['submitted', 'under_review', 'negotiation']
        ).exists()

    # New methods
    def update_schedule_status(self):
        """Update scheduling fields based on dependencies"""
        # Check if this task has dependencies
        has_blocking = TaskDependency.objects.filter(
            to_task=self, 
            dependency_type='finish_to_start'
        ).exists()
        
        self.can_start = not has_blocking
        self.save()
    
    def get_blocking_tasks(self):
        """Get tasks that are blocking this one from starting"""
        return [d.from_task for d in self.dependencies.all()]
    
    def get_dependent_tasks(self):
        """Get tasks that depend on this one"""
        return [d.to_task for d in self.dependents.all()]
    
    def estimate_completion_date(self):
        """Estimate completion date based on start date and duration"""
        if self.earliest_start_date:
            return self.earliest_start_date + timezone.timedelta(days=self.estimated_days)
        return None

class BidManager(models.Manager):
    """
    Custom manager for bid-related queries
    """
    def active_bids(self):
        return self.get_queryset().exclude(
            state__in=['withdrawn', 'rejected', 'archived']
        )

    def for_project(self, project_id):
        return self.filter(project_id=project_id).select_related(
            'freelancer',
            'project'
        ).prefetch_related(
            'items',
            'attachments'
        )

    def freelancer_bids(self, freelancer_id):
        return self.filter(freelancer_id=freelancer_id).order_by('-created_at')



class Bid(models.Model):
    BID_TYPES = (
        ('fixed', 'Fixed Price'),
        ('hourly', 'Hourly Rate'),
        ('milestone', 'Milestone-Based'),
        ('hybrid', 'Hybrid Model'),
    )

    BID_STATES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('interview_requested', 'Interview Requested'),
        ('interview_accepted', 'Interview Accepted'),
        ('interview_declined', 'Interview Declined'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    )

    # Core Relationships
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE,
        null=True
    )
    freelancer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='submitted_bids'
    )
    invited_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invited_bids'
    )

    # Bid Metadata
    bid_type = models.CharField(max_length=20, choices=BID_TYPES, default='fixed')
    version = models.PositiveIntegerField(default=1)
    parent_bid = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revisions'
    )
    state = models.CharField(max_length=20, choices=BID_STATES, default='draft')
    is_archived = models.BooleanField(default=False)

    # Financial Details
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(max_length=3, default='INR')
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Timeline
    proposed_start = models.DateField()
    proposed_end = models.DateField()
    delivery_buffer_days = models.PositiveIntegerField(default=0)

    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_edited_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name='modified_bids'
    )

    # Custom Manager
    objects = BidManager()

    class Meta:
        unique_together = ('project', 'freelancer', 'version')
        indexes = [
            models.Index(fields=['state', 'project', 'freelancer']),
            models.Index(fields=['total_value', 'currency']),
            models.Index(fields=['proposed_start', 'proposed_end']),
        ]

    def __str__(self):
        return f"Bid #{self.id} - {self.get_bid_type_display()} ({self.state})"

    def submit(self):
        """Submit bid with automatic project validation"""
        if self.state != 'draft':
            raise ValidationError("Only draft bids can be submitted.")
        self.state = 'submitted'
        self.version += 1
        self.save()

    def mark_under_review(self):
        """Mark bid as shortlisted (under review) - works for all tiers"""
        if self.state != 'submitted':
            raise ValidationError("Only submitted bids can be shortlisted.")
        self.state = 'under_review'
        self.save()

    def mark_submitted(self):
        """Move bid back to submitted (un-shortlist)"""
        if self.state != 'under_review':
            raise ValidationError("Only shortlisted bids can be moved back to submitted.")
        self.state = 'submitted'
        self.save()

    def request_interview(self):
        """Request interview (Standard/Premium tiers only)"""
        if self.state != 'under_review':
            raise ValidationError("Only shortlisted bids can have interview requested.")
        self.state = 'interview_requested'
        self.save()

    def accept_interview(self):
        """Freelancer accepts interview invitation"""
        if self.state != 'interview_requested':
            raise ValidationError("Only interview requested bids can be accepted by freelancer.")
        self.state = 'interview_accepted'
        self.save()

    def decline_interview(self):
        """Freelancer declines interview invitation"""
        if self.state != 'interview_requested':
            raise ValidationError("Only interview requested bids can be declined by freelancer.")
        self.state = 'interview_declined'
        self.save()

    def accept(self):
        """Accept the bid - works from under_review, interview_requested, or interview_accepted"""
        if self.state not in ['under_review', 'interview_requested', 'interview_accepted']:
            raise ValidationError("Only shortlisted or interviewed bids can be accepted.")
        self.state = 'accepted'
        self.save()

    def reject(self):
        """Reject the bid - works from under_review, interview_requested, or interview_accepted"""
        if self.state not in ['under_review', 'interview_requested', 'interview_accepted']:
            raise ValidationError("Only shortlisted or interviewed bids can be rejected.")
        self.state = 'rejected'
        self.save()

    def withdraw(self):
        """Withdraw the bid"""
        if self.state not in ['draft', 'submitted', 'under_review', 'interview_requested']:
            raise ValidationError("Only draft, submitted, under review, or interview requested bids can be withdrawn.")
        self.state = 'withdrawn'
        self.save()

    def clean(self):
        """Validate bid state transitions and relationships"""
        # Check basic relationship validity
        if not self.project:
            raise ValidationError("Project must be set.")
        
        # Check for duplicates with same project, freelancer, and state
        existing_bids = Bid.objects.filter(
            project=self.project,
            freelancer=self.freelancer,
            state=self.state
        ).exclude(pk=self.pk)
        
        if existing_bids.exists():
            raise ValidationError(f"You already have a bid with status '{self.state}' for this project")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class BidItem(models.Model):
    """
    Detailed breakdown of bid components with multiple pricing models
    """
    ITEM_TYPES = (
        ('task', 'Task'),
        ('project', 'Project'),
        ('milestone', 'Milestone'),
        ('service', 'Service'),
        ('material', 'Material'),
    )

    bid = models.ForeignKey(
        Bid,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    description = models.TextField()
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    delivery_days = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['item_type', 'bid']),
        ]

    @property
    def total_price(self):
        return self.quantity * self.unit_price * (1 + self.tax_rate/100)


class BidAttachment(models.Model):
    """
    Supporting documents for bids
    """
    bid = models.ForeignKey(
        Bid,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='bid_attachments/')
    url = models.URLField(max_length=255,null=True,blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class BidNegotiationLog(models.Model):
    """
    Audit trail for bid negotiation history
    """
    bid = models.ForeignKey(
        Bid,
        on_delete=models.CASCADE,
        related_name='negotiation_logs'
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    event_type = models.CharField(max_length=50)
    previous_state = models.CharField(max_length=50)
    new_state = models.CharField(max_length=50)
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['bid', 'timestamp']),
        ]


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('GPAY', 'Google Pay'),
        ('PAYPAL', 'PayPal'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]

    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
    ]
    
    from_user = models.ForeignKey(User, related_name='payments_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='payments_received', on_delete=models.CASCADE)
    payment_for = models.CharField(max_length=50)  # e.g., task, project
    project = models.ForeignKey(Project, related_name='payments', on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey(Task, related_name='payments', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='initiated')
    invoice_number = models.CharField(max_length=255, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=10, default='INR')
    installment_period = models.CharField(max_length=50, blank=True, null=True)
    discount_promo = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Ensure atomicity of the payment process
        with transaction.atomic():
            # Handle 'paid' status
            if self.status == 'paid':
                if self.task and self.task.status == "completed" and self.amount <= self.task.budget:
                    print("hiii")
                    self.task.is_payment_updated = True
                    self.task.payment_status = "completed"
                    self.task.save()

                    # Update the project's total spent
                    self.project.total_spent += self.amount
                    self.project.save()

                elif self.project and self.project.status == 'completed' and self.amount <= self.project.budget:
                    self.project.payment_status = "completed"
                    self.project.total_spent += self.amount
                    self.project.save()

            # Always call the parent save method after all logic is processed
            super().save(*args, **kwargs)

class UserFeedback(models.Model):
    from_user = models.ForeignKey(User, related_name='given_feedback', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='received_feedback', on_delete=models.CASCADE)

    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)], default=5)
    feedback_type = models.CharField(max_length=50, choices=[
        ('collaboration', 'Collaboration'),
        ('work_quality', 'Work Quality'),
        ('communication', 'Communication'),
        ('timeliness', 'Timeliness'),
        ('professionalism', 'Professionalism'),
    ])
    
    # Detailed comment or review
    comment = models.TextField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optionally, approval or flagging of feedback (e.g., for moderation purposes)
    is_approved = models.BooleanField(default=True)
    
    # Reference to parent feedback if it's a reply to another feedback
    parent = models.ForeignKey('self', related_name='replies', null=True, blank=True, on_delete=models.CASCADE)
    
    # Method to return a readable string representation of the feedback
    def __str__(self):
        return f"Feedback from {self.from_user.username} to {self.to_user.username} ({self.feedback_type})"
    
    class Meta:
        unique_together = ('from_user', 'to_user', 'feedback_type')  # Enforce one feedback per user pair and type
        ordering = ['-created_at']  # Order feedback by most recent
    

class Notification(models.Model):
    TYPE_CHOICES = [
        ('Messages', 'Messages'),
        ('Payments', 'Payments'),
        ('Projects', 'Projects'),
        ('Events', 'Events'),
        ('Workspace', 'Workspace'),
        ('Revisions', 'Revisions'),
        ('OBSP', 'OBSP'),
        ('Instructions', 'Instructions'),
        ('System', 'System'),
        # Add more as needed
    ]
    PRIORITY_CHOICES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subtype = models.CharField(max_length=50, blank=True, null=True)  # e.g. 'revision_created', 'workspace_instruction'
    title = models.CharField(null=True, max_length=200)
    notification_text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='info')

    # Generic relation to any model (Workspace, WorkspaceRevision, OBSPMilestone, Project, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    # object_id = models.PositiveIntegerField(null=True, blank=True)
    related_model_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'related_model_id')

    # Flexible metadata for extra context (e.g., milestone title, revision number, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.notification_text}"

    def mark_as_read(self):
        self.is_read = True
        self.save()

class Milestone(models.Model):
    MILESTONE_TYPE_CHOICES = [
        ('payment', 'Payment Only'),
        ('progress', 'Progress Only'),
        ('hybrid', 'Both Payment & Progress'),
        ('hourly', 'Hourly Tracking')  # New type for hourly projects
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    
    title = models.CharField(max_length=255)
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='milestones'  # This will allow project.milestones
    )
    task = models.ForeignKey(
        Task, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='milestones'  # This will allow task.milestones
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)  # Make nullable for hourly projects
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPE_CHOICES, default='hybrid')
    is_automated = models.BooleanField(default=True)
    
    # Add the missing status field
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # New fields for hourly projects
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    max_hours = models.PositiveIntegerField(null=True, blank=True)
    priority_level = models.CharField(
        max_length=20, 
        choices=[
            ('low', 'Low Priority'),
            ('medium', 'Medium Priority'),
            ('high', 'High Priority'),
            ('critical', 'Critical')
        ],
        default='medium'
    )
    quality_requirements = models.TextField(blank=True, null=True)
    deliverables = models.TextField(blank=True, null=True)
    
    # Add completed_at field for tracking completion
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Add missing fields from migration 0014
    actual_hours = models.PositiveIntegerField(null=True, blank=True)
    client_approved_hours = models.BooleanField(default=False)
    escrow_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Add missing fields from migration 0015
    client_approval_required = models.BooleanField(default=False)
    hours_submitted_at = models.DateTimeField(null=True, blank=True)
    overage_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['due_date']

    def clean(self):
        if not (self.project or self.task):
            raise ValidationError("Must be associated with a project or task")
        if self.project and self.task:
            raise ValidationError("Cannot belong to both project and task")
        
        # Validate based on milestone type
        if self.milestone_type == 'progress' and self.amount > 0:
            raise ValidationError("Progress-only milestones cannot have payment amounts")
        
        # Validate hourly milestone fields
        if self.milestone_type == 'hourly':
            if not self.estimated_hours or self.estimated_hours <= 0:
                raise ValidationError("Hourly milestones must have estimated hours")
            if not self.max_hours or self.max_hours <= 0:
                raise ValidationError("Hourly milestones must have maximum hours")
            if self.max_hours < self.estimated_hours:
                raise ValidationError("Maximum hours cannot be less than estimated hours")
        
        # Ensure project doesn't have conflicting milestone types
        if self.project and hasattr(self.project, 'payment_strategy'):
            if self.project.payment_strategy == 'lump_sum' and self.milestone_type in ['payment', 'hybrid']:
                raise ValidationError("Cannot add payment milestones to lump-sum projects")

    def __str__(self):
        return f"{self.title} ({self.get_milestone_type_display()})"

    def mark_paid(self):
        if self.status != 'paid':
            self.status = 'paid'
            self.completed_at = timezone.now()
            self.save()
            self._update_parent_payment()
            
            # Prevent double payment by clearing task/project automated payment
            if self.project and self.project.payment_status == 'completed':
                self.project.payment_status = 'not_initiated'
                self.project.save()

    def _update_parent_payment(self):
        """Update parent project payment status"""
        if self.project:
            self.project.update_payment_strategy()

class Invitation(models.Model):
    """
    Unified invitation system for various platform interactions
    """
    INVITATION_TYPES = [
        ('project_assignment', 'Project Assignment'),
        ('bid_invitation', 'Bid Invitation'),
        ('interview_request', 'Interview Request'),
        ('collaboration_invite', 'Collaboration Invite'),
        ('connection_request', 'Connection Request'),
        ('milestone_review', 'Milestone Review'),
        ('payment_approval', 'Payment Approval'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Core fields
    invitation_type = models.CharField(max_length=30, choices=INVITATION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Users involved - FIXED: Added related_name to avoid clashes
    from_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_core_invitations'  # Changed from 'sent_invitations'
    )
    to_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_core_invitations'  # Changed from 'received_invitations'
    )
    
    # Generic relationship - FLEXIBLE: Can link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Invitation details
    title = models.CharField(max_length=255)
    message = models.TextField()
    terms = models.JSONField(default=dict, blank=True)  # Flexible terms storage
    
    # Timing
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Response details
    response_message = models.TextField(blank=True)
    response_terms = models.JSONField(default=dict, blank=True)
    
    # System fields
    is_urgent = models.BooleanField(default=False)
    priority_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        default='medium'
    )
    
    # Performance optimization
    class Meta:
        indexes = [
            models.Index(fields=['invitation_type', 'status']),
            models.Index(fields=['from_user', 'status']),
            models.Index(fields=['to_user', 'status']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_invitation_type_display()} from {self.from_user.username} to {self.to_user.username}"

    def clean(self):
        """Validate invitation based on type"""
        super().clean()
        
        # Type-specific validations
        if self.invitation_type == 'project_assignment':
            if not self.related_object or not isinstance(self.related_object, Bid):
                raise ValidationError("Project assignment invitations require a bid")
                
        elif self.invitation_type == 'bid_invitation':
            if not self.related_object or not isinstance(self.related_object, Project):
                raise ValidationError("Bid invitations require a project")
                
        elif self.invitation_type == 'interview_request':
            if not self.related_object or not isinstance(self.related_object, Bid):
                raise ValidationError("Interview requests require a bid")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at

    @property
    def can_respond(self):
        """Check if invitation can still be responded to"""
        return self.status == 'pending' and not self.is_expired

    def accept(self, response_message="", response_terms=None):
        """Accept the invitation"""
        if not self.can_respond:
            raise ValidationError("Invitation cannot be accepted")
            
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.response_message = response_message
        if response_terms:
            self.response_terms = response_terms
        self.save()
        
        # Trigger type-specific actions
        self._handle_acceptance()

    def decline(self, response_message="", response_terms=None):
        """Decline the invitation"""
        if not self.can_respond:
            raise ValidationError("Invitation cannot be declined")
            
        self.status = 'declined'
        self.responded_at = timezone.now()
        self.response_message = response_message
        if response_terms:
            self.response_terms = response_terms
        self.save()
        
        # Trigger type-specific actions
        self._handle_declination()

    def cancel(self):
        """Cancel the invitation (by sender)"""
        if self.status != 'pending':
            raise ValidationError("Only pending invitations can be cancelled")
            
        self.status = 'cancelled'
        self.save()

    def _handle_acceptance(self):
        """Handle invitation acceptance based on type"""
        if self.invitation_type == 'project_assignment':
            self._handle_project_assignment_acceptance()
        elif self.invitation_type == 'interview_request':
            self._handle_interview_acceptance()
        elif self.invitation_type == 'bid_invitation':
            self._handle_bid_invitation_acceptance()

    def _handle_declination(self):
        """Handle invitation declination based on type"""
        if self.invitation_type == 'project_assignment':
            self._handle_project_assignment_declination()
        elif self.invitation_type == 'interview_request':
            self._handle_interview_declination()

    def _handle_project_assignment_acceptance(self):
        """Handle project assignment acceptance"""
        if isinstance(self.related_object, Bid):
            bid = self.related_object
            project = bid.project
            
            # Accept the bid
            bid.accept()
            
            # Assign project to freelancer
            project.assigned_to.add(self.to_user)
            project.status = 'ongoing'
            project.save()
            
            # Create notification with username instead of full name
            Notification.objects.create(
                user=self.from_user,
                type='Projects',
                related_model_id=project.id,
                title='Project Assignment Accepted',
                notification_text=f'{self.to_user.username} has accepted the project assignment for "{project.title}"'
            )

    def _handle_interview_acceptance(self):
        """Handle interview request acceptance"""
        if isinstance(self.related_object, Bid):
            bid = self.related_object
            
            # Update bid state to interview_accepted
            bid.accept_interview()
            
            # Create notification with username instead of full name
            Notification.objects.create(
                user=self.from_user,
                type='Projects',
                related_model_id=bid.project.id,
                title='Interview Accepted',
                notification_text=f'{self.to_user.username} has accepted the interview request for project "{bid.project.title}"'
            )

    def _handle_project_assignment_declination(self):
        """Handle project assignment declination"""
        if isinstance(self.related_object, Bid):
            bid = self.related_object
            
            # Reject the bid
            bid.reject()
            
            # Create notification with username instead of full name
            Notification.objects.create(
                user=self.from_user,
                type='Projects',
                related_model_id=bid.project.id,
                title='Project Assignment Declined',
                notification_text=f'{self.to_user.username} has declined the project assignment for project "{bid.project.title}"'
            )

    def _handle_interview_declination(self):
        """Handle interview request declination"""
        if isinstance(self.related_object, Bid):
            bid = self.related_object
            
            # Update bid state to interview_declined
            bid.decline_interview()
            
            # Create notification with username instead of full name
            Notification.objects.create(
                user=self.from_user,
                type='Projects',
                related_model_id=bid.project.id,
                title='Interview Declined',
                notification_text=f'{self.to_user.username} has declined the interview request for project "{bid.project.title}"'
            )

    @classmethod
    def create_project_assignment_invitation(cls, bid, message="", expires_in_hours=24):
        """Create a project assignment invitation"""
        return cls.objects.create(
            invitation_type='project_assignment',
            from_user=bid.project.client,
            to_user=bid.freelancer,
            content_type=ContentType.objects.get_for_model(bid),
            object_id=bid.id,
            title=f'Project Assignment: {bid.project.title}',
            message=message or f'You have been selected for the project "{bid.project.title}". Please review and accept the assignment.',
            expires_at=timezone.now() + timezone.timedelta(hours=expires_in_hours),
            terms={
                'project_id': bid.project.id,
                'bid_id': bid.id,
                'total_value': float(bid.total_value),
                'currency': bid.currency,
                'proposed_start': bid.proposed_start.isoformat(),
                'proposed_end': bid.proposed_end.isoformat(),
            }
        )

    @classmethod
    def create_interview_invitation(cls, bid, message="", expires_in_hours=48):
        """Create an interview invitation"""
        return cls.objects.create(
            invitation_type='interview_request',
            from_user=bid.project.client,
            to_user=bid.freelancer,
            content_type=ContentType.objects.get_for_model(bid),
            object_id=bid.id,
            title=f'Interview Request: {bid.project.title}',
            message=message or f'We would like to schedule an interview for the project "{bid.project.title}". Please respond to this invitation.',
            expires_at=timezone.now() + timezone.timedelta(hours=expires_in_hours),
            terms={
                'project_id': bid.project.id,
                'bid_id': bid.id,
                'interview_type': 'client_requested',
            }
        )

    @classmethod
    def create_bid_invitation(cls, project, freelancer, message="", expires_in_hours=72):
        """Create a bid invitation"""
        return cls.objects.create(
            invitation_type='bid_invitation',
            from_user=project.client,
            to_user=freelancer,
            content_type=ContentType.objects.get_for_model(project),
            object_id=project.id,
            title=f'Bid Invitation: {project.title}',
            message=message or f'You have been invited to submit a bid for the project "{project.title}".',
            expires_at=timezone.now() + timezone.timedelta(hours=expires_in_hours),
            terms={
                'project_id': project.id,
                'budget_range': {
                    'min': float(project.budget * 0.8),
                    'max': float(project.budget * 1.2)
                },
                'deadline': project.deadline.isoformat(),
            }
        )

    # Helper methods for querying related objects
    @property
    def project(self):
        """Get the related project if it exists"""
        if self.invitation_type in ['project_assignment', 'interview_request'] and isinstance(self.related_object, Bid):
            return self.related_object.project
        elif self.invitation_type == 'bid_invitation' and isinstance(self.related_object, Project):
            return self.related_object
        return None

    @property
    def bid(self):
        """Get the related bid if it exists"""
        if self.invitation_type in ['project_assignment', 'interview_request'] and isinstance(self.related_object, Bid):
            return self.related_object
        return None

    @property
    def task(self):
        """Get the related task if it exists"""
        if isinstance(self.related_object, Task):
            return self.related_object
        return None

class Referral(models.Model):
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='referrals_made'
    )
    referred_email = models.EmailField()
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='referrals_received', 
        null=True, blank=True
    )
    user_type = models.CharField(
        max_length=20, 
        choices=[('freelancer', 'Freelancer'), ('client', 'Client')]
    )
    code = models.CharField(max_length=20)  # Remove unique=True - same code can be used multiple times
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Only prevent duplicate referrals from same referrer to same email
        unique_together = ['referrer', 'referred_email']
        indexes = [
            models.Index(fields=['referrer', 'accepted']),
            models.Index(fields=['referred_email']),
            models.Index(fields=['code']),
        ]

    def clean(self):
        """Custom validation to prevent self-referrals"""
        if self.referrer and self.referred_user and self.referrer == self.referred_user:
            raise ValidationError("A user cannot refer themselves.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def mark_accepted(self, user):
        self.referred_user = user
        self.accepted = True
        self.accepted_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.referrer} referred {self.referred_email} ({self.user_type})"

class Reward(models.Model):
    REWARD_TYPES = [
        ('referral', 'Referral Bonus'),
        ('first_project', 'First Project Bonus'),
        ('milestone_completion', 'Milestone Completion'),
        ('profile_completion', 'Profile Completion'),
        ('streak_bonus', 'Streak Bonus'),
        ('loyalty', 'Loyalty Reward'),
        ('promotional', 'Promotional Reward'),
        ('achievement', 'Achievement Unlocked'),
    ]
    
    REWARD_STATUS = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('claimed', 'Claimed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rewards')
    reward_type = models.CharField(max_length=50, choices=REWARD_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    
    # Status and timing
    status = models.CharField(max_length=20, choices=REWARD_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    
    # Reference fields (for tracking what triggered the reward)
    reference_type = models.CharField(max_length=50, blank=True)  # 'referral', 'project', etc.
    reference_id = models.CharField(max_length=100, blank=True)   # ID of the triggering event
    
    # Metadata for flexible data storage
    metadata = models.JSONField(default=dict, blank=True)
    
    # Indexes for performance
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'reward_type']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.reward_type} - ₹{self.amount}"

    @property
    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    def claim(self):
        if self.status == 'pending' and not self.is_expired:
            self.status = 'claimed'
            self.claimed_at = timezone.now()
            self.save()
            return True
        return False

    def add_to_wallet(self):
        """Automatically add reward to user's wallet"""
        try:
            from financeapp.models.wallet import Wallet
            wallet, created = Wallet.objects.get_or_create(user=self.user)
            wallet.deposit(
                amount=self.amount,
                description=f"Referral reward: {self.reward_type}",
                reference_id=str(self.id)
            )
            self.status = 'claimed'
            self.claimed_at = timezone.now()
            self.save()
            return True
        except Exception as e:
            print(f"Error adding reward to wallet: {e}")
            return False

class ProjectMilestoneNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('client_feedback', 'Client Feedback'),
        ('freelancer_note', 'Freelancer Note'),
        ('internal_note', 'Internal Note'),
        ('milestone_feedback', 'Milestone Feedback'),
    ]
    milestone = models.ForeignKey('core.Milestone', on_delete=models.CASCADE, related_name='notes')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_private = models.BooleanField(default=False)
    is_aknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_note_type_display()} - {self.milestone.title} - {self.created_by.username}"


        