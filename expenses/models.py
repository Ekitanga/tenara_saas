from django.db import models
from accounts.models import LandlordProfile


class Expense(models.Model):
    """
    Expense tracking for property-related costs.
    """
    CATEGORY_CHOICES = [
        ('repairs', 'Repairs'),
        ('electricity', 'Electricity'),
        ('water', 'Water'),
        ('maintenance', 'Maintenance'),
        ('insurance', 'Insurance'),
        ('taxes', 'Property Taxes'),
        ('salaries', 'Salaries/Wages'),
        ('security', 'Security Services'),
        ('cleaning', 'Cleaning Services'),
        ('legal', 'Legal Fees'),
        ('marketing', 'Marketing/Advertising'),
        ('other', 'Other'),
    ]
    
    landlord = models.ForeignKey(LandlordProfile, on_delete=models.CASCADE, related_name='expenses')
    expense_property = models.ForeignKey('properties.Property', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses', help_text='Associated property (optional)')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField(help_text='Detailed description of the expense')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField(help_text='Date expense was incurred')
    receipt = models.FileField(upload_to='expense_receipts/', null=True, blank=True, help_text='Upload receipt or supporting document')
    vendor_name = models.CharField(max_length=255, blank=True, help_text='Vendor/supplier name')
    vendor_contact = models.CharField(max_length=100, blank=True, help_text='Vendor contact')
    notes = models.TextField(blank=True, help_text='Additional notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses'
        ordering = ['-expense_date', '-created_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
    
    def __str__(self):
        return f"{self.get_category_display()} - KES {self.amount} ({self.expense_date})"
    
    def get_property_name(self):
        return self.expense_property.name if self.expense_property else 'General'