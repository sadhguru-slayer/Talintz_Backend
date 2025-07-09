from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FreelancerViewSet, ProjectManagementViewSet, BidViewSet, BidItemViewSet,
    InvitationResponseViewSet
)
from .obspviews  import *
from .profileViews import (
    FreelancerProfileDataView,
    PersonalInfoUpdateView,
    ProfessionalInfoUpdateView,
    PortfolioUpdateView,
    CertificationsUpdateView,
    BankingUpdateView,
    ProfilePictureUpdateView,
)
from .projectRecommendation import ProjectRecommendationView, BrowseProjectsView
from .dashboard_views import freelancer_workspaces,assigned_projects, ProjectDetailsAPIView

router = DefaultRouter()
router.register(r'homepage', FreelancerViewSet, basename='homepage')
router.register(r'projects', ProjectManagementViewSet, basename='project')
router.register(r'bids', BidViewSet, basename='bid')
router.register(r'bid-items', BidItemViewSet, basename='bid-item')
router.register(r'invitations', InvitationResponseViewSet, basename='invitation')

urlpatterns = [
    path('', include(router.urls)),
   # Add these to your existing URLs
path('obsps/', obsp_list_with_eligibility, name='obsp_list_with_eligibility'),
path('get_profile_data/', FreelancerProfileDataView.as_view(), name='freelancer_profile_data'),
path('obsps/<int:obsp_id>/', obsp_detail_with_eligibility, name='obsp_detail_with_eligibility'),
    # OBSP endpoints
path('obsp/apply/', apply_for_obsp, name='apply_for_obsp'),
path('obsp/applications/', get_my_applications, name='get_my_applications'),
path('project-recommendations/', ProjectRecommendationView.as_view(), name='project_recommendations'),
path('browse-projects/', BrowseProjectsView.as_view(), name='browse_projects'),
path('update_profile/personal/', PersonalInfoUpdateView.as_view(), name='update_personal_info'),
path('update_profile/professional/', ProfessionalInfoUpdateView.as_view(), name='update_professional_info'),
path('update_profile/portfolio/', PortfolioUpdateView.as_view(), name='update_portfolio'),
path('update_profile/certifications/', CertificationsUpdateView.as_view(), name='update_certifications'),
path('update_profile/banking/', BankingUpdateView.as_view(), name='update_banking'),
path('update_profile_picture/', ProfilePictureUpdateView.as_view(), name='update_profile_picture'),

# Projects and workspaces
    path('assigned-projects/', assigned_projects, name='assigned_projects'),
    path('workspaces/', freelancer_workspaces, name='freelancer_workspaces'),
    path('project-details/<int:project_id>/', ProjectDetailsAPIView.as_view(), name='freelancer_project_details'),

]

