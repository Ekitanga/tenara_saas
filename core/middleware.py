from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect


class TenantMiddleware(MiddlewareMixin):
    """
    Multi-tenant middleware for strict data isolation.
    Attaches landlord or tenant profile to request object.
    """

    def process_request(self, request):
        """Process each request and attach profile"""
        
        # Initialize attributes
        request.landlord = None
        request.tenant = None
        request.superadmin = None

        if not request.user.is_authenticated:
            return None

        # Import here to avoid circular imports
        from accounts.models import LandlordProfile, TenantProfile

        # CRITICAL: Handle superusers and staff first
        if request.user.is_superuser or request.user.is_staff:
            request.superadmin = request.user
            # Super admin might also want to see landlord data for testing
            # Don't block them from any page
            return None

        # Handle Tenant Users
        if hasattr(request.user, 'is_tenant') and request.user.is_tenant:
            try:
                request.tenant = request.user.tenant_profile
            except TenantProfile.DoesNotExist:
                # Create profile if doesn't exist
                request.tenant = TenantProfile.objects.create(user=request.user)
            return None

        # Handle Landlord Users
        if hasattr(request.user, 'is_landlord') and request.user.is_landlord:
            try:
                request.landlord = request.user.landlord_profile
            except LandlordProfile.DoesNotExist:
                # Create profile if doesn't exist
                request.landlord = LandlordProfile.objects.create(user=request.user)

            # Exempt certain paths from subscription checks
            exempt_paths = [
                '/admin/',
                '/static/',
                '/media/',
                '/accounts/',
                '/subscriptions/',
                '/',
            ]

            is_exempt = any(request.path.startswith(path) for path in exempt_paths)

            # Check subscription status (but don't block if no subscription yet)
            if not is_exempt and request.landlord.subscription:
                if not request.landlord.subscription.get_is_active():
                    if not request.path.startswith('/subscriptions/'):
                        return redirect('subscriptions:expired')

        return None