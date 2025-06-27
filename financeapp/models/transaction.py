from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class TransactionQuerySet(models.QuerySet):
    def by_user(self, user):
        """Get all transactions related to a user"""
        return self.filter(
            models.Q(from_user=user) | models.Q(to_user=user)
        )
    
    def by_date_range(self, start_date, end_date):
        """Get transactions between two dates"""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def by_status(self, status):
        """Get transactions with specific status"""
        return self.filter(status=status)
    
    def successful(self):
        """Get all successful transactions"""
        return self.filter(status='completed')

    def by_milestone(self, milestone):
        """Get transactions related to a specific milestone"""
        return self.filter(milestone=milestone)

    def by_subscription(self, subscription):
        """Get transactions related to a subscription"""
        return self.filter(metadata__subscription_id=str(subscription.id))

    def by_tier(self, tier):
        """Get transactions related to a commission tier"""
        return self.filter(metadata__tier_id=str(tier.id))

    def with_proof(self):
        """Get transactions that have proof attached"""
        return self.filter(metadata__has_key='proof')

class TransactionManager(models.Manager):
    def get_queryset(self):
        return TransactionQuerySet(self.model, using=self._db)
    
    def by_user(self, user):
        return self.get_queryset().by_user(user)
    
    def calculate_revenue(self, start_date=None, end_date=None):
        """Calculate total platform revenue from transactions"""
        queryset = self.get_queryset().filter(
            status='completed',
            metadata__has_key='platform_fee'
        )
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        total = Decimal('0.00')
        for transaction in queryset:
            fee = transaction.metadata.get('platform_fee', 0)
            total += Decimal(str(fee))
        
        return total

    def create_milestone_payment(self, milestone, **kwargs):
        """Create a payment transaction for a milestone"""
        if not milestone.task and not milestone.project:
            raise ValueError("Milestone must be associated with a task or project")

        return self.create(
            from_user=milestone.project.client if milestone.project else milestone.task.project.client,
            to_user=milestone.task.assigned_to.first() if milestone.task else milestone.project.assigned_to.first(),
            amount=milestone.amount,
            payment_type='milestone',
            project=milestone.project,
            task=milestone.task,
            milestone=milestone,
            metadata={
                'milestone_id': str(milestone.id),
                'milestone_title': milestone.title,
                'milestone_type': milestone.milestone_type,
            },
            **kwargs
        )

class Transaction(models.Model):
    """
    Central transaction model for all money movements on the platform.
    
    Tracks payments between users, fees collected by the platform,
    refunds, and other financial operations.
    """
    PAYMENT_TYPES = [
        ('project', 'Project Payment'),
        ('milestone', 'Milestone Payment'),
        ('task', 'Task Payment'),
        ('withdrawal', 'Withdrawal'),
        ('refund', 'Refund'),
        ('subscription', 'Subscription Payment'),
        ('deposit', 'Wallet Deposit'),
        ('escrow', 'Escrow Payment'),
        ('commission', 'Commission'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    ]
    
    CURRENCY_CHOICES = [
        ('INR', 'Indian Rupee'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='sent_transactions'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='received_transactions'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    
    # Optional relations with other objects
    project = models.ForeignKey(
        'core.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    task = models.ForeignKey(
        'core.Task', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    milestone = models.ForeignKey(
        'core.Milestone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Transaction details
    description = models.CharField(max_length=255, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    platform_fee_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    net_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Related transactions
    parent_transaction = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='related_transactions'
    )
    
    # Payment method details
    payment_method = models.CharField(max_length=50, blank=True)
    payment_processor = models.CharField(max_length=50, blank=True)
    payment_processor_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional metadata
    metadata = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Add proof-related fields
    proof_of_payment = models.FileField(
        upload_to='transaction_proofs/',
        null=True,
        blank=True
    )
    proof_verified = models.BooleanField(default=False)
    proof_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_transactions'
    )
    proof_verified_at = models.DateTimeField(null=True, blank=True)

    # Add tier-related fields
    commission_tier = models.ForeignKey(
        'financeapp.CommissionTier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )

    # Add subscription-related fields
    subscription = models.ForeignKey(
        'financeapp.SubscriptionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )

    # Add ID verification fields
    id_verified = models.BooleanField(default=False)
    id_verification_method = models.CharField(max_length=50, blank=True)
    id_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='id_verified_transactions'
    )
    id_verified_at = models.DateTimeField(null=True, blank=True)
    
    objects = TransactionManager()
    
    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_user', 'to_user']),
            models.Index(fields=['status', 'payment_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['project']),
            models.Index(fields=['task']),
            models.Index(fields=['proof_verified']),
            models.Index(fields=['id_verified']),
            models.Index(fields=['commission_tier']),
            models.Index(fields=['subscription']),
        ]
    
    def __str__(self):
        return f"{self.payment_type} #{self.transaction_id}: {self.amount} {self.currency}"
    
    @staticmethod
    def generate_transaction_id():
        """Generate a unique transaction ID"""
        import time
        return f"TXN-{int(time.time())}-{uuid.uuid4().hex[:8].upper()}"
    
    def save(self, *args, **kwargs):
        # Set transaction ID if not already set
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        
        # Calculate net amount
        self.net_amount = self.amount - self.platform_fee_amount - self.tax_amount
        
        super().save(*args, **kwargs)
    
    def mark_completed(self):
        """Mark transaction as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, reason=None):
        """Mark transaction as failed"""
        self.status = 'failed'
        if reason:
            self.notes = f"{self.notes}\nFailure reason: {reason}".strip()
        self.save()
    
    def refund(self, reason=None):
        """Create a refund transaction"""
        if self.status != 'completed':
            raise ValueError("Only completed transactions can be refunded")
        
        from django.utils import timezone
        
        self.status = 'refunded'
        self.save()
        
        # Create refund transaction
        refund = Transaction.objects.create(
            from_user=self.to_user,
            to_user=self.from_user,
            amount=self.amount,
            payment_type='refund',
            currency=self.currency,
            project=self.project,
            task=self.task,
            milestone=self.milestone,
            description=f"Refund for transaction {self.transaction_id}",
            parent_transaction=self,
            payment_method=self.payment_method,
            metadata={
                'original_transaction': self.transaction_id,
                'refund_reason': reason or "Customer requested refund"
            },
            notes=reason or "Customer requested refund"
        )
        
        return refund
    
    @property
    def is_income(self):
        """Check if transaction is income for platform"""
        return self.payment_type in ['commission', 'subscription']
    
    @property
    def is_completed(self):
        """Check if transaction is completed"""
        return self.status == 'completed'
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('transaction_detail', args=[self.transaction_id])

    def verify_proof(self, verified_by):
        """Mark proof as verified"""
        from django.utils import timezone
        self.proof_verified = True
        self.proof_verified_by = verified_by
        self.proof_verified_at = timezone.now()
        self.save()

    def verify_id(self, method, verified_by):
        """Mark ID verification as complete"""
        from django.utils import timezone
        self.id_verified = True
        self.id_verification_method = method
        self.id_verified_by = verified_by
        self.id_verified_at = timezone.now()
        self.save()

    def get_related_objects(self):
        """Get all related objects (project, task, milestone, etc.)"""
        return {
            'project': self.project,
            'task': self.task,
            'milestone': self.milestone,
            'subscription': self.subscription,
            'commission_tier': self.commission_tier
        }

    def get_proof_url(self):
        """Get URL for proof of payment"""
        if self.proof_of_payment:
            return self.proof_of_payment.url
        return None

    def get_related_transactions(self):
        """Get all related transactions (refunds, parent, etc.)"""
        return self.related_transactions.all()