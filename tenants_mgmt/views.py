from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Lease
from accounts.models import User, TenantProfile
from properties.models import Unit
from invoicing.models import Invoice
import random
import string


class TenantListView(LoginRequiredMixin, View):
    """List all tenants for the landlord"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        # Get all active leases for this landlord
        active_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        ).select_related(
            'tenant__user',
            'unit__unit_property'
        ).order_by('tenant__user__first_name')

        # Get all terminated/expired leases
        inactive_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status__in=['terminated', 'expired']
        ).select_related(
            'tenant__user',
            'unit__unit_property'
        ).order_by('-move_out_date')[:10]

        context = {
            'active_leases': active_leases,
            'inactive_leases': inactive_leases,
        }

        return render(request, 'landlord/tenant_list.html', context)


class TenantCreateView(LoginRequiredMixin, View):
    """Create a new tenant and assign to a unit (lease)"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied. You must be a landlord.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found. Please contact support.')
            return redirect('demo:home')

        landlord = request.landlord

        # Check subscription limit
        if landlord.subscription:
            units_limit = landlord.subscription.plan.max_units

            # Count current occupied units
            occupied_count = Unit.objects.filter(
                unit_property__landlord=landlord,
                lease__status='active'
            ).distinct().count()

            if occupied_count >= units_limit:
                messages.error(
                    request,
                    f'You have reached your plan limit of {units_limit} units. '
                    'Please upgrade your subscription to add more tenants.'
                )
                return redirect('subscriptions:plans')

        # Get vacant units for this landlord
        vacant_units = Unit.objects.filter(
            unit_property__landlord=landlord
        ).exclude(
            lease__status='active'
        ).select_related('unit_property')

        if not vacant_units.exists():
            messages.warning(request, 'No vacant units available. All units are occupied.')
            return redirect('tenants:list')

        return render(request, 'landlord/tenant_form.html', {
            'vacant_units': vacant_units
        })

    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        # Tenant personal information
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        emergency_contact = request.POST.get('emergency_contact', '').strip()
        emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()

        # Lease information
        unit_id = request.POST.get('unit')
        start_date = request.POST.get('start_date')
        deposit_amount = request.POST.get('deposit_amount', 0)
        deposit_paid = request.POST.get('deposit_paid') == 'on'

        # Validate required fields
        if not all([first_name, last_name, phone_number, unit_id, start_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('tenants:create')

        # Get unit and verify ownership
        try:
            unit = Unit.objects.get(
                pk=unit_id,
                unit_property__landlord=request.landlord
            )
        except Unit.DoesNotExist:
            messages.error(request, 'Invalid unit selected.')
            return redirect('tenants:create')

        # Check if unit has an active lease
        if Lease.objects.filter(unit=unit, status='active').exists():
            messages.error(request, 'This unit is already occupied.')
            return redirect('tenants:create')

        # Generate username from phone number
        clean_phone = phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        username = f"tenant_{clean_phone}"

        # Check if user with this username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'A tenant with this phone number already exists.')
            return redirect('tenants:create')

        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'A user with this email already exists.')
            return redirect('tenants:create')

        try:
            # Generate a random but secure password
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

            # Create tenant user account
            tenant_user = User.objects.create_user(
                username=username,
                email=email if email else f"{username}@tenara.local",
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                role='tenant'
            )

            # Create tenant profile
            tenant_profile = TenantProfile.objects.create(
                user=tenant_user,
                national_id=national_id,
                emergency_contact=emergency_contact,
                emergency_contact_name=emergency_contact_name
            )

            # Create lease
            lease = Lease.objects.create(
                unit=unit,
                tenant=tenant_profile,
                start_date=start_date,
                status='active',
                rent_amount=unit.monthly_rent,
                deposit_amount=deposit_amount,
                deposit_paid=deposit_paid,
                deposit_paid_date=timezone.now().date() if deposit_paid else None,
                move_in_date=start_date
            )

            messages.success(
                request,
                f'Tenant "{first_name} {last_name}" added successfully! '
                f'Login credentials - Username: {username} | Password: {password} '
                '(Please share these credentials securely with the tenant)'
            )
            return redirect('tenants:detail', pk=lease.pk)

        except Exception as e:
            messages.error(request, f'Error creating tenant: {str(e)}')
            print(f"Tenant creation error: {e}")
            import traceback
            traceback.print_exc()
            return redirect('tenants:create')


class TenantDetailView(LoginRequiredMixin, View):
    """View tenant details and lease information"""

    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        lease = get_object_or_404(
            Lease,
            pk=pk,
            unit__unit_property__landlord=request.landlord
        )

        # Get tenant's invoices
        invoices = Invoice.objects.filter(
            lease=lease
        ).order_by('-billing_month')

        # Calculate payment statistics
        total_paid = sum(inv.amount_paid for inv in invoices)
        total_owed = sum(inv.total_amount for inv in invoices)
        total_arrears = sum(inv.balance for inv in invoices if inv.balance > 0)

        context = {
            'lease': lease,
            'invoices': invoices,
            'total_paid': total_paid,
            'total_owed': total_owed,
            'total_arrears': total_arrears,
        }

        return render(request, 'landlord/tenant_detail.html', context)


class TenantUpdateView(LoginRequiredMixin, View):
    """Update tenant information"""

    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        lease = get_object_or_404(
            Lease,
            pk=pk,
            unit__unit_property__landlord=request.landlord
        )

        return render(request, 'landlord/tenant_form.html', {
            'lease': lease,
            'editing': True
        })

    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        lease = get_object_or_404(
            Lease,
            pk=pk,
            unit__unit_property__landlord=request.landlord
        )

        tenant_user = lease.tenant.user
        tenant_profile = lease.tenant

        # Update tenant personal information
        tenant_user.first_name = request.POST.get('first_name', tenant_user.first_name)
        tenant_user.last_name = request.POST.get('last_name', tenant_user.last_name)
        tenant_user.email = request.POST.get('email', tenant_user.email)
        tenant_user.phone_number = request.POST.get('phone_number', tenant_user.phone_number)
        tenant_user.save()

        tenant_profile.national_id = request.POST.get('national_id', tenant_profile.national_id)
        tenant_profile.emergency_contact = request.POST.get('emergency_contact', tenant_profile.emergency_contact)
        tenant_profile.emergency_contact_name = request.POST.get('emergency_contact_name', tenant_profile.emergency_contact_name)
        tenant_profile.save()

        messages.success(request, 'Tenant information updated successfully!')
        return redirect('tenants:detail', pk=pk)


class TenantDeleteView(LoginRequiredMixin, View):
    """Delete tenant (only if no invoices/payments exist)"""

    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        lease = get_object_or_404(
            Lease,
            pk=pk,
            unit__unit_property__landlord=request.landlord
        )

        # Check if tenant has invoices
        if Invoice.objects.filter(lease=lease).exists():
            messages.error(
                request,
                'Cannot delete tenant with existing invoices. Terminate lease instead.'
            )
            return redirect('tenants:detail', pk=pk)

        tenant_name = lease.tenant.user.get_full_name()
        tenant_user = lease.tenant.user
        tenant_profile = lease.tenant

        # Delete lease, profile, and user
        lease.delete()
        tenant_profile.delete()
        tenant_user.delete()

        messages.success(request, f'Tenant "{tenant_name}" deleted successfully!')
        return redirect('tenants:list')


class LeaseCreateView(LoginRequiredMixin, View):
    """Create a new lease for existing tenant"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        # Get all tenant profiles
        tenants = TenantProfile.objects.filter(
            leases__unit__unit_property__landlord=request.landlord
        ).distinct().select_related('user')

        # Get vacant units
        vacant_units = Unit.objects.filter(
            unit_property__landlord=request.landlord
        ).exclude(
            lease__status='active'
        ).select_related('unit_property')

        if not vacant_units.exists():
            messages.warning(request, 'No vacant units available.')
            return redirect('tenants:list')

        return render(request, 'landlord/lease_form.html', {
            'tenants': tenants,
            'vacant_units': vacant_units
        })

    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        tenant_id = request.POST.get('tenant')
        unit_id = request.POST.get('unit')
        start_date = request.POST.get('start_date')
        deposit_amount = request.POST.get('deposit_amount', 0)
        deposit_paid = request.POST.get('deposit_paid') == 'on'

        if not all([tenant_id, unit_id, start_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('tenants:lease_create')

        tenant = get_object_or_404(TenantProfile, pk=tenant_id)
        unit = get_object_or_404(
            Unit,
            pk=unit_id,
            unit_property__landlord=request.landlord
        )

        if Lease.objects.filter(unit=unit, status='active').exists():
            messages.error(request, 'This unit is already occupied.')
            return redirect('tenants:lease_create')

        # Check if tenant already has active lease
        if Lease.objects.filter(tenant=tenant, status='active').exists():
            messages.error(request, 'This tenant already has an active lease.')
            return redirect('tenants:lease_create')

        lease = Lease.objects.create(
            unit=unit,
            tenant=tenant,
            start_date=start_date,
            status='active',
            rent_amount=unit.monthly_rent,
            deposit_amount=deposit_amount,
            deposit_paid=deposit_paid,
            deposit_paid_date=timezone.now().date() if deposit_paid else None,
            move_in_date=start_date
        )

        messages.success(request, 'Lease created successfully!')
        return redirect('tenants:detail', pk=lease.pk)


class LeaseTerminateView(LoginRequiredMixin, View):
    """Terminate a lease"""

    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        if not request.landlord:
            messages.error(request, 'Landlord profile not found.')
            return redirect('demo:home')

        lease = get_object_or_404(
            Lease,
            pk=pk,
            unit__unit_property__landlord=request.landlord
        )

        if lease.status != 'active':
            messages.warning(request, 'This lease is already terminated.')
            return redirect('tenants:detail', pk=pk)

        termination_date = request.POST.get('termination_date', timezone.now().date())

        # Check for unpaid invoices
        unpaid_invoices = Invoice.objects.filter(
            lease=lease,
            status__in=['pending', 'overdue', 'partial']
        )

        if unpaid_invoices.exists():
            total_arrears = sum(inv.balance for inv in unpaid_invoices)
            messages.warning(
                request,
                f'Warning: Tenant has outstanding arrears of KES {total_arrears:,.2f}'
            )

        # Terminate lease
        lease.terminate_lease(termination_date)

        messages.success(request, 'Lease terminated successfully!')
        return redirect('tenants:detail', pk=pk)


class TenantPortalView(LoginRequiredMixin, View):
    """Tenant portal - view own lease and invoices"""

    def get(self, request):
        # Check if user is a tenant
        if not hasattr(request.user, 'is_tenant') or not request.user.is_tenant:
            messages.error(request, 'Access denied. Tenant account required.')
            return redirect('demo:home')

        # Get tenant profile
        try:
            tenant_profile = request.user.tenant_profile
        except TenantProfile.DoesNotExist:
            messages.error(request, 'Tenant profile not found.')
            return redirect('demo:home')

        # Get active lease
        current_lease = Lease.objects.filter(
            tenant=tenant_profile,
            status='active'
        ).select_related('unit__unit_property').first()

        if not current_lease:
            return render(request, 'tenant/portal.html', {
                'current_lease': None,
                'invoices': [],
                'total_paid': 0,
                'total_arrears': 0,
            })

        # Get invoices
        invoices = Invoice.objects.filter(
            lease=current_lease
        ).order_by('-billing_month')

        # Calculate statistics
        total_paid = sum(inv.amount_paid for inv in invoices)
        total_arrears = sum(inv.balance for inv in invoices if inv.balance > 0)

        context = {
            'current_lease': current_lease,
            'invoices': invoices,
            'total_paid': total_paid,
            'total_arrears': total_arrears,
        }

        return render(request, 'tenant/portal.html', context)