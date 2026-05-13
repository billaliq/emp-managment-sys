from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta, date, time
from django.views.decorators.http import require_http_methods, require_POST
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
import json
import csv
import re
import logging

logger = logging.getLogger(__name__)

from EMSwebsite.models import (
    Employees, Department, Position, Attendance, AttendanceSettings, LeaveRequest, HolidayDate,
    Team, TeamMember, Project, Payroll, PayrollRecord, SalaryIncrement, SystemSettings,
    Loan, LoanRepayment, LoanPool, LoanPoolTransaction, UserProfile, SalaryDisbursement, SalaryDisbursementRecord,
    IncrementSettings, Notification, EmployeeAdditionalDocument, SalarySlipRequest,
    Policy, Complaint, AIChatMessage, ZKDevice, AttendanceLog,
    Report, ReportTemplate, ReportSchedule,
)
from .helpers import (
    validate_date, get_current_employee, scope_by_user, only_me_employee_qs,
    role_required, admin_required, hr_or_admin_required, finance_or_admin_required,
    has_valid_attendance_exception, auto_mark_absent_for_date, sync_attendance_with_holidays,
)
from EMSwebsite.context_processors import get_notifications


def loans(request):  # full, scoped version
    loan_pool, _ = LoanPool.objects.get_or_create(
        is_active=True,
        defaults={
            'name': 'Company Loan Pool',
            'total_amount': Decimal('100000.00'),
            'available_amount': Decimal('100000.00'),
            'created_by': request.user.employee if hasattr(request.user, 'employee') else None
        }
    )

    my_loans_qs = scope_by_user(Loan.objects.all(), request, field='employee')
    my_repayments_qs = LoanRepayment.objects.filter(loan__in=my_loans_qs)
    total_loans = my_loans_qs.count()
    total_loan_amount = my_loans_qs.aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
    total_repaid = my_repayments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    pending_approvals = my_loans_qs.filter(status='pending').count()

    all_loans = scope_by_user(Loan.objects.select_related('employee','loan_pool').order_by('-created_at'), request, field='employee')
    pending_loans = scope_by_user(Loan.objects.select_related('employee','loan_pool').filter(status='pending').order_by('-created_at'), request, field='employee')

    # Get active loans for repayment modal
    active_loans = scope_by_user(Loan.objects.select_related('employee', 'employee__department').filter(status__in=['approved', 'active']), request, field='employee')

    # Calculate overdue loans (loans past end_date with remaining balance)
    from django.utils import timezone
    today = timezone.now().date()

    # Get loans that are past end_date and have remaining balance
    overdue_loans_qs = my_loans_qs.filter(
        status__in=['approved', 'active'],
        end_date__lt=today
    ).annotate(
        total_repaid=Sum('repayments__amount')
    ).filter(
        total_repaid__lt=F('total_amount')
    )
    overdue_loans = overdue_loans_qs.count()

    # Get actual repayment records for repayments tab
    repayment_records = LoanRepayment.objects.select_related('loan', 'loan__employee', 'loan__employee__department').filter(loan__in=all_loans).order_by('-payment_date')[:50]

    # Calculate total pending repayments (sum of remaining balances for active loans)
    # Use annotation to calculate remaining balance
    active_loans_with_balance = my_loans_qs.filter(status__in=['approved', 'active']).annotate(
        total_repaid=Sum('repayments__amount')
    )
    total_pending_repayments = Decimal('0.00')
    for loan in active_loans_with_balance:
        total_repaid = loan.total_repaid or Decimal('0.00')
        remaining = loan.total_amount - total_repaid
        if remaining > 0:
            total_pending_repayments += remaining

    # Calculate report statistics
    total_issued = my_loans_qs.filter(status__in=['approved', 'active', 'completed']).aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
    avg_loan = my_loans_qs.filter(status__in=['approved', 'active']).aggregate(avg=Avg('loan_amount'))['avg'] or Decimal('0.00')

    # Calculate default rate (overdue loans / total active loans * 100)
    active_loans_count = my_loans_qs.filter(status__in=['approved', 'active']).count()
    default_rate = (overdue_loans / active_loans_count * 100) if active_loans_count > 0 else Decimal('0.0')

    # Collection rate (total repaid / total issued * 100)
    collection_rate = (total_repaid / total_issued * 100) if total_issued > 0 else Decimal('0.0')

    # Determine user role
    if request.user.is_superuser:
        user_role = 'admin'
        is_admin = True
    else:
        try:
            profile = request.user.profile
            user_role = profile.role
            is_admin = (profile.role == 'admin')
        except:
            user_role = 'employee'
            is_admin = False

    recent_transactions = LoanPoolTransaction.objects.select_related('created_by').filter(pool=loan_pool).order_by('-created_at')[:10]

    return render(request, 'pages/loans.html', {
        'loan_pool': loan_pool,
        'stats': {
            'total_loan_amount': total_loan_amount,
            'approved_loans': my_loans_qs.filter(status__in=['approved', 'active']).count(),
            'pending_approvals': pending_approvals,
            'amount_repaid': total_repaid,
            'pool_utilization': loan_pool.utilization_percentage,
            'overdue_loans': overdue_loans,
            'total_pending_repayments': total_pending_repayments,
        },
        'all_loans': all_loans,
        'pending_loans': pending_loans,
        'active_loans': active_loans,
        'repayments_data': repayment_records,  # Use actual repayment records
        'report_data': {
            'total_issued': total_issued,
            'average_loan': avg_loan,
            'default_rate': default_rate,
            'collection_rate': collection_rate,
        },
        'employees': only_me_employee_qs(request).filter(status=1).order_by('firstname'),
        'recent_transactions': recent_transactions,
        'user_role': user_role,
        'is_admin': is_admin,
        'current_employee': get_current_employee(request),
    })

@login_required
@require_http_methods(["POST"])
def create_loan(request):
    try:
        employee_id = request.POST.get('employee')
        loan_amount = Decimal(request.POST.get('loan_amount', 0))
        interest_rate = Decimal('0')  # Interest rate removed - always 0
        number_of_installments = int(request.POST.get('installments', 0))
        start_date = request.POST.get('start_date')
        purpose = request.POST.get('purpose', '')

        # If employee_id is not provided or empty, use the logged-in employee (for self-application)
        if not employee_id or employee_id == '':
            current_employee = get_current_employee(request)
            if not current_employee:
                return JsonResponse({'success': False, 'error': 'Employee profile not found. Please contact administrator.'})
            employee = current_employee
        else:
            employee = get_object_or_404(only_me_employee_qs(request), pk=employee_id)

        if not all([loan_amount, number_of_installments, start_date]):
            return JsonResponse({'success': False, 'error': 'All required fields must be filled'})

        if number_of_installments <= 0:
            return JsonResponse({'success': False, 'error': 'Number of installments must be greater than 0'})

        if loan_amount <= 0:
            return JsonResponse({'success': False, 'error': 'Loan amount must be greater than 0'})



        active_loans = Loan.objects.filter(employee=employee, status__in=['approved','active'])
        if active_loans.exists():
            return JsonResponse({'success': False, 'error': 'Employee already has an active loan. Only one active loan per employee is allowed.'})

        if employee.salary:
            max_allowed = Decimal(employee.salary) * Decimal('1.5')
            if loan_amount > max_allowed:
                return JsonResponse({'success': False, 'error': f'Loan amount cannot exceed 1.5 times monthly salary (${max_allowed:.2f})'})

        loan_pool = LoanPool.objects.filter(is_active=True).first()
        if not loan_pool:
            return JsonResponse({'success': False, 'error': 'No active loan pool found. Please contact administrator.'})

        if not loan_pool.can_approve_loan(loan_amount):
            if loan_pool.available_amount > 0:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient funds in loan pool. Available: ${loan_pool.available_amount:.2f}. Would you like to apply for a partial loan of ${loan_pool.available_amount:.2f}?',
                    'partial_loan_available': True,
                    'partial_amount': float(loan_pool.available_amount)
                })
            else:
                return JsonResponse({'success': False, 'error': 'No funds available in loan pool. Please try again later.'})

        # No interest rate - total amount equals loan amount
        total_amount = loan_amount
        monthly_payment = total_amount / number_of_installments

        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = start_date_obj + timedelta(days=number_of_installments * 30)

        loan = Loan.objects.create(
            employee=employee, loan_pool=loan_pool, loan_amount=loan_amount,
            interest_rate=interest_rate, total_amount=total_amount,
            number_of_installments=number_of_installments, monthly_payment=monthly_payment,
            start_date=start_date_obj, end_date=end_date_obj, purpose=purpose, status='pending'
        )

        LoanPoolTransaction.objects.create(
            pool=loan_pool, transaction_type='loan_approval', amount=loan_amount,
            description=f'Loan application for {employee.firstname} {employee.lastname}',
            created_by=request.user.employee if hasattr(request.user, 'employee') else None
        )
        return JsonResponse({'success': True, 'message': 'Loan created successfully and pending approval', 'loan_id': loan.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def update_loan_status(request):
    try:
        loan_id = request.POST.get('loan_id'); action = request.POST.get('action')  # 'approve' or 'reject'
        loan = get_object_or_404(scope_by_user(Loan.objects.all(), request, field='employee'), pk=loan_id)

        if action == 'approve':
            if loan.loan_pool and not loan.loan_pool.can_approve_loan(loan.loan_amount):
                return JsonResponse({'success': False, 'error': f'Cannot approve loan. Insufficient funds in pool. Available: ${loan.loan_pool.available_amount:.2f}'})
            success, approved_amount = loan.approve_with_pool_constraints()
            if success:
                if loan.loan_pool:
                    LoanPoolTransaction.objects.create(
                        pool=loan.loan_pool, transaction_type='loan_approval', amount=approved_amount,
                        description=f'Loan approved for {loan.employee.firstname} {loan.employee.lastname}',
                        created_by=request.user.employee if hasattr(request.user, 'employee') else None
                    )
                msg = f'Loan approved successfully for ${approved_amount:.2f}'
                if loan.is_partial_loan:
                    msg += f' (Partial loan - originally requested ${loan.original_requested_amount:.2f})'
                return JsonResponse({'success': True, 'message': msg, 'is_partial': loan.is_partial_loan, 'approved_amount': float(approved_amount)})
            else:
                return JsonResponse({'success': False, 'error': 'Cannot approve loan due to pool constraints'})
        elif action == 'reject':
            loan.status = 'rejected'; loan.save()
            if loan.loan_pool:
                LoanPoolTransaction.objects.create(
                    pool=loan.loan_pool, transaction_type='loan_cancellation', amount=0,
                    description=f'Loan rejected for {loan.employee.firstname} {loan.employee.lastname}',
                    created_by=request.user.employee if hasattr(request.user, 'employee') else None
                )

        return JsonResponse({'success': True, 'message': f'Loan {action}d successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def add_repayment(request):
    try:
        loan_id = request.POST.get('loan'); amount = Decimal(request.POST.get('amount', 0))
        payment_date = request.POST.get('payment_date'); payment_method = request.POST.get('payment_method')
        notes = request.POST.get('notes', '')

        if not all([loan_id, amount, payment_date, payment_method]):
            return JsonResponse({'success': False, 'error': 'All fields are required'})

        loan = get_object_or_404(scope_by_user(Loan.objects.all(), request, field='employee'), pk=loan_id)

        if amount > loan.remaining_balance:
            return JsonResponse({'success': False, 'error': f'Payment amount (${amount}) exceeds remaining balance (${loan.remaining_balance})'})

        repayment = LoanRepayment.objects.create(
            loan=loan, amount=amount, payment_date=datetime.strptime(payment_date, '%Y-%m-%d').date(),
            payment_method=payment_method, notes=notes,
            created_by=request.user.employee if hasattr(request.user, 'employee') else None
        )

        if loan.remaining_balance == 0:
            loan.status = 'completed'; loan.save()

        return JsonResponse({'success': True, 'message': 'Repayment recorded successfully', 'repayment_id': repayment.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_loan_details(request, loan_id):
    try:
        loan = get_object_or_404(scope_by_user(Loan.objects.select_related('employee', 'employee__department', 'loan_pool'), request, field='employee'), pk=loan_id)
        data = {
            'id': loan.id,
            'employee_name': f"{loan.employee.firstname} {loan.employee.lastname or ''}".strip(),
            'employee_code': loan.employee.code or '',
            'department': loan.employee.department.name if loan.employee.department else 'No Department',
            'loan_amount': str(loan.loan_amount),
            'interest_rate': str(loan.interest_rate),
            'total_amount': str(loan.total_amount),
            'remaining_balance': str(loan.remaining_balance),
            'amount_repaid': str(loan.amount_repaid),
            'number_of_installments': loan.number_of_installments,
            'installments_paid': loan.installments_paid,
            'installments_remaining': loan.installments_remaining,
            'monthly_payment': str(loan.monthly_payment),
            'start_date': loan.start_date.strftime('%Y-%m-%d'),
            'end_date': loan.end_date.strftime('%Y-%m-%d'),
            'purpose': loan.purpose or '',
            'status': loan.status,
            'status_display': loan.get_status_display(),
            'progress_percentage': round(loan.progress_percentage, 1),
            'created_at': loan.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        return JsonResponse({'success': True, 'loan': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_loan_repayments(request, loan_id):
    try:
        loan = get_object_or_404(scope_by_user(Loan.objects.all(), request, field='employee'), pk=loan_id)
        repayments = LoanRepayment.objects.filter(loan=loan).select_related('created_by').order_by('-payment_date')

        repayments_data = []
        for repayment in repayments:
            repayments_data.append({
                'id': repayment.id,
                'amount': str(repayment.amount),
                'payment_date': repayment.payment_date.strftime('%Y-%m-%d'),
                'payment_method': repayment.get_payment_method_display(),
                'notes': repayment.notes or '',
                'created_by': f"{repayment.created_by.firstname} {repayment.created_by.lastname or ''}".strip() if repayment.created_by else 'System',
                'created_at': repayment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })

        return JsonResponse({
            'success': True,
            'repayments': repayments_data,
            'total_repaid': str(loan.amount_repaid),
            'remaining_balance': str(loan.remaining_balance),
            'total_amount': str(loan.total_amount),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def export_loans_report(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="loans_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Employee Name','Current Salary','Total Loans','Outstanding Amount','Monthly Deduction','Status'])

    for e in only_me_employee_qs(request).filter(status=1):
        e_loans = Loan.objects.filter(employee=e, status__in=['approved','active'])
        total_e_loans = e_loans.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        outstanding_amount = sum(ln.remaining_balance for ln in e_loans)
        monthly_deduction = sum(ln.monthly_payment for ln in e_loans)
        if e_loans.exists():
            writer.writerow([
                str(e), f"${e.salary}", f"${total_e_loans}", f"${outstanding_amount}",
                f"${monthly_deduction}", 'Active' if outstanding_amount > 0 else 'Completed'
            ])
    return response

@login_required
@require_http_methods(["POST"])
def manage_loan_pool(request):
    try:
        action = request.POST.get('action')
        amount = Decimal(request.POST.get('amount', 0))
        description = request.POST.get('description', '')
        if not amount or amount <= 0:
            return JsonResponse({'success': False, 'error': 'Invalid amount'})

        loan_pool = LoanPool.objects.filter(is_active=True).first()
        if not loan_pool:
            return JsonResponse({'success': False, 'error': 'No active loan pool found'})

        if action == 'increase':
            loan_pool.increase_pool(amount); transaction_type = 'increase'; message = f'Loan pool increased by ${amount:.2f}'
        elif action == 'decrease':
            if not loan_pool.decrease_pool(amount):
                return JsonResponse({'success': False, 'error': f'Cannot decrease pool. Insufficient available amount. Available: ${loan_pool.available_amount:.2f}'})
            transaction_type = 'decrease'; message = f'Loan pool decreased by ${amount:.2f}'
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})

        LoanPoolTransaction.objects.create(
            pool=loan_pool, transaction_type=transaction_type, amount=amount,
            description=description or message,
            created_by=request.user.employee if hasattr(request.user, 'employee') else None
        )

        return JsonResponse({
            'success': True,
            'message': message,
            'pool_data': {
                'total_amount': float(loan_pool.total_amount),
                'available_amount': float(loan_pool.available_amount),
                'utilization_percentage': float(loan_pool.utilization_percentage)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_loan_pool_status(request):
    try:
        loan_pool = LoanPool.objects.filter(is_active=True).first()
        if not loan_pool:
            return JsonResponse({'success': False, 'error': 'No active loan pool found'})

        recent_transactions = LoanPoolTransaction.objects.filter(pool=loan_pool).order_by('-created_at')[:10]
        transactions_data = [{
            'type': t.get_transaction_type_display(),
            'amount': float(t.amount),
            'description': t.description,
            'date': t.created_at.strftime('%Y-%m-%d %H:%M'),
            'created_by': str(t.created_by) if t.created_by else 'System'
        } for t in recent_transactions]

        return JsonResponse({
            'success': True,
            'pool_data': {
                'total_amount': float(loan_pool.total_amount),
                'available_amount': float(loan_pool.available_amount),
                'utilized_amount': float(loan_pool.utilized_amount),
                'utilization_percentage': float(loan_pool.utilization_percentage),
                'is_active': loan_pool.is_active
            },
            'recent_transactions': transactions_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_employee_loan_eligibility(request, employee_id):
    try:
        employee = get_object_or_404(only_me_employee_qs(request), pk=employee_id)
        loan_pool = LoanPool.objects.filter(is_active=True).first()
        if not loan_pool:
            return JsonResponse({'success': False, 'error': 'No active loan pool found'})

        active_loans = Loan.objects.filter(employee=employee, status__in=['approved','active'])
        has_active_loan = active_loans.exists()
        max_loan_amount = Decimal(employee.salary) * Decimal('1.5') if employee.salary else Decimal('0')
        pool_available = loan_pool.available_amount
        actual_available = min(max_loan_amount, pool_available)

        return JsonResponse({
            'success': True,
            'employee': {'id': employee.id, 'name': f"{employee.firstname} {employee.lastname}", 'salary': float(employee.salary) if employee.salary else 0},
            'eligibility': {
                'has_active_loan': has_active_loan,
                'max_loan_amount': float(max_loan_amount),
                'pool_available': float(pool_available),
                'actual_available': float(actual_available),
                'can_apply': not has_active_loan and actual_available > 0
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ===========================
#   REPORT VIEWS
# ===========================
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Count
import json
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import csv

from EMSwebsite.models import Report, ReportTemplate
