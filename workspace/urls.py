from django.urls import path
from .freelancer_workspace import freelancer_overview, freelancer_milestones, workspace_payments,WorkspaceRevisionsAPIView, WorkspaceNotificationsAPIView, mark_notification_read, submit_milestone_deliverables, request_milestone_revision, acknowledge_milestone_feedback, post_milestone_note
from workspace import client_workspace,views   # Import your new view

urlpatterns = [
    # Freelancer urls
    path('freelancer/overview/<int:workspace_id>/', freelancer_overview, name='freelancer_workspace_overview'),
    path('freelancer/milestones/<int:workspace_id>/', freelancer_milestones, name='freelancer_workspace_milestones'),
    path('freelancer/payments/<int:workspace_id>/', workspace_payments, name='freelancer_workspace_payments'),
    path('freelancer/revisions/<int:workspace_id>/', WorkspaceRevisionsAPIView.as_view(), name='freelancer_workspace_revisions'),
    path('freelancer/notifications/<int:workspace_id>/', views.WorkspaceNotificationsAPIView.as_view(), name='freelancer_workspace_notifications'),
    path('freelancer/notifications/<int:workspace_id>/<int:notification_id>/read/', views.mark_notification_read, name='freelancer_notification_mark_read'),
    path('freelancer/workspace/<int:workspace_id>/milestone/<str:milestone_type>/<int:milestone_id>/submit/', submit_milestone_deliverables, name='submit_milestone_deliverables'),
    path('freelancer/workspace/<int:workspace_id>/milestone/<str:milestone_type>/<int:milestone_id>/request-revision/', request_milestone_revision, name='request_milestone_revision'),
    path('freelancer/workspace/<int:workspace_id>/milestone/<str:milestone_type>/<int:milestone_id>/acknowledge-feedback/', acknowledge_milestone_feedback, name='acknowledge_milestone_feedback'),
    path('freelancer/workspace/<int:workspace_id>/milestone/<str:milestone_type>/<int:milestone_id>/post-note/', post_milestone_note, name='post_milestone_note'),

    # Client urls
    path('client/overview/<int:workspace_id>/', client_workspace.client_overview, name='client_workspace_overview'),
    path('client/milestones/<int:workspace_id>/', client_workspace.client_milestones, name='client_workspace_milestones'),
    path('client/payments/<int:workspace_id>/', client_workspace.workspace_payments, name='client_workspace_payments'),
    path('client/revisions/<int:workspace_id>/', client_workspace.WorkspaceRevisionsAPIView.as_view(), name='client_workspace_revisions'),
    path('client/notifications/<int:workspace_id>/', views.WorkspaceNotificationsAPIView.as_view(), name='client_workspace_notifications'),
    path('client/notifications/<int:workspace_id>/<int:notification_id>/read/', views.mark_notification_read, name='client_notification_mark_read'),

]
