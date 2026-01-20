from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Properties
    path('properties/', views.PropertyListView.as_view(), name='property_list'),
    path('properties/create/', views.PropertyCreateView.as_view(), name='property_create'),
    path('properties/<int:pk>/', views.PropertyDetailView.as_view(), name='property_detail'),
    path('properties/<int:pk>/edit/', views.PropertyUpdateView.as_view(), name='property_update'),
    path('properties/<int:pk>/delete/', views.PropertyDeleteView.as_view(), name='property_delete'),
    
    # Units
    path('units/create/', views.UnitCreateView.as_view(), name='unit_create'),
    path('units/<int:pk>/edit/', views.UnitUpdateView.as_view(), name='unit_update'),
    path('units/<int:pk>/delete/', views.UnitDeleteView.as_view(), name='unit_delete'),
]