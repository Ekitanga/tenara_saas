def subscription_context(request):
    """Add subscription info to all templates"""
    context = {
        'subscription': None,
        'subscription_status': None,
        'is_trial': False,
        'days_remaining': 0,
        'units_used': 0,
        'units_limit': 0,
        'business_name': '',
    }
    
    # Only process for authenticated users
    if not request.user.is_authenticated:
        return context
    
    # Only process for landlords
    if not hasattr(request.user, 'is_landlord') or not request.user.is_landlord:
        return context
    
    # Get landlord profile safely
    try:
        landlord = request.user.landlord_profile
    except:
        return context
    
    if not landlord:
        return context
    
    # Set business name
    context['business_name'] = landlord.business_name or ''
    
    # Get subscription info
    subscription = landlord.subscription
    if subscription:
        context['subscription'] = subscription
        context['subscription_status'] = subscription.status if subscription.get_is_active() else 'expired'
        context['is_trial'] = subscription.status == 'trial'
        context['days_remaining'] = subscription.get_days_remaining()
        context['units_used'] = landlord.units_used
        context['units_limit'] = subscription.plan.max_units
    
    return context