from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid
from django.utils import timezone
from django.core.validators import MinValueValidator

class Hold(models.Model):
    """
    Track different types of holds on wallet funds
    """
    HOLD_TYPE_CHOICES = [
        ('project_milestone', 'Project Milestone'),
        ('obsp_purchase', 'OBSP Purchase'),
        ('auto_pay_commitment', 'Auto-Pay Commitment'),
        ('subscription', 'Subscription Hold'),
        ('dispute', 'Dispute Hold'),
        ('manual', 'Manual Hold'),
        ('obsp_stake', 'OBSP Stake'),
        # Add more as needed
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('released', 'Released'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        'financeapp.Wallet',
        on_delete=models.CASCADE,
        related_name='holds'
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True)
    hold_type = models.CharField(max_length=32, choices=HOLD_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Reference to the object that created this hold
    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wallet_holds'
    )
    milestone = models.ForeignKey(
        'core.Milestone',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wallet_holds'
    )
    obsp_response = models.ForeignKey(
        'OBSP.OBSPResponse',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wallet_holds'
    )
    
    # Hold details
    title = models.CharField(max_length=255)
    description = models.TextField()
    reference_id = models.CharField(max_length=100, unique=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Additional metadata
    metadata = models.JSONField(default=dict)
    
    # New fields
    reason = models.TextField(blank=True, null=True)
    released = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Wallet Hold"
        verbose_name_plural = "Wallet Holds"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['hold_type', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Hold({self.hold_type}) - {self.amount} for {self.user.username}"
    
    @staticmethod
    def generate_reference_id():
        """Generate a unique reference ID for hold tracking"""
        import time
        return f"HOLD-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"
    
    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = self.generate_reference_id()
        super().save(*args, **kwargs)
    
    def release(self, reason="Manual release"):
        """Release this hold"""
        if self.status != 'active':
            raise ValueError(f"Cannot release hold with status: {self.status}")
        
        self.status = 'released'
        self.released_at = timezone.now()
        self.metadata['release_reason'] = reason
        self.save()
        
        # Update wallet hold balance
        self.wallet.hold_balance -= self.amount
        self.wallet.save()
        
        # Create wallet transaction for the release
        from .wallet import WalletTransaction
        WalletTransaction.objects.create(
            wallet=self.wallet,
            amount=self.amount,
            transaction_type='release',
            reference_id=WalletTransaction.generate_reference_id(),
            description=f"Hold released: {self.title}",
            status='completed',
            metadata={
                'hold_id': str(self.id),
                'hold_type': self.hold_type,
                'release_reason': reason
            }
        )
    
    def cancel(self, reason="Hold cancelled"):
        """Cancel this hold"""
        if self.status != 'active':
            raise ValueError(f"Cannot cancel hold with status: {self.status}")
        
        self.status = 'cancelled'
        self.released_at = timezone.now()
        self.metadata['cancel_reason'] = reason
        self.save()
        
        # Update wallet hold balance
        self.wallet.hold_balance -= self.amount
        self.wallet.save()
    
    @property
    def is_expired(self):
        """Check if hold has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def days_remaining(self):
        """Get days remaining until expiration"""
        if not self.expires_at:
            return None
        remaining = self.expires_at - timezone.now()
        return max(0, remaining.days)
