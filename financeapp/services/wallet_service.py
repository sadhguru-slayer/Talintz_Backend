from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Wallet, WalletTransaction
import uuid

class WalletService:
    @staticmethod
    def generate_reference_id():
        return f"WAL-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    @transaction.atomic
    def create_wallet(user):
        """Create a new wallet for a user"""
        if hasattr(user, 'wallet'):
            raise ValidationError("User already has a wallet")
        
        wallet = Wallet.objects.create(user=user)
        return wallet

    @staticmethod
    @transaction.atomic
    def process_deposit(wallet, amount, metadata=None):
        """Process a deposit to the wallet"""
        if amount <= 0:
            raise ValidationError("Amount must be positive")

        try:
            # Create transaction record
            transaction = WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type='deposit',
                reference_id=WalletService.generate_reference_id(),
                metadata=metadata or {}
            )

            # Update wallet balance
            wallet.deposit(amount)
            transaction.status = 'completed'
            transaction.save()

            return transaction
        except Exception as e:
            raise ValidationError(f"Deposit failed: {str(e)}")

    @staticmethod
    @transaction.atomic
    def process_withdrawal(wallet, amount, metadata=None):
        """Process a withdrawal from the wallet"""
        if amount <= 0:
            raise ValidationError("Amount must be positive")

        if wallet.balance < amount:
            raise ValidationError("Insufficient funds")

        try:
            # Create transaction record
            transaction = WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type='withdrawal',
                reference_id=WalletService.generate_reference_id(),
                metadata=metadata or {}
            )

            # Update wallet balance
            wallet.withdraw(amount)
            transaction.status = 'completed'
            transaction.save()

            return transaction
        except Exception as e:
            raise ValidationError(f"Withdrawal failed: {str(e)}")

    @staticmethod
    def get_balance(wallet):
        """Get current wallet balance"""
        return wallet.balance

    @staticmethod
    def get_transaction_history(wallet, transaction_type=None, start_date=None, end_date=None):
        """Get wallet transaction history with optional filters"""
        transactions = WalletTransaction.objects.filter(wallet=wallet)

        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        if start_date:
            transactions = transactions.filter(timestamp__gte=start_date)
        if end_date:
            transactions = transactions.filter(timestamp__lte=end_date)

        return transactions.order_by('-timestamp')