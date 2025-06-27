from datetime import datetime, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from finance.models import SubscriptionPlan, UserSubscription
from finance.services.payment_processor import PaymentProcessor

class SubscriptionService:
    @staticmethod
    def get_duration_days(duration):
        """Convert duration to days"""
        duration_mapping = {
            'monthly': 30,
            'quarterly': 90,
            'half_yearly': 180,
            'yearly': 365
        }
        return duration_mapping.get(duration)

    @staticmethod
    @transaction.atomic
    def subscribe_user(user, plan_id, payment_method=None):
        """Subscribe a user to a plan"""
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            
            # Check for active subscription
            active_sub = UserSubscription.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if active_sub:
                raise ValidationError("User already has an active subscription")

            # Calculate end date
            duration_days = SubscriptionService.get_duration_days(plan.duration)
            end_date = datetime.now() + timedelta(days=duration_days)

            # Process payment
            payment_processor = PaymentProcessor()
            transaction_obj = payment_processor.process_payment(
                from_user=user,
                to_user=User.objects.get(username='platform'),
                amount=plan.price,
                payment_type='subscription',
                payment_method=payment_method
            )

            # Create subscription
            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                end_date=end_date,
                is_active=True
            )

            return subscription

        except Exception as e:
            raise ValidationError(f"Subscription failed: {str(e)}")

    @staticmethod
    def cancel_subscription(subscription_id):
        """Cancel a subscription"""
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            subscription.is_active = False
            subscription.save()
            return subscription
        except UserSubscription.DoesNotExist:
            raise ValidationError("Subscription not found")

    @staticmethod
    def process_renewals():
        """Process automatic renewals for subscriptions"""
        today = datetime.now()
        expiring_subs = UserSubscription.objects.filter(
            is_active=True,
            auto_renew=True,
            end_date__date=today.date()
        )

        for sub in expiring_subs:
            try:
                SubscriptionService.subscribe_user(
                    sub.user,
                    sub.plan.id,
                    payment_method='wallet'  # Default to wallet for renewals
                )
            except Exception as e:
                # Log renewal failure
                print(f"Renewal failed for subscription {sub.id}: {str(e)}")

    @staticmethod
    def get_subscription_status(user):
        """Get user's subscription status"""
        subscription = UserSubscription.objects.filter(
            user=user,
            is_active=True
        ).first()

        if not subscription:
            return {
                'has_subscription': False,
                'plan': None,
                'days_remaining': 0
            }

        days_remaining = (subscription.end_date - datetime.now()).days

        return {
            'has_subscription': True,
            'plan': subscription.plan,
            'days_remaining': days_remaining
        }