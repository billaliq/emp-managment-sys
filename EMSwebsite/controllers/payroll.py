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


# Payroll Page Views
@login_required
def payroll(request):
    """Enhanced payroll view with advanced filtering - accessible to all users (scoped)"""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Check user role
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Base queryset - scoped for employee users
    # For admin/hr/finance/superuser: show all records
    # For employees: show only their own records
    current_employee = None
    if is_admin_user or request.user.is_superuser:
        base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position')
    else:
        # For employee users, filter to their own records
        current_employee = get_current_employee(request)
        if current_employee:
            base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position').filter(employee=current_employee)
            # Check if employee has any payroll records
            if not base_qs.exists():
                messages.info(request, f'No payroll records found for {current_employee.firstname} {current_employee.lastname or ""}.')
        else:
            # Employee not linked - show message
            messages.warning(request, 'Employee profile not linked to your account. Please contact administrator.')
            base_qs = PayrollRecord.objects.none()

    # Advanced filtering
    search_query = request.GET.get('search', '').strip()
    employee_id = request.GET.get('employee_id', '').strip()
    department_id = request.GET.get('department', '').strip()
    status_filter = request.GET.get('status', '').strip()
    month_filter = request.GET.get('month', '').strip()
    year_filter = request.GET.get('year', '').strip()

    # Apply filters
    if search_query and is_admin_user:
        # Only allow search for admin users
        base_qs = base_qs.filter(
            Q(employee__code__icontains=search_query) |
            Q(employee__firstname__icontains=search_query) |
            Q(employee__lastname__icontains=search_query) |
            Q(employee__email__icontains=search_query)
        )

    if employee_id and is_admin_user:
        # Only allow employee filter for admin users
        try:
            base_qs = base_qs.filter(employee_id=int(employee_id))
        except ValueError:
            pass

    if department_id and is_admin_user:
        # Only allow department filter for admin users
        try:
            base_qs = base_qs.filter(employee__department_id=int(department_id))
        except ValueError:
            pass

    if status_filter and status_filter in ['paid', 'pending', 'failed']:
        base_qs = base_qs.filter(status=status_filter)

    if month_filter and year_filter:
        try:
            base_qs = base_qs.filter(
                pay_date__year=int(year_filter),
                pay_date__month=int(month_filter)
            )
        except ValueError:
            pass
    elif not month_filter and not year_filter:
        # Default to current month only for admin users (to reduce data load)
        # For employees, show all their records
        if is_admin_user:
            base_qs = base_qs.filter(pay_date__gte=month_start, pay_date__lte=today)
        # For employees, don't apply date filter - show all their records

    # Monthly stats - calculate based on current month for all users
    monthly_records = base_qs.filter(pay_date__gte=month_start, pay_date__lte=today)
    total_payroll = monthly_records.aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')
    employees_paid = monthly_records.filter(status='paid').values('employee').distinct().count()
    average_salary = monthly_records.aggregate(avg=Avg('net_salary'))['avg'] or Decimal('0.00')
    pending_approvals = monthly_records.filter(status='pending').count()

    # For employee users, also calculate total stats (all time)
    if not is_admin_user and not request.user.is_superuser:
        total_records = base_qs  # All records for the employee
        total_payroll_all = total_records.aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')
        total_records_count = total_records.count()
    else:
        total_payroll_all = total_payroll
        total_records_count = monthly_records.count()

    # Get payroll records (limit for display, but allow export of all)
    payroll_records = base_qs.order_by('-pay_date', 'employee__firstname')[:500]

    increments = scope_by_user(
        SalaryIncrement.objects.select_related('employee').order_by('-effective_date'),
        request, field='employee'
    )[:100]

    recent_payrolls = Payroll.objects.order_by('-pay_date')[:5]

    # Check if user is finance/admin/superuser for disbursement features
    is_finance_user = request.user.is_superuser
    if not is_finance_user:
        try:
            profile = request.user.profile
            is_finance_user = profile.role in ['finance', 'admin']
        except:
            pass

    # Get recent disbursements for finance users
    recent_disbursements = []
    if is_finance_user:
        recent_disbursements = SalaryDisbursement.objects.all().order_by('-initiated_at')[:10]

    # Get departments for filter dropdown (admin only)
    departments = []
    if is_admin_user:
        from EMSwebsite.models import Department
        departments = Department.objects.all().order_by('name')

    # Get employees for filter dropdown (admin only)
    employees_list = []
    if is_admin_user:
        employees_list = only_me_employee_qs(request).filter(status=1).order_by('firstname')

    return render(request, 'pages/payroll.html', {
        'stats': {
            'total_payroll': total_payroll,
            'employees_paid': employees_paid,
            'average_salary': average_salary,
            'pending_approvals': pending_approvals,
        },
        'payroll_records': payroll_records,
        'increments': increments,
        'employees': only_me_employee_qs(request).filter(status=1).order_by('firstname'),
        'employees_list': employees_list,
        'departments': departments,
        'recent_payrolls': recent_payrolls,
        'recent_disbursements': recent_disbursements,
        'is_finance_user': is_finance_user,
        'is_admin_user': is_admin_user,
        'user_role': user_role,
        'current_employee': current_employee,
        'search_query': search_query,
        'timezone': timezone,
        'filters': {
            'employee_id': employee_id,
            'department_id': department_id,
            'status': status_filter,
            'month': month_filter,
            'year': year_filter,
        },
    })


@login_required
@hr_or_admin_required
@require_POST
def process_payroll(request):
    pay_period = request.POST.get('pay_period')
    pay_date = request.POST.get('pay_date')
    employee_ids = request.POST.getlist('employees') or request.POST.getlist('employees[]')

    if not pay_period or not pay_date:
        messages.error(request, 'Pay period and pay date are required.')
        return redirect('payroll')

    pay_date_obj = datetime.strptime(pay_date, '%Y-%m-%d').date()
    payroll = Payroll.objects.create(pay_period=pay_period, pay_date=pay_date_obj, processed_by=request.user)

    qs = only_me_employee_qs(request).filter(status=1)  # scoped processing
    if employee_ids and 'all' not in employee_ids:
        qs = qs.filter(id__in=employee_ids)

    created = 0
    for emp in qs:
        base = Decimal(emp.salary or 0)
        allowances = Decimal('0.00')
        deductions = Decimal('0.00')
        net = base + allowances - deductions
        PayrollRecord.objects.create(
            payroll=payroll,
            employee=emp,
            base_salary=base,
            allowances=allowances,
            deductions=deductions,
            net_salary=net,
            pay_date=pay_date_obj,
            status='pending'
        )
        created += 1

    # Notify admins about payroll processing
    from .utils.notifications import notify_admins
    notify_admins(
        'payroll',
        'Payroll Processed',
        f"Payroll for {pay_period} has been processed. {created} employee(s) included. Pay date: {pay_date_obj.strftime('%B %d, %Y')}.",
        payroll.id,
        'Payroll'
    )

    messages.success(request, f"Payroll created with {created} records.")
    return redirect('payroll')


@login_required
@require_POST
def update_payroll_record(request, pk):
    rec = get_object_or_404(scope_by_user(PayrollRecord.objects.all(), request, field='employee'), pk=pk)
    base = Decimal(request.POST.get('base_salary') or 0)
    allowances = Decimal(request.POST.get('allowances') or 0)
    deductions = Decimal(request.POST.get('deductions') or 0)
    status_val = request.POST.get('status') or rec.status
    net = base + allowances - deductions

    rec.base_salary = base
    rec.allowances = allowances
    rec.deductions = deductions
    rec.net_salary = net
    rec.status = status_val
    rec.save()
    return JsonResponse({'success': True, 'net_salary': f"{net:.2f}", 'status': rec.status})


@login_required
def payroll_record_detail(request, pk):
    """View individual payroll record details"""
    # Check if user is admin
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Base queryset - scoped for employee users
    if is_admin_user or request.user.is_superuser:
        base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll')
    else:
        # For employee users, filter to their own records
        current_employee = get_current_employee(request)
        if current_employee:
            base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll').filter(employee=current_employee)
        else:
            base_qs = PayrollRecord.objects.none()

    record = get_object_or_404(base_qs, pk=pk)
    latest_slip = record.salary_slip_requests.first() if hasattr(record, "salary_slip_requests") else None

    return render(request, 'pages/payroll_record_detail.html', {
        'record': record,
        'is_admin_user': is_admin_user,
        'user_role': user_role,
        'latest_slip': latest_slip,
    })


@login_required
@require_POST
def request_salary_slip(request, pk):
    """Employee requests a salary slip for a specific payroll record."""
    # Determine current employee (for non-admin users)
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except UserProfile.DoesNotExist:
        user_role = 'employee'

    base_qs = PayrollRecord.objects.select_related('employee')
    if not is_admin_user:
        current_employee = get_current_employee(request)
        if current_employee:
            base_qs = base_qs.filter(employee=current_employee)
        else:
            messages.error(request, "Employee profile not linked. Please contact administrator.")
            return redirect('payroll')

    record = get_object_or_404(base_qs, pk=pk)

    # Create or reuse latest request if still pending
    slip = record.salary_slip_requests.filter(employee=record.employee).first()
    if slip and slip.status == 'pending':
        messages.info(request, "Salary slip request is already pending approval.")
    else:
        SalarySlipRequest.objects.create(
            payroll_record=record,
            employee=record.employee,
            requested_by=request.user,
            status='pending',
        )
        messages.success(request, "Salary slip request submitted and awaiting approval from HR/Admin.")

    return redirect('payroll')


@login_required
@hr_or_admin_required
@require_POST
def approve_salary_slip(request, pk):
    """Admin/HR approves or rejects a salary slip request."""
    action = request.POST.get('action', 'approve')
    slip = get_object_or_404(SalarySlipRequest, pk=pk)

    if slip.status != 'pending':
        messages.info(request, "This salary slip request has already been processed.")
        return redirect('payroll_record_detail', pk=slip.payroll_record.pk)

    slip.status = 'approved' if action == 'approve' else 'rejected'
    slip.decided_by = request.user
    slip.decided_at = timezone.now()
    note = request.POST.get('note', '').strip()
    if note:
        slip.note = note
    slip.save()

    messages.success(
        request,
        f"Salary slip request has been {slip.get_status_display().lower()} for {slip.employee.firstname} {slip.employee.lastname or ''}."
    )
    return redirect('payroll_record_detail', pk=slip.payroll_record.pk)


@login_required
def payroll_print(request, pk=None):
    """Print view for payroll records - single or all with filters"""
    # Check if user is admin
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    if pk:
        # Print single record
        # Base queryset - scoped for employee users
        if is_admin_user or request.user.is_superuser:
            base_qs_for_record = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll')
        else:
            # For employee users, filter to their own records
            current_employee = get_current_employee(request)
            if current_employee:
                base_qs_for_record = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll').filter(employee=current_employee)
            else:
                base_qs_for_record = PayrollRecord.objects.none()

        record = get_object_or_404(base_qs_for_record, pk=pk)
        records = [record]
        title = f"Payroll Record - {record.employee.firstname} {record.employee.lastname}"
        # For single record, totals are the same as the record values
        total_base = record.base_salary
        total_allowances = record.allowances
        total_deductions = record.deductions
        total_net = record.net_salary
    else:
        # Print all records with filters
        # Base queryset - scoped for employee users
        if is_admin_user or request.user.is_superuser:
            base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll')
        else:
            # For employee users, filter to their own records
            current_employee = get_current_employee(request)
            if current_employee:
                base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position', 'payroll').filter(employee=current_employee)
            else:
                base_qs = PayrollRecord.objects.none()

        # Apply same filters as main view
        search_query = request.GET.get('search', '').strip()
        employee_id = request.GET.get('employee_id', '').strip()
        department_id = request.GET.get('department', '').strip()
        status_filter = request.GET.get('status', '').strip()
        month_filter = request.GET.get('month', '').strip()
        year_filter = request.GET.get('year', '').strip()

        if search_query and is_admin_user:
            # Only allow search for admin users
            base_qs = base_qs.filter(
                Q(employee__code__icontains=search_query) |
                Q(employee__firstname__icontains=search_query) |
                Q(employee__lastname__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )

        if employee_id and is_admin_user:
            # Only allow employee filter for admin users
            try:
                base_qs = base_qs.filter(employee_id=int(employee_id))
            except ValueError:
                pass

        if department_id and is_admin_user:
            # Only allow department filter for admin users
            try:
                base_qs = base_qs.filter(employee__department_id=int(department_id))
            except ValueError:
                pass

        if status_filter and status_filter in ['paid', 'pending', 'failed']:
            base_qs = base_qs.filter(status=status_filter)

        if month_filter and year_filter:
            try:
                base_qs = base_qs.filter(
                    pay_date__year=int(year_filter),
                    pay_date__month=int(month_filter)
                )
            except ValueError:
                pass

        records = base_qs.order_by('-pay_date', 'employee__firstname')
        title = "All Payroll Records"

    # Calculate totals
    total_base = sum(record.base_salary for record in records)
    total_allowances = sum(record.allowances for record in records)
    total_deductions = sum(record.deductions for record in records)
    total_net = sum(record.net_salary for record in records)

    return render(request, 'pages/payroll_print.html', {
        'records': records,
        'title': title,
        'is_admin_user': is_admin_user,
        'print_date': timezone.now(),
        'total_base': total_base,
        'total_allowances': total_allowances,
        'total_deductions': total_deductions,
        'total_net': total_net,
    })


@login_required
def payroll_export_csv(request):
    """Export payroll records to CSV"""
    # Check user role for proper scoping
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Base queryset - scoped for employee users
    if is_admin_user or request.user.is_superuser:
        base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position')
    else:
        # For employee users, filter to their own records
        current_employee = get_current_employee(request)
        if current_employee:
            base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position').filter(employee=current_employee)
        else:
            base_qs = PayrollRecord.objects.none()

    # Apply filters
    search_query = request.GET.get('search', '').strip()
    employee_id = request.GET.get('employee_id', '').strip()
    department_id = request.GET.get('department', '').strip()
    status_filter = request.GET.get('status', '').strip()
    month_filter = request.GET.get('month', '').strip()
    year_filter = request.GET.get('year', '').strip()

    if search_query and is_admin_user:
        # Only allow search for admin users
        base_qs = base_qs.filter(
            Q(employee__code__icontains=search_query) |
            Q(employee__firstname__icontains=search_query) |
            Q(employee__lastname__icontains=search_query) |
            Q(employee__email__icontains=search_query)
        )

    if employee_id and is_admin_user:
        # Only allow employee filter for admin users
        try:
            base_qs = base_qs.filter(employee_id=int(employee_id))
        except ValueError:
            pass

    if department_id and is_admin_user:
        # Only allow department filter for admin users
        try:
            base_qs = base_qs.filter(employee__department_id=int(department_id))
        except ValueError:
            pass

    if status_filter and status_filter in ['paid', 'pending', 'failed']:
        base_qs = base_qs.filter(status=status_filter)

    if month_filter and year_filter:
        try:
            base_qs = base_qs.filter(
                pay_date__year=int(year_filter),
                pay_date__month=int(month_filter)
            )
        except ValueError:
            pass

    records = base_qs.order_by('-pay_date', 'employee__firstname')

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payroll_records_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Employee ID', 'Employee Name', 'Department', 'Position', 'Base Salary',
        'Allowances', 'Deductions', 'Net Salary', 'Pay Date', 'Status', 'Notes'
    ])

    for record in records:
        writer.writerow([
            record.employee.code or '',
            f"{record.employee.firstname} {record.employee.lastname or ''}".strip(),
            record.employee.department.name if record.employee.department else '',
            record.employee.position.name if record.employee.position else '',
            str(record.base_salary),
            str(record.allowances),
            str(record.deductions),
            str(record.net_salary),
            record.pay_date.strftime('%Y-%m-%d'),
            record.get_status_display(),
            record.notes or '',
        ])

    return response


@login_required
def payroll_export_excel(request):
    """Export payroll records to Excel (CSV format that opens in Excel)"""
    # For now, use CSV which Excel can open
    # If openpyxl is available, we can use it for true Excel format
    try:
        # Optional dependency: openpyxl may not be installed
        import openpyxl  # pyright: ignore[reportMissingImports]
        from openpyxl.styles import Font, Alignment  # pyright: ignore[reportMissingImports]

        # Check user role for proper scoping
        is_admin_user = request.user.is_superuser
        try:
            user_role = request.user.profile.role
            is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
        except:
            user_role = 'employee'

        # Base queryset - scoped for employee users
        if is_admin_user or request.user.is_superuser:
            base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position')
        else:
            # For employee users, filter to their own records
            current_employee = get_current_employee(request)
            if current_employee:
                base_qs = PayrollRecord.objects.select_related('employee', 'employee__department', 'employee__position').filter(employee=current_employee)
            else:
                base_qs = PayrollRecord.objects.none()

        # Apply filters (same as CSV)
        search_query = request.GET.get('search', '').strip()
        employee_id = request.GET.get('employee_id', '').strip()
        department_id = request.GET.get('department', '').strip()
        status_filter = request.GET.get('status', '').strip()
        month_filter = request.GET.get('month', '').strip()
        year_filter = request.GET.get('year', '').strip()

        if search_query and is_admin_user:
            # Only allow search for admin users
            base_qs = base_qs.filter(
                Q(employee__code__icontains=search_query) |
                Q(employee__firstname__icontains=search_query) |
                Q(employee__lastname__icontains=search_query) |
                Q(employee__email__icontains=search_query)
            )

        if employee_id and is_admin_user:
            # Only allow employee filter for admin users
            try:
                base_qs = base_qs.filter(employee_id=int(employee_id))
            except ValueError:
                pass

        if department_id and is_admin_user:
            # Only allow department filter for admin users
            try:
                base_qs = base_qs.filter(employee__department_id=int(department_id))
            except ValueError:
                pass

        if status_filter and status_filter in ['paid', 'pending', 'failed']:
            base_qs = base_qs.filter(status=status_filter)

        if month_filter and year_filter:
            try:
                base_qs = base_qs.filter(
                    pay_date__year=int(year_filter),
                    pay_date__month=int(month_filter)
                )
            except ValueError:
                pass

        records = base_qs.order_by('-pay_date', 'employee__firstname')

        # Create Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Payroll Records"

        # Headers
        headers = [
            'Employee ID', 'Employee Name', 'Department', 'Position', 'Base Salary',
            'Allowances', 'Deductions', 'Net Salary', 'Pay Date', 'Status', 'Notes'
        ]
        ws.append(headers)

        # Style header row
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        # Add data
        for record in records:
            ws.append([
                record.employee.code or '',
                f"{record.employee.firstname} {record.employee.lastname or ''}".strip(),
                record.employee.department.name if record.employee.department else '',
                record.employee.position.name if record.employee.position else '',
                float(record.base_salary),
                float(record.allowances),
                float(record.deductions),
                float(record.net_salary),
                record.pay_date.strftime('%Y-%m-%d'),
                record.get_status_display(),
                record.notes or '',
            ])

        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="payroll_records_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        wb.save(response)
        return response

    except ImportError:
        # Fallback to CSV if openpyxl is not available
        return payroll_export_csv(request)


@login_required
@require_POST
def add_increment(request):
    employee_id = request.POST.get('employee')
    effective_date = request.POST.get('effective_date')
    new_salary = Decimal(request.POST.get('new_salary') or 0)
    reason = request.POST.get('reason', '')

    if not (employee_id and effective_date and new_salary):
        return JsonResponse({'success': False, 'message': 'Missing fields.'}, status=400)

    employee = get_object_or_404(only_me_employee_qs(request), pk=employee_id)  # scoped
    old_salary = Decimal(employee.salary or 0)
    inc_percent = Decimal('0.00') if old_salary == 0 else (new_salary - old_salary) * Decimal('100.0') / old_salary

    SalaryIncrement.objects.create(
        employee=employee,
        old_salary=old_salary,
        new_salary=new_salary,
        increase_percent=inc_percent,
        effective_date=datetime.strptime(effective_date, '%Y-%m-%d').date(),
        reason=reason,
        applied_by=request.user
    )
    employee.salary = new_salary
    employee.save(update_fields=['salary'])
    return JsonResponse({'success': True})


# ===========================
#   SIMPLE PAGES
# ===========================

@login_required
@login_required

# Payroll API Views
def api_get_payrolls(request):
    qs = scope_by_user(PayrollRecord.objects.select_related('employee').order_by('-pay_date'), request, field='employee')
    month = request.GET.get('month'); year = request.GET.get('year'); pay_date = request.GET.get('pay_date'); payroll_id = request.GET.get('payroll_id')
    employee_q = (request.GET.get('employee') or '').strip()

    if payroll_id:
        qs = qs.filter(payroll_id=payroll_id)
    elif pay_date:
        pd = parse_date(pay_date)
        if pd: qs = qs.filter(pay_date=pd)
    elif month and year:
        try:
            qs = qs.filter(pay_date__year=int(year), pay_date__month=int(month))
        except Exception:
            pass

    if employee_q:
        qs = qs.filter(Q(employee__firstname__icontains=employee_q)|Q(employee__lastname__icontains=employee_q)|Q(employee__code__icontains=employee_q))

    data = [{
        "id": rec.id,
        "employee_id": rec.employee.id,
        "employee_name": f"{getattr(rec.employee, 'firstname','')} {getattr(rec.employee, 'lastname','')}".strip(),
        "base_salary": str(rec.base_salary),
        "allowances": str(rec.allowances),
        "deductions": str(rec.deductions),
        "net_salary": str(rec.net_salary),
        "pay_date": rec.pay_date.strftime('%Y-%m-%d'),
        "status": rec.status,
        "notes": rec.notes or "",
    } for rec in qs[:2000]]
    return JsonResponse({"records": data})

@login_required
def api_process_payroll(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Use POST"}, status=400)
    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = request.POST

        pay_period = payload.get('pay_period') or payload.get('payPeriod')
        pay_date = payload.get('pay_date') or payload.get('payDate')
        employees_list = payload.get('employees') or []
        if not pay_period or not pay_date:
            return JsonResponse({"success": False, "error": "pay_period and pay_date required"}, status=400)

        pd = parse_date(pay_date)
        if not pd: return JsonResponse({"success": False, "error": "Invalid pay_date"}, status=400)

        payroll = Payroll.objects.create(pay_period=pay_period, pay_date=pd, processed_by=request.user)

        emp_qs = only_me_employee_qs(request).filter(status=1)
        if isinstance(employees_list, list) and 'all' not in employees_list:
            ids = [int(e) for e in employees_list if str(e).isdigit()]
            emp_qs = emp_qs.filter(id__in=ids)

        created = 0
        default_allowances = Decimal(payload.get('default_allowances') or 0)
        default_deductions = Decimal(payload.get('default_deductions') or 0)

        for emp in emp_qs:
            base = Decimal(getattr(emp, 'salary', 0) or 0)
            PayrollRecord.objects.create(
                payroll=payroll, employee=emp,
                base_salary=base, allowances=default_allowances, deductions=default_deductions,
                pay_date=pd, status='paid', processed_at=timezone.now()
            )
            created += 1

        return JsonResponse({"success": True, "created": created, "payroll_id": payroll.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

# ===========================
#   SALARY DISBURSEMENT (BANK API INTEGRATION)
# ===========================

@login_required
@finance_or_admin_required
def search_employees_payroll(request):
    """Search employees by ID or name for payroll - Admin/Finance/Superuser only"""
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'success': False, 'error': 'Search query required'}, status=400)

    employees = Employees.objects.filter(
        Q(code__icontains=query) |
        Q(firstname__icontains=query) |
        Q(lastname__icontains=query) |
        Q(email__icontains=query)
    ).filter(status=1)[:50]  # Only active employees, limit to 50

    results = []
    for emp in employees:
        results.append({
            'id': emp.id,
            'code': emp.code,
            'name': f"{emp.firstname} {emp.lastname or ''}".strip(),
            'email': emp.email or emp.official_email or '',
            'department': emp.department.name if emp.department else '',
            'position': emp.position.name if emp.position else '',
            'salary': float(emp.salary or 0),
            'account_number': emp.account_number or '',
            'bank_name': emp.bank_name or '',
        })

    return JsonResponse({'success': True, 'employees': results})


@login_required
@finance_or_admin_required
@require_POST
def bulk_salary_disbursement(request):
    """Initiate bulk salary disbursement via bank API - Finance/Admin/Superuser only"""
    import json
    import uuid
    from datetime import datetime

    try:
        data = json.loads(request.body) if request.body else request.POST
        payroll_record_ids = data.get('payroll_record_ids', [])
        payment_method = data.get('payment_method', 'bank_api')
        notes = data.get('notes', '')

        if not payroll_record_ids:
            return JsonResponse({'success': False, 'error': 'No payroll records selected'}, status=400)

        # Get payroll records
        payroll_records = PayrollRecord.objects.filter(
            id__in=payroll_record_ids,
            status__in=['pending', 'paid']  # Can process pending or re-process paid
        ).select_related('employee')

        if not payroll_records.exists():
            return JsonResponse({'success': False, 'error': 'No valid payroll records found'}, status=400)

        # Create disbursement record
        disbursement_id = f"DISB-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        total_amount = sum(Decimal(str(rec.net_salary)) for rec in payroll_records)

        disbursement = SalaryDisbursement.objects.create(
            disbursement_id=disbursement_id,
            payroll=payroll_records.first().payroll,
            initiated_by=request.user,
            total_amount=total_amount,
            total_employees=payroll_records.count(),
            status='pending',
            payment_method=payment_method,
            notes=notes
        )

        # Create disbursement records for each employee
        disbursement_records = []
        bank_payload = []

        for pr in payroll_records:
            # Get employee bank details
            bank_account = pr.employee.account_number or ''
            bank_name = pr.employee.bank_name or ''

            # Create disbursement record
            disb_record = SalaryDisbursementRecord.objects.create(
                disbursement=disbursement,
                payroll_record=pr,
                employee=pr.employee,
                amount=pr.net_salary,
                bank_account_number=bank_account,
                bank_name=bank_name,
                status='pending'
            )
            disbursement_records.append(disb_record)

            # Prepare bank API payload
            if bank_account:
                bank_payload.append({
                    'employee_id': pr.employee.code,
                    'employee_name': f"{pr.employee.firstname} {pr.employee.lastname or ''}".strip(),
                    'account_number': bank_account,
                    'bank_name': bank_name,
                    'amount': float(pr.net_salary),
                    'currency': 'USD',
                    'reference': f"SAL-{pr.employee.code}-{pr.pay_date.strftime('%Y%m%d')}",
                    'description': f"Salary payment for {pr.pay_date.strftime('%B %Y')}"
                })

        # Update disbursement with bank API request
        disbursement.bank_api_request = {
            'disbursement_id': disbursement_id,
            'total_amount': float(total_amount),
            'total_transactions': len(bank_payload),
            'transactions': bank_payload,
            'timestamp': datetime.now().isoformat()
        }
        disbursement.save()

        # Process via bank API (simulated or real)
        if payment_method == 'bank_api':
            result = process_bank_api_disbursement(disbursement, bank_payload)
        else:
            # Manual processing
            result = {
                'success': True,
                'message': 'Disbursement created. Please process manually.',
                'disbursement_id': disbursement_id
            }
            disbursement.status = 'pending'
            disbursement.save()

        return JsonResponse({
            'success': True,
            'disbursement_id': disbursement_id,
            'message': result.get('message', 'Disbursement initiated successfully'),
            'total_amount': float(total_amount),
            'total_employees': payroll_records.count()
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def process_bank_api_disbursement(disbursement, bank_payload):
    """Process salary disbursement via bank API (can be replaced with actual API integration)"""
    from django.conf import settings

    # This is a placeholder - replace with actual bank API integration
    try:
        # Simulate API call (replace with actual bank API endpoint)
        # bank_api_url = getattr(settings, 'BANK_API_URL', 'https://api.bank.com/bulk-transfer')
        # bank_api_key = getattr(settings, 'BANK_API_KEY', '')
        #
        # headers = {
        #     'Authorization': f'Bearer {bank_api_key}',
        #     'Content-Type': 'application/json'
        # }
        #
        # response = requests.post(
        #     bank_api_url,
        #     json={
        #         'disbursement_id': disbursement.disbursement_id,
        #         'transactions': bank_payload
        #     },
        #     headers=headers,
        #     timeout=30
        # )
        #
        # if response.status_code == 200:
        #     api_response = response.json()
        #     # Process response and update records
        # else:
        #     raise Exception(f"Bank API error: {response.status_code}")

        # For now, simulate successful processing
        disbursement.status = 'processing'
        disbursement.save()

        # Simulate processing each record
        successful = 0
        failed = 0

        for record in disbursement.payment_records.all():
            # Simulate API response (replace with actual processing)
            import random
            if random.random() > 0.1:  # 90% success rate for simulation
                record.status = 'success'
                record.transaction_id = f"TXN-{disbursement.disbursement_id}-{record.id}"
                record.bank_response = {'status': 'success', 'transaction_id': record.transaction_id}
                record.processed_at = timezone.now()
                record.save()

                # Update payroll record status
                record.payroll_record.status = 'paid'
                record.payroll_record.processed_at = timezone.now()
                record.payroll_record.save()

                successful += 1
            else:
                record.status = 'failed'
                record.error_message = 'Simulated bank API failure'
                record.processed_at = timezone.now()
                record.save()
                failed += 1

        # Update disbursement status
        disbursement.successful_payments = successful
        disbursement.failed_payments = failed
        disbursement.status = 'completed' if failed == 0 else 'partial' if successful > 0 else 'failed'
        disbursement.processed_at = timezone.now()
        disbursement.completed_at = timezone.now() if disbursement.status == 'completed' else None
        disbursement.bank_api_response = {
            'successful': successful,
            'failed': failed,
            'status': disbursement.status
        }
        disbursement.save()

        return {
            'success': True,
            'message': f'Disbursement processed: {successful} successful, {failed} failed',
            'successful': successful,
            'failed': failed
        }

    except Exception as e:
        disbursement.status = 'failed'
        disbursement.error_message = str(e)
        disbursement.save()
        return {
            'success': False,
            'message': f'Disbursement failed: {str(e)}'
        }


@login_required
@finance_or_admin_required
def get_disbursement_details(request, disbursement_id):
    """Get details of a salary disbursement - Finance/Admin/Superuser only"""
    try:
        disbursement = SalaryDisbursement.objects.get(disbursement_id=disbursement_id)
        records = SalaryDisbursementRecord.objects.filter(disbursement=disbursement).select_related('employee', 'payroll_record')

        data = {
            'disbursement': {
                'id': disbursement.disbursement_id,
                'status': disbursement.status,
                'total_amount': float(disbursement.total_amount),
                'total_employees': disbursement.total_employees,
                'successful_payments': disbursement.successful_payments,
                'failed_payments': disbursement.failed_payments,
                'initiated_by': disbursement.initiated_by.get_full_name() if disbursement.initiated_by else 'Unknown',
                'initiated_at': disbursement.initiated_at.isoformat(),
                'processed_at': disbursement.processed_at.isoformat() if disbursement.processed_at else None,
                'payment_method': disbursement.payment_method,
                'notes': disbursement.notes,
            },
            'records': [
                {
                    'employee_code': rec.employee.code,
                    'employee_name': f"{rec.employee.firstname} {rec.employee.lastname or ''}".strip(),
                    'amount': float(rec.amount),
                    'status': rec.status,
                    'transaction_id': rec.transaction_id,
                    'error_message': rec.error_message,
                    'processed_at': rec.processed_at.isoformat() if rec.processed_at else None,
                }
                for rec in records
            ]
        }

        return JsonResponse({'success': True, 'data': data})
    except SalaryDisbursement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Disbursement not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@finance_or_admin_required
def list_disbursements(request):
    """List all salary disbursements - Finance/Admin/Superuser only"""
    disbursements = SalaryDisbursement.objects.all().order_by('-initiated_at')[:100]

    data = [
        {
            'id': d.disbursement_id,
            'status': d.status,
            'total_amount': float(d.total_amount),
            'total_employees': d.total_employees,
            'successful': d.successful_payments,
            'failed': d.failed_payments,
            'initiated_by': d.initiated_by.get_full_name() if d.initiated_by else 'Unknown',
            'initiated_at': d.initiated_at.isoformat(),
            'payment_method': d.payment_method,
        }
        for d in disbursements
    ]

    return JsonResponse({'success': True, 'disbursements': data})


@login_required
def api_update_payroll_record(request, pk):
    record = get_object_or_404(scope_by_user(PayrollRecord.objects.all(), request, field='employee'), pk=pk)
    if request.method not in ('POST', 'PUT'):
        return JsonResponse({"success": False, "error": "Use POST/PUT"}, status=400)
    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = request.POST

        base = payload.get('base_salary') or payload.get('base')
        allowances = payload.get('allowances'); deductions = payload.get('deductions')
        status = payload.get('status'); notes = payload.get('notes')

        if base is not None: record.base_salary = Decimal(base)
        if allowances is not None: record.allowances = Decimal(allowances)
        if deductions is not None: record.deductions = Decimal(deductions)
        if status: record.status = status
        if notes is not None: record.notes = notes
        record.processed_at = timezone.now(); record.save()
        return JsonResponse({"success": True, "id": record.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
def api_add_increment(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Use POST"}, status=400)
    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = request.POST

        emp_id = payload.get('employee_id'); new_salary = payload.get('new_salary'); eff_date = payload.get('effective_date'); reason = payload.get('reason', '')
        if not emp_id or not new_salary or not eff_date:
            return JsonResponse({"success": False, "error": "employee_id,new_salary,effective_date required"}, status=400)

        emp = get_object_or_404(only_me_employee_qs(request), pk=emp_id)
        old = Decimal(getattr(emp, 'salary', 0) or 0); new = Decimal(new_salary)
        increase_amount = new - old
        increase_percent = ((new - old) / old * 100) if old > 0 else 0

        inc = SalaryIncrement.objects.create(
            employee=emp, old_salary=old, new_salary=new,
            increase_percent=increase_percent,
            increase_amount=increase_amount,
            effective_date=parse_date(eff_date), reason=reason, applied_by=request.user,
            is_automatic=False
        )

        # Update employee salary and increment tracking
        emp.salary = int(new)
        emp.last_increment_date = parse_date(eff_date)

        # Calculate next increment date (6 months from effective date)
        from dateutil.relativedelta import relativedelta
        increment_settings = IncrementSettings.get_active()
        emp.next_increment_date = parse_date(eff_date) + relativedelta(months=increment_settings.cycle_months)

        emp.save(update_fields=['salary', 'last_increment_date', 'next_increment_date'])
        return JsonResponse({"success": True, "increment_id": inc.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
def api_get_increments(request):
    qs = scope_by_user(SalaryIncrement.objects.select_related('employee').order_by('-applied_at'), request, field='employee')[:200]
    data = [{
        "id": inc.id,
        "employee_id": inc.employee.id,
        "employee_name": f"{getattr(inc.employee,'firstname','')} {getattr(inc.employee,'lastname','')}".strip(),
        "old_salary": str(inc.old_salary),
        "new_salary": str(inc.new_salary),
        "increase_percent": str(inc.increase_percent),
        "effective_date": inc.effective_date.strftime('%Y-%m-%d'),
        "reason": inc.reason or "",
    } for inc in qs]
    return JsonResponse({"increments": data})
