from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from decimal import Decimal
from .models import Payment
from invoicing.models import Invoice
import json
import logging

logger = logging.getLogger(__name__)


class PaymentListView(LoginRequiredMixin, View):
    """List all payments for the landlord"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # Get filter parameters
        status_filter = request.GET.get('status', 'all')
        method_filter = request.GET.get('method', 'all')

        # Base queryset
        payments = Payment.objects.filter(
            invoice__lease__unit__unit_property__landlord=request.landlord
        ).select_related(
            'invoice__lease__tenant__user',
            'invoice__lease__unit__unit_property',
            'recorded_by'
        ).order_by('-payment_date')

        # Apply filters
        if status_filter != 'all':
            payments = payments.filter(status=status_filter)

        if method_filter != 'all':
            payments = payments.filter(payment_method=method_filter)

        # Calculate summary statistics
        from django.db.models import Sum, Count, Q

        stats = payments.filter(status='confirmed').aggregate(
            total_confirmed=Sum('amount'),
            count_mpesa=Count('id', filter=Q(payment_method='mpesa')),
            count_cash=Count('id', filter=Q(payment_method='cash')),
            count_bank=Count('id', filter=Q(payment_method='bank')),
            count_cheque=Count('id', filter=Q(payment_method='cheque')),
        )

        pending_amount = payments.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0

        context = {
            'payments': payments[:100],
            'status_filter': status_filter,
            'method_filter': method_filter,
            'stats': stats,
            'pending_amount': pending_amount,
        }

        return render(request, 'landlord/payment_list.html', context)


class RecordManualPaymentView(LoginRequiredMixin, View):
    """Manually record a payment (cash, bank transfer, cheque, etc.)"""

    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # Get invoice ID if provided in query params
        invoice_id = request.GET.get('invoice')
        selected_invoice = None

        if invoice_id:
            selected_invoice = get_object_or_404(
                Invoice,
                pk=invoice_id,
                lease__unit__unit_property__landlord=request.landlord
            )

        # Get all unpaid/partially paid invoices
        unpaid_invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=request.landlord,
            status__in=['pending', 'overdue', 'partial']
        ).select_related(
            'lease__tenant__user',
            'lease__unit__unit_property'
        ).order_by('-billing_month')

        context = {
            'unpaid_invoices': unpaid_invoices,
            'selected_invoice': selected_invoice,
        }

        return render(request, 'landlord/record_payment.html', context)

    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        # Get form data
        invoice_id = request.POST.get('invoice')
        amount_str = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        payment_date = request.POST.get('payment_date', timezone.now().date())
        notes = request.POST.get('notes', '')
        payment_proof = request.FILES.get('payment_proof')

        # For non-M-Pesa payments
        reference_number = request.POST.get('reference_number', '')

        # Validate required fields
        if not all([invoice_id, amount_str, payment_method]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('payments:record_manual')

        # Get invoice and verify ownership
        invoice = get_object_or_404(
            Invoice,
            pk=invoice_id,
            lease__unit__unit_property__landlord=request.landlord
        )

        # Validate amount - convert to Decimal
        try:
            amount = Decimal(str(amount_str))
            if amount <= 0:
                raise ValueError('Amount must be positive')
        except (ValueError, Exception):
            messages.error(request, 'Invalid amount.')
            return redirect('payments:record_manual')

        # Check if amount exceeds balance
        invoice_balance = Decimal(str(invoice.balance))
        if amount > invoice_balance:
            messages.warning(
                request,
                f'Payment amount (KES {amount:,.2f}) exceeds invoice balance (KES {invoice_balance:,.2f}). '
                f'Recording payment for the balance only.'
            )
            amount = invoice_balance

        # Create payment record
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            is_manual=True,
            recorded_by=request.user,
            notes=notes,
            payment_proof=payment_proof,
            status='confirmed',
            payment_date=payment_date,
            confirmed_at=timezone.now(),
            transaction_id=reference_number or f'MANUAL-{timezone.now().strftime("%Y%m%d%H%M%S")}'
        )

        # Update invoice amount_paid - ensure Decimal types
        current_paid = Decimal(str(invoice.amount_paid or 0))
        invoice.amount_paid = current_paid + amount
        invoice.save()

        messages.success(
            request,
            f'Payment of KES {amount:,.2f} recorded successfully! Invoice balance: KES {invoice.balance:,.2f}'
        )

        return redirect('invoicing:detail', pk=invoice.pk)


class InitiateMpesaPaymentView(View):
    """Initiate M-Pesa STK Push payment (for tenants)"""

    @transaction.atomic
    def post(self, request):
        """Handle M-Pesa payment initiation"""

        try:
            # Get data from request
            invoice_id = request.POST.get('invoice_id')
            phone_number = request.POST.get('phone_number')
            amount_str = request.POST.get('amount')

            # Validate required fields
            if not all([invoice_id, phone_number, amount_str]):
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required fields'
                }, status=400)

            # Get invoice
            invoice = get_object_or_404(Invoice, pk=invoice_id)

            # Validate amount - convert to Decimal
            try:
                amount = Decimal(str(amount_str))
                if amount <= 0:
                    raise ValueError('Amount must be positive')
            except (ValueError, Exception):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid amount'
                }, status=400)

            # Sanitize phone number (remove spaces, +, etc.)
            phone_number = phone_number.replace(' ', '').replace('+', '')

            # Ensure phone starts with 254
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif not phone_number.startswith('254'):
                phone_number = '254' + phone_number

            # Create pending payment record
            payment = Payment.objects.create(
                invoice=invoice,
                amount=amount,
                payment_method='mpesa',
                phone_number=phone_number,
                status='pending',
                transaction_id=f'PENDING-{timezone.now().strftime("%Y%m%d%H%M%S")}'
            )

            # TODO: Actual M-Pesa API integration here
            # For now, we'll simulate a successful response

            return JsonResponse({
                'success': True,
                'message': 'M-Pesa payment initiated. Please check your phone for the payment prompt.',
                'payment_id': payment.id,
                'checkout_request_id': 'SIMULATED-CHECKOUT-ID'
            })

        except Exception as e:
            logger.error(f'M-Pesa initiation error: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': f'Error initiating payment: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(View):
    """Handle M-Pesa payment callback/notification"""

    def post(self, request):
        """Process M-Pesa callback"""

        try:
            # Parse callback data
            callback_data = json.loads(request.body)

            logger.info(f'M-Pesa callback received: {callback_data}')

            # Extract relevant data from callback
            result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
            checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')

            # Extract metadata
            callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])

            mpesa_receipt = None
            phone_number = None
            transaction_date = None
            amount = None

            for item in callback_metadata:
                name = item.get('Name')
                value = item.get('Value')

                if name == 'MpesaReceiptNumber':
                    mpesa_receipt = value
                elif name == 'PhoneNumber':
                    phone_number = value
                elif name == 'TransactionDate':
                    transaction_date = value
                elif name == 'Amount':
                    amount = Decimal(str(value)) if value else None

            # Find payment record
            payment = Payment.objects.filter(
                phone_number__icontains=str(phone_number)[-9:] if phone_number else '',
                status='pending'
            ).order_by('-created_at').first()

            if not payment:
                logger.warning(f'Payment not found for callback: {callback_data}')
                return HttpResponse('OK')

            # Check result code
            if result_code == 0:
                # Payment successful
                payment.status = 'confirmed'
                payment.mpesa_receipt_number = mpesa_receipt
                payment.transaction_id = mpesa_receipt
                payment.confirmed_at = timezone.now()
                payment.save()

                # Update invoice - ensure Decimal types
                current_paid = Decimal(str(payment.invoice.amount_paid or 0))
                payment_amount = Decimal(str(payment.amount or 0))
                payment.invoice.amount_paid = current_paid + payment_amount
                payment.invoice.save()

                logger.info(f'Payment {payment.id} confirmed via M-Pesa: {mpesa_receipt}')

            else:
                # Payment failed
                payment.status = 'failed'
                payment.notes = f'M-Pesa payment failed: {result_desc}'
                payment.save()

                logger.warning(f'Payment {payment.id} failed: {result_desc}')

            return HttpResponse('OK')

        except Exception as e:
            logger.error(f'M-Pesa callback error: {str(e)}')
            return HttpResponse('ERROR', status=500)

    def get(self, request):
        """Handle GET requests (validation URL)"""
        return HttpResponse('OK')


class PaymentDetailView(LoginRequiredMixin, View):
    """View payment details"""

    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        payment = get_object_or_404(
            Payment,
            pk=pk,
            invoice__lease__unit__unit_property__landlord=request.landlord
        )

        return render(request, 'landlord/payment_detail.html', {
            'payment': payment
        })


class ConfirmPaymentView(LoginRequiredMixin, View):
    """Manually confirm a pending payment"""

    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        payment = get_object_or_404(
            Payment,
            pk=pk,
            invoice__lease__unit__unit_property__landlord=request.landlord
        )

        if payment.status == 'confirmed':
            messages.warning(request, 'Payment is already confirmed.')
            return redirect('payments:payment_list')

        # Confirm payment
        payment.confirm_payment()

        messages.success(request, f'Payment of KES {payment.amount:,.2f} confirmed successfully!')
        return redirect('invoicing:detail', pk=payment.invoice.pk)


class DeletePaymentView(LoginRequiredMixin, View):
    """Delete a payment record (only pending/failed)"""

    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')

        payment = get_object_or_404(
            Payment,
            pk=pk,
            invoice__lease__unit__unit_property__landlord=request.landlord
        )

        # Don't allow deleting confirmed payments
        if payment.status == 'confirmed':
            messages.error(request, 'Cannot delete a confirmed payment.')
            return redirect('payments:payment_list')

        invoice_pk = payment.invoice.pk
        payment.delete()

        messages.success(request, 'Payment record deleted successfully!')
        return redirect('invoicing:detail', pk=invoice_pk)