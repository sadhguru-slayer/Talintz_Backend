from django.db.models import Q
from django.utils import timezone
from ..models import Reward, Referral
from financeapp.models.transaction import Transaction
from financeapp.models.wallet import WalletTransaction

class AutomatedRewardService:
    
    @staticmethod
    def check_and_grant_referral_rewards(user):
        """
        Check if user has completed their first transaction and grant referral rewards
        This should be called whenever a user completes a transaction
        """
        try:
            # Get all referrals where this user is the referred user
            referrals = Referral.objects.filter(
                referred_user=user,
                accepted=True
            )
            
            if not referrals.exists():
                return False  # No referrals found
            
            # Check if this is the user's first completed transaction
            if not AutomatedRewardService._is_first_completed_transaction(user):
                return False  # Not the first transaction
            
            # Grant rewards to all referrers
            rewards_granted = []
            for referral in referrals:
                reward = AutomatedRewardService._create_referral_reward(referral, user)
                if reward:
                    rewards_granted.append(reward)
            
            return rewards_granted
            
        except Exception as e:
            print(f"Error in check_and_grant_referral_rewards: {e}")
            return False
    
    @staticmethod
    def _is_first_completed_transaction(user):
        """Check if this is the user's first completed transaction"""
        
        # For Clients: Check first completed transaction (project, milestone, subscription)
        if user.role == 'client':
            # Check Transaction model
            has_completed_transaction = Transaction.objects.filter(
                from_user=user,
                status='completed',
                payment_type__in=['project', 'milestone', 'subscription']
            ).exists()
            
            # Check WalletTransaction model
            has_completed_wallet_transaction = WalletTransaction.objects.filter(
                wallet__user=user,
                status='completed',
                transaction_type__in=['obsp_purchase', 'subscription', 'payment']
            ).exists()
            
            return has_completed_transaction or has_completed_wallet_transaction
        
        # For Freelancers: Check first received payment
        elif user.role == 'freelancer':
            # Check Transaction model for received payments
            has_received_payment = Transaction.objects.filter(
                to_user=user,
                status='completed',
                payment_type__in=['project', 'milestone', 'task']
            ).exists()
            
            return has_received_payment
        
        return False
    
    @staticmethod
    def _create_referral_reward(referral, referred_user):
        """Create and grant referral reward to the referrer"""
        try:
            # Check if reward already exists for this referral
            existing_reward = Reward.objects.filter(
                user=referral.referrer,
                reward_type='referral',
                reference_type='referral',
                reference_id=str(referral.id)
            ).first()
            
            if existing_reward:
                return existing_reward  # Reward already exists
            
            # Create new reward
            reward = Reward.objects.create(
                user=referral.referrer,
                reward_type='referral',
                amount=1000,  # ₹1000 reward
                status='pending',
                reference_type='referral',
                reference_id=str(referral.id),
                metadata={
                    'referred_user_id': referred_user.id,
                    'referred_email': referral.referred_email,
                    'user_type': referral.user_type,
                    'referral_scenario': f"{referral.referrer.role}->{referred_user.role}"
                }
            )
            
            # Automatically add to wallet
            reward.add_to_wallet()
            
            return reward
            
        except Exception as e:
            print(f"Error creating referral reward: {e}")
            return None
    
    @staticmethod
    def get_referral_scenario_summary():
        """Get summary of all referral scenarios"""
        scenarios = {
            'C->C': 0,  # Client refers Client
            'C->F': 0,  # Client refers Freelancer
            'F->C': 0,  # Freelancer refers Client
            'F->F': 0,  # Freelancer refers Freelancer
        }
        
        referrals = Referral.objects.filter(accepted=True)
        
        for referral in referrals:
            if referral.referred_user:
                scenario = f"{referral.referrer.role.upper()[0]}->{referral.referred_user.role.upper()[0]}"
                scenarios[scenario] += 1
        
        return scenarios
