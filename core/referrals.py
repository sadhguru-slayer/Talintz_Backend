# backend/core/views/referral_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Referral, Reward
from .services.automated_reward_service import AutomatedRewardService

class ReferralStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's referral statistics"""
        user = request.user
        
        # Get referrals made by user
        referrals_made = Referral.objects.filter(referrer=user)
        successful_referrals = referrals_made.filter(accepted=True)
        
        # Get rewards earned from referrals
        referral_rewards = Reward.objects.filter(
            user=user,
            reward_type='referral'
        )
        
        # Calculate total earnings
        total_earned = sum([reward.amount for reward in referral_rewards])
        pending_earnings = sum([reward.amount for reward in referral_rewards.filter(status='pending')])
        
        # Get scenario breakdown
        scenarios = {
            'C->C': successful_referrals.filter(referrer__role='client', referred_user__role='client').count(),
            'C->F': successful_referrals.filter(referrer__role='client', referred_user__role='freelancer').count(),
            'F->C': successful_referrals.filter(referrer__role='freelancer', referred_user__role='client').count(),
            'F->F': successful_referrals.filter(referrer__role='freelancer', referred_user__role='freelancer').count(),
        }
        
        return Response({
            'total_referrals': referrals_made.count(),
            'successful_referrals': successful_referrals.count(),
            'total_earned': float(total_earned),
            'pending_earnings': float(pending_earnings),
            'referral_code': user.referral_code,
            'scenarios': scenarios
        })

class ReferralHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's referral history"""
        user = request.user
        
        referrals = Referral.objects.filter(referrer=user).select_related('referred_user')
        
        referral_history = []
        for referral in referrals:
            # Get reward for this referral
            reward = Reward.objects.filter(
                user=user,
                reward_type='referral',
                reference_id=str(referral.id)
            ).first()
            
            referral_history.append({
                'id': referral.id,
                'referred_email': referral.referred_email,
                'referred_user_name': referral.referred_user.username if referral.referred_user else None,
                'user_type': referral.user_type,
                'accepted': referral.accepted,
                'accepted_at': referral.accepted_at,
                'created_at': referral.created_at,
                'reward_amount': float(reward.amount) if reward else 0,
                'reward_status': reward.status if reward else None,
                'scenario': f"{referral.referrer.role.upper()[0]}->{referral.user_type.upper()[0]}"
            })
        
        return Response(referral_history)

class UserReferralDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get complete referral data for user"""
        user = request.user
        
        # Get user's referral code
        referral_code = user.referral_code
        
        # Get referrals made by user
        referrals = Referral.objects.filter(referrer=user).select_related('referred_user')
        
        # Get rewards earned from referrals
        referral_rewards = Reward.objects.filter(
            user=user,
            reward_type='referral'
        )
        
        # Calculate stats
        total_referrals = referrals.count()
        successful_referrals = referrals.filter(accepted=True).count()
        pending_referrals = referrals.filter(accepted=False).count()
        total_earned = sum([reward.amount for reward in referral_rewards])
        pending_earnings = sum([reward.amount for reward in referral_rewards.filter(status='pending')])
        
        # Build referral history
        referral_history = []
        for referral in referrals:
            # Get reward for this referral
            reward = referral_rewards.filter(reference_id=str(referral.id)).first()
            
            referral_history.append({
                'id': referral.id,
                'referred_email': referral.referred_email,
                'referred_user_name': referral.referred_user.username if referral.referred_user else None,
                'user_type': referral.user_type,
                'accepted': referral.accepted,
                'accepted_at': referral.accepted_at,
                'created_at': referral.created_at,
                'reward_amount': float(reward.amount) if reward else 0,
                'reward_status': reward.status if reward else None,
                'scenario': f"{referral.referrer.role.upper()[0]}->{referral.user_type.upper()[0]}"
            })
        
        # Build rewards list
        rewards_list = []
        for reward in referral_rewards:
            rewards_list.append({
                'id': str(reward.id),
                'type': reward.reward_type,
                'amount': float(reward.amount),
                'status': reward.status,
                'created_at': reward.created_at,
                'claimed_at': reward.claimed_at,
                'metadata': reward.metadata
            })
        
        # Console log the data (for debugging)
        print("=== USER REFERRAL DATA ===")
        print(f"User: {user.username} (ID: {user.id})")
        print(f"Referral Code: {referral_code}")
        print(f"Total Referrals: {total_referrals}")
        print(f"Successful Referrals: {successful_referrals}")
        print(f"Pending Referrals: {pending_referrals}")
        print(f"Total Earned: ₹{total_earned}")
        print(f"Pending Earnings: ₹{pending_earnings}")
        print(f"Referral History Count: {len(referral_history)}")
        print(f"Rewards Count: {len(rewards_list)}")
        print("=== END REFERRAL DATA ===")
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'referral_code': referral_code
            },
            'stats': {
                'total_referrals': total_referrals,
                'successful_referrals': successful_referrals,
                'pending_referrals': pending_referrals,
                'total_earned': float(total_earned),
                'pending_earnings': float(pending_earnings)
            },
            'referral_history': referral_history,
            'rewards': rewards_list
        })