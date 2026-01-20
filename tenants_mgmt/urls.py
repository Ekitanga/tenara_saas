from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    path('', views.TenantListView.as_view(), name='list'),
    path('create/', views.TenantCreateView.as_view(), name='create'),
    path('<int:pk>/', views.TenantDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.TenantUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.TenantDeleteView.as_view(), name='delete'),
    path('lease/create/', views.LeaseCreateView.as_view(), name='lease_create'),
    path('lease/<int:pk>/terminate/', views.LeaseTerminateView.as_view(), name='lease_terminate'),
    
    # Tenant Portal
    path('portal/', views.TenantPortalView.as_view(), name='portal'),
]