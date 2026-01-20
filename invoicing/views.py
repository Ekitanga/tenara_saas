from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q, Count
from decimal import Decimal
from .models import Invoice
from tenants_mgmt.models import Lease
from properties.models import Property, Unit


class InvoiceListView(LoginRequiredMixin, View):
    """List all invoices for the CURRENT landlord only"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # STRICT FILTER: Only invoices for THIS landlord's units
        invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=request.landlord
        ).select_related(
            'lease__tenant__user',
            'lease__unit__unit_property'
        ).order_by('-created_at')

        # Get filter parameters - FIX: Handle empty strings properly
        status_filter = request.GET.get('status', '').strip()
        property_filter = request.GET.get('property', '').strip()
        month_filter = request.GET.get('month', '').strip()

        # Apply filters - FIX: Only filter if value is not empty
        if status_filter and status_filter != 'all':
            invoices = invoices.filter(status=status_filter)

        if property_filter and property_filter != 'all':
            try:
                # Convert to int to ensure it's a valid ID
                property_id = int(property_filter)
                invoices = invoices.filter(lease__unit__unit_property__pk=property_id)
            except (ValueError, TypeError):
                # Invalid property ID, ignore filter
                pass

        if month_filter and month_filter != 'all':
            from datetime import datetime
            try:
                filter_date = datetime.strptime(month_filter, '%Y-%m').date()
                invoices = invoices.filter(billing_month=filter_date)
            except:
                pass

        # ONLY THIS landlord's properties for filter dropdown
        properties = Property.objects.filter(landlord=request.landlord)

        # Calculate statistics - ONLY for THIS landlord
        stats = invoices.aggregate(
            total_count=Count('id'),
            total_billed=Sum('total_amount'),
            total_collected=Sum('amount_paid'),
            total_outstanding=Sum('total_amount') - Sum('amount_paid')
        )

        context = {
            'invoices': invoices,
            'properties': properties,
            'status_filter': status_filter or 'all',
            'property_filter': property_filter or 'all',
            'month_filter': month_filter or 'all',
            'stats': stats,
        }

        return render(request, 'landlord/invoice_list.html', context)


class InvoiceCreateView(LoginRequiredMixin, View):
    """Create a new invoice - ONLY for THIS landlord's tenants"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # STRICT FILTER: Only active leases for THIS landlord's units
        active_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        ).select_related(
            'tenant__user',
            'unit__unit_property'
        )

        return render(request, 'landlord/invoice_form.html', {
            'active_leases': active_leases
        })

    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # Get form data
        lease_id = request.POST.get('lease')
        billing_month = request.POST.get('billing_month')
        due_date = request.POST.get('due_date')
        rent_amount = request.POST.get('rent_amount')
        water_amount = request.POST.get('water_amount', 0)
        garbage_amount = request.POST.get('garbage_amount', 0)
        other_charges = request.POST.get('other_charges', 0)
        notes = request.POST.get('notes', '')

        # CRITICAL: Verify lease belongs to THIS landlord
        lease = get_object_or_404(
            Lease,
            pk=lease_id,
            unit__unit_property__landlord=request.landlord  # ← STRICT CHECK
        )

        # Convert billing_month string to date
        from datetime import datetime
        try:
            billing_month_date = datetime.strptime(billing_month, '%Y-%m').date()
        except:
            messages.error(request, 'Invalid billing month format.')
            return redirect('invoicing:create')

        # Check for duplicate invoice
        existing = Invoice.objects.filter(
            lease=lease,
            billing_month=billing_month_date
        ).exists()

        if existing:
            messages.error(request, f'Invoice for {billing_month} already exists for this tenant.')
            return redirect('invoicing:create')

        # Create invoice
        invoice = Invoice.objects.create(
            lease=lease,
            billing_month=billing_month_date,
            due_date=due_date,
            rent_amount=Decimal(str(rent_amount)),
            water_amount=Decimal(str(water_amount)),
            garbage_amount=Decimal(str(garbage_amount)),
            other_charges=Decimal(str(other_charges)),
            notes=notes
        )

        messages.success(request, f'Invoice {invoice.invoice_number} created successfully!')
        return redirect('invoicing:detail', pk=invoice.pk)


class InvoiceDetailView(LoginRequiredMixin, View):
    """View invoice details - ONLY if belongs to THIS landlord"""

    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # CRITICAL: Verify invoice belongs to THIS landlord
        invoice = get_object_or_404(
            Invoice,
            pk=pk,
            lease__unit__unit_property__landlord=request.landlord  # ← STRICT CHECK
        )

        return render(request, 'landlord/invoice_detail.html', {
            'invoice': invoice
        })


class InvoiceUpdateView(LoginRequiredMixin, View):
    """Update invoice - ONLY if belongs to THIS landlord"""

    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # CRITICAL: Verify invoice belongs to THIS landlord
        invoice = get_object_or_404(
            Invoice,
            pk=pk,
            lease__unit__unit_property__landlord=request.landlord  # ← STRICT CHECK
        )

        # STRICT FILTER: Only THIS landlord's active leases
        active_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        ).select_related('tenant__user', 'unit__unit_property')

        return render(request, 'landlord/invoice_form.html', {
            'invoice': invoice,
            'active_leases': active_leases
        })

    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # CRITICAL: Verify invoice belongs to THIS landlord
        invoice = get_object_or_404(
            Invoice,
            pk=pk,
            lease__unit__unit_property__landlord=request.landlord  # ← STRICT CHECK
        )

        # Don't allow editing paid invoices
        if invoice.status == 'paid':
            messages.error(request, 'Cannot edit a fully paid invoice.')
            return redirect('invoicing:detail', pk=pk)

        # Get form data
        billing_month = request.POST.get('billing_month')
        due_date = request.POST.get('due_date')
        rent_amount = request.POST.get('rent_amount')
        water_amount = request.POST.get('water_amount', 0)
        garbage_amount = request.POST.get('garbage_amount', 0)
        other_charges = request.POST.get('other_charges', 0)
        notes = request.POST.get('notes', '')

        # Update invoice
        from datetime import datetime
        try:
            invoice.billing_month = datetime.strptime(billing_month, '%Y-%m').date()
        except:
            messages.error(request, 'Invalid billing month format.')
            return redirect('invoicing:update', pk=pk)

        invoice.due_date = due_date
        invoice.rent_amount = Decimal(str(rent_amount))
        invoice.water_amount = Decimal(str(water_amount))
        invoice.garbage_amount = Decimal(str(garbage_amount))
        invoice.other_charges = Decimal(str(other_charges))
        invoice.notes = notes
        invoice.save()

        messages.success(request, 'Invoice updated successfully!')
        return redirect('invoicing:detail', pk=pk)


class InvoiceDeleteView(LoginRequiredMixin, View):
    """Delete invoice - ONLY if belongs to THIS landlord"""

    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # CRITICAL: Verify invoice belongs to THIS landlord
        invoice = get_object_or_404(
            Invoice,
            pk=pk,
            lease__unit__unit_property__landlord=request.landlord  # ← STRICT CHECK
        )

        # Don't allow deleting paid invoices
        if invoice.status == 'paid':
            messages.error(request, 'Cannot delete a fully paid invoice.')
            return redirect('invoicing:detail', pk=pk)

        # Don't allow deleting invoices with payments
        if invoice.payments.exists():
            messages.error(request, 'Cannot delete invoice with payments. Delete payments first.')
            return redirect('invoicing:detail', pk=pk)

        invoice_number = invoice.invoice_number
        invoice.delete()

        messages.success(request, f'Invoice {invoice_number} deleted successfully!')
        return redirect('invoicing:list')


class GenerateMonthlyInvoicesView(LoginRequiredMixin, View):
    """Bulk generate invoices - ONLY for THIS landlord's tenants"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # STRICT FILTER: Only THIS landlord's active tenants
        from datetime import datetime, timedelta

        next_month = (timezone.now() + timedelta(days=30)).date()
        suggested_due_date = next_month.replace(day=15)

        # Count active tenants for THIS landlord only
        active_tenants_count = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        ).count()

        # Estimate total
        active_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        )
        estimated_total = sum([lease.rent_amount for lease in active_leases])

        context = {
            'next_month': next_month,
            'suggested_due_date': suggested_due_date,
            'active_tenants_count': active_tenants_count,
            'estimated_total': estimated_total,
        }

        return render(request, 'landlord/generate_invoices.html', context)

    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        billing_month = request.POST.get('billing_month')
        due_date = request.POST.get('due_date')

        # Convert to date
        from datetime import datetime
        try:
            billing_month_date = datetime.strptime(billing_month, '%Y-%m').date()
        except:
            messages.error(request, 'Invalid billing month format.')
            return redirect('invoicing:generate_monthly')

        # STRICT FILTER: Only THIS landlord's active leases
        active_leases = Lease.objects.filter(
            unit__unit_property__landlord=request.landlord,
            status='active'
        ).select_related('unit', 'tenant')

        created_count = 0
        skipped_count = 0

        for lease in active_leases:
            # Check if invoice already exists
            existing = Invoice.objects.filter(
                lease=lease,
                billing_month=billing_month_date
            ).exists()

            if existing:
                skipped_count += 1
                continue

            # Create invoice
            Invoice.objects.create(
                lease=lease,
                billing_month=billing_month_date,
                due_date=due_date,
                rent_amount=lease.rent_amount,
                water_amount=lease.unit.get_water_charge(),
                garbage_amount=lease.unit.garbage_fee,
                other_charges=Decimal('0.00')
            )
            created_count += 1

        messages.success(
            request,
            f'Generated {created_count} invoices for {billing_month_date.strftime("%B %Y")}. '
            f'Skipped {skipped_count} existing invoices.'
        )

        return redirect('invoicing:list')