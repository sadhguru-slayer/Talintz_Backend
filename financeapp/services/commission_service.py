from decimal import Decimal
from django.db import transaction
from ..models import CommissionTier, Commission, Transaction
from django.core.exceptions import ValidationError

class CommissionService:
    @staticmethod
    def get_applicable_tier(amount):
        """Get the appropriate commission tier for a given amount"""
        try:
            tier = CommissionTier.objects.filter(
                min_amount__lte=amount,
                max_amount__gte=amount,
                is_active=True
            ).first()
            
            if not tier:
                raise ValidationError("No applicable commission tier found")
                
            return tier
        except Exception as e:
            raise ValidationError(f"Error determining commission tier: {str(e)}")

    @staticmethod
    @transaction.atomic
    def calculate_commission(transaction_obj):
        """Calculate commission for a transaction"""
        amount = transaction_obj.amount
        tier = CommissionService.get_applicable_tier(amount)
        
        # Calculate commission amount
        commission_amount = (Decimal(str(amount)) * Decimal(str(tier.percentage))) / Decimal('100.0')
        
        # Create commission record
        commission = Commission.objects.create(
            transaction=transaction_obj,
            amount=commission_amount,
            percentage=tier.percentage,
            tier=tier
        )
        
        return commission

    @staticmethod
    def get_commission_summary(start_date=None, end_date=None):
        """Get commission summary for a date range"""
        commissions = Commission.objects.all()
        
        if start_date:
            commissions = commissions.filter(created_at__gte=start_date)
        if end_date:
            commissions = commissions.filter(created_at__lte=end_date)
            
        total_commission = commissions.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.0')
        
        return {
            'total_commission': total_commission,
            'commission_count': commissions.count(),
            'commissions': commissions
        }

    @staticmethod
    def apply_special_discount(commission, discount_percentage):
        """Apply special discount to commission"""
        if not 0 <= discount_percentage <= 100:
            raise ValidationError("Invalid discount percentage")
            
        original_amount = commission.amount
        discount = (Decimal(str(original_amount)) * Decimal(str(discount_percentage))) / Decimal('100.0')
        commission.amount = original_amount - discount
        commission.save()
        
        return commission