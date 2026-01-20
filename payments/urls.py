from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.PaymentListView.as_view(), name='payment_list'),
    path('record/', views.RecordManualPaymentView.as_view(), name='record_manual'),
    path('mpesa/initiate/', views.InitiateMpesaPaymentView.as_view(), name='mpesa_initiate'),
    path('mpesa/callback/', views.MpesaCallbackView.as_view(), name='mpesa_callback'),
]