from django.test import TestCase
from django.urls import reverse

from accounts.models import LandlordProfile, User


class CoreSignupTests(TestCase):
    def test_landlord_can_create_workspace_without_subscription_plan(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'new-landlord',
            'email': 'owner@example.com',
            'phone_number': '0712345678',
            'business_name': 'Sunrise Properties',
            'password': 'Strong-pass123',
            'password2': 'Strong-pass123',
        })

        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(username='new-landlord')
        profile = LandlordProfile.objects.get(user=user)
        self.assertEqual(profile.business_name, 'Sunrise Properties')
        self.assertIsNone(profile.subscription)

    def test_core_mode_does_not_show_deferred_navigation_items(self):
        user = User.objects.create_user(username='landlord', password='Strong-pass123', role='landlord')
        LandlordProfile.objects.create(user=user, business_name='Test')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Properties')
        self.assertNotContains(response, 'Subscription')
        self.assertNotContains(response, 'Reminders')
