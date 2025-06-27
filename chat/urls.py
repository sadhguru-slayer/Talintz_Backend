from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, MessageViewSet,start_conversation
from django.urls import path

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = router.urls

urlpatterns += [
    path('start_conversation/',start_conversation , name='start_conversation'),
]