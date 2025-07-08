# client/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .DashBoardViews import ClientWorkspaces,EventViewSet,RecentActivityView,PostedProjects,DashBoard_Overview,ActivityListView,SpecifiedActivityListView,SpendingDistributionByProject,CollaborationView,ProjectDetailsAPIView,BidsAPIView, InvitationViewSet
from core.views import *
from .DashBoardViews import SpendingDataView
from .profileViews import delete_document,UnAuthClientViews,ClientViews,update_profile,ClientReviewsandRatings,post_reply, update_terms_acceptance, FreelancerProfileDataView
# from .profileViews import ClientViews,ClientProfileUpdateView,update_profile
from .views import CHomePageView
from django.urls import re_path
from .views import ClientBidsOverviewView
from .consumers import NotificationConsumer
from .DashBoardViews import AcceptBidView, RejectBidView, BidUnderReviewView, NegotiateBidView, BidSubmittedView, BidInterviewRequestView
from .views import FreelancerListView

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]

router = DefaultRouter()

# # Register your views here
# router.register(r'homeEssentialStats', views.HomeEssentialStatsViewSet, basename='homeEssentialStats')
# router.register(r'products_summary', views.ProjectSummaryViewSet, basename='products_summary')
# router.register(r'upcomingDeadlines', views.UpcomingDeadlinesViewSet, basename='upcomingDeadlines')
# router.register(r'recentactivity', views.RecentActivityViewSet, basename='recentactivity')
# router.register(r'spendingOverview', views.SpendingOverviewViewSet, basename='spendingOverview')
router.register(r'events', EventViewSet, basename='events')

# Add the invitation router
invitation_router = DefaultRouter()
invitation_router.register(r'invitations', InvitationViewSet, basename='invitation')

urlpatterns = [
    path('', include(router.urls)),
    path('homepage/', CHomePageView.as_view(), name='homepage'),
    path('recent_activity/', RecentActivityView.as_view(), name='recent_activity'),
    path('specified_recent_activity/', SpecifiedActivityListView.as_view(), name='specified_recent_activity'),
    path('other_recent_activity/', ActivityListView.as_view(), name='other_recent_activity'),
    path('posted_projects/', PostedProjects.as_view(), name='posted_projects'),
    path('workspaces/', ClientWorkspaces.as_view(), name='client_workspaces'),

    path('dashboard_overview/', DashBoard_Overview.as_view(), name='dashboard_overview'),
    path('spending_data/', SpendingDataView.as_view(), name='spending_data'),
    path('spending_distribution_by_project/', SpendingDistributionByProject.as_view(), name='spending_distribution_by_project'),

    # Profile
    path('get_profile_data/', ClientViews.as_view(), name='get_profile_data'),
    path('get_unauth_profile_data/', UnAuthClientViews.as_view(), name='get_unauth_profile_data'),
    path('get_other_freelancer_profile_data/', FreelancerProfileDataView.as_view(), name='get_other_freelancer_profile_data'),
     path('update_profile/', update_profile, name='update_profile'),
     path('get_reviews/', ClientReviewsandRatings.as_view(), name='get_reviews'),
     path('post_reply/',post_reply , name='post_reply'),
     path('get_collaborations/',CollaborationView.as_view() , name='get_collaborations'),


    #  Connections
     path('get_project/<int:project_id>',ProjectDetailsAPIView.as_view() , name='get_project'),
     path('get_bids_on_project/<int:projectId>', BidsAPIView.as_view(), name='get_bids_on_project'),
    path('update_terms_acceptance', update_terms_acceptance, name='update_terms_acceptance'),

    # Bids
    path('get_bids_overview/', ClientBidsOverviewView.as_view(), name='get_bids_overview'),
    path('accept_bid/', AcceptBidView.as_view(), name='accept_bid'),
    path('reject_bid/', RejectBidView.as_view(), name='reject_bid'),
    path('mark_bid_under_review/', BidUnderReviewView.as_view(), name='mark_bid_under_review'),
    path('negotiate_bid/', NegotiateBidView.as_view(), name='negotiate_bid'),
    path('delete_document/<int:document_id>/', delete_document, name='delete_document'),
    path('mark_bid_submitted/', BidSubmittedView.as_view(), name='mark_bid_submitted'),
    path('request_interview/', BidInterviewRequestView.as_view(), name='request_interview'),

    # Add invitation URLs
    path('', include(invitation_router.urls)),
    path('freelancers/', FreelancerListView.as_view(), name='freelancer-list'),
]
