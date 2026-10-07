from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from .models import User, LandlordProfile, TenantProfile


class SignupView(View):
    def get(self, request):
        return render(request, 'accounts/signup.html')

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        phone_number = request.POST.get('phone_number')
        business_name = request.POST.get('business_name')

        if password != password2:
            messages.error(request, 'Passwords do not match')
            return redirect('accounts:signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('accounts:signup')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone_number=phone_number,
            role='landlord'
        )

        landlord_profile = LandlordProfile.objects.create(
            user=user,
            business_name=business_name
        )

        login(request, user)
        messages.success(request, 'Welcome to TENARA! Your rental workspace is ready.')
        return redirect('dashboard')


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return self.redirect_by_role(request.user)
        return render(request, 'accounts/login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active_account:
                login(request, user)
                return self.redirect_by_role(user)
            else:
                messages.error(request, 'Your account has been suspended')
        else:
            messages.error(request, 'Invalid username or password')

        return redirect('accounts:login')

    def redirect_by_role(self, user):
        if user.is_superuser:
            return redirect('superadmin:dashboard')
        elif user.is_landlord:
            return redirect('dashboard')
        elif user.is_tenant:
            return redirect('tenants:portal')
        return redirect('demo:home')


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.success(request, 'You have been logged out')
        return redirect('demo:home')


class PasswordResetView(View):
    def get(self, request):
        return render(request, 'accounts/password_reset.html')

    def post(self, request):
        email = request.POST.get('email')
        messages.success(request, 'Password reset link sent to your email')
        return redirect('accounts:login')


class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'accounts/profile.html', {'landlord_profile': getattr(request, 'landlord', None)})

    def post(self, request):
        if request.user.is_landlord:
            profile = request.landlord
            profile.business_name = request.POST.get('business_name', '')
            profile.save()
            messages.success(request, 'Profile updated successfully')

        return redirect('accounts:profile')