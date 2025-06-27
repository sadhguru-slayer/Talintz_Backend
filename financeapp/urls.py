from django.urls import path
from . import views

urlpatterns = [

    path('wallet/balance/', views.get_wallet_balance, name='get_wallet_balance'),

    path('wallet/create-order/', views.create_wallet_order, name='wallet_create_order'),

    path('wallet/verify-payment/', views.verify_wallet_payment, name='wallet_verify_payment'),

    path('wallet/details/', views.get_comprehensive_wallet_details, name='wallet_details'),

    path('wallet/freelancer-details/', views.freelancer_wallet_details, name='freelancer_wallet_details'),
]
