from django.db import transaction
from django.conf import settings
from decimal import Decimal
from ..models import Wallet, WalletTransaction, Transaction, Commission, CommissionTier
from ..models.commission import SpecialCommissionRate
import uuid

class PaymentService:
    """Service to handle all payment operations with proper commission tracking"""
    
    @staticmethod
    def add_funds_to_wallet(user, amount, payment_method="razorpay", reference_id=None):
        """Add funds to user's wallet (no commission)"""
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=user)
            wallet_tx = wallet.deposit(
                amount=amount,
                description=f"Wallet deposit via {payment_method}",
                reference_id=reference_id
            )
            
            # Create main Transaction record for audit
            main_tx = Transaction.objects.create(
                from_user=user,  # User is paying to themselves (wallet)
                to_user=user,    # User is receiving into their wallet
                amount=amount,
                payment_type='deposit',
                status='completed',
                payment_method=payment_method,
                payment_processor='razorpay',
                description=f"Wallet deposit: {amount}",
                transaction_id=Transaction.generate_transaction_id(),
                metadata={
                    'wallet_transaction_id': str(wallet_tx.id),
                    'reference_id': reference_id,
                    'purpose': 'wallet_deposit'
                }
            )
            
            return {
                'wallet_transaction': wallet_tx,
                'main_transaction': main_tx,
                'new_balance': wallet.balance
            }
    
    @staticmethod
    def process_obsp_purchase(client, obsp_template, selected_level, total_price, wallet_payment=True):
        """Process OBSP purchase with 18% commission"""
        with transaction.atomic():
            if wallet_payment:
                # Deduct from client's wallet
                client_wallet = Wallet.objects.select_for_update().get(user=client)
                if client_wallet.balance < total_price:
                    raise ValueError(f"Insufficient wallet balance. Available: {client_wallet.balance}, Required: {total_price}")
                
                # Calculate commission (18% of total price)
                commission_amount = total_price * Decimal('0.18')
                freelancer_amount = total_price - commission_amount
                
                # Deduct from client wallet
                wallet_tx = client_wallet.process_obsp_purchase(
                    amount=total_price,
                    description=f"OBSP Purchase: {obsp_template.title} - {selected_level} level"
                )
                
                # Create main transaction record
                main_tx = Transaction.objects.create(
                    from_user=client,
                    to_user=obsp_template.created_by,  # OBSP creator
                    amount=total_price,
                    payment_type='subscription',  # Using subscription type for OBSP
                    status='completed',
                    payment_method='wallet',
                    description=f"OBSP Purchase: {obsp_template.title}",
                    transaction_id=Transaction.generate_transaction_id(),
                    platform_fee_amount=commission_amount,
                    net_amount=freelancer_amount,
                    metadata={
                        'obsp_template_id': str(obsp_template.id),
                        'selected_level': selected_level,
                        'wallet_transaction_id': str(wallet_tx.id),
                        'purpose': 'obsp_purchase'
                    }
                )
                
                # Create commission record
                commission = Commission.objects.create(
                    transaction=main_tx,
                    amount=commission_amount,
                    percentage=Decimal('18.00'),
                    tier=None,  # Fixed 18% for OBSP
                    is_discounted=False,
                    metadata={
                        'obsp_template_id': str(obsp_template.id),
                        'commission_type': 'obsp_purchase'
                    }
                )
                
                # Credit freelancer's wallet (if they have one)
                try:
                    freelancer_wallet = Wallet.objects.select_for_update().get(user=obsp_template.created_by)
                    freelancer_wallet.deposit(
                        amount=freelancer_amount,
                        description=f"OBSP earnings: {obsp_template.title}",
                        reference_id=WalletTransaction.generate_reference_id()
                    )
                except Wallet.DoesNotExist:
                    # Freelancer doesn't have wallet yet, create one
                    freelancer_wallet = Wallet.objects.create(user=obsp_template.created_by)
                    freelancer_wallet.deposit(
                        amount=freelancer_amount,
                        description=f"OBSP earnings: {obsp_template.title}",
                        reference_id=WalletTransaction.generate_reference_id()
                    )
                
                return {
                    'success': True,
                    'total_paid': total_price,
                    'commission_amount': commission_amount,
                    'freelancer_amount': freelancer_amount,
                    'wallet_transaction': wallet_tx,
                    'main_transaction': main_tx,
                    'commission': commission
                }
            else:
                # Direct payment (future implementation)
                raise NotImplementedError("Direct payment for OBSP not implemented yet")
    
    @staticmethod
    def process_project_payment(client, freelancer, amount, project=None, milestone=None, wallet_payment=True):
        """Process project/milestone payment with 15% commission"""
        with transaction.atomic():
            if wallet_payment:
                # Deduct from client's wallet
                client_wallet = Wallet.objects.select_for_update().get(user=client)
                if client_wallet.balance < amount:
                    raise ValueError(f"Insufficient wallet balance. Available: {client_wallet.balance}, Required: {amount}")
                
                # Calculate commission (15% of payment)
                commission_amount = amount * Decimal('0.15')
                freelancer_amount = amount - commission_amount
                
                # Deduct from client wallet
                wallet_tx = client_wallet.process_obsp_purchase(
                    amount=amount,
                    description=f"Project payment: {project.title if project else 'Milestone payment'}"
                )
                
                # Create main transaction record
                main_tx = Transaction.objects.create(
                    from_user=client,
                    to_user=freelancer,
                    amount=amount,
                    payment_type='milestone' if milestone else 'project',
                    status='completed',
                    payment_method='wallet',
                    project=project,
                    milestone=milestone,
                    description=f"Payment for {project.title if project else 'milestone'}",
                    transaction_id=Transaction.generate_transaction_id(),
                    platform_fee_amount=commission_amount,
                    net_amount=freelancer_amount,
                    metadata={
                        'wallet_transaction_id': str(wallet_tx.id),
                        'purpose': 'project_payment'
                    }
                )
                
                # Create commission record
                commission = Commission.objects.create(
                    transaction=main_tx,
                    amount=commission_amount,
                    percentage=Decimal('15.00'),
                    tier=None,  # Fixed 15% for project payments
                    is_discounted=False,
                    metadata={
                        'commission_type': 'project_payment'
                    }
                )
                
                # Credit freelancer's wallet
                freelancer_wallet = Wallet.objects.select_for_update().get(user=freelancer)
                freelancer_wallet.deposit(
                    amount=freelancer_amount,
                    description=f"Payment received: {project.title if project else 'milestone'}",
                    reference_id=WalletTransaction.generate_reference_id()
                )
                
                return {
                    'success': True,
                    'total_paid': amount,
                    'commission_amount': commission_amount,
                    'freelancer_amount': freelancer_amount,
                    'wallet_transaction': wallet_tx,
                    'main_transaction': main_tx,
                    'commission': commission
                }
            else:
                # Direct payment (future implementation)
                raise NotImplementedError("Direct payment for projects not implemented yet")
    
    @staticmethod
    def process_subscription_payment(user, subscription_plan, amount, payment_method="razorpay"):
        """Process subscription payment (no wallet, direct payment)"""
        with transaction.atomic():
            # Create main transaction record
            main_tx = Transaction.objects.create(
                from_user=user,
                to_user=user,  # Platform receives the payment
                amount=amount,
                payment_type='subscription',
                status='completed',
                payment_method=payment_method,
                payment_processor='razorpay',
                subscription=subscription_plan,
                description=f"Subscription: {subscription_plan.name}",
                transaction_id=Transaction.generate_transaction_id(),
                metadata={
                    'subscription_plan_id': str(subscription_plan.id),
                    'purpose': 'subscription_payment'
                }
            )
            
            return {
                'success': True,
                'main_transaction': main_tx
            }

    @staticmethod
    def process_obsp_milestone_payment(obsp_assignment, milestone):
        """Process payment for specific OBSP milestone completion"""
        with transaction.atomic():
            # Calculate payment amount based on milestone percentage
            total_amount = obsp_assignment.freelancer_payout
            milestone_amount = (total_amount * milestone.payout_percentage) / 100
            
            # Use existing payment service for the transaction
            result = PaymentService.process_project_payment(
                client=obsp_assignment.obsp_response.client,
                freelancer=obsp_assignment.assigned_freelancer,
                amount=milestone_amount,
                wallet_payment=True
            )
            
            # Update the transaction with OBSP details
            main_tx = result['main_transaction']
            main_tx.payment_type = 'obsp'
            main_tx.obsp_response = obsp_assignment.obsp_response
            main_tx.obsp_assignment = obsp_assignment
            main_tx.obsp_milestone = milestone
            main_tx.description = f"OBSP Milestone Payment: {milestone.title}"
            main_tx.metadata.update({
                'obsp_response_id': str(obsp_assignment.obsp_response.id),
                'obsp_assignment_id': str(obsp_assignment.id),
                'milestone_id': str(milestone.id),
                'milestone_title': milestone.title,
                'payout_percentage': float(milestone.payout_percentage),
                'total_project_amount': float(total_amount),
            })
            main_tx.save()
            
            # Update milestone status
            milestone.status = 'completed'
            milestone.save()
            
            # Update assignment progress
            obsp_assignment.progress_percentage += milestone.payout_percentage
            obsp_assignment.save()
            
            return result

    @staticmethod
    def get_obsp_payment_summary(obsp_response):
        """Get payment summary for OBSP response"""
        transactions = Transaction.objects.filter(
            obsp_response=obsp_response,
            status='completed'
        )
        
        total_paid = sum(tx.amount for tx in transactions)
        total_due = obsp_response.total_price
        
        return {
            'total_due': float(total_due),
            'total_paid': float(total_paid),
            'remaining': float(total_due - total_paid),
            'transactions_count': transactions.count(),
            'last_payment': transactions.first().completed_at if transactions.exists() else None,
        } 