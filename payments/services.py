from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Payment


@transaction.atomic
def confirm_payment(payment, *, receipt_number=''):
    """Confirm one payment and update its invoice exactly once."""
    locked = Payment.objects.select_for_update().select_related('invoice').get(pk=payment.pk)
    if locked.status == 'confirmed':
        return locked
    if locked.status == 'failed':
        raise ValueError('A failed payment cannot be confirmed.')
    invoice = locked.invoice.__class__.objects.select_for_update().get(pk=locked.invoice_id)
    amount = Decimal(str(locked.amount))
    balance = Decimal(str(invoice.total_amount - invoice.amount_paid))
    if amount > balance:
        raise ValueError('Payment exceeds the invoice balance.')
    locked.status = 'confirmed'
    locked.confirmed_at = timezone.now()
    if receipt_number:
        locked.mpesa_receipt_number = receipt_number
        locked.transaction_id = receipt_number
    locked.save(update_fields=['status', 'confirmed_at', 'mpesa_receipt_number', 'transaction_id', 'updated_at'])
    from .models import PaymentAudit
    PaymentAudit.objects.create(payment=locked, action='confirmed', status=locked.status, amount=locked.amount, actor=locked.recorded_by, notes='Payment confirmed and applied to invoice.')
    invoice.amount_paid = Decimal(str(invoice.amount_paid)) + amount
    invoice.save(update_fields=['amount_paid', 'status', 'total_amount', 'updated_at'])
    return locked
