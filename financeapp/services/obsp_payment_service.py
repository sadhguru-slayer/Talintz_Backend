from django.db import transaction
from django.utils import timezone
from ..models import Transaction
from OBSP.models import OBSPResponse, OBSPAssignment, OBSPMilestone

class OBSPPaymentService:
    @staticmethod
    def create_obsp_payment(obsp_response, freelancer, amount, milestone=None):
        """Create payment for OBSP assignment"""
        with transaction.atomic():
            # Create transaction
            tx = Transaction.objects.create(
                from_user=obsp_response.client,
                to_user=freelancer,
                amount=amount,
                payment_type='obsp',
                status='pending',
                obsp_response=obsp_response,
                description=f"OBSP Payment: {obsp_response.template.title}",
                transaction_id=Transaction.generate_transaction_id(),
                metadata={
                    'obsp_response_id': str(obsp_response.id),
                    'template_title': obsp_response.template.title,
                    'selected_level': obsp_response.selected_level,
                }
            )
            
            # If milestone is provided, link it
            if milestone:
                tx.obsp_milestone = milestone
                tx.metadata['milestone_id'] = str(milestone.id)
                tx.metadata['milestone_title'] = milestone.title
                tx.save()
            
            return tx
    
    @staticmethod
    def process_milestone_payment(obsp_assignment, milestone):
        """Process payment for specific milestone completion"""
        with transaction.atomic():
            # Calculate payment amount based on milestone percentage
            total_amount = obsp_assignment.freelancer_payout
            milestone_amount = (total_amount * milestone.payout_percentage) / 100
            
            # Create transaction
            tx = Transaction.objects.create(
                from_user=obsp_assignment.obsp_response.client,
                to_user=obsp_assignment.assigned_freelancer,
                amount=milestone_amount,
                payment_type='obsp',
                status='completed',
                obsp_response=obsp_assignment.obsp_response,
                obsp_assignment=obsp_assignment,
                obsp_milestone=milestone,
                description=f"Milestone Payment: {milestone.title}",
                transaction_id=Transaction.generate_transaction_id(),
                completed_at=timezone.now(),
                metadata={
                    'milestone_id': str(milestone.id),
                    'milestone_title': milestone.title,
                    'payout_percentage': float(milestone.payout_percentage),
                    'total_project_amount': float(total_amount),
                }
            )
            
            # Update milestone status
            milestone.status = 'completed'
            milestone.save()
            
            # Update assignment progress
            obsp_assignment.progress_percentage += milestone.payout_percentage
            obsp_assignment.save()
            
            return tx
    
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