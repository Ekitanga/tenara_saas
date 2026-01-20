from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom User model with role-based access control.
    Supports three roles: Super Admin, Landlord, and Tenant.
    """
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('landlord', 'Landlord'),
        ('tenant', 'Tenant'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='landlord')
    phone_number = models.CharField(max_length=15, blank=True)
    is_active_account = models.BooleanField(default=True, help_text='Account can be suspended by super admin')
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_superadmin(self):
        return self.is_superuser or self.role == 'superadmin'
    
    @property
    def is_landlord(self):
        return self.role == 'landlord' and not self.is_superuser
    
    @property
    def is_tenant(self):
        return self.role == 'tenant' and not self.is_superuser


class LandlordProfile(models.Model):
    """
    Extended profile for landlord users.
    Stores business information and API credentials.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='landlord_profile')
    business_name = models.CharField(max_length=255, blank=True)
    subscription = models.ForeignKey(
        'subscriptions.Subscription', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='landlord_profiles'
    )
    
    # M-Pesa API Credentials (Per Landlord)
    mpesa_consumer_key = models.CharField(max_length=255, blank=True)
    mpesa_consumer_secret = models.CharField(max_length=255, blank=True)
    mpesa_shortcode = models.CharField(max_length=20, blank=True)
    mpesa_passkey = models.TextField(blank=True)
    
    # Bonga SMS API Credentials (Per Landlord)
    bonga_api_key = models.CharField(max_length=255, blank=True)
    bonga_sender_id = models.CharField(max_length=20, default='TENARA')
    
    # SMTP Email Credentials (Per Landlord)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'landlord_profiles'
        verbose_name = 'Landlord Profile'
        verbose_name_plural = 'Landlord Profiles'
    
    def __str__(self):
        return f"{self.user.username} - {self.business_name or 'Profile'}"
    
    @property
    def is_subscription_active(self):
        """Check if landlord has an active subscription"""
        if not self.subscription:
            return False
        return self.subscription.get_is_active()
    
    @property
    def units_used(self):
        """Count total units across all properties"""
        from properties.models import Unit
        return Unit.objects.filter(unit_property__landlord=self).count()
    
    @property
    def units_remaining(self):
        """Calculate remaining units based on subscription plan"""
        if not self.subscription:
            return 0
        return self.subscription.plan.max_units - self.units_used
    
    @property
    def can_add_units(self):
        """Check if landlord can add more units"""
        if not self.subscription:
            return False
        return self.units_used < self.subscription.plan.max_units


class TenantProfile(models.Model):
    """
    Extended profile for tenant users.
    Stores tenant-specific information.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_profile')
    national_id = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_profiles'
        verbose_name = 'Tenant Profile'
        verbose_name_plural = 'Tenant Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Tenant"
    
    @property
    def current_lease(self):
        """Get tenant's active lease"""
        from tenants_mgmt.models import Lease
        return Lease.objects.filter(tenant=self, status='active').first()
    
    @property
    def current_unit(self):
        """Get tenant's current unit"""
        lease = self.current_lease
        return lease.unit if lease else None