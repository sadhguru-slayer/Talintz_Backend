from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal
import uuid
from django.utils import timezone

class WalletManager(models.Manager):
    def get_or_create_wallet(self, user):
        """Get a user's wallet or create one if it doesn't exist"""
        wallet, created = self.get_or_create(user=user)
        return wallet
    
    def get_active_wallets(self):
        """Get all active wallets"""
        return self.filter(is_active=True)
    
    def get_inactive_wallets(self):
        """Get all inactive wallets"""
        return self.filter(is_active=False)

class Wallet(models.Model):
    """
    User wallet for storing and managing funds on the platform.
    
    Each user has one wallet that can be used for:
    - Receiving payments
    - Paying for services
    - Withdrawing funds
    - Paying subscription fees
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    hold_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount temporarily held for pending transactions"
    )
    currency = models.CharField(max_length=3, default='INR')
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = WalletManager()
    
    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['balance']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s Wallet ({self.currency} {self.balance})"
    
    def deposit(self, amount, description="Deposit", reference_id=None):
        """Add funds to wallet"""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        self.balance += Decimal(str(amount))
        self.last_updated = timezone.now()
        self.save()
        
        # Create transaction record
        tx = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='credit',
            status='completed',
            description=description,
            reference_id=reference_id
        )
        return tx
    
    def withdraw(self, amount, description="Withdrawal"):
        """Remove funds from wallet"""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        self.balance -= amount
        self.save()
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='withdrawal',
            reference_id=WalletTransaction.generate_reference_id(),
            description=description,
            status='completed'
        )
        return True
    
    def hold(self, amount, description="Payment hold"):
        """Place a hold on funds for pending transactions"""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        self.balance -= amount
        self.hold_balance += amount
        self.save()
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='hold',
            reference_id=WalletTransaction.generate_reference_id(),
            description=description,
            status='pending'
        )
        return True
    
    def release_hold(self, amount, description="Hold released"):
        """Release held funds back to available balance"""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.hold_balance < amount:
            raise ValueError("Hold amount exceeds held balance")
        
        self.hold_balance -= amount
        self.balance += amount
        self.save()
        
        # Create transaction record
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='release',
            reference_id=WalletTransaction.generate_reference_id(),
            description=description,
            status='completed'
        )
        return True
    
    def transfer(self, to_wallet, amount, description="Wallet transfer"):
        """Transfer funds to another wallet"""
        from django.db import transaction
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        # Ensure atomic transaction
        with transaction.atomic():
            self.withdraw(amount, f"Transfer to {to_wallet.user.username}")
            to_wallet.deposit(amount, f"Transfer from {self.user.username}")
        
        return True
    
    @property
    def available_balance(self):
        """Return balance available for transactions"""
        return self.balance
    
    @property
    def total_balance(self):
        """Return total balance including held amounts"""
        return self.balance + self.hold_balance
    
    def get_transaction_history(self, limit=None):
        """Return wallet transaction history"""
        transactions = WalletTransaction.objects.filter(wallet=self).order_by('-timestamp')
        if limit:
            transactions = transactions[:limit]
        return transactions
    
    def process_obsp_purchase(self, amount, description="OBSP Purchase"):
        """Process OBSP purchase from wallet"""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        self.balance -= amount
        self.save()
        
        # Create transaction record with new type
        tx = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='obsp_purchase',  # Use new type
            reference_id=WalletTransaction.generate_reference_id(),
            description=description,
            status='completed'
        )
        return tx
    
    def create_hold(self, hold_type, amount, title, description, **kwargs):
        """Create a new hold on wallet funds"""
        from .hold import Hold
        
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        # Create the hold record
        hold = Hold.objects.create(
            wallet=self,
            hold_type=hold_type,
            amount=amount,
            title=title,
            description=description,
            **kwargs
        )
        
        # Update wallet balance
        self.balance -= amount
        self.hold_balance += amount
        self.save()
        
        # Create wallet transaction
        WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='hold',
            reference_id=WalletTransaction.generate_reference_id(),
            description=f"Hold created: {title}",
            status='pending',
            metadata={
                'hold_id': str(hold.id),
                'hold_type': hold_type
            }
        )
        
        return hold
    
    def get_active_holds(self):
        """Get all active holds for this wallet"""
        return self.holds.filter(status='active')
    
    def get_holds_by_type(self, hold_type):
        """Get holds of a specific type"""
        return self.holds.filter(hold_type=hold_type, status='active')
    
    def get_total_hold_amount(self):
        """Get total amount currently on hold"""
        return self.holds.filter(status='active').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

class WalletTransactionManager(models.Manager):
    def get_pending_transactions(self):
        """Get all pending transactions"""
        return self.filter(status='pending')
    
    def get_completed_transactions(self):
        """Get all completed transactions"""
        return self.filter(status='completed')
    
    def get_failed_transactions(self):
        """Get all failed transactions"""
        return self.filter(status='failed')

class WalletTransaction(models.Model):
    """
    Record of all wallet transactions including deposits, withdrawals,
    transfers, holds, and releases.
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('hold', 'Hold'),
        ('release', 'Release'),
        ('commission', 'Commission'),
        ('subscription', 'Subscription Fee'),
        ('obsp_purchase', 'OBSP Purchase'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)
    reference_id = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    related_transaction = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='related_transactions'
    )
    
    objects = WalletTransactionManager()
    
    class Meta:
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['wallet', 'transaction_type']),
            models.Index(fields=['status', 'timestamp']),
            models.Index(fields=['reference_id']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} ({self.reference_id})"
    
    @staticmethod
    def generate_reference_id():
        """Generate a unique reference ID for transaction tracking"""
        import time
        return f"WAL-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"
    
    def mark_completed(self):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.save()
    
    def mark_failed(self):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.save()
    
    def mark_cancelled(self):
        """Mark transaction as cancelled"""
        self.status = 'cancelled'
        self.save()
    
    @property
    def is_credit(self):
        """Check if transaction adds money to wallet"""
        return self.transaction_type in ['deposit', 'refund', 'release']
    
    @property
    def is_debit(self):
        """Check if transaction removes money from wallet"""
        return self.transaction_type in ['withdrawal', 'payment', 'hold', 'commission', 'subscription']