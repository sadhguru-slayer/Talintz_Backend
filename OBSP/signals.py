from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from OBSP.models import OBSPResponse
from freelancer.models import FreelancerOBSPEligibility
from core.models import Notification, User  # Assuming Notification is in core.models
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging
from django.utils.html import escape

logger = logging.getLogger(__name__)

@receiver(post_save, sender=OBSPResponse)
def send_obsp_response_notifications(sender, instance, created, **kwargs):
    """
    Signal handler to send notifications to eligible freelancers after an OBSP response is saved.
    This runs after the view has returned the response to the client.
    """
    if created or instance.status == 'submitted':  # Only trigger on new responses or when status is submitted
        try:
            with transaction.atomic():
                # Get eligible freelancers for this template and level
                selected_level = instance.selected_level
                if selected_level:
                    eligible_freelancers = FreelancerOBSPEligibility.objects.filter(
                        obsp_template=instance.template,
                        eligibility_data__has_key=selected_level,
                        **{f'eligibility_data__{selected_level}__is_eligible': True}
                    ).values('freelancer__id', 'freelancer__username')
                    
                    eligible_list = list(eligible_freelancers)
                    
                    if eligible_list:
                        for freelancer_data in eligible_list:
                            freelancer = User.objects.get(id=freelancer_data['freelancer__id'])
                            
                            obsp_title = escape(instance.template.title)
                            level_display = instance.get_selected_level_display()
                            obsp_url = f"/freelancer/obsp/obspresponse/{instance.id}"

                            notification_html = f"""
  <div style='padding: 20px; text-align: center;'>
    <h2 style='font-size: 1.5rem; color: #222; margin-bottom: 10px; font-weight: 700;'>
      New OBSP Opportunity
    </h2>
    <p style='font-size: 1.1rem; color: #444; margin-bottom: 16px;'>
      You are eligible for <b>{obsp_title}</b>
      <span style='display:inline-block; margin-left:6px; padding:2px 10px; border-radius:6px; background:#f5f5f5; color:#333; font-size:1rem; font-weight:500;'>
        {level_display}
      </span>
    </p>
    <a href='{obsp_url}'
       style='display:inline-block; padding:10px 28px; font-size:1rem; font-weight:600; color:#fff; background:#2d7ff9; border-radius:6px; text-decoration:none; box-shadow:0 1px 4px rgba(0,0,0,0.06); transition:background 0.2s;'>
      View Opportunity
    </a>
  </div>
"""

                            notification = Notification.objects.create(
                                user=freelancer,
                                title="New OBSP Opportunity",
                                notification_text=notification_html,
                                type='obsp_opportunity',
                                is_read=False,
                            )
                            
                            # Broadcast via WebSocket (using your existing consumers)
                            channel_layer = get_channel_layer()
                            group_name = f"freelancer_notification_{freelancer.id}"  # Matches your consumer group
                            
                            async_to_sync(channel_layer.group_send)(
                                group_name,
                                {
                                    'type': 'send_notification',
                                    'notification': {
                                        'id': notification.id,
                                        'title': notification.title,
                                        'notification_text': notification.notification_text,
                                        'created_at': notification.created_at.isoformat(),
                                        'related_model_id': instance.id,  # Link back to the OBSP response
                                        'type': notification.type,
                                    }
                                }
                            )
                            
                            logger.info(f"Notification sent to freelancer {freelancer.username} for OBSP response {instance.id}")
                    
                    logger.info(f"Notifications processed for OBSP response {instance.id}")
        except Exception as e:
            logger.error(f"Error in send_obsp_response_notifications: {str(e)}") 


        