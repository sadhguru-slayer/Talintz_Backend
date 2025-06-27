from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from decimal import Decimal
import uuid

class CommissionTierManager(models.Manager):
    def get_for_amount(self, amount):
        """Get appropriate tier for a given amount"""
        return self.filter(
            min_amount__lte=amount,
            max_amount__gte=amount,
            is_active=True
        ).first()
    
    def active_tiers(self):
        """Get all active commission tiers"""
        return self.filter(is_active=True).order_by('min_amount')

class CommissionTier(models.Model):
    """
    Defines commission rate tiers based on transaction amount ranges.
    
    Higher transaction amounts typically have lower commission percentages.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    min_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    max_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    flat_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    # Different rates for different user types or payment methods
    freelancer_discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Discount percentage for freelancers"
    )
    client_discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Discount percentage for clients"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CommissionTierManager()
    
    class Meta:
        verbose_name = "Commission Tier"
        verbose_name_plural = "Commission Tiers"
        ordering = ['min_amount']
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_amount__gt=models.F('min_amount')),
                name='max_amount_greater_than_min'
            )
        ]
        indexes = [
            models.Index(fields=['min_amount', 'max_amount']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name}: {self.percentage}% ({self.min_amount} - {self.max_amount})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Ensure max_amount > min_amount
        if self.max_amount <= self.min_amount:
            raise ValidationError("Maximum amount must be greater than minimum amount")
        
        # Check for overlapping tiers
        overlapping = CommissionTier.objects.filter(
            is_active=True,
            min_amount__lte=self.max_amount,
            max_amount__gte=self.min_amount
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("Commission tier range overlaps with existing tier")
    
    def calculate_commission(self, amount, user_type=None):
        """Calculate commission for a given amount"""
        amount = Decimal(str(amount))
        
        # Apply percentage commission
        commission = (amount * self.percentage / 100) + self.flat_fee
        
        # Apply discounts based on user type
        if user_type == 'freelancer' and self.freelancer_discount > 0:
            discount = commission * (self.freelancer_discount / 100)
            commission -= discount
        elif user_type == 'client' and self.client_discount > 0:
            discount = commission * (self.client_discount / 100)
            commission -= discount
        
        return commission.quantize(Decimal('0.01'))

class SpecialCommissionRate(models.Model):
    """
    Custom commission rates for specific users or categories,
    overriding the standard tier-based rates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='special_commission_rates',
        null=True,
        blank=True
    )
    category = models.ForeignKey(
        'core.Category',
        on_delete=models.CASCADE,
        related_name='special_commission_rates',
        null=True,
        blank=True
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    flat_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    reason = models.TextField(blank=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Special Commission Rate"
        verbose_name_plural = "Special Commission Rates"
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(category__isnull=False),
                name='user_or_category_required'
            )
        ]
    
    def __str__(self):
        if self.user:
            return f"Special rate for {self.user.username}: {self.percentage}%"
        return f"Special rate for {self.category.name}: {self.percentage}%"
    
    def calculate_commission(self, amount):
        """Calculate commission using special rate"""
        amount = Decimal(str(amount))
        return (amount * self.percentage / 100) + self.flat_fee

class Commission(models.Model):
    """
    Records of actual commissions charged on transactions.
    
    Links to the transaction and stores the commission amount and percentage.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(
        'Transaction', 
        on_delete=models.CASCADE,
        related_name='commission'
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    tier = models.ForeignKey(
        CommissionTier, 
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    special_rate = models.ForeignKey(
        SpecialCommissionRate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_discounted = models.BooleanField(default=False)
    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    discount_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Commission"
        verbose_name_plural = "Commissions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tier']),
        ]
    
    def __str__(self):
        return f"Commission of {self.amount} ({self.percentage}%) for {self.transaction}"
    
    @property
    def discount_amount(self):
        """Calculate discount amount if applicable"""
        if self.is_discounted and self.original_amount:
            return self.original_amount - self.amount
        return Decimal('0.00')
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage if applicable"""
        if self.is_discounted and self.original_amount and self.original_amount > 0:
            return ((self.original_amount - self.amount) / self.original_amount * 100).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
