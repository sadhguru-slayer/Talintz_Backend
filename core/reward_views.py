from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from ..services.reward_service import RewardService
from ..models import Reward

class UserRewardsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get user's rewards with filtering"""
        status_filter = request.query_params.get('status')
        reward_type = request.query_params.get('type')
        
        rewards = RewardService.get_user_rewards(
            user=request.user,
            status=status_filter,
            reward_type=reward_type
        )
        
        summary = RewardService.get_user_reward_summary(request.user)
        
        return Response({
            'rewards': [
                {
                    'id': str(reward.id),
                    'type': reward.reward_type,
                    'amount': float(reward.amount),
                    'status': reward.status,
                    'created_at': reward.created_at,
                    'expires_at': reward.expires_at,
                    'metadata': reward.metadata
                }
                for reward in rewards
            ],
            'summary': summary
        })

class ClaimRewardView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, reward_id):
        """Claim a specific reward"""
        success, message = RewardService.claim_reward(reward_id, request.user)
        
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
