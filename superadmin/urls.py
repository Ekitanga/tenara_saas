from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),
    
    # Landlord Management
    path('landlords/', views.landlords_list, name='landlords'),
    path('landlords/<int:pk>/', views.landlord_detail, name='landlord_detail'),
    path('landlords/<int:pk>/toggle-status/', views.toggle_landlord_status, name='toggle_landlord_status'),
    
    # Subscription Management
    path('subscriptions/', views.subscriptions_list, name='subscriptions'),
    path('subscriptions/plans/', views.subscription_plans, name='subscription_plans'),
    
    # Reports
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
    
    # System
    path('settings/', views.system_settings, name='system_settings'),
    path('activity/', views.activity_log, name='activity_log'),
]
