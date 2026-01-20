from django.db import models
from decimal import Decimal
from accounts.models import LandlordProfile


class Property(models.Model):
    """
    Property model representing a building or complex.
    Each landlord can have multiple properties.
    """
    landlord = models.ForeignKey(
        LandlordProfile,
        on_delete=models.CASCADE,
        related_name='properties'
    )
    name = models.CharField(max_length=255, help_text='Property name or building name')
    location = models.CharField(max_length=255, help_text='Physical location/address')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties'
        ordering = ['name']
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'

    def __str__(self):
        return f"{self.name} - {self.location}"

    def get_total_units(self):
        return self.units.count()

    def get_occupied_units(self):
        return self.units.filter(lease__status='active').distinct().count()

    def get_vacant_units(self):
        return self.get_total_units() - self.get_occupied_units()

    def get_occupancy_rate(self):
        total = self.get_total_units()
        if total == 0:
            return 0
        occupied = self.get_occupied_units()
        return (occupied / total) * 100

    def get_vacancy_rate(self):
        total = self.get_total_units()
        if total == 0:
            return 0
        occupied = self.get_occupied_units()
        return ((total - occupied) / total) * 100


class Unit(models.Model):
    """
    Individual rental unit within a property.
    Configurable rent and utility charges.
    """
    UNIT_TYPE_CHOICES = [
        ('bedsitter', 'Bedsitter'),
        ('1bedroom', '1 Bedroom'),
        ('2bedroom', '2 Bedroom'),
        ('3bedroom', '3 Bedroom'),
        ('studio', 'Studio'),
        ('shop', 'Shop'),
        ('office', 'Office'),
        ('other', 'Other'),
    ]

    WATER_BILLING_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('metered', 'Metered'),
        ('included', 'Included in Rent'),
    ]

    unit_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=50, help_text='Unit number or identifier')
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, help_text='Base monthly rent amount')
    garbage_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Monthly garbage collection fee')
    water_billing_type = models.CharField(max_length=20, choices=WATER_BILLING_CHOICES, default='fixed')
    water_fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Fixed monthly water charge')
    water_rate_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Rate per cubic meter if metered')
    
    # For metered water - store last reading
    last_water_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Last water meter reading')
    last_reading_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'units'
        unique_together = ['unit_property', 'unit_number']
        ordering = ['unit_number']
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'

    def __str__(self):
        return f"{self.unit_property.name} - Unit {self.unit_number}"

    def is_occupied(self):
        return self.lease.filter(status='active').exists()

    def get_current_tenant(self):
        lease = self.lease.filter(status='active').first()
        return lease.tenant if lease else None

    def get_water_charge(self, current_reading=None):
        """
        Calculate water charge based on billing type.
        For metered: requires current_reading parameter
        For fixed: returns fixed amount
        For included: returns 0
        """
        if self.water_billing_type == 'included':
            return Decimal('0.00')
        elif self.water_billing_type == 'fixed':
            return self.water_fixed_amount
        elif self.water_billing_type == 'metered':
            if current_reading is not None:
                # Calculate consumption
                consumption = Decimal(str(current_reading)) - self.last_water_reading
                if consumption < 0:
                    consumption = Decimal('0.00')
                return consumption * self.water_rate_per_unit
            else:
                # No reading provided, return 0 (will need manual entry)
                return Decimal('0.00')
        return Decimal('0.00')

    def update_water_reading(self, new_reading):
        """Update the water meter reading"""
        from django.utils import timezone
        self.last_water_reading = Decimal(str(new_reading))
        self.last_reading_date = timezone.now().date()
        self.save()


class WaterReading(models.Model):
    """
    Water meter readings for metered units.
    Allows tracking consumption over time.
    """
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='water_readings')
    reading_date = models.DateField()
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2)
    consumption = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='water_readings_recorded'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'water_readings'
        ordering = ['-reading_date']
        verbose_name = 'Water Reading'
        verbose_name_plural = 'Water Readings'

    def __str__(self):
        return f"{self.unit} - {self.reading_date} ({self.consumption} units)"

    def save(self, *args, **kwargs):
        # Calculate consumption and amount
        self.consumption = self.current_reading - self.previous_reading
        if self.consumption < 0:
            self.consumption = Decimal('0.00')
        self.amount = self.consumption * self.unit.water_rate_per_unit
        
        # Update unit's last reading
        self.unit.last_water_reading = self.current_reading
        self.unit.last_reading_date = self.reading_date
        self.unit.save()
        
        super().save(*args, **kwargs)