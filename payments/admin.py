from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Payment admin"""
    list_display = [
        'id',
        'invoice', 
        'amount', 
        'payment_method',
        'mpesa_receipt_number',
        'status',
        'is_manual',
        'payment_date',
        'confirmed_at'
    ]
    list_filter = ['payment_method', 'status', 'is_manual', 'payment_date', 'created_at']
    search_fields = [
        'invoice__invoice_number',
        'mpesa_receipt_number', 
        'transaction_id',
        'phone_number',
        'invoice__lease__tenant__user__username'
    ]
    raw_id_fields = ['invoice', 'recorded_by']
    readonly_fields = ['payment_date', 'created_at', 'updated_at', 'landlord', 'tenant']
    date_hierarchy = 'payment_date'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('invoice', 'amount', 'payment_method', 'status')
        }),
        ('M-Pesa Details', {
            'fields': ('mpesa_receipt_number', 'phone_number', 'transaction_id'),
            'classes': ('collapse',)
        }),
        ('Manual Payment', {
            'fields': ('is_manual', 'recorded_by', 'payment_proof', 'notes'),
            'classes': ('collapse',)
        }),
        ('Related Information', {
            'fields': ('landlord', 'tenant')
        }),
        ('Timestamps', {
            'fields': ('payment_date', 'confirmed_at', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['confirm_payments', 'fail_payments']
    
    def confirm_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'confirmed':
                payment.confirm_payment()
                count += 1
        self.message_user(request, f'{count} payment(s) confirmed.')
    confirm_payments.short_description = 'Confirm selected payments'
    
    def fail_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'failed':
                payment.fail_payment()
                count += 1
        self.message_user(request, f'{count} payment(s) marked as failed.')
    fail_payments.short_description = 'Mark selected payments as failed'