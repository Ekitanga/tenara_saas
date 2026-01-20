from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from .models import SubscriptionPlan


class PlansView(View):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'subscriptions/plans.html', {'plans': plans})


class ManageSubscriptionView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'subscriptions/manage.html')


class SubscriptionExpiredView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'subscriptions/expired.html')


class UpgradeSubscriptionView(LoginRequiredMixin, View):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'subscriptions/upgrade.html', {'plans': plans})