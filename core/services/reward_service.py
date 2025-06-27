from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import Reward
from django.core.cache import cache

class RewardService:
    @staticmethod
    def create_reward(user, reward_type, amount, reference_type=None, reference_id=None, metadata=None, expires_in_days=30):
        """Create a new reward for a user"""
        expires_at = timezone.now() + timedelta(days=expires_in_days) if expires_in_days else None
        
        return Reward.objects.create(
            user=user,
            reward_type=reward_type,
            amount=amount,
            status='pending',
            reference_type=reference_type,
            reference_id=reference_id,
            metadata=metadata or {},
            expires_at=expires_at
        )
    
    @staticmethod
    def get_user_rewards(user, status=None, reward_type=None, limit=50):
        """Get rewards for a user with optional filtering"""
        queryset = Reward.objects.filter(user=user)
        
        if status:
            queryset = queryset.filter(status=status)
        if reward_type:
            queryset = queryset.filter(reward_type=reward_type)
            
        return queryset[:limit]
    
    @staticmethod
    def get_user_reward_summary(user):
        """Get summary with caching"""
        cache_key = f"user_rewards_summary_{user.id}"
        cached_summary = cache.get(cache_key)
        
        if cached_summary is None:
            cached_summary = Reward.objects.filter(user=user).aggregate(
                total_earned=Sum('amount'),
                total_claimed=Sum('amount', filter=Q(status='claimed')),
                pending_amount=Sum('amount', filter=Q(status='pending')),
                active_rewards=Sum('amount', filter=Q(status='active'))
            )
            # Cache for 5 minutes
            cache.set(cache_key, cached_summary, 300)
        
        return cached_summary
    
    @staticmethod
    def claim_reward(reward_id, user):
        """Claim a specific reward"""
        try:
            reward = Reward.objects.get(id=reward_id, user=user, status='pending')
            if reward.claim():
                # Add to user's wallet/balance here
                return True, "Reward claimed successfully"
            return False, "Reward cannot be claimed"
        except Reward.DoesNotExist:
            return False, "Reward not found"
    
    @staticmethod
    def cleanup_expired_rewards():
        """Mark expired rewards as expired (run as periodic task)"""
        expired_count = Reward.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        ).update(status='expired')
        return expired_count

    @staticmethod
    def invalidate_user_cache(user_id):
        """Invalidate cache when rewards change"""
        cache.delete(f"user_rewards_summary_{user_id}")
