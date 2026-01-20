from django.contrib import admin
from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ['title', 'landlord', 'reminder_property', 'reminder_date', 'reminder_time', 'frequency', 'is_active', 'last_sent', 'next_send_date']
    list_filter = ['frequency', 'is_active', 'send_sms', 'send_email', 'reminder_date', 'created_at']
    search_fields = ['title', 'description', 'landlord__user__username', 'landlord__business_name', 'reminder_property__name']
    raw_id_fields = ['landlord', 'reminder_property']
    readonly_fields = ['created_at', 'updated_at', 'last_sent']
    date_hierarchy = 'reminder_date'
    
    fieldsets = (
        ('Reminder Information', {
            'fields': ('landlord', 'reminder_property', 'title', 'description')
        }),
        ('Schedule', {
            'fields': ('reminder_date', 'reminder_time', 'frequency', 'next_send_date')
        }),
        ('Notification Settings', {
            'fields': ('send_sms', 'send_email', 'is_active')
        }),
        ('Status', {
            'fields': ('last_sent',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_reminders', 'deactivate_reminders']
    
    def activate_reminders(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} reminder(s) activated.')
    activate_reminders.short_description = 'Activate selected reminders'
    
    def deactivate_reminders(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} reminder(s) deactivated.')
    deactivate_reminders.short_description = 'Deactivate selected reminders'