from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    
    path('send/', views.send_money, name='send_money'),
    path('send_link/', views.send_money_link, name='send_money_link'),
    
    path('claim/<str:claim_id>/', views.claim_money, name='claim_money'),
    
    path('exchange-gift-card/', views.exchange_for_gift_card, name='exchange_gift_card'),
    
    path('swap/', views.path_payment, name='path_payment'),
    path('swap/<str:claim_id>/', views.path_payment, name='path_payment_temp'),
    path('gift-card/', views.buy_gift_card, name='buy_gift_card'),
    path('gift-card/<str:claim_id>/', views.buy_gift_card, name='buy_gift_card_temp'),
    
    # Temporary account dashboard and actions
    path('claim/<str:claim_id>/dashboard/', views.claim_money, name='temp_dashboard'),
    path('claim/<str:claim_id>/merge/', views.merge_account, name='merge_account'),
    
    
    path('api/check-balance/', views.check_balance, name='check_balance'),
    path('api/validate-address/', views.validate_address, name='validate_address'),
    path('faucet/', views.faucet, name='faucet'),

]