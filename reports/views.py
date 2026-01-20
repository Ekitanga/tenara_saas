from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from datetime import timedelta
from invoicing.models import Invoice
from payments.models import Payment
from expenses.models import Expense
from properties.models import Property, Unit
from tenants_mgmt.models import Lease


class ReportsDashboardView(LoginRequiredMixin, View):
    """Main reports dashboard with overview"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        
        # Date ranges
        today = timezone.now().date()
        current_month = today.replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        current_year = today.replace(month=1, day=1)
        
        # Revenue summary
        revenue_stats = {
            'current_month': Invoice.objects.filter(
                lease__unit__unit_property__landlord=landlord,
                billing_month=current_month
            ).aggregate(
                billed=Sum('total_amount'),
                collected=Sum('amount_paid')
            ),
            'last_month': Invoice.objects.filter(
                lease__unit__unit_property__landlord=landlord,
                billing_month=last_month
            ).aggregate(
                billed=Sum('total_amount'),
                collected=Sum('amount_paid')
            ),
            'year_to_date': Invoice.objects.filter(
                lease__unit__unit_property__landlord=landlord,
                billing_month__gte=current_year
            ).aggregate(
                billed=Sum('total_amount'),
                collected=Sum('amount_paid')
            ),
        }
        
        # Occupancy stats
        total_units = Unit.objects.filter(unit_property__landlord=landlord).count()
        occupied_units = Unit.objects.filter(
            unit_property__landlord=landlord,
            lease__status='active'
        ).distinct().count()
        
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Arrears
        total_arrears = 0
        arrears_invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=landlord,
            status__in=['pending', 'overdue', 'partial']
        )
        for inv in arrears_invoices:
            total_arrears += inv.balance
        
        # Expenses
        expense_stats = {
            'current_month': Expense.objects.filter(
                landlord=landlord,
                expense_date__year=current_month.year,
                expense_date__month=current_month.month
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'last_month': Expense.objects.filter(
                landlord=landlord,
                expense_date__year=last_month.year,
                expense_date__month=last_month.month
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'year_to_date': Expense.objects.filter(
                landlord=landlord,
                expense_date__gte=current_year
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        # Net profit
        net_profit_current = (revenue_stats['current_month']['collected'] or 0) - expense_stats['current_month']
        
        context = {
            'revenue_stats': revenue_stats,
            'occupancy_rate': occupancy_rate,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'total_arrears': total_arrears,
            'expense_stats': expense_stats,
            'net_profit_current': net_profit_current,
            'current_month': current_month,
            'last_month': last_month,
        }
        
        return render(request, 'landlord/reports_dashboard.html', context)


class RevenueReportView(LoginRequiredMixin, View):
    """Detailed revenue report"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        
        # Get date range from query params
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Default to current year
        if not start_date:
            start_date = timezone.now().date().replace(month=1, day=1)
        else:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Revenue by month
        invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=landlord,
            billing_month__gte=start_date,
            billing_month__lte=end_date
        )
        
        # Revenue by property
        revenue_by_property = Property.objects.filter(
            landlord=landlord
        ).annotate(
            total_billed=Sum('units__lease__invoices__total_amount', filter=Q(
                units__lease__invoices__billing_month__gte=start_date,
                units__lease__invoices__billing_month__lte=end_date
            )),
            total_collected=Sum('units__lease__invoices__amount_paid', filter=Q(
                units__lease__invoices__billing_month__gte=start_date,
                units__lease__invoices__billing_month__lte=end_date
            ))
        )
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'invoices': invoices,
            'revenue_by_property': revenue_by_property,
        }
        
        return render(request, 'landlord/revenue_report.html', context)


class ArrearsReportView(LoginRequiredMixin, View):
    """Arrears aging report"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        today = timezone.now().date()
        
        # Get all unpaid/partially paid invoices
        arrears_invoices = Invoice.objects.filter(
            lease__unit__unit_property__landlord=landlord,
            status__in=['pending', 'overdue', 'partial']
        ).select_related(
            'lease__tenant__user',
            'lease__unit__unit_property'
        ).order_by('due_date')
        
        # Calculate aging buckets
        aging_data = {
            'current': [],  # Not yet due
            '1-30': [],     # 1-30 days overdue
            '31-60': [],    # 31-60 days overdue
            '61-90': [],    # 61-90 days overdue
            '90+': [],      # 90+ days overdue
        }
        
        for invoice in arrears_invoices:
            days_overdue = (today - invoice.due_date).days
            
            if days_overdue <= 0:
                aging_data['current'].append(invoice)
            elif days_overdue <= 30:
                aging_data['1-30'].append(invoice)
            elif days_overdue <= 60:
                aging_data['31-60'].append(invoice)
            elif days_overdue <= 90:
                aging_data['61-90'].append(invoice)
            else:
                aging_data['90+'].append(invoice)
        
        # Calculate totals
        totals = {}
        for bucket, invoices in aging_data.items():
            totals[bucket] = sum(inv.balance for inv in invoices)
        
        context = {
            'aging_data': aging_data,
            'totals': totals,
            'grand_total': sum(totals.values()),
        }
        
        return render(request, 'landlord/arrears_report.html', context)


class OccupancyReportView(LoginRequiredMixin, View):
    """Occupancy and vacancy report"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        
        # Occupancy by property
        properties = Property.objects.filter(landlord=landlord).prefetch_related('units')
        
        property_stats = []
        for prop in properties:
            total = prop.get_total_units()
            occupied = prop.get_occupied_units()
            vacant = total - occupied
            
            property_stats.append({
                'property': prop,
                'total_units': total,
                'occupied_units': occupied,
                'vacant_units': vacant,
                'occupancy_rate': (occupied / total * 100) if total > 0 else 0,
            })
        
        # Overall stats
        total_units = sum(p['total_units'] for p in property_stats)
        total_occupied = sum(p['occupied_units'] for p in property_stats)
        overall_occupancy = (total_occupied / total_units * 100) if total_units > 0 else 0
        
        context = {
            'property_stats': property_stats,
            'total_units': total_units,
            'total_occupied': total_occupied,
            'overall_occupancy': overall_occupancy,
        }
        
        return render(request, 'landlord/occupancy_report.html', context)


class ExpensesReportView(LoginRequiredMixin, View):
    """Expenses breakdown report"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        
        # Get date range
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date:
            start_date = timezone.now().date().replace(month=1, day=1)
        else:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Expenses by category
        expenses_by_category = Expense.objects.filter(
            landlord=landlord,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).values('category').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Expenses by property
        expenses_by_property = Expense.objects.filter(
            landlord=landlord,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).values('expense_property__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Total
        total_expenses = sum(item['total'] for item in expenses_by_category)
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'expenses_by_category': expenses_by_category,
            'expenses_by_property': expenses_by_property,
            'total_expenses': total_expenses,
        }
        
        return render(request, 'landlord/expenses_report.html', context)


class ProfitReportView(LoginRequiredMixin, View):
    """Profit and loss report"""
    
    def get(self, request):
        if not request.user.is_landlord:
            messages.error(request, 'Access denied.')
            return redirect('demo:home')
        
        landlord = request.landlord
        
        # Get date range
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date:
            start_date = timezone.now().date().replace(month=1, day=1)
        else:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Revenue (payments received)
        total_revenue = Payment.objects.filter(
            invoice__lease__unit__unit_property__landlord=landlord,
            payment_date__gte=start_date,
            payment_date__lte=end_date,
            status='confirmed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Expenses
        total_expenses = Expense.objects.filter(
            landlord=landlord,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Net profit
        net_profit = total_revenue - total_expenses
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
        }
        
        return render(request, 'landlord/profit_report.html', context)