from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from core.validators import validate_supporting_file
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
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
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
        validators=[validate_supporting_file],
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
        constraints = [models.CheckConstraint(check=Q(amount__gt=0), name='payment_amount_positive')]
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        method = self.get_payment_method_display()
        manual_flag = " (Manual)" if self.is_manual else ""
        return f"Payment {self.id} - KES {self.amount} ({method}){manual_flag}"

    def save(self, *args, **kwargs):
        # Invoice accounting is handled by payments.services.confirm_payment.
        # Keeping it out of save() prevents duplicate balance updates from admin,
        # callbacks, and ordinary model saves.
        if self.pk:
            previous = Payment.objects.get(pk=self.pk)
            if previous.status == 'confirmed' and self.status != 'confirmed':
                from django.core.exceptions import ValidationError
                raise ValidationError('Confirmed payments cannot be reversed.')
        super().save(*args, **kwargs)

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
        """Confirm and account for this payment exactly once."""
        from .services import confirm_payment
        return confirm_payment(self)

    def fail_payment(self):
        """Mark payment as failed"""
        if self.status != 'failed':
            self.status = 'failed'
            self.save()


class PaymentAudit(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='audit_events')
    action = models.CharField(max_length=50)
    status = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_audit_events')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'payment_audit_events'
