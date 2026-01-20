from django.urls import path
from . import views

app_name = 'demo'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('demo/', views.DemoView.as_view(), name='view'),
]