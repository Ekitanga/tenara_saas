"""
Management command to set up demo data for TENARA SaaS
Run with: python manage.py setup_demo
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from accounts.models import User, LandlordProfile, TenantProfile
from subscriptions.models import SubscriptionPlan, Subscription
from properties.models import Property, Unit
from tenants_mgmt.models import Lease
from invoicing.models import Invoice
from payments.models import Payment
from expenses.models import Expense
from reminders.models import Reminder
import random


class Command(BaseCommand):
    help = 'Set up demo data for TENARA SaaS'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🚀 Setting up TENARA Demo...'))
        
        # Clear existing demo data
        self.clear_demo_data()
        
        # Create demo landlord
        demo_landlord = self.create_demo_landlord()
        
        # Create subscription
        self.create_subscription(demo_landlord)
        
        # Create properties and units
        properties = self.create_properties(demo_landlord)
        
        # Create tenants and leases
        tenants = self.create_tenants_and_leases(demo_landlord, properties)
        
        # Create invoices
        self.create_invoices(tenants)
        
        # Create payments
        self.create_payments()
        
        # Create expenses
        self.create_expenses(demo_landlord, properties)
        
        # Create reminders
        self.create_reminders(demo_landlord, properties)
        
        self.stdout.write(self.style.SUCCESS('✅ Demo setup complete!'))
        self.stdout.write(self.style.SUCCESS('📧 Demo Login: demo@tenara.com'))
        self.stdout.write(self.style.SUCCESS('🔑 Password: demo1234'))

    def clear_demo_data(self):
        """Remove existing demo data"""
        self.stdout.write('🧹 Clearing existing demo data...')
        User.objects.filter(username='demolandlord').delete()

    def create_demo_landlord(self):
        """Create demo landlord account"""
        self.stdout.write('👤 Creating demo landlord...')
        
        user = User.objects.create_user(
            username='demolandlord',
            email='demo@tenara.com',
            password='demo1234',
            first_name='Demo',
            last_name='Landlord',
            role='landlord',
            phone_number='+254712345678'
        )
        
        landlord = LandlordProfile.objects.create(
            user=user,
            business_name='Demo Properties Ltd',
            bonga_sender_id='TENARA'
        )
        
        return landlord

    def create_subscription(self, landlord):
        """Create active subscription"""
        self.stdout.write('💳 Creating subscription...')
        
        # Get or create PRO plan
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name='PRO',
            defaults={
                'max_units': 20,
                'monthly_price': Decimal('2999.00'),
                'features': {
                    'unlimited_properties': True,
                    'unlimited_tenants': True,
                    'reports': True,
                    'sms_notifications': True
                }
            }
        )
        
        subscription = Subscription.objects.create(
            landlord=landlord,
            plan=plan,
            status='active',
            start_date=timezone.now().date() - timedelta(days=60),
            end_date=timezone.now().date() + timedelta(days=20),
            auto_renew=True
        )
        
        landlord.subscription = subscription
        landlord.save()

    def create_properties(self, landlord):
        """Create demo properties with units"""
        self.stdout.write('🏢 Creating properties and units...')
        
        properties_data = [
            {
                'name': 'Sunset Apartments',
                'location': 'Kilimani, Nairobi',
                'description': 'Modern 2-bedroom apartments in prime location',
                'units': [
                    {'number': 'A1', 'type': '2bedroom', 'rent': 25000},
                    {'number': 'A2', 'type': '2bedroom', 'rent': 25000},
                    {'number': 'A3', 'type': '2bedroom', 'rent': 26000},
                    {'number': 'A4', 'type': '2bedroom', 'rent': 26000},
                    {'number': 'B1', 'type': '1bedroom', 'rent': 18000},
                    {'number': 'B2', 'type': '1bedroom', 'rent': 18000},
                ]
            },
            {
                'name': 'Green Valley Studios',
                'location': 'Westlands, Nairobi',
                'description': 'Affordable bedsitters for young professionals',
                'units': [
                    {'number': '101', 'type': 'bedsitter', 'rent': 12000},
                    {'number': '102', 'type': 'bedsitter', 'rent': 12000},
                    {'number': '103', 'type': 'bedsitter', 'rent': 13000},
                    {'number': '104', 'type': 'studio', 'rent': 15000},
                ]
            },
            {
                'name': 'Parkside Commercial Plaza',
                'location': 'CBD, Nairobi',
                'description': 'Prime commercial units in the heart of the city',
                'units': [
                    {'number': 'S1', 'type': 'shop', 'rent': 35000},
                    {'number': 'S2', 'type': 'shop', 'rent': 40000},
                    {'number': 'O1', 'type': 'office', 'rent': 45000},
                ]
            }
        ]
        
        properties = []
        for prop_data in properties_data:
            property_obj = Property.objects.create(
                landlord=landlord,
                name=prop_data['name'],
                location=prop_data['location'],
                description=prop_data['description']
            )
            
            for unit_data in prop_data['units']:
                Unit.objects.create(
                    unit_property=property_obj,
                    unit_number=unit_data['number'],
                    unit_type=unit_data['type'],
                    monthly_rent=Decimal(str(unit_data['rent'])),
                    garbage_fee=Decimal('200.00'),
                    water_billing_type='fixed',
                    water_fixed_amount=Decimal('500.00')
                )
            
            properties.append(property_obj)
        
        return properties

    def create_tenants_and_leases(self, landlord, properties):
        """Create demo tenants with active leases"""
        self.stdout.write('👥 Creating tenants and leases...')
        
        tenants_data = [
            {'first': 'John', 'last': 'Kamau', 'email': 'john.kamau@email.com', 'phone': '+254722111222'},
            {'first': 'Mary', 'last': 'Wanjiru', 'email': 'mary.w@email.com', 'phone': '+254733222333'},
            {'first': 'Peter', 'last': 'Ochieng', 'email': 'p.ochieng@email.com', 'phone': '+254744333444'},
            {'first': 'Grace', 'last': 'Akinyi', 'email': 'grace.a@email.com', 'phone': '+254755444555'},
            {'first': 'David', 'last': 'Mwangi', 'email': 'd.mwangi@email.com', 'phone': '+254766555666'},
            {'first': 'Sarah', 'last': 'Njeri', 'email': 's.njeri@email.com', 'phone': '+254777666777'},
            {'first': 'James', 'last': 'Otieno', 'email': 'j.otieno@email.com', 'phone': '+254788777888'},
            {'first': 'Jane', 'last': 'Muthoni', 'email': 'jane.m@email.com', 'phone': '+254799888999'},
        ]
        
        # Get all units
        all_units = Unit.objects.filter(unit_property__landlord=landlord)
        
        leases = []
        for i, tenant_data in enumerate(tenants_data[:len(all_units)]):
            # Create tenant user
            user = User.objects.create_user(
                username=f"tenant{i+1}",
                email=tenant_data['email'],
                password='demo1234',
                first_name=tenant_data['first'],
                last_name=tenant_data['last'],
                role='tenant',
                phone_number=tenant_data['phone']
            )
            
            tenant_profile = TenantProfile.objects.create(
                user=user,
                national_id=f'{random.randint(10000000, 99999999)}',
                emergency_contact='+254700000000',
                emergency_contact_name='Emergency Contact'
            )
            
            # Assign to unit
            unit = all_units[i]
            
            # Create lease (some recent, some older)
            months_ago = random.randint(2, 18)
            start_date = timezone.now().date() - timedelta(days=months_ago * 30)
            
            lease = Lease.objects.create(
                unit=unit,
                tenant=tenant_profile,
                start_date=start_date,
                status='active',
                deposit_amount=unit.monthly_rent,
                deposit_paid=True,
                deposit_paid_date=start_date,
                rent_amount=unit.monthly_rent,
                move_in_date=start_date
            )
            
            leases.append(lease)
        
        return leases

    def create_invoices(self, leases):
        """Create invoices for the past 3 months"""
        self.stdout.write('📄 Creating invoices...')
        
        today = timezone.now().date()
        
        for lease in leases:
            # Create invoices for last 3 months
            for month_offset in range(3):
                billing_date = date(today.year, today.month, 1) - timedelta(days=month_offset * 30)
                billing_date = billing_date.replace(day=1)
                due_date = billing_date.replace(day=5)
                
                # Skip if before lease start
                if billing_date < lease.start_date:
                    continue
                
                invoice = Invoice.objects.create(
                    lease=lease,
                    billing_month=billing_date,
                    due_date=due_date,
                    rent_amount=lease.rent_amount,
                    water_amount=lease.unit.water_fixed_amount,
                    garbage_amount=lease.unit.garbage_fee,
                    other_charges=Decimal('0.00')
                )

    def create_payments(self):
        """Create payment records"""
        self.stdout.write('💰 Creating payments...')
        
        invoices = Invoice.objects.all()
        
        for invoice in invoices:
            # 70% chance of payment
            if random.random() < 0.7:
                # Some full, some partial
                if random.random() < 0.8:
                    amount = invoice.total_amount
                else:
                    amount = invoice.total_amount * Decimal('0.5')
                
                payment = Payment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    payment_method=random.choice(['mpesa', 'cash', 'bank']),
                    mpesa_receipt_number=f'QBR{random.randint(100000, 999999)}' if random.random() < 0.6 else '',
                    phone_number=invoice.tenant.user.phone_number,
                    status='confirmed',
                    payment_date=invoice.due_date + timedelta(days=random.randint(-2, 10))
                )
                payment.confirm_payment()

    def create_expenses(self, landlord, properties):
        """Create expense records"""
        self.stdout.write('💸 Creating expenses...')
        
        expenses_data = [
            {'category': 'repairs', 'desc': 'Plumbing repair - Unit A1', 'amount': 5500},
            {'category': 'electricity', 'desc': 'Common area electricity bill', 'amount': 8200},
            {'category': 'maintenance', 'desc': 'Elevator service and maintenance', 'amount': 12000},
            {'category': 'cleaning', 'desc': 'Monthly cleaning service', 'amount': 6000},
            {'category': 'security', 'desc': 'Security guard salary', 'amount': 25000},
            {'category': 'water', 'desc': 'Water bill - Main meter', 'amount': 15000},
        ]
        
        for exp_data in expenses_data:
            Expense.objects.create(
                landlord=landlord,
                expense_property=random.choice(properties),
                category=exp_data['category'],
                description=exp_data['desc'],
                amount=Decimal(str(exp_data['amount'])),
                expense_date=timezone.now().date() - timedelta(days=random.randint(1, 60)),
                vendor_name='Demo Vendor Co.'
            )

    def create_reminders(self, landlord, properties):
        """Create reminder records"""
        self.stdout.write('⏰ Creating reminders...')
        
        reminders_data = [
            {
                'title': 'Property Tax Payment Due',
                'desc': 'Annual property tax payment deadline approaching',
                'days': 15
            },
            {
                'title': 'Insurance Renewal',
                'desc': 'Building insurance policy up for renewal',
                'days': 30
            },
            {
                'title': 'Elevator Inspection',
                'desc': 'Quarterly elevator safety inspection required',
                'days': 7
            },
            {
                'title': 'Water Meter Reading',
                'desc': 'Monthly water meter readings for all units',
                'days': 3
            },
        ]
        
        for rem_data in reminders_data:
            Reminder.objects.create(
                landlord=landlord,
                reminder_property=random.choice(properties),
                title=rem_data['title'],
                description=rem_data['desc'],
                reminder_date=timezone.now().date() + timedelta(days=rem_data['days']),
                frequency='once',
                is_active=True
            )