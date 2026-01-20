from django.db import models
from django.utils import timezone
from datetime import timedelta


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('PLUS', 'PLUS'),
        ('PRO', 'PRO'),
        ('BUSINESS', 'BUSINESS'),
        ('ENTERPRISE', 'ENTERPRISE'),
    ]
    
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    max_units = models.IntegerField(help_text='Maximum number of units allowed')
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=dict, help_text='Plan features in JSON format')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_plans'
        ordering = ['monthly_price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return f"{self.name} - {self.max_units} units - KES {self.monthly_price}"


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial'),
    ]
    
    landlord = models.ForeignKey('accounts.LandlordProfile', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
    
    def save(self, *args, **kwargs):
        if not self.end_date:
            if self.status == 'trial':
                self.end_date = timezone.now().date() + timedelta(days=14)
            else:
                self.end_date = timezone.now().date() + timedelta(days=30)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.landlord.user.username} - {self.plan.name} ({self.status})"
    
    def get_is_active(self):
        if self.status == 'suspended':
            return False
        return self.end_date >= timezone.now().date()
    
    def get_days_remaining(self):
        if self.end_date:
            delta = self.end_date - timezone.now().date()
            return max(0, delta.days)
        return 0
    
    def get_is_expiring_soon(self):
        return 0 < self.get_days_remaining() <= 7
    
    def get_is_expired(self):
        return self.end_date < timezone.now().date()


class SubscriptionPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='mpesa')
    transaction_id = models.CharField(max_length=100, unique=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscription_payments'
        ordering = ['-created_at']
        verbose_name = 'Subscription Payment'
        verbose_name_plural = 'Subscription Payments'
    
    def __str__(self):
        return f"Payment {self.transaction_id} - KES {self.amount} ({self.status})"
    
    def confirm_payment(self):
        self.status = 'confirmed'
        self.paid_at = timezone.now()
        self.save()
        
        subscription = self.subscription
        if subscription.end_date < timezone.now().date():
            subscription.end_date = timezone.now().date() + timedelta(days=30)
        else:
            subscription.end_date = subscription.end_date + timedelta(days=30)
        
        subscription.status = 'active'
        subscription.save()