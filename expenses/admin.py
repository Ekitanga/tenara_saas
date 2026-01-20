from django.contrib import admin
from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['landlord', 'category', 'amount', 'expense_date', 'expense_property', 'vendor_name', 'created_at']
    list_filter = ['category', 'expense_date', 'landlord', 'created_at']
    search_fields = ['description', 'vendor_name', 'landlord__user__username', 'landlord__business_name', 'expense_property__name']
    raw_id_fields = ['landlord', 'expense_property']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'expense_date'
    
    fieldsets = (
        ('Expense Information', {
            'fields': ('landlord', 'expense_property', 'category', 'amount', 'expense_date')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Vendor Information', {
            'fields': ('vendor_name', 'vendor_contact'),
            'classes': ('collapse',)
        }),
        ('Supporting Documents', {
            'fields': ('receipt',),
            'classes': ('collapse',)
        }),
        ('Additional Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )