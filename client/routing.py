from django.urls import re_path
from .consumers import NotificationConsumer,NotificationShowConsumer

websocket_urlpatterns = [
    re_path(r"ws/notification_count/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/notifications/$", NotificationShowConsumer.as_asgi()),
]
