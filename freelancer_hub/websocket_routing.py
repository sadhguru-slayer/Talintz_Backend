from django.urls import re_path
from client.consumers import NotificationConsumer
from freelancer.consumers import FreelancerNotificationConsumer, FreelancerNotificationShowConsumer

websocket_urlpatterns = [
    # Client routes
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
    
    # Freelancer routes
    re_path(r"ws/freelancer/notification_count/$", FreelancerNotificationConsumer.as_asgi()),
    re_path(r"ws/freelancer/notifications/$", FreelancerNotificationShowConsumer.as_asgi()),
]
