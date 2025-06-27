# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Connection, Notification,User,Project,Task,Payment
from Profile.models import FreelancerProfile
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from .serializers import UserSerializer
from financeapp.models.transaction import Transaction
from financeapp.models.wallet import WalletTransaction
from .services.automated_reward_service import AutomatedRewardService

from django.urls import reverse

@receiver(post_save, sender=Connection)
def create_connection_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        # Create a notification for the user who sent the connection request
        message_from_user = _(f"You have sent a connection request to <strong><a href='/{instance.to_user.role}/profile/{instance.to_user.id}/view_profile'>{instance.to_user.username}</a></strong>.")
        message_from_user = str(message_from_user)
        fuser = instance.from_user
        
        Notification.objects.create(
            user=fuser,  # The user who sent the request
            type='Connections',
            related_model_id=instance.id,  # Link to the Connection model
            notification_text=message_from_user,
        )

        # Create a notification for the user who received the connection request
        message_to_user = _(f"You have received a connection request from <strong><a href='/{instance.from_user.role}/profile/{instance.from_user.id}/view_profile'>{instance.from_user.username}</a></strong>.")
        message_to_user = str(message_to_user)
        tuser = instance.to_user
        Notification.objects.create(
            user=tuser,  # The user who received the request
            type='Connections',
            related_model_id=instance.id,  # Link to the Connection model
            notification_text=message_to_user,
        )



from django.db.models.signals import m2m_changed
@receiver(m2m_changed, sender=Project.skills_required.through)
def create_project_notification(sender, instance, action, **kwargs):
    if action == "post_add":  # This triggers after skills are added
        # Fetch all skills required for the project
        project_skills = set(instance.skills_required.all())

        if project_skills:
            # Check if there are any tasks associated with this project
            tasks = Task.objects.filter(project=instance)

            # If there are tasks, send notifications based on task skills
            if tasks.exists():
                for task in tasks:
                    task_skills = set(task.skills_required_for_task.all())
                    send_skill_based_notifications(instance, task_skills, task)

            # If there are no tasks, send notifications based on project skills
            else:
                send_skill_based_notifications(instance, project_skills, None)
                
def send_skill_based_notifications(project_instance, required_skills, task_instance):
    # For each freelancer, check if their skills align with the project or task
    freelancers = User.objects.filter(role='freelancer')

    for freelancer in freelancers:
        # Get or create freelancer profile
        freelancer_profile, created = FreelancerProfile.objects.get_or_create(user=freelancer)

        # Get the freelancer's skills
        freelancer_skills = set(freelancer_profile.skills.all())

        # Calculate the skill match percentage
        skill_match = len(freelancer_skills.intersection(required_skills)) / len(required_skills) * 100 if required_skills else 0

        # Prepare notification text - Convert gettext_lazy to string immediately
        if skill_match > 0:
            # Create the notification text parts separately and convert to string
            if task_instance:
                title_part = f"A task titled <strong>{task_instance.title}</strong>"
            else:
                title_part = f"The project titled <strong>{project_instance.title}</strong>"

            notification_text = (
                f"Exciting opportunity! {title_part} "
                f"is looking for skills you possess! "
                f"Your skill alignment with this {'task' if task_instance else 'project'} is <strong>{skill_match:.2f}%</strong>."
            )

            # Create the notification with the plain string
            Notification.objects.create(
                user=freelancer,
                type='Projects' if not task_instance else 'Tasks',
                related_model_id=project_instance.id if not task_instance else task_instance.id,
                notification_text=notification_text
            )

@receiver(m2m_changed, sender=Task.skills_required_for_task.through)
def create_task_notification(sender, instance, action, **kwargs):
    if action == "post_add":
        # For each freelancer, check if their skills align with the task
        task_skills = set(instance.skills_required_for_task.all())
        
        # Send notifications based on task skills
        send_skill_based_notifications(instance.project, task_skills, instance)


@receiver(post_save, sender=Payment)
def create_payment_notification(sender, instance, created, **kwargs):
    """
    Signal to create notifications when a Payment is created or its status is updated.
    """
    if created:
        if instance.status == 'initiated':
            # Notification for payment creation
            notification_text_to_user = _(
                f"A new payment of {instance.amount} {instance.currency} has been initiated for {instance.payment_for}. "
                f"Payment method: {instance.get_payment_method_display()}. Status: {instance.get_status_display()}."
            )
            notification_title_to_user = _(
                f"Payment initiated: {instance.amount}{instance.currency} - {instance.status}"
            )

            notification_text_to_user = str(notification_text_to_user)
            notification_title_to_user = str(notification_title_to_user)

            to_user = instance.to_user

            Notification.objects.create(
                title=notification_title_to_user,
                user=to_user,  # Notify the recipient of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=notification_text_to_user
            )
        elif instance.status == 'pending':
            notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} for {instance.payment_for} is pending. "
                f"Please complete the payment process."
            )
            title = _(
                f"Pending payment: {instance.amount}{instance.currency}"
            )
            notification_text = str(notification_text)
            title = str(title)
            user = instance.from_user

            Notification.objects.create(
                title=title,
                user=user,  # Notify the sender of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=notification_text
            )
        elif instance.status == 'paid':
            notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} for {instance.payment_for} has been marked as paid. "
                f"Transaction ID: {instance.transaction_id}."
            )
            receiver_title = _(
                f"Payment received: {instance.amount}{instance.currency} from {instance.from_user.username}"
            )
            notification_text = str(notification_text)
            receiver_title = str(receiver_title)

            user = instance.to_user

            Notification.objects.create(
                title=receiver_title,
                user=user,  # Notify the recipient of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=notification_text
            )

            # Notify the sender of the payment
            sender_notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} to {instance.to_user.username} for {instance.payment_for} "
                f"has been successfully processed. Transaction ID: {instance.transaction_id}."
            )
            sender_title = _(
                f"Payment sent: {instance.amount}{instance.currency} to {instance.to_user.username}"
            )
            sender_notification_text = str(sender_notification_text)
            sender_title = str(sender_title)
            user = instance.from_user
            Notification.objects.create(
                title=sender_title,
                user=user,  # Notify the sender of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=sender_notification_text
            )

    else:
        # Notification for payment status update
        if instance.status == 'paid':
            notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} for {instance.payment_for} has been marked as paid. "
                f"Transaction ID: {instance.transaction_id}."
            )
            notification_title = _(
                f"Payment confirmed: {instance.amount}{instance.currency} - Paid"
            )
            notification_text = str(notification_text)
            notification_title = str(notification_title)

            user = instance.to_user

            Notification.objects.create(
                title=notification_title,
                user=user,  # Notify the recipient of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=notification_text
            )

            # Notify the sender of the payment
            sender_notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} to {instance.to_user.username} for {instance.payment_for} "
                f"has been successfully processed. Transaction ID: {instance.transaction_id}."
            )
            sender_notification_text = str(sender_notification_text)
            user = instance.from_user
            Notification.objects.create(
                title=notification_title,
                user=user,  # Notify the sender of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=sender_notification_text
            )
        elif instance.status == 'pending':
            notification_text = _(
                f"Your payment of {instance.amount} {instance.currency} for {instance.payment_for} is pending. "
                f"Please complete the payment process."
            )
            notification_title = _(
                f"Pending payment: {instance.amount}{instance.currency} - Pending"
            )
            notification_text = str(notification_text)
            notification_title = str(notification_title)
            user = instance.from_user

            Notification.objects.create(
                title=notification_title,
                user=user,  # Notify the sender of the payment
                type='Payments',
                related_model_id=instance.id,
                notification_text=notification_text
            )

@receiver(post_save, sender=Transaction)
def trigger_referral_reward_on_transaction(sender, instance, created, **kwargs):
    """
    Trigger referral reward when a transaction is completed
    """
    if instance.status == 'completed':
        # Check for referral rewards for the user who made the transaction
        AutomatedRewardService.check_and_grant_referral_rewards(instance.from_user)
        
        # Also check for the user who received the transaction (for freelancers)
        if instance.to_user:
            AutomatedRewardService.check_and_grant_referral_rewards(instance.to_user)

@receiver(post_save, sender=WalletTransaction)
def trigger_referral_reward_on_wallet_transaction(sender, instance, created, **kwargs):
    """
    Trigger referral reward when a wallet transaction is completed
    """
    if instance.status == 'completed':
        # Check for referral rewards for the wallet owner
        AutomatedRewardService.check_and_grant_referral_rewards(instance.wallet.user)

