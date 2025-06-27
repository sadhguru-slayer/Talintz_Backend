from django.urls import re_path
from .consumers import FreelancerNotificationConsumer, FreelancerNotificationShowConsumer
 
websocket_urlpatterns = [
    re_path(r"ws/freelancer/notification_count/$", FreelancerNotificationConsumer.as_asgi()),
    re_path(r"ws/freelancer/notifications/$", FreelancerNotificationShowConsumer.as_asgi()),
] 