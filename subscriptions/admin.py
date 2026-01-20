from django.contrib import admin
from .models import SubscriptionPlan, Subscription, SubscriptionPayment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_units', 'monthly_price', 'is_active', 'created_at']
    list_filter = ['is_active', 'name']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Plan Details', {
            'fields': ('name', 'max_units', 'monthly_price', 'is_active')
        }),
        ('Features', {
            'fields': ('features',),
            'description': 'Enter plan features as JSON'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['landlord', 'plan', 'status', 'start_date', 'end_date', 'auto_renew']
    list_filter = ['status', 'plan', 'auto_renew', 'start_date']
    search_fields = ['landlord__user__username', 'landlord__business_name']
    raw_id_fields = ['landlord']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('landlord', 'plan', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'auto_renew')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_subscriptions', 'suspend_subscriptions', 'expire_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} subscription(s) activated.')
    activate_subscriptions.short_description = 'Activate selected subscriptions'
    
    def suspend_subscriptions(self, request, queryset):
        updated = queryset.update(status='suspended')
        self.message_user(request, f'{updated} subscription(s) suspended.')
    suspend_subscriptions.short_description = 'Suspend selected subscriptions'
    
    def expire_subscriptions(self, request, queryset):
        updated = queryset.update(status='expired')
        self.message_user(request, f'{updated} subscription(s) expired.')
    expire_subscriptions.short_description = 'Expire selected subscriptions'


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'amount', 'transaction_id', 'payment_method', 'status', 'paid_at', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['transaction_id', 'mpesa_receipt_number', 'subscription__landlord__user__username']
    raw_id_fields = ['subscription']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('subscription', 'amount', 'payment_method')
        }),
        ('Transaction Information', {
            'fields': ('transaction_id', 'mpesa_receipt_number', 'status')
        }),
        ('Dates', {
            'fields': ('paid_at', 'created_at')
        }),
    )
    
    actions = ['confirm_payments']
    
    def confirm_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'confirmed':
                payment.confirm_payment()
                count += 1
        self.message_user(request, f'{count} payment(s) confirmed and subscriptions extended.')
    confirm_payments.short_description = 'Confirm selected payments'