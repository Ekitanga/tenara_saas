from django.contrib import admin
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Invoice admin"""
    list_display = [
        'invoice_number', 
        'lease', 
        'billing_month', 
        'due_date',
        'total_amount', 
        'amount_paid', 
        'balance',
        'status',
        'created_at'
    ]
    list_filter = ['status', 'billing_month', 'due_date', 'created_at']
    search_fields = [
        'invoice_number', 
        'lease__tenant__user__username',
        'lease__tenant__user__first_name',
        'lease__tenant__user__last_name',
        'lease__unit__unit_number'
    ]
    raw_id_fields = ['lease']
    readonly_fields = [
        'invoice_number', 
        'total_amount', 
        'balance',
        'status',
        'landlord',
        'tenant',
        'unit',
        'property',
        'created_at', 
        'updated_at'
    ]
    date_hierarchy = 'billing_month'
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'lease', 'status')
        }),
        ('Billing Period', {
            'fields': ('billing_month', 'due_date')
        }),
        ('Charges Breakdown', {
            'fields': ('rent_amount', 'water_amount', 'garbage_amount', 'other_charges')
        }),
        ('Water Meter (if applicable)', {
            'fields': ('water_meter_reading', 'previous_meter_reading'),
            'classes': ('collapse',)
        }),
        ('Totals', {
            'fields': ('total_amount', 'amount_paid', 'balance')
        }),
        ('Related Information', {
            'fields': ('landlord', 'tenant', 'unit', 'property')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['mark_as_paid', 'mark_as_overdue']
    
    def mark_as_paid(self, request, queryset):
        count = 0
        for invoice in queryset:
            invoice.amount_paid = invoice.total_amount
            invoice.save()
            count += 1
        self.message_user(request, f'{count} invoice(s) marked as paid.')
    mark_as_paid.short_description = 'Mark selected invoices as paid'
    
    def mark_as_overdue(self, request, queryset):
        updated = queryset.update(status='overdue')
        self.message_user(request, f'{updated} invoice(s) marked as overdue.')
    mark_as_overdue.short_description = 'Mark selected invoices as overdue'