# Use this page for sending verification code to user email, and verify again here, if verified then update the user model is_email_verified to True

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
import random
import string

from .models import User

class SendEmailVerificationCode(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_email_verified:
            return Response({"detail": "Email already verified."}, status=status.HTTP_400_BAD_REQUEST)
        
        code = str(random.randint(100000, 999999))
        cache.set(f"email_verif_{user.id}", code, timeout=10*60)  # 10 minutes
        
        try:
            send_mail(
                "Your Email Verification Code",
                f"Your verification code is: {code}",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,  # This will raise an exception if email fails
            )
            return Response({"detail": "Verification code sent."}, status=status.HTTP_200_OK)
        except Exception as e:
            # If email fails, still return success but log the error
            print(f"Email sending failed: {e}")
            print(f"Verification code for {user.email}: {code}")
            return Response({"detail": "Verification code sent."}, status=status.HTTP_200_OK)

class VerifyEmailCode(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def generate_referral_code(self, user):
        """Generate a unique referral code for the user"""
        # Create a referral code using user ID and random string
        base_code = f"{user.id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
        
        # Ensure uniqueness
        while User.objects.filter(referral_code=base_code).exists():
            base_code = f"{user.id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
        
        return base_code

    def post(self, request):
        user = request.user
        code = request.data.get("code")
        if not code:
            return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        cached_code = cache.get(f"email_verif_{user.id}")
        print(code,cached_code)
        if not cached_code:
            return Response({"detail": "No code found or code expired."}, status=status.HTTP_400_BAD_REQUEST)
        
        if code != cached_code:
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Update email verification status
            user.is_email_verified = True
            
            # Generate and assign referral code if not already exists
            if not user.referral_code:
                user.referral_code = self.generate_referral_code(user)
            
            user.save()
            cache.delete(f"email_verif_{user.id}")
            
            return Response({
                "detail": "Email verified successfully.",
                "referral_code": user.referral_code
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"detail": "Failed to update user verification status."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)