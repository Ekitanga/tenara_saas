from django.db import models
from django.utils import timezone
from accounts.models import TenantProfile
from properties.models import Unit


class Lease(models.Model):
    """
    Lease agreement linking a tenant to a unit.
    Tracks lease status and deposit information.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]
    
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='lease')
    tenant = models.ForeignKey(TenantProfile, on_delete=models.CASCADE, related_name='leases')
    
    start_date = models.DateField(help_text='Lease start date')
    end_date = models.DateField(null=True, blank=True, help_text='Lease end date (optional)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Deposit Information
    deposit_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Security deposit amount'
    )
    deposit_paid = models.BooleanField(default=False)
    deposit_paid_date = models.DateField(null=True, blank=True)
    
    # Lease Terms
    rent_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Monthly rent amount (frozen at lease creation)'
    )
    
    # Move-in/Move-out
    move_in_date = models.DateField(null=True, blank=True)
    move_out_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True, help_text='Additional notes or terms')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leases'
        ordering = ['-start_date']
        verbose_name = 'Lease'
        verbose_name_plural = 'Leases'
    
    def __str__(self):
        return f"{self.unit} - {self.tenant.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        """Auto-set rent_amount from unit if not set"""
        if not self.rent_amount:
            self.rent_amount = self.unit.monthly_rent
        super().save(*args, **kwargs)
    
    @property
    def landlord(self):
        """Get landlord from unit's property"""
        return self.unit.property.landlord
    
    @property
    def is_active(self):
        """Check if lease is currently active"""
        return self.status == 'active'
    
    @property
    def duration_months(self):
        """Calculate lease duration in months"""
        if self.end_date:
            delta = self.end_date - self.start_date
            return delta.days // 30
        return None
    
    @property
    def is_deposit_pending(self):
        """Check if deposit is still pending"""
        return self.deposit_amount > 0 and not self.deposit_paid
    
    @property
    def total_rent_paid(self):
        """Calculate total rent paid through invoices"""
        from invoicing.models import Invoice
        from django.db.models import Sum
        
        total = Invoice.objects.filter(
            lease=self,
            status='paid'
        ).aggregate(total=Sum('amount_paid'))['total']
        
        return total or 0
    
    @property
    def total_arrears(self):
        """Calculate total outstanding arrears"""
        from invoicing.models import Invoice
        from django.db.models import Sum, F
        
        arrears = Invoice.objects.filter(
            lease=self,
            status__in=['pending', 'overdue', 'partial']
        ).aggregate(
            total=Sum(F('total_amount') - F('amount_paid'))
        )['total']
        
        return arrears or 0
    
    def terminate_lease(self, termination_date=None):
        """Terminate lease and mark as terminated"""
        self.status = 'terminated'
        self.move_out_date = termination_date or timezone.now().date()
        self.save()