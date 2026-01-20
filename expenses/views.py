from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import Expense
from properties.models import Property


class ExpenseListView(LoginRequiredMixin, View):
    """List all expenses for the landlord"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Get filter parameters
        category_filter = request.GET.get('category', 'all')
        property_filter = request.GET.get('property', 'all')
        month_filter = request.GET.get('month', '')
        
        # Base queryset
        expenses = Expense.objects.filter(
            landlord=request.landlord
        ).select_related('expense_property').order_by('-expense_date', '-created_at')
        
        # Apply filters
        if category_filter != 'all':
            expenses = expenses.filter(category=category_filter)
        
        if property_filter != 'all':
            try:
                expenses = expenses.filter(expense_property_id=property_filter)
            except ValueError:
                pass
        
        if month_filter:
            try:
                filter_date = timezone.datetime.strptime(month_filter, '%Y-%m').date()
                expenses = expenses.filter(
                    expense_date__year=filter_date.year,
                    expense_date__month=filter_date.month
                )
            except ValueError:
                pass
        
        # Calculate summary statistics
        from django.db.models import Sum, Count, Q
        
        stats = expenses.aggregate(
            total_expenses=Sum('amount'),
            count_repairs=Count('id', filter=Q(category='repairs')),
            count_electricity=Count('id', filter=Q(category='electricity')),
            count_water=Count('id', filter=Q(category='water')),
            count_maintenance=Count('id', filter=Q(category='maintenance')),
        )
        
        # Get properties for filter dropdown
        properties = Property.objects.filter(landlord=request.landlord)
        
        context = {
            'expenses': expenses[:100],  # Limit to 100 for performance
            'category_filter': category_filter,
            'property_filter': property_filter,
            'month_filter': month_filter,
            'stats': stats,
            'properties': properties,
        }
        
        return render(request, 'landlord/expense_list.html', context)


class ExpenseCreateView(LoginRequiredMixin, View):
    """Create a new expense record"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Get all properties for this landlord
        properties = Property.objects.filter(landlord=request.landlord)
        
        return render(request, 'landlord/expense_form.html', {
            'properties': properties
        })
    
    @transaction.atomic
    def post(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        # Get form data
        property_id = request.POST.get('property')
        category = request.POST.get('category')
        description = request.POST.get('description')
        amount = request.POST.get('amount')
        expense_date = request.POST.get('expense_date')
        vendor_name = request.POST.get('vendor_name', '')
        vendor_contact = request.POST.get('vendor_contact', '')
        notes = request.POST.get('notes', '')
        receipt = request.FILES.get('receipt')
        
        # Validate required fields
        if not all([category, description, amount, expense_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('expenses:create')
        
        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError('Amount must be positive')
        except ValueError:
            messages.error(request, 'Invalid amount.')
            return redirect('expenses:create')
        
        # Get property if provided
        expense_property = None
        if property_id:
            expense_property = get_object_or_404(
                Property,
                pk=property_id,
                landlord=request.landlord
            )
        
        # Create expense
        expense = Expense.objects.create(
            landlord=request.landlord,
            expense_property=expense_property,
            category=category,
            description=description,
            amount=amount,
            expense_date=expense_date,
            vendor_name=vendor_name,
            vendor_contact=vendor_contact,
            notes=notes,
            receipt=receipt
        )
        
        messages.success(request, f'Expense of KES {amount:,.2f} recorded successfully!')
        return redirect('expenses:detail', pk=expense.pk)


class ExpenseDetailView(LoginRequiredMixin, View):
    """View expense details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        expense = get_object_or_404(
            Expense,
            pk=pk,
            landlord=request.landlord
        )
        
        return render(request, 'landlord/expense_detail.html', {
            'expense': expense
        })


class ExpenseUpdateView(LoginRequiredMixin, View):
    """Update expense details"""
    
    def get(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        expense = get_object_or_404(
            Expense,
            pk=pk,
            landlord=request.landlord
        )
        
        properties = Property.objects.filter(landlord=request.landlord)
        
        return render(request, 'landlord/expense_form.html', {
            'expense': expense,
            'properties': properties,
            'editing': True
        })
    
    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        expense = get_object_or_404(
            Expense,
            pk=pk,
            landlord=request.landlord
        )
        
        # Get form data
        property_id = request.POST.get('property')
        category = request.POST.get('category')
        description = request.POST.get('description')
        amount = request.POST.get('amount')
        expense_date = request.POST.get('expense_date')
        vendor_name = request.POST.get('vendor_name', '')
        vendor_contact = request.POST.get('vendor_contact', '')
        notes = request.POST.get('notes', '')
        receipt = request.FILES.get('receipt')
        
        # Validate required fields
        if not all([category, description, amount, expense_date]):
            messages.error(request, 'Please fill all required fields.')
            return redirect('expenses:update', pk=pk)
        
        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError('Amount must be positive')
        except ValueError:
            messages.error(request, 'Invalid amount.')
            return redirect('expenses:update', pk=pk)
        
        # Get property if provided
        expense_property = None
        if property_id:
            expense_property = get_object_or_404(
                Property,
                pk=property_id,
                landlord=request.landlord
            )
        
        # Update expense
        expense.expense_property = expense_property
        expense.category = category
        expense.description = description
        expense.amount = amount
        expense.expense_date = expense_date
        expense.vendor_name = vendor_name
        expense.vendor_contact = vendor_contact
        expense.notes = notes
        
        if receipt:
            expense.receipt = receipt
        
        expense.save()
        
        messages.success(request, 'Expense updated successfully!')
        return redirect('expenses:detail', pk=pk)


class ExpenseDeleteView(LoginRequiredMixin, View):
    """Delete an expense record"""
    
    @transaction.atomic
    def post(self, request, pk):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        expense = get_object_or_404(
            Expense,
            pk=pk,
            landlord=request.landlord
        )
        
        amount = expense.amount
        category = expense.get_category_display()
        expense.delete()
        
        messages.success(request, f'{category} expense of KES {amount:,.2f} deleted successfully!')
        return redirect('expenses:list')