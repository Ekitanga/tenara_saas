from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import LandlordProfile, TenantProfile, User
from expenses.models import Expense
from invoicing.models import Invoice
from payments.models import Payment, PaymentAudit
from payments.services import confirm_payment
from properties.models import Property, Unit
from tenants_mgmt.models import Lease


class CoreRentalWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='Strong-pass123', role='landlord')
        self.landlord = LandlordProfile.objects.create(user=self.user, business_name='Sunrise Properties')
        self.other_user = User.objects.create_user(username='other', password='Strong-pass123', role='landlord')
        self.other_landlord = LandlordProfile.objects.create(user=self.other_user, business_name='Other Properties')
        self.property = Property.objects.create(landlord=self.landlord, name='Sunrise', location='Nairobi')
        self.unit = Unit.objects.create(
            unit_property=self.property, unit_number='A1', unit_type='bedsitter',
            monthly_rent=Decimal('15000'), water_billing_type='included'
        )
        tenant_user = User.objects.create_user(username='tenant_a', password='Strong-pass123', role='tenant')
        tenant_profile = TenantProfile.objects.create(user=tenant_user)
        self.lease = Lease.objects.create(
            unit=self.unit, tenant=tenant_profile, start_date=date(2026, 1, 1),
            rent_amount=Decimal('15000'), status='active'
        )
        self.invoice = Invoice.objects.create(
            lease=self.lease, billing_month=date(2026, 1, 1), due_date=date(2026, 1, 10),
            rent_amount=Decimal('15000')
        )

    def test_complete_workflow_records_payment_once_and_updates_balance(self):
        payment = Payment.objects.create(
            invoice=self.invoice, amount=Decimal('15000'), payment_method='cash',
            is_manual=True, recorded_by=self.user, status='pending'
        )
        confirm_payment(payment)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('15000.00'))
        self.assertEqual(self.invoice.status, 'paid')
        self.assertEqual(PaymentAudit.objects.filter(payment=payment, action='confirmed').count(), 1)
        confirm_payment(payment)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('15000.00'))


    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('accounts:logout')).status_code, 302)

    def test_deferred_routes_are_blocked_in_core_mode(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/subscriptions/plans/').status_code, 404)
        self.assertEqual(self.client.get('/reminders/').status_code, 404)
        self.assertEqual(self.client.post('/payments/mpesa/initiate/').status_code, 404)

    def test_landlord_cannot_access_another_landlords_invoice(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('invoicing:detail', args=[self.invoice.pk]))
        self.assertEqual(response.status_code, 404)

    def test_landlord_dashboard_has_setup_checklist(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Set up your rental workspace')
        self.assertNotContains(response, 'Subscription')
        self.assertNotContains(response, 'Reminders')

    def test_expense_keeps_decimal_precision(self):
        expense = Expense.objects.create(
            landlord=self.landlord, expense_property=self.property, category='repairs',
            description='Plumbing', amount=Decimal('1250.55'), expense_date=date(2026, 1, 5)
        )
        self.assertEqual(expense.amount, Decimal('1250.55'))
