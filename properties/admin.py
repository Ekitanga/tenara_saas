from django.contrib import admin
from .models import Property, Unit


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['name', 'landlord', 'location', 'created_at']
    list_filter = ['landlord', 'created_at']
    search_fields = ['name', 'location', 'landlord__user__username', 'landlord__business_name']
    raw_id_fields = ['landlord']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Property Information', {
            'fields': ('landlord', 'name', 'location', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['unit_number', 'unit_property', 'unit_type', 'monthly_rent', 'water_billing_type', 'created_at']
    list_filter = ['unit_type', 'water_billing_type', 'created_at']
    search_fields = ['unit_number', 'unit_property__name', 'unit_property__landlord__user__username']
    raw_id_fields = ['unit_property']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Unit Information', {
            'fields': ('unit_property', 'unit_number', 'unit_type')
        }),
        ('Rent Configuration', {
            'fields': ('monthly_rent', 'garbage_fee')
        }),
        ('Water Billing', {
            'fields': ('water_billing_type', 'water_fixed_amount', 'water_rate_per_unit')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )