from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('plans/', views.PlansView.as_view(), name='plans'),
    path('manage/', views.ManageSubscriptionView.as_view(), name='manage'),
    path('expired/', views.SubscriptionExpiredView.as_view(), name='expired'),
    path('upgrade/', views.UpgradeSubscriptionView.as_view(), name='upgrade'),
]