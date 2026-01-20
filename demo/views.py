from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login
from accounts.models import User


class HomeView(View):
    """Marketing homepage"""
    def get(self, request):
        return render(request, 'marketing/home.html')


class DemoView(View):
    """Live demo view - auto-login as demo user"""
    def get(self, request):
        # Check if demo user exists
        try:
            demo_user = User.objects.get(username='demolandlord')
            # Auto-login the demo user
            login(request, demo_user, backend='django.contrib.auth.backends.ModelBackend')
            # Redirect to landlord dashboard
            return redirect('dashboard')
        except User.DoesNotExist:
            # Demo not set up yet - show setup message
            return render(request, 'marketing/demo.html', {
                'demo_ready': False,
                'message': 'Demo data not found. Please run: python manage.py setup_demo'
            })