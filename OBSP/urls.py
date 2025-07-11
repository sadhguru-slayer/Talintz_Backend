from django.urls import path
from . import views

urlpatterns = [
    path('preview/<int:obsp_id>/', views.obsp_preview, name='obsp_preview'),
    
    path('api/list/', views.obsp_list, name='obsp_list'),
    path('api/<int:obsp_id>/', views.obsp_detail, name='obsp_detail'),
    path('api/<int:obsp_id>/fields/', views.obsp_fields, name='obsp_fields'),
    path('api/<int:obsp_id>/fields/<str:level>/', views.obsp_fields, name='obsp_fields_level'),
    path('api/<int:obsp_id>/check-eligibility/<str:level>/', views.check_purchase_eligibility, name='check_purchase_eligibility'),
    path('api/<int:obsp_id>/submit/', views.submit_obsp_response, name='submit_obsp_response'),
    
    # New endpoint for fetching draft response data
    path('api/<int:obsp_id>/draft/<str:level>/', views.get_draft_response, name='get_draft_response'),

    # Client side obsps
     path('api/responses/', views.obsp_response_list, name='obsp_response_list'),
    path('api/responses/<int:response_id>/', views.obsp_response_detail, name='obsp_response_detail'),
   
]
