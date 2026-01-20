from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Reminder
from properties.models import Property


class ReminderListView(LoginRequiredMixin, View):
    """List all reminders for the landlord"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Get active and upcoming reminders
        active_reminders = Reminder.objects.filter(
            landlord=request.landlord,
            is_active=True
        ).select_related('reminder_property').order_by('next_send_date', 'reminder_time')
        
        # Get inactive/past reminders
        inactive_reminders = Reminder.objects.filter(
            landlord=request.landlord,
            is_active=False
        ).select_related('reminder_property').order_by('-last_sent')[:20]
        
        context = {
            'active_reminders': active_reminders,
            'inactive_reminders': inactive_reminders,
        }
        
        return render(request, 'landlord/reminder_list.html', context)


class ReminderCreateView(LoginRequiredMixin, View):
    """Create a new reminder"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        properties = Property.objects.filter(landlord=request.landlord)
        
        return render(request, 'landlord/reminder_form.html', {
            'properties': properties
        })
    
    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Get form data
        property_id = request.POST.get('property')
        title = request.POST.get('title')
        description = request.POST.get('description')
        reminder_date = request.POST.get('reminder_date')
        reminder_time = request.POST.get('reminder_time', '09:00')
        frequency = request.POST.get('frequency', 'once')
        send_sms = request.POST.get('send_sms') == 'on'
        send_email = request.POST.get('send_email') == 'on'
        
        # Validate required fields
        if not all([title, description, reminder_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('reminders:create')
        
        # Get property if provided
        reminder_property = None
        if property_id:
            reminder_property = get_object_or_404(
                Property,
                pk=property_id,
                landlord=request.landlord
            )
        
        # Create reminder
        reminder = Reminder.objects.create(
            landlord=request.landlord,
            reminder_property=reminder_property,
            title=title,
            description=description,
            reminder_date=reminder_date,
            reminder_time=reminder_time,
            frequency=frequency,
            send_sms=send_sms,
            send_email=send_email,
            is_active=True
        )
        
        messages.success(request, f'Reminder "{title}" created successfully!')
        return redirect('reminders:detail', pk=reminder.pk)


class ReminderDetailView(LoginRequiredMixin, View):
    """View reminder details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        reminder = get_object_or_404(
            Reminder,
            pk=pk,
            landlord=request.landlord
        )
        
        return render(request, 'landlord/reminder_detail.html', {
            'reminder': reminder
        })


class ReminderUpdateView(LoginRequiredMixin, View):
    """Update reminder details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        reminder = get_object_or_404(
            Reminder,
            pk=pk,
            landlord=request.landlord
        )
        
        properties = Property.objects.filter(landlord=request.landlord)
        
        return render(request, 'landlord/reminder_form.html', {
            'reminder': reminder,
            'properties': properties,
            'editing': True
        })
    
    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        reminder = get_object_or_404(
            Reminder,
            pk=pk,
            landlord=request.landlord
        )
        
        # Get form data
        property_id = request.POST.get('property')
        title = request.POST.get('title')
        description = request.POST.get('description')
        reminder_date = request.POST.get('reminder_date')
        reminder_time = request.POST.get('reminder_time', '09:00')
        frequency = request.POST.get('frequency', 'once')
        send_sms = request.POST.get('send_sms') == 'on'
        send_email = request.POST.get('send_email') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate required fields
        if not all([title, description, reminder_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('reminders:update', pk=pk)
        
        # Get property if provided
        reminder_property = None
        if property_id:
            reminder_property = get_object_or_404(
                Property,
                pk=property_id,
                landlord=request.landlord
            )
        
        # Update reminder
        reminder.reminder_property = reminder_property
        reminder.title = title
        reminder.description = description
        reminder.reminder_date = reminder_date
        reminder.reminder_time = reminder_time
        reminder.frequency = frequency
        reminder.send_sms = send_sms
        reminder.send_email = send_email
        reminder.is_active = is_active
        reminder.save()
        
        messages.success(request, 'Reminder updated successfully!')
        return redirect('reminders:detail', pk=pk)


class ReminderDeleteView(LoginRequiredMixin, View):
    """Delete a reminder"""
    
    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        reminder = get_object_or_404(
            Reminder,
            pk=pk,
            landlord=request.landlord
        )
        
        title = reminder.title
        reminder.delete()
        
        messages.success(request, f'Reminder "{title}" deleted successfully!')
        return redirect('reminders:list')


class ReminderCompleteView(LoginRequiredMixin, View):
    """Mark a reminder as complete"""
    
    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        reminder = get_object_or_404(
            Reminder,
            pk=pk,
            landlord=request.landlord
        )
        
        # Mark as inactive/complete
        reminder.is_active = False
        reminder.last_sent = timezone.now()
        reminder.save()
        
        messages.success(request, f'Reminder "{reminder.title}" marked as complete!')
        return redirect('reminders:list')