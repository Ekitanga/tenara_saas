from django.contrib import admin
from .models import Lease


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    """Lease admin"""
    list_display = [
        'unit', 
        'tenant', 
        'start_date', 
        'end_date',
        'status',
        'rent_amount',
        'deposit_paid',
        'created_at'
    ]
    list_filter = ['status', 'deposit_paid', 'start_date', 'created_at']
    search_fields = [
        'unit__unit_number', 
        'unit__property__name',
        'tenant__user__username',
        'tenant__user__first_name',
        'tenant__user__last_name'
    ]
    raw_id_fields = ['unit', 'tenant']
    readonly_fields = ['created_at', 'updated_at', 'landlord', 'is_active']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Lease Information', {
            'fields': ('unit', 'tenant', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'move_in_date', 'move_out_date')
        }),
        ('Financial', {
            'fields': ('rent_amount', 'deposit_amount', 'deposit_paid', 'deposit_paid_date')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Status', {
            'fields': ('landlord', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_leases', 'terminate_leases']
    
    def activate_leases(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} lease(s) activated.')
    activate_leases.short_description = 'Activate selected leases'
    
    def terminate_leases(self, request, queryset):
        from django.utils import timezone
        count = 0
        for lease in queryset:
            lease.terminate_lease(timezone.now().date())
            count += 1
        self.message_user(request, f'{count} lease(s) terminated.')
    terminate_leases.short_description = 'Terminate selected leases'