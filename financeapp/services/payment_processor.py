from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Transaction, PaymentMethod, PaymentGatewayLog
import uuid

class PaymentProcessor:
    @staticmethod
    def generate_transaction_id():
        return f"TXN-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    @transaction.atomic
    def process_payment(from_user, to_user, amount, payment_type, payment_method=None, **kwargs):
        """Process a payment between users"""
        try:
            # Create transaction record
            transaction_obj = Transaction.objects.create(
                from_user=from_user,
                to_user=to_user,
                amount=amount,
                payment_type=payment_type,
                transaction_id=PaymentProcessor.generate_transaction_id(),
                status='processing',
                **kwargs
            )

            # Get commission calculation
            commission_service = CommissionService()
            commission = commission_service.calculate_commission(transaction_obj)
            final_amount = amount - commission.amount

            # Process based on payment method
            if payment_method == 'wallet':
                PaymentProcessor._process_wallet_payment(
                    transaction_obj, 
                    from_user, 
                    to_user, 
                    amount, 
                    commission.amount
                )
            else:
                PaymentProcessor._process_gateway_payment(
                    transaction_obj,
                    payment_method,
                    amount
                )

            return transaction_obj

        except Exception as e:
            if transaction_obj:
                transaction_obj.status = 'failed'
                transaction_obj.save()
            raise ValidationError(f"Payment processing failed: {str(e)}")

    @staticmethod
    def _process_wallet_payment(transaction_obj, from_user, to_user, amount, commission_amount):
        """Handle wallet-to-wallet transfers"""
        wallet_service = WalletService()
        
        # Deduct from sender
        wallet_service.process_withdrawal(
            from_user.wallet,
            amount,
            {'transaction_id': transaction_obj.transaction_id}
        )
        
        # Credit to receiver (minus commission)
        wallet_service.process_deposit(
            to_user.wallet,
            amount - commission_amount,
            {'transaction_id': transaction_obj.transaction_id}
        )
        
        # Credit commission to platform wallet
        platform_wallet = Wallet.objects.get(user__username='platform')
        wallet_service.process_deposit(
            platform_wallet,
            commission_amount,
            {'transaction_id': transaction_obj.transaction_id}
        )
        
        transaction_obj.status = 'completed'
        transaction_obj.save()

    @staticmethod
    def _process_gateway_payment(transaction_obj, payment_method, amount):
        """Handle payments through payment gateway"""
        # Implement payment gateway integration here
        # Example: Razorpay, Stripe, etc.
        pass

    @staticmethod
    def process_refund(transaction_obj, reason):
        """Process refund for a transaction"""
        if transaction_obj.status != 'completed':
            raise ValidationError("Can only refund completed transactions")

        with transaction.atomic():
            # Create refund transaction
            refund_transaction = Transaction.objects.create(
                from_user=transaction_obj.to_user,
                to_user=transaction_obj.from_user,
                amount=transaction_obj.amount,
                payment_type='refund',
                transaction_id=PaymentProcessor.generate_transaction_id(),
                metadata={'original_transaction': transaction_obj.transaction_id, 'reason': reason}
            )

            # Process refund based on original payment method
            if transaction_obj.payment_method == 'wallet':
                PaymentProcessor._process_wallet_payment(
                    refund_transaction,
                    transaction_obj.to_user,
                    transaction_obj.from_user,
                    transaction_obj.amount,
                    0  # No commission on refunds
                )

            transaction_obj.status = 'refunded'
            transaction_obj.save()

            return refund_transaction