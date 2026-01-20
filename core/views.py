from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from datetime import date, timedelta
from decimal import Decimal
from properties.models import Property, Unit
from tenants_mgmt.models import Lease
from invoicing.models import Invoice
from payments.models import Payment
from expenses.models import Expense


@login_required
def dashboard(request):
    """Main dashboard with role-based routing"""

    # Super Admin Dashboard
    if request.user.is_superuser or (hasattr(request.user, 'is_superadmin') and request.user.is_superadmin):
        return super_admin_dashboard(request)

    # Landlord Dashboard
    if hasattr(request.user, 'is_landlord') and request.user.is_landlord:
        return landlord_dashboard(request)

    # Tenant Dashboard
    if hasattr(request.user, 'is_tenant') and request.user.is_tenant:
        return tenant_dashboard(request)

    # Fallback
    return render(request, 'landlord/dashboard.html', {'page_title': 'Dashboard'})


def super_admin_dashboard(request):
    """Super Admin platform overview"""
    from accounts.models import LandlordProfile
    from subscriptions.models import Subscription

    total_landlords = LandlordProfile.objects.count()
    active_subs = Subscription.objects.filter(end_date__gte=date.today()).count()
    total_properties = Property.objects.count()
    total_units = Unit.objects.count()
    occupied = Unit.objects.filter(lease__status='active').distinct().count()

    total_revenue = Payment.objects.filter(status='confirmed').aggregate(total=Sum('amount'))['total'] or 0

    recent_landlords = LandlordProfile.objects.select_related('user').order_by('-created_at')[:10]

    expiring_soon = Subscription.objects.filter(
        end_date__gte=date.today(),
        end_date__lte=date.today() + timedelta(days=7)
    ).select_related('landlord__user', 'plan')

    context = {
        'page_title': 'Super Admin Dashboard',
        'is_super_admin': True,
        'subscription_status': 'active',
        'stats': {
            'total_landlords': total_landlords,
            'active_subscriptions': active_subs,
            'total_properties': total_properties,
            'total_units': total_units,
            'occupied_units': occupied,
            'occupancy_rate': (occupied / total_units * 100) if total_units > 0 else 0,
            'total_revenue': total_revenue,
        },
        'recent_landlords': recent_landlords,
        'expiring_soon': expiring_soon,
        'recent_payments': [],
        'recent_invoices': [],
    }

    return render(request, 'landlord/dashboard.html', context)


def landlord_dashboard(request):
    """Landlord dashboard with subscription info"""

    # Get landlord from request (set by middleware)
    if not hasattr(request, 'landlord') or request.landlord is None:
        from accounts.models import LandlordProfile
        try:
            landlord = LandlordProfile.objects.get(user=request.user)
            request.landlord = landlord
        except LandlordProfile.DoesNotExist:
            # Create landlord profile if it doesn't exist
            landlord = LandlordProfile.objects.create(user=request.user)
            request.landlord = landlord

    landlord = request.landlord

    # Subscription information
    subscription = landlord.subscription
    days_remaining = 0
    is_trial = False
    subscription_status = 'none'
    units_used = 0
    units_limit = 0

    if subscription:
        days_remaining = (subscription.end_date - date.today()).days
        is_trial = subscription.status == 'trial'
        subscription_status = 'active' if subscription.get_is_active() else 'expired'
        units_used = landlord.units_used
        units_limit = subscription.plan.max_units

    # Property stats
    total_properties = Property.objects.filter(landlord=landlord).count()
    total_units = Unit.objects.filter(unit_property__landlord=landlord).count()
    occupied_units = Unit.objects.filter(
        unit_property__landlord=landlord,
        lease__status='active'
    ).distinct().count()
    vacant_units = total_units - occupied_units

    # Financial stats (current month)
    current_month = date.today().month
    current_year = date.today().year

    rent_collected = Payment.objects.filter(
        invoice__lease__unit__unit_property__landlord=landlord,
        payment_date__month=current_month,
        payment_date__year=current_year,
        status='confirmed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = Expense.objects.filter(
        landlord=landlord,
        expense_date__month=current_month,
        expense_date__year=current_year
    ).aggregate(total=Sum('amount'))['total'] or 0

    net_profit = Decimal(str(rent_collected)) - Decimal(str(total_expenses))

    # Calculate pending amount properly (balance = total_amount - amount_paid)
    pending_invoices = Invoice.objects.filter(
        lease__unit__unit_property__landlord=landlord,
        status__in=['pending', 'overdue', 'partial']
    )
    pending_amount = Decimal('0')
    for inv in pending_invoices:
        pending_amount += (inv.total_amount - inv.amount_paid)

    # Recent activity
    recent_payments = Payment.objects.filter(
        invoice__lease__unit__unit_property__landlord=landlord
    ).select_related('invoice__lease__tenant__user').order_by('-payment_date')[:5]

    recent_invoices = Invoice.objects.filter(
        lease__unit__unit_property__landlord=landlord
    ).select_related('lease__tenant__user', 'lease__unit').order_by('-created_at')[:5]

    upcoming_due = Invoice.objects.filter(
        lease__unit__unit_property__landlord=landlord,
        status__in=['pending', 'partial'],
        due_date__gte=date.today(),
        due_date__lte=date.today() + timedelta(days=7)
    ).count()

    context = {
        'page_title': 'Dashboard',
        'subscription': subscription,
        'days_remaining': days_remaining,
        'is_trial': is_trial,
        'subscription_status': subscription_status,
        'units_used': units_used,
        'units_limit': units_limit,
        'stats': {
            'total_properties': total_properties,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'vacant_units': vacant_units,
            'occupancy_rate': (occupied_units / total_units * 100) if total_units > 0 else 0,
            'rent_collected': rent_collected,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'pending_amount': pending_amount,
            'upcoming_due': upcoming_due,
        },
        'recent_payments': recent_payments,
        'recent_invoices': recent_invoices,
    }

    return render(request, 'landlord/dashboard.html', context)


def tenant_dashboard(request):
    """Tenant portal view"""
    from accounts.models import TenantProfile
    
    # Get tenant profile safely
    tenant = None
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
    else:
        try:
            tenant = request.user.tenant_profile
        except TenantProfile.DoesNotExist:
            return render(request, 'tenant/portal.html', {
                'page_title': 'Tenant Portal',
                'current_lease': None,
                'invoices': [],
                'total_paid': 0,
                'total_arrears': 0,
            })

    if not tenant:
        return render(request, 'tenant/portal.html', {
            'page_title': 'Tenant Portal',
            'current_lease': None,
            'invoices': [],
            'total_paid': 0,
            'total_arrears': 0,
        })

    active_lease = Lease.objects.filter(
        tenant=tenant,
        status='active'
    ).select_related('unit__unit_property__landlord__user').first()

    if not active_lease:
        return render(request, 'tenant/portal.html', {
            'page_title': 'Tenant Portal',
            'current_lease': None,
            'invoices': [],
            'total_paid': 0,
            'total_arrears': 0,
        })

    invoices = Invoice.objects.filter(
        lease=active_lease
    ).order_by('-billing_month')

    # Calculate totals properly (balance is a property, not a field)
    total_paid = Decimal('0')
    total_arrears = Decimal('0')
    for inv in invoices:
        total_paid += inv.amount_paid
        if inv.status in ['pending', 'overdue', 'partial']:
            total_arrears += (inv.total_amount - inv.amount_paid)

    context = {
        'page_title': 'Tenant Portal',
        'current_lease': active_lease,
        'invoices': invoices,
        'total_paid': total_paid,
        'total_arrears': total_arrears,
    }

    return render(request, 'tenant/portal.html', context)