from django.db import models
from django.utils import timezone
from accounts.models import LandlordProfile


class Reminder(models.Model):
    """
    Reminder system for landlord tasks.
    """
    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    landlord = models.ForeignKey(LandlordProfile, on_delete=models.CASCADE, related_name='reminders')
    reminder_property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, null=True, blank=True, related_name='reminders', help_text='Associated property (optional)')
    title = models.CharField(max_length=255, help_text='Reminder title/summary')
    description = models.TextField(help_text='Detailed description')
    reminder_date = models.DateField(help_text='Date to send reminder')
    reminder_time = models.TimeField(default='09:00:00', help_text='Time to send reminder')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once', help_text='How often this reminder repeats')
    send_sms = models.BooleanField(default=True, help_text='Send SMS notification')
    send_email = models.BooleanField(default=True, help_text='Send email notification')
    is_active = models.BooleanField(default=True, help_text='Active reminders will be sent')
    last_sent = models.DateTimeField(null=True, blank=True, help_text='Last time reminder was sent')
    next_send_date = models.DateField(null=True, blank=True, help_text='Next scheduled send date')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reminders'
        ordering = ['reminder_date', 'reminder_time']
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminders'
    
    def __str__(self):
        return f"{self.title} - {self.reminder_date}"
    
    def save(self, *args, **kwargs):
        if not self.next_send_date:
            self.next_send_date = self.reminder_date
        super().save(*args, **kwargs)