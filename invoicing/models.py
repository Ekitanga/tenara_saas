from django.db import models
from django.utils import timezone
from tenants_mgmt.models import Lease
import uuid
from decimal import Decimal
from datetime import date


class Invoice(models.Model):
    """
    Monthly invoice/bill for a tenant.
    Auto-generated or manually created by landlord.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True, editable=False)

    # Billing Period
    billing_month = models.DateField(help_text='Month being billed (first day of month)')
    due_date = models.DateField(help_text='Payment due date')

    # Bill Breakdown
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Monthly rent charge')
    water_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Water charge for the month')
    garbage_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Garbage collection fee')
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Other charges (repairs, penalties, etc.)')

    # Totals
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, help_text='Total invoice amount')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Total amount paid against this invoice')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Water Meter Reading (for metered units)
    water_meter_reading = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    previous_meter_reading = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-billing_month', '-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        unique_together = ['lease', 'billing_month']

    def save(self, *args, **kwargs):
        """Auto-generate invoice number and calculate totals"""
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()

        # Ensure numeric fields are Decimal
        self.rent_amount = Decimal(str(self.rent_amount))
        self.water_amount = Decimal(str(self.water_amount))
        self.garbage_amount = Decimal(str(self.garbage_amount))
        self.other_charges = Decimal(str(self.other_charges))
        self.amount_paid = Decimal(str(self.amount_paid))

        # Calculate total amount
        self.total_amount = self.rent_amount + self.water_amount + self.garbage_amount + self.other_charges

        # Ensure due_date is a date object
        if isinstance(self.due_date, str):
            from datetime import datetime
            self.due_date = datetime.strptime(self.due_date, '%Y-%m-%d').date()

        # Update status based on payment
        self.update_status()

        super().save(*args, **kwargs)

    def generate_invoice_number(self):
        month_str = timezone.now().strftime('%Y%m')
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"INV-{month_str}-{unique_id}"

    def update_status(self):
        today = timezone.now().date()
        
        # Ensure due_date is a date object for comparison
        due_date = self.due_date
        if isinstance(due_date, str):
            from datetime import datetime
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif due_date < today:
            self.status = 'overdue'
        else:
            self.status = 'pending'

    def __str__(self):
        return f"{self.invoice_number} - {self.lease.tenant.user.get_full_name()}"

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    @property
    def is_paid(self):
        return self.status == 'paid'

    @property
    def is_overdue(self):
        today = timezone.now().date()
        due_date = self.due_date
        if isinstance(due_date, str):
            from datetime import datetime
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        return self.status == 'overdue' or (due_date < today and not self.is_paid)

    @property
    def days_overdue(self):
        if self.is_overdue:
            today = timezone.now().date()
            due_date = self.due_date
            if isinstance(due_date, str):
                from datetime import datetime
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            return (today - due_date).days
        return 0

    @property
    def landlord(self):
        return self.lease.landlord

    @property
    def tenant(self):
        return self.lease.tenant

    @property
    def unit(self):
        return self.lease.unit

    @property
    def property(self):
        return self.lease.unit.unit_property

    def calculate_water_amount(self):
        unit = self.lease.unit
        if unit.water_billing_type == 'fixed':
            return unit.water_fixed_amount
        elif unit.water_billing_type == 'metered':
            if self.water_meter_reading is not None and self.previous_meter_reading is not None:
                return (self.water_meter_reading - self.previous_meter_reading) * unit.water_rate_per_unit
            return Decimal('0')
        return Decimal('0')

    def record_payment(self, amount):
        self.amount_paid += Decimal(str(amount))
        self.save()