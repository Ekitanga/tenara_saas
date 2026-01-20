from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def superadmin_required(view_func):
    """
    Decorator that ensures only Super Admin users can access the view.
    Redirects other users to their appropriate dashboard.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to continue.')
            return redirect('accounts:login')
        
        # Check if user is superadmin (is_superuser OR role == 'superadmin')
        if not request.user.is_superadmin:
            messages.error(request, 'Access denied. Super Admin privileges required.')
            # Redirect based on role
            if request.user.is_landlord:
                return redirect('dashboard')
            elif request.user.is_tenant:
                return redirect('tenants:portal')
            else:
                return redirect('demo:home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
