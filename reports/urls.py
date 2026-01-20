from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportsDashboardView.as_view(), name='dashboard'),
    path('revenue/', views.RevenueReportView.as_view(), name='revenue'),
    path('arrears/', views.ArrearsReportView.as_view(), name='arrears'),
    path('occupancy/', views.OccupancyReportView.as_view(), name='occupancy'),
    path('expenses/', views.ExpensesReportView.as_view(), name='expenses'),
    path('profit/', views.ProfitReportView.as_view(), name='profit'),
]