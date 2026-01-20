from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from .decorators import superadmin_required

# Import models from other apps
from accounts.models import User, LandlordProfile, TenantProfile
from subscriptions.models import Subscription, SubscriptionPlan, SubscriptionPayment
from properties.models import Property, Unit
from payments.models import Payment
from invoicing.models import Invoice


@superadmin_required
def dashboard(request):
    """
    Super Admin Dashboard - Platform overview with key metrics.
    """
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    # User Statistics
    total_landlords = User.objects.filter(role='landlord').count()
    total_tenants = User.objects.filter(role='tenant').count()
    new_landlords_30d = User.objects.filter(
        role='landlord', 
        date_joined__gte=thirty_days_ago
    ).count()
    
    # Subscription Statistics
    active_subscriptions = Subscription.objects.filter(
        status__in=['active', 'trial']
    ).count()
    trial_subscriptions = Subscription.objects.filter(status='trial').count()
    expired_subscriptions = Subscription.objects.filter(status='expired').count()
    
    # Revenue Statistics - using paid_at instead of payment_date
    total_revenue = SubscriptionPayment.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    revenue_30d = SubscriptionPayment.objects.filter(
        status='completed',
        paid_at__gte=thirty_days_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Property Statistics
    total_properties = Property.objects.count()
    total_units = Unit.objects.count()
    # Count occupied units by checking if they have a lease
    occupied_units = Unit.objects.filter(lease__isnull=False).distinct().count()
    
    # Platform Activity
    total_payments = Payment.objects.count()
    total_invoices = Invoice.objects.count()
    
    # Recent Landlords (last 10 signups)
    recent_landlords = User.objects.filter(
        role='landlord'
    ).select_related('landlord_profile').order_by('-date_joined')[:10]
    
    # Subscriptions expiring soon (next 7 days)
    seven_days_later = today + timedelta(days=7)
    expiring_soon = Subscription.objects.filter(
        end_date__lte=seven_days_later,
        end_date__gte=today,
        status__in=['active', 'trial']
    ).select_related('landlord__user', 'plan')[:10]
    
    # Monthly revenue trend (last 6 months) - using paid_at
    six_months_ago = today - timedelta(days=180)
    monthly_revenue = SubscriptionPayment.objects.filter(
        status='completed',
        paid_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('paid_at')
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')
    
    context = {
        # User Stats
        'total_landlords': total_landlords,
        'total_tenants': total_tenants,
        'new_landlords_30d': new_landlords_30d,
        
        # Subscription Stats
        'active_subscriptions': active_subscriptions,
        'trial_subscriptions': trial_subscriptions,
        'expired_subscriptions': expired_subscriptions,
        
        # Revenue Stats
        'total_revenue': total_revenue,
        'revenue_30d': revenue_30d,
        
        # Property Stats
        'total_properties': total_properties,
        'total_units': total_units,
        'occupied_units': occupied_units,
        'occupancy_rate': round((occupied_units / total_units * 100) if total_units > 0 else 0, 1),
        
        # Activity Stats
        'total_payments': total_payments,
        'total_invoices': total_invoices,
        
        # Lists
        'recent_landlords': recent_landlords,
        'expiring_soon': expiring_soon,
        'monthly_revenue': list(monthly_revenue),
    }
    
    return render(request, 'superadmin/dashboard.html', context)


@superadmin_required
def landlords_list(request):
    """
    List all landlords with their subscription status and property counts.
    """
    # Filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    landlords = User.objects.filter(role='landlord').select_related('landlord_profile')
    
    if search_query:
        landlords = landlords.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(landlord_profile__business_name__icontains=search_query)
        )
    
    # Annotate with property and unit counts
    landlord_data = []
    for landlord in landlords.order_by('-date_joined'):
        profile = getattr(landlord, 'landlord_profile', None)
        subscription = profile.subscription if profile else None
        
        properties_count = Property.objects.filter(landlord=profile).count() if profile else 0
        units_count = Unit.objects.filter(unit_property__landlord=profile).count() if profile else 0
        tenants_count = 0  # Simplified - can be expanded later
        
        # Apply status filter
        if status_filter:
            if status_filter == 'active' and (not subscription or subscription.status != 'active'):
                continue
            elif status_filter == 'trial' and (not subscription or subscription.status != 'trial'):
                continue
            elif status_filter == 'expired' and (not subscription or subscription.status != 'expired'):
                continue
            elif status_filter == 'suspended' and landlord.is_active_account:
                continue
        
        landlord_data.append({
            'user': landlord,
            'profile': profile,
            'subscription': subscription,
            'properties_count': properties_count,
            'units_count': units_count,
            'tenants_count': tenants_count,
        })
    
    context = {
        'landlords': landlord_data,
        'total_count': len(landlord_data),
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'superadmin/landlords.html', context)


@superadmin_required
def landlord_detail(request, pk):
    """
    View detailed information about a specific landlord.
    """
    landlord = get_object_or_404(User, pk=pk, role='landlord')
    profile = getattr(landlord, 'landlord_profile', None)
    
    properties = Property.objects.filter(landlord=profile) if profile else []
    
    # Get subscription history
    subscription_history = Subscription.objects.filter(
        landlord=profile
    ).order_by('-created_at') if profile else []
    
    # Get payment history - using paid_at
    payment_history = SubscriptionPayment.objects.filter(
        subscription__landlord=profile
    ).order_by('-paid_at')[:20] if profile else []
    
    context = {
        'landlord': landlord,
        'profile': profile,
        'properties': properties,
        'subscription_history': subscription_history,
        'payment_history': payment_history,
    }
    
    return render(request, 'superadmin/landlord_detail.html', context)


@superadmin_required
def toggle_landlord_status(request, pk):
    """
    Suspend or activate a landlord account.
    """
    landlord = get_object_or_404(User, pk=pk, role='landlord')
    
    if request.method == 'POST':
        landlord.is_active_account = not landlord.is_active_account
        landlord.save()
        
        status = 'activated' if landlord.is_active_account else 'suspended'
        messages.success(request, f'Landlord account {landlord.username} has been {status}.')
    
    return redirect('superadmin:landlord_detail', pk=pk)


@superadmin_required
def subscriptions_list(request):
    """
    List all subscriptions with filtering options.
    """
    status_filter = request.GET.get('status', '')
    plan_filter = request.GET.get('plan', '')
    
    subscriptions = Subscription.objects.select_related(
        'landlord__user', 'plan'
    ).order_by('-created_at')
    
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    
    if plan_filter:
        subscriptions = subscriptions.filter(plan_id=plan_filter)
    
    plans = SubscriptionPlan.objects.filter(is_active=True)
    
    # Calculate stats
    total_active = subscriptions.filter(status='active').count()
    total_trial = subscriptions.filter(status='trial').count()
    total_expired = subscriptions.filter(status='expired').count()
    
    context = {
        'subscriptions': subscriptions,
        'plans': plans,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'total_active': total_active,
        'total_trial': total_trial,
        'total_expired': total_expired,
    }
    
    return render(request, 'superadmin/subscriptions.html', context)


@superadmin_required
def subscription_plans(request):
    """
    Manage subscription plans.
    """
    # Using monthly_price instead of price
    plans = SubscriptionPlan.objects.all().order_by('monthly_price')
    
    # Count subscribers per plan
    plan_data = []
    for plan in plans:
        subscriber_count = Subscription.objects.filter(
            plan=plan, 
            status__in=['active', 'trial']
        ).count()
        plan_data.append({
            'plan': plan,
            'subscriber_count': subscriber_count,
        })
    
    context = {
        'plans': plan_data,
    }
    
    return render(request, 'superadmin/subscription_plans.html', context)


@superadmin_required
def revenue_report(request):
    """
    Revenue analytics and reports.
    """
    today = timezone.now().date()
    
    # Date range filter
    period = request.GET.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    
    start_date = today - timedelta(days=days)
    
    # Revenue data - using paid_at
    payments = SubscriptionPayment.objects.filter(
        status='completed',
        paid_at__gte=start_date
    )
    
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
    payment_count = payments.count()
    
    # Revenue by plan
    revenue_by_plan = payments.values(
        'subscription__plan__name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Daily revenue - using paid_at
    daily_revenue = payments.values('paid_at__date').annotate(
        total=Sum('amount')
    ).order_by('paid_at__date')
    
    context = {
        'total_revenue': total_revenue,
        'payment_count': payment_count,
        'revenue_by_plan': revenue_by_plan,
        'daily_revenue': list(daily_revenue),
        'period': period,
        'start_date': start_date,
    }
    
    return render(request, 'superadmin/revenue_report.html', context)


@superadmin_required
def system_settings(request):
    """
    System-wide settings and configuration.
    """
    if request.method == 'POST':
        # Handle settings update
        messages.success(request, 'System settings updated successfully.')
        return redirect('superadmin:system_settings')
    
    context = {
        'debug_mode': True,  # You can pull this from settings
    }
    
    return render(request, 'superadmin/system_settings.html', context)


@superadmin_required
def activity_log(request):
    """
    View recent system activity.
    """
    # Recent logins, signups, payments, etc.
    recent_users = User.objects.order_by('-date_joined')[:50]
    recent_payments = SubscriptionPayment.objects.select_related(
        'subscription__landlord__user'
    ).order_by('-paid_at')[:50]
    
    context = {
        'recent_users': recent_users,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'superadmin/activity_log.html', context)
