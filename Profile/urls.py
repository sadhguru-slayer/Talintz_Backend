from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientProfileViewSet,FreelancerProfileViewSet

router = DefaultRouter()
router.register(r'client-profile', ClientProfileViewSet, basename='client-profile')
router.register(r'freelancer-profile', FreelancerProfileViewSet, basename='freelancer-profile')

urlpatterns = [
    path('api/', include(router.urls)),
]
