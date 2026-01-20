from django.db import models
from django.utils import timezone
from decimal import Decimal
from invoicing.models import Invoice
from accounts.models import User


class Payment(models.Model):
    """
    Payment record for rent payments.
    Supports M-Pesa and manual payment recording.
    """
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)

    # M-Pesa Fields
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)

    # Manual Payment Fields (landlord recorded)
    is_manual = models.BooleanField(
        default=False,
        help_text='True if payment was manually recorded by landlord'
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_payments',
        help_text='Landlord who recorded this manual payment'
    )
    payment_proof = models.FileField(
        upload_to='payment_proofs/',
        null=True,
        blank=True,
        help_text='Upload payment proof (receipt, screenshot, etc.)'
    )
    notes = models.TextField(blank=True, help_text='Additional notes about this payment')

    # Status and Timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-payment_date']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        method = self.get_payment_method_display()
        manual_flag = " (Manual)" if self.is_manual else ""
        return f"Payment {self.id} - KES {self.amount} ({method}){manual_flag}"

    def save(self, *args, **kwargs):
        """Update invoice when payment is confirmed"""
        is_new = self.pk is None
        old_status = None

        if not is_new:
            old_payment = Payment.objects.get(pk=self.pk)
            old_status = old_payment.status

        super().save(*args, **kwargs)

        # If payment just got confirmed, update invoice
        if self.status == 'confirmed' and old_status != 'confirmed':
            # Ensure both values are Decimal to avoid type errors
            current_paid = Decimal(str(self.invoice.amount_paid or 0))
            payment_amount = Decimal(str(self.amount or 0))
            self.invoice.amount_paid = current_paid + payment_amount
            self.invoice.save()

    @property
    def landlord(self):
        """Get landlord from invoice"""
        return self.invoice.landlord

    @property
    def tenant(self):
        """Get tenant from invoice"""
        return self.invoice.tenant

    @property
    def is_confirmed(self):
        """Check if payment is confirmed"""
        return self.status == 'confirmed'

    @property
    def is_mpesa(self):
        """Check if this is an M-Pesa payment"""
        return self.payment_method == 'mpesa'

    def confirm_payment(self):
        """Mark payment as confirmed"""
        if self.status != 'confirmed':
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()

    def fail_payment(self):
        """Mark payment as failed"""
        if self.status != 'failed':
            self.status = 'failed'
            self.save()
