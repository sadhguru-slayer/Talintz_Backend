from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import uuid

class SubscriptionPlanManager(models.Manager):
    def active_plans(self):
        return self.filter(is_active=True)
    
    def get_plan_by_duration(self, duration):
        return self.filter(duration=duration, is_active=True).first()

class SubscriptionPlan(models.Model):
    """
    Represents subscription plans available on the platform.
    Plans can have different durations, prices, and commission rates.
    """
    DURATION_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half Yearly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True)
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, db_index=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Commission percentage for platform"
    )
    features = models.JSONField(default=dict)
    max_projects = models.PositiveIntegerField(default=10)
    max_connections = models.PositiveIntegerField(default=50)
    transaction_fee_discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Discount percentage on platform transaction fees"
    )
    priority_support = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = SubscriptionPlanManager()
    
    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        ordering = ['price', 'duration']
        indexes = [
            models.Index(fields=['is_active', 'duration']),
            models.Index(fields=['price']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_duration_display()})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('subscription_plan_detail', args=[self.slug])
    
    def get_duration_in_days(self):
        """Convert subscription duration to days"""
        duration_mapping = {
            'monthly': 30,
            'quarterly': 90,
            'half_yearly': 180,
            'yearly': 365
        }
        return duration_mapping.get(self.duration, 0)
    
    @property
    def monthly_price(self):
        """Calculate equivalent monthly price for comparison"""
        if self.duration == 'monthly':
            return self.price
        
        months = {
            'quarterly': 3,
            'half_yearly': 6,
            'yearly': 12
        }.get(self.duration, 1)
        
        return self.price / months

class UserSubscriptionManager(models.Manager):
    def active_subscriptions(self):
        return self.filter(is_active=True, end_date__gt=timezone.now())
    
    def expired_subscriptions(self):
        return self.filter(is_active=True, end_date__lte=timezone.now())
    
    def upcoming_renewals(self, days=7):
        """Get subscriptions due for renewal in the next X days"""
        threshold = timezone.now() + timezone.timedelta(days=days)
        return self.filter(
            is_active=True, 
            auto_renew=True, 
            end_date__lte=threshold,
            end_date__gt=timezone.now()
        )

class UserSubscription(models.Model):
    """
    Represents a user's subscription to a plan.
    Tracks subscription period, renewal status, and payment history.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)
    is_trial = models.BooleanField(default=False)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    last_renewed_at = models.DateTimeField(null=True, blank=True)
    cancel_requested = models.BooleanField(default=False)
    cancellation_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserSubscriptionManager()
    
    class Meta:
        verbose_name = "User Subscription"
        verbose_name_plural = "User Subscriptions"
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['end_date', 'auto_renew']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s {self.plan.name} subscription"
    
    def save(self, *args, **kwargs):
        """Ensure subscription end date is set correctly"""
        if not self.end_date:
            days = self.plan.get_duration_in_days()
            self.end_date = self.start_date + timezone.timedelta(days=days)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if subscription has expired"""
        return timezone.now() > self.end_date
    
    @property
    def days_remaining(self):
        """Get days remaining in subscription"""
        if self.is_expired:
            return 0
        delta = self.end_date - timezone.now()
        return max(0, delta.days)
    
    def renew(self):
        """Renew the subscription for another period"""
        if not self.is_active or self.cancel_requested:
            return False
        
        old_end_date = self.end_date
        days = self.plan.get_duration_in_days()
        
        # If expired, start from now; otherwise extend from end date
        if self.is_expired:
            self.start_date = timezone.now()
            self.end_date = self.start_date + timezone.timedelta(days=days)
        else:
            self.end_date = self.end_date + timezone.timedelta(days=days)
        
        self.last_renewed_at = timezone.now()
        self.save()
        
        # Log renewal in transaction history (you would implement this)
        return True
    
    def cancel(self, reason=''):
        """Request cancellation at end of subscription period"""
        self.cancel_requested = True
        self.cancellation_reason = reason
        self.cancellation_date = timezone.now()
        self.auto_renew = False
        self.save()
        return True
    
    def cancel_immediately(self, reason=''):
        """Cancel subscription immediately"""
        self.cancel_requested = True
        self.cancellation_reason = reason
        self.cancellation_date = timezone.now()
        self.is_active = False
        self.auto_renew = False
        self.save()
        return True