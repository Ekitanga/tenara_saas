from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='list'),
    path('create/', views.InvoiceCreateView.as_view(), name='create'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='delete'),
    path('generate-monthly/', views.GenerateMonthlyInvoicesView.as_view(), name='generate_monthly'),
]