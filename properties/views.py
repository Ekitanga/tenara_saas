from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from .models import Property, Unit
from invoicing.models import Invoice
from payments.models import Payment
from expenses.models import Expense
from accounts.models import LandlordProfile
from django.db.models import Sum, Q
from django.utils import timezone


class DashboardView(LoginRequiredMixin, View):
    """Main landlord dashboard with statistics and recent activity"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied. Landlord account required.')
            return redirect('demo:home')
        
        # Get landlord profile - fallback if middleware didn't attach it
        if not hasattr(request, 'landlord') or request.landlord is None:
            try:
                request.landlord = request.user.landlord_profile
            except LandlordProfile.DoesNotExist:
                messages.error(request, 'Landlord profile not found.')
                return redirect('demo:home')
        
        landlord = request.landlord
        current_month = timezone.now().date().replace(day=1)
        
        # Subscription status
        subscription = landlord.subscription
        if subscription:
            subscription_status = subscription.status if subscription.get_is_active() else 'expired'
            is_trial = subscription.status == 'trial'
            days_remaining = subscription.get_days_remaining()
            units_used = landlord.units_used
            units_limit = subscription.plan.max_units
        else:
            subscription_status = None
            is_trial = False
            days_remaining = 0
            units_used = 0
            units_limit = 0
        
        # Calculate statistics
        total_properties = Property.objects.filter(landlord=landlord).count()
        total_units = Unit.objects.filter(unit_property__landlord=landlord).count()
        occupied_units = Unit.objects.filter(
            unit_property__landlord=landlord,
            lease__status='active'
        ).distinct().count()
        
        # Occupancy rate
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Rent statistics for current month
        rent_collected = Payment.objects.filter(
            invoice__lease__unit__unit_property__landlord=landlord,
            invoice__billing_month=current_month,
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Total arrears (all unpaid/partially paid invoices)
        arrears_invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=landlord,
            status__in=['pending', 'overdue', 'partial']
        )
        
        pending_amount = 0
        for invoice in arrears_invoices:
            pending_amount += (invoice.total_amount - invoice.amount_paid)
        
        # Expenses for current month
        total_expenses = Expense.objects.filter(
            landlord=landlord,
            expense_date__month=current_month.month,
            expense_date__year=current_month.year
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Net profit
        net_profit = rent_collected - total_expenses
        
        # Recent activity
        recent_payments = Payment.objects.filter(
            invoice__lease__unit__unit_property__landlord=landlord,
            status='confirmed'
        ).select_related(
            'invoice__lease__tenant__user',
            'invoice__lease__unit__unit_property'
        ).order_by('-payment_date')[:5]
        
        recent_invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=landlord
        ).select_related(
            'lease__tenant__user',
            'lease__unit__unit_property'
        ).order_by('-created_at')[:5]
        
        context = {
            'subscription': subscription,
            'subscription_status': subscription_status,
            'is_trial': is_trial,
            'days_remaining': days_remaining,
            'units_used': units_used,
            'units_limit': units_limit,
            'stats': {
                'total_properties': total_properties,
                'total_units': total_units,
                'occupied_units': occupied_units,
                'occupancy_rate': occupancy_rate,
                'rent_collected': rent_collected,
                'pending_amount': pending_amount,
                'total_expenses': total_expenses,
                'net_profit': net_profit,
            },
            'recent_payments': recent_payments,
            'recent_invoices': recent_invoices,
        }
        
        return render(request, 'landlord/dashboard.html', context)


class PropertyListView(LoginRequiredMixin, View):
    """List all properties for the landlord"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        properties = Property.objects.filter(
            landlord=request.landlord
        ).prefetch_related('units')
        
        return render(request, 'landlord/property_list.html', {
            'properties': properties
        })


class PropertyCreateView(LoginRequiredMixin, View):
    """Create a new property"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        return render(request, 'landlord/property_form.html')
    
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        name = request.POST.get('name')
        location = request.POST.get('location')
        description = request.POST.get('description', '')
        
        if not name or not location:
            messages.error(request, 'Property name and location are required.')
            return redirect('property_create')
        
        property_obj = Property.objects.create(
            landlord=request.landlord,
            name=name,
            location=location,
            description=description
        )
        
        messages.success(request, f'Property "{name}" created successfully!')
        return redirect('property_detail', pk=property_obj.pk)


class PropertyDetailView(LoginRequiredMixin, View):
    """View property details and units"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        property_obj = get_object_or_404(
            Property,
            pk=pk,
            landlord=request.landlord
        )
        
        units = property_obj.units.all().prefetch_related('lease')
        
        return render(request, 'landlord/property_detail.html', {
            'property': property_obj,
            'units': units
        })


class PropertyUpdateView(LoginRequiredMixin, View):
    """Update property details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        property_obj = get_object_or_404(
            Property,
            pk=pk,
            landlord=request.landlord
        )
        
        return render(request, 'landlord/property_form.html', {
            'property': property_obj
        })
    
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        property_obj = get_object_or_404(
            Property,
            pk=pk,
            landlord=request.landlord
        )
        
        name = request.POST.get('name')
        location = request.POST.get('location')
        description = request.POST.get('description', '')
        
        if not name or not location:
            messages.error(request, 'Property name and location are required.')
            return redirect('property_update', pk=pk)
        
        property_obj.name = name
        property_obj.location = location
        property_obj.description = description
        property_obj.save()
        
        messages.success(request, 'Property updated successfully!')
        return redirect('property_detail', pk=pk)


class PropertyDeleteView(LoginRequiredMixin, View):
    """Delete a property"""
    
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        property_obj = get_object_or_404(
            Property,
            pk=pk,
            landlord=request.landlord
        )
        
        property_name = property_obj.name
        property_obj.delete()
        
        messages.success(request, f'Property "{property_name}" deleted successfully!')
        return redirect('property_list')


class UnitCreateView(LoginRequiredMixin, View):
    """Create a new unit"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        properties = Property.objects.filter(landlord=request.landlord)
        
        if not properties.exists():
            messages.warning(request, 'Please create a property first before adding units.')
            return redirect('property_create')
        
        return render(request, 'landlord/unit_form.html', {
            'properties': properties
        })
    
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Check unit limit
        current_units = Unit.objects.filter(unit_property__landlord=request.landlord).count()
        
        if request.landlord.subscription:
            max_units = request.landlord.subscription.plan.max_units
            if current_units >= max_units:
                messages.error(request, f'Unit limit reached ({max_units} units). Please upgrade your plan.')
                return redirect('subscriptions:plans')
        else:
            messages.error(request, 'No active subscription. Please subscribe to a plan.')
            return redirect('subscriptions:plans')
        
        # Get form data
        property_id = request.POST.get('property')
        unit_number = request.POST.get('unit_number')
        unit_type = request.POST.get('unit_type')
        monthly_rent = request.POST.get('monthly_rent')
        garbage_fee = request.POST.get('garbage_fee', 0)
        water_billing_type = request.POST.get('water_billing_type')
        water_fixed_amount = request.POST.get('water_fixed_amount', 0)
        water_rate_per_unit = request.POST.get('water_rate_per_unit', 0)
        
        # Validate required fields
        if not all([property_id, unit_number, unit_type, monthly_rent, water_billing_type]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('unit_create')
        
        # Get property and verify ownership
        property_obj = get_object_or_404(
            Property,
            pk=property_id,
            landlord=request.landlord
        )
        
        # Check for duplicate unit number in same property
        if Unit.objects.filter(unit_property=property_obj, unit_number=unit_number).exists():
            messages.error(request, f'Unit "{unit_number}" already exists in this property.')
            return redirect('unit_create')
        
        # Create unit
        unit = Unit.objects.create(
            unit_property=property_obj,
            unit_number=unit_number,
            unit_type=unit_type,
            monthly_rent=monthly_rent,
            garbage_fee=garbage_fee,
            water_billing_type=water_billing_type,
            water_fixed_amount=water_fixed_amount,
            water_rate_per_unit=water_rate_per_unit
        )
        
        messages.success(request, f'Unit "{unit_number}" created successfully!')
        return redirect('property_detail', pk=property_obj.pk)


class UnitUpdateView(LoginRequiredMixin, View):
    """Update unit details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        unit = get_object_or_404(
            Unit,
            pk=pk,
            unit_property__landlord=request.landlord
        )
        
        properties = Property.objects.filter(landlord=request.landlord)
        
        return render(request, 'landlord/unit_form.html', {
            'unit': unit,
            'properties': properties
        })
    
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        unit = get_object_or_404(
            Unit,
            pk=pk,
            unit_property__landlord=request.landlord
        )
        
        # Get form data
        property_id = request.POST.get('property')
        unit_number = request.POST.get('unit_number')
        unit_type = request.POST.get('unit_type')
        monthly_rent = request.POST.get('monthly_rent')
        garbage_fee = request.POST.get('garbage_fee', 0)
        water_billing_type = request.POST.get('water_billing_type')
        water_fixed_amount = request.POST.get('water_fixed_amount', 0)
        water_rate_per_unit = request.POST.get('water_rate_per_unit', 0)
        
        # Validate required fields
        if not all([property_id, unit_number, unit_type, monthly_rent, water_billing_type]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('unit_update', pk=pk)
        
        # Get property and verify ownership
        property_obj = get_object_or_404(
            Property,
            pk=property_id,
            landlord=request.landlord
        )
        
        # Check for duplicate unit number (excluding current unit)
        duplicate = Unit.objects.filter(
            unit_property=property_obj,
            unit_number=unit_number
        ).exclude(pk=pk)
        
        if duplicate.exists():
            messages.error(request, f'Unit "{unit_number}" already exists in this property.')
            return redirect('unit_update', pk=pk)
        
        # Update unit
        unit.unit_property = property_obj
        unit.unit_number = unit_number
        unit.unit_type = unit_type
        unit.monthly_rent = monthly_rent
        unit.garbage_fee = garbage_fee
        unit.water_billing_type = water_billing_type
        unit.water_fixed_amount = water_fixed_amount
        unit.water_rate_per_unit = water_rate_per_unit
        unit.save()
        
        messages.success(request, 'Unit updated successfully!')
        return redirect('property_detail', pk=unit.unit_property.pk)


class UnitDeleteView(LoginRequiredMixin, View):
    """Delete a unit"""
    
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        unit = get_object_or_404(
            Unit,
            pk=pk,
            unit_property__landlord=request.landlord
        )
        
        # Check if unit has active lease
        if unit.is_occupied():
            messages.error(request, 'Cannot delete unit with active lease. Terminate lease first.')
            return redirect('property_detail', pk=unit.unit_property.pk)
        
        property_pk = unit.unit_property.pk
        unit_number = unit.unit_number
        unit.delete()
        
        messages.success(request, f'Unit "{unit_number}" deleted successfully!')
        return redirect('property_detail', pk=property_pk)
