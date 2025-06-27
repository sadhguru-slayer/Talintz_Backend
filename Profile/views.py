from rest_framework import viewsets
from .models import ClientProfile,FreelancerProfile
from .serializers import ClientProfileSerializer,FreelancerProfileSerializer
from rest_framework.permissions import IsAuthenticated
from core.models import Project
from core.serializers import ProjectResponseSerializer

class ClientProfileViewSet(viewsets.ModelViewSet):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow users to see their own profile
        return self.queryset.filter(user=self.request.user)
    
class FreelancerProfileViewSet(viewsets.ModelViewSet):
    queryset = FreelancerProfile.objects.all()
    serializer_class = FreelancerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow users to see their own profile
        return self.queryset.filter(user=self.request.user)
    

    
    # These overrides are unnecessary and might cause issues
    # The ModelViewSet already handles serialization properly
    # def list(self, request, *args, **kwargs):
    #     response = super().list(request, *args, **kwargs)
    #     response.data = [
    #         self.get_serializer(project).data for project in self.get_queryset()
    #     ]
    #     return response

    # def retrieve(self, request, *args, **kwargs):
    #     response = super().retrieve(request, *args, **kwargs)
    #     response.data = self.get_serializer(self.get_object()).data
    #     return response


