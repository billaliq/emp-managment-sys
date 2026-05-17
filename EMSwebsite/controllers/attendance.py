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
from io import BytesIO
from django.utils.dateparse import parse_date

# ReportLab imports for PDF generation
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

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


def _holiday_name_by_date(dates):
    """
    Build a mapping {date -> holiday_name} for the given set/list of dates using the HolidayDate model.
    Avoids N+1 queries by loading holidays once for the date range, then checking in Python.
    """
    from EMSwebsite.models import HolidayDate

    dates = {d for d in (dates or []) if d}
    if not dates:
        return {}

    try:
        min_d = min(dates)
        max_d = max(dates)
    except Exception:
        return {}

    try:
        # Get all holidays in the date range
        holidays = list(
            HolidayDate.objects.filter(
                date__gte=min_d,
                date__lte=max_d,
            ).only("name", "date")
        )
    except Exception:
        # HolidayDate table may not exist yet (migrations not run) or DB error
        return {}

    if not holidays:
        return {}

    # Create a mapping of date -> holiday name
    out = {}
    holiday_dict = {h.date: h.name for h in holidays}
    for d in dates:
        if d in holiday_dict:
            out[d] = holiday_dict[d]
    return out


def _attach_holiday_fields(records):
    """
    Attach `is_holiday_date` and `holiday_name` attributes to each attendance record for rendering.
    """
    try:
        dates = {r.date for r in records if getattr(r, "date", None)}
    except Exception:
        dates = set()
        try:
            for r in list(records):
                if getattr(r, "date", None):
                    dates.add(r.date)
        except Exception:
            dates = set()

    holiday_map = _holiday_name_by_date(dates)

    # Mutate in-place for templates/serialization
    try:
        for r in records:
            name = holiday_map.get(getattr(r, "date", None))
            setattr(r, "is_holiday_date", bool(name))
            setattr(r, "holiday_name", name or "")
    except Exception:
        pass


@login_required
def attendance(request):
    """Main attendance view - properly scoped for all users with team filtering"""
    today = timezone.now().date()
    current_month = today.replace(day=1)

    # Check if today is weekend (Saturday=5, Sunday=6)
    is_weekend = today.weekday() >= 5

    # Check user role
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Get current employee
    current_employee = get_current_employee(request)

    # For employees (non-admin), redirect to their own detailed attendance view
    if not is_admin_user and current_employee:
        return redirect('employee_attendance', employee_id=current_employee.id)

    # Get team filter from request
    team_filter = request.GET.get('team', '')

    # ✅ SAFER ACTIVE FILTER (handles 1, "1", True, "active")
    active_filter = (
        Q(status=1) |
        Q(status=True) |
        Q(status='1') |
        Q(status__iexact='active')
    )

    # Base queryset - properly scoped
    if is_admin_user or request.user.is_superuser:
        base_qs = Attendance.objects.select_related('employee')

        # ✅ Only ACTIVE employees + exclude test/dummy
        employees_qs = Employees.objects.filter(active_filter).exclude(
            Q(code__icontains='test') |
            Q(code__icontains='dummy') |
            Q(code__icontains='sample') |
            Q(firstname__icontains='test') |
            Q(firstname__icontains='dummy') |
            Q(firstname__icontains='sample') |
            Q(lastname__icontains='test') |
            Q(lastname__icontains='dummy') |
            Q(lastname__icontains='sample')
        )

        # Apply team filter if provided
        if team_filter:
            employees_qs = employees_qs.filter(team=team_filter)
            base_qs = base_qs.filter(employee__team=team_filter)

        employees = employees_qs.order_by('firstname')
        total_employees = employees.count()  # ✅ now correct
    else:
        if current_employee:
            base_qs = Attendance.objects.select_related('employee').filter(employee=current_employee)
            total_employees = 1
            employees = Employees.objects.filter(pk=current_employee.pk)
            if not base_qs.exists():
                messages.info(request, f'No attendance records found for {current_employee.firstname} {current_employee.lastname or ""}.')
        else:
            messages.warning(request, 'Employee profile not linked to your account. Please contact administrator.')
            base_qs = Attendance.objects.none()
            total_employees = 0
            employees = Employees.objects.none()

    # Exclude dummy/test data
    base_qs = base_qs.exclude(
        Q(employee__code__icontains='test') |
        Q(employee__code__icontains='dummy') |
        Q(employee__code__icontains='sample') |
        Q(employee__firstname__icontains='test') |
        Q(employee__firstname__icontains='dummy') |
        Q(employee__firstname__icontains='sample') |
        Q(employee__lastname__icontains='test') |
        Q(employee__lastname__icontains='dummy') |
        Q(employee__lastname__icontains='sample') |
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )

    # Auto-absent: Mark employees as absent/weekend if they haven't marked attendance today.
    employees_for_auto = Employees.objects.none()
    if is_admin_user:
        employees_for_auto = employees
    elif current_employee:
        employees_for_auto = Employees.objects.filter(pk=current_employee.pk)

    if employees_for_auto.exists():
        auto_mark_absent_for_date(today, employees_for_auto, team_filter if team_filter else None)

    # Sync existing attendance records with holidays (in case holidays were added after records were created)
    # Get date range from request if provided, otherwise sync today and a reasonable range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    sync_start = validate_date(date_from) if date_from else today
    sync_end = validate_date(date_to) if date_to else today

    # If no date filters, sync a wider range (last 30 days to next 30 days) to catch all holidays
    if not date_from and not date_to:
        from datetime import timedelta
        sync_start = today - timedelta(days=30)
        sync_end = today + timedelta(days=30)

    try:
        sync_attendance_with_holidays(date_range_start=sync_start, date_range_end=sync_end)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error syncing attendance with holidays: {str(e)}', exc_info=True)
        pass  # Silently fail if there's an issue

    # Refresh base_qs to include newly created/updated attendance records while preserving scoping
    # This ensures we get the latest data after sync (important after holiday deletion)
    if is_admin_user or request.user.is_superuser:
        base_qs = Attendance.objects.select_related('employee')
        if team_filter:
            base_qs = base_qs.filter(employee__team=team_filter)
    else:
        base_qs = Attendance.objects.select_related('employee').filter(employee__in=employees_for_auto)

    # Re-apply exclusions
    base_qs = base_qs.exclude(
        Q(employee__code__icontains='test') |
        Q(employee__code__icontains='dummy') |
        Q(employee__code__icontains='sample') |
        Q(employee__firstname__icontains='test') |
        Q(employee__firstname__icontains='dummy') |
        Q(employee__firstname__icontains='sample') |
        Q(employee__lastname__icontains='test') |
        Q(employee__lastname__icontains='dummy') |
        Q(employee__lastname__icontains='sample') |
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )

    team_choices = Employees.TEAM_CHOICES

    teams_with_leads = []
    if is_admin_user:
        teams = Team.objects.select_related('leader', 'department').all()
        for team in teams:
            teams_with_leads.append({
                'id': team.id,
                'name': team.name,
                'lead_name': team.leader.team if team.leader and team.leader.team else f"{team.leader.firstname} {team.leader.lastname or ''}" if team.leader else 'No Lead',
                'lead_id': team.leader.id if team.leader else None,
                'members_count': team.members_count,
            })

    base_qs = base_qs.select_related('employee')

    # Filter out weekend records without attendance (employee didn't arrive on weekend)
    # Weekend records should only show if employee has check-in or check-out
    base_qs = base_qs.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    # Today's attendance summary (AFTER all exclusions for accurate counts)
    today_attendance_records = base_qs.filter(date=today).select_related('employee')

    # ✅ Present = anyone with check-in OR check-out OR status is present-like
    today_present = today_attendance_records.filter(
        Q(check_in_time__isnull=False) |
        Q(check_out_time__isnull=False) |
        Q(status__in=['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting'])
    ).count()

    # ✅ Absent = absent status AND no check-in/out
    today_absent = today_attendance_records.filter(
        status='absent',
        check_in_time__isnull=True,
        check_out_time__isnull=True
    ).count()

    today_late = today_attendance_records.filter(status='late').count()
    today_leave = today_attendance_records.filter(status='leave').count()

    # Weekend work: only if weekend AND worked
    if today.weekday() >= 5:
        today_weekend_work = today_attendance_records.filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
    else:
        today_weekend_work = 0

    today_attendance_rate = (today_present / total_employees * 100) if total_employees > 0 else 0

    # Monthly stats - properly scoped
    monthly_records = base_qs.filter(date__gte=current_month, date__lte=today)

    monthly_present = monthly_records.filter(
        Q(check_in_time__isnull=False) |
        Q(check_out_time__isnull=False) |
        Q(status__in=['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting'])
    ).count()

    monthly_total = monthly_records.count()
    monthly_attendance_rate = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0

    late_arrivals = base_qs.filter(date=today, status='late').count()
    early_departures = base_qs.filter(date=today, status='early-out').count()
    overtime_hours = base_qs.filter(date=today).aggregate(total=Sum('overtime_hours'))['total'] or 0

    # Apply status filter if provided
    status_filter = request.GET.get('status', '').strip()
    if status_filter and status_filter != 'all':
        if status_filter == 'present':
            # Present = anyone who has check-in OR check-out OR status is explicitly present-like
            base_qs = base_qs.filter(
                Q(check_in_time__isnull=False) |
                Q(check_out_time__isnull=False) |
                Q(status__in=['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting'])
            )
        elif status_filter == 'absent':
            # Absent includes: absent, leave
            # Exclude weekend records (they're neither present nor absent)
            base_qs = base_qs.filter(
                status__in=['absent', 'leave']
            ).exclude(status='weekend')
        elif status_filter == 'late':
            # Late arrivals
            base_qs = base_qs.filter(status='late')
        elif status_filter == 'overtime':
            # Overtime: records with status='overtime' OR overtime_hours > 0
            base_qs = base_qs.filter(
                Q(status='overtime') | Q(overtime_hours__gt=0)
            )
        elif status_filter == 'leave':
            # On leave
            base_qs = base_qs.filter(status='leave')
        elif status_filter == 'weekend':
            # Weekend work: weekend date AND employee worked
            base_qs = base_qs.filter(
                Q(date__week_day__in=[1, 7]) &
                (Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False))
            )
        else:
            # For other status values, filter by status
            base_qs = base_qs.filter(status=status_filter)

    # Get all records ordered by date (latest first) and updated_at (most recent first)
    if is_admin_user or request.user.is_superuser:
        today_records = base_qs.filter(date=today).order_by('-updated_at', 'employee__firstname')
        other_records = base_qs.filter(date__lt=today).order_by('-date', '-updated_at', 'employee__firstname')
        from itertools import chain
        all_records = list(chain(today_records, other_records))
    else:
        all_records = base_qs.filter(date__lte=today).order_by('-date', '-updated_at')

    # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
    seen = {}
    unique_records = []
    for record in all_records:
        key = (record.employee_id, record.date)
        if key not in seen:
            seen[key] = record
            unique_records.append(record)
        else:
            # If duplicate found, keep the one with the latest updated_at
            existing_record = seen[key]
            if record.updated_at > existing_record.updated_at:
                # Replace with newer record
                unique_records.remove(existing_record)
                seen[key] = record
                unique_records.append(record)

    # Re-sort after deduplication to ensure proper ordering
    if is_admin_user or request.user.is_superuser:
        # Sort by date (descending), then by employee name
        unique_records.sort(key=lambda x: (-x.date.toordinal(), x.employee.firstname))
    else:
        # Sort by date (descending)
        unique_records.sort(key=lambda x: -x.date.toordinal())

    # Attach holiday info from Holiday configuration BEFORE pagination
    # This ensures all records have holiday data attached
    _attach_holiday_fields(unique_records)

    per_page = int(request.GET.get('per_page', 50))
    if per_page not in [10, 25, 50, 100, 200]:
        per_page = 50

    paginator = Paginator(unique_records, per_page)
    page = request.GET.get('page', 1)
    try:
        attendance_records = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        attendance_records = paginator.page(1)

    can_mark_attendance = request.user.is_superuser or (user_role in ['admin', 'hr'])

    # Get all holiday dates for display
    holiday_dates = {h.date: h.name for h in HolidayDate.objects.all()}

    return render(request, 'pages/attendance.html', {
        'today_attendance_rate': round(today_attendance_rate, 1),
        'monthly_attendance_rate': round(monthly_attendance_rate, 1),
        'late_arrivals': late_arrivals,
        'early_departures': early_departures,
        'overtime_hours': int(overtime_hours),
        'attendance_records': attendance_records,
        'attendance_records_paginated': attendance_records,
        'employees': employees,
        'today': today,
        'is_weekend': is_weekend,
        'today_attendance_summary': {
            'total': total_employees,   # ✅ now only active employees
            'present': today_present,
            'absent': today_absent,
            'late': today_late,
            'leave': today_leave,
            'weekend_work': today_weekend_work,
        },
        'today_attendance_records': today_attendance_records,
        'team_choices': team_choices,
        'teams_with_leads': teams_with_leads,
        'selected_team': team_filter,
        'user_role': user_role,
        'is_admin': request.user.is_superuser or (user_role == 'admin'),
        'can_mark_attendance': can_mark_attendance,
        'current_employee': current_employee,
        'per_page': per_page,
        'holiday_dates': holiday_dates,
    })


@login_required
def employee_attendance(request, employee_id):
    """
    View attendance records for a specific employee
    Accessible by admin/HR/superuser for any employee, or by employees for their own records
    """
    # Check user role
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Get the employee
    try:
        employee = Employees.objects.select_related('department', 'position').get(pk=employee_id)
    except Employees.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('employee_profile')

    # Check if user has permission to view this employee's attendance
    current_employee = get_current_employee(request)
    if not is_admin_user:
        # Employees can only view their own attendance
        if not current_employee or current_employee.id != employee.id:
            messages.error(request, 'You do not have permission to view this employee\'s attendance.')
            return redirect('attendance')

    today = timezone.now().date()
    current_month = today.replace(day=1)

    # Base queryset - only this employee's attendance
    base_qs = Attendance.objects.select_related('employee').filter(employee=employee)

    # Filter out weekend records without attendance
    base_qs = base_qs.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    # Exclude dummy/test data
    base_qs = base_qs.exclude(
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )

    # Get date filters from request
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status_filter = request.GET.get('status', '').strip()

    from_date = validate_date(date_from)
    to_date = validate_date(date_to)

    # Apply date filters
    if from_date and to_date:
        base_qs = base_qs.filter(date__gte=from_date, date__lte=to_date)
    elif from_date:
        base_qs = base_qs.filter(date__gte=from_date)
    elif to_date:
        base_qs = base_qs.filter(date__lte=to_date)

    # Apply status filter
    if status_filter and status_filter != 'all':
        if status_filter == 'present':
            # Present = anyone who has check-in OR check-out OR status is explicitly present-like
            base_qs = base_qs.filter(
                Q(check_in_time__isnull=False) |
                Q(check_out_time__isnull=False) |
                Q(status__in=['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting'])
            )
        elif status_filter == 'absent':
            base_qs = base_qs.filter(status__in=['absent', 'leave']).exclude(status='weekend')
        elif status_filter == 'late':
            # Late arrivals
            base_qs = base_qs.filter(status='late')
        elif status_filter == 'overtime':
            # Overtime: records with status='overtime' OR overtime_hours > 0
            base_qs = base_qs.filter(
                Q(status='overtime') | Q(overtime_hours__gt=0)
            )
        elif status_filter == 'leave':
            # On leave
            base_qs = base_qs.filter(status='leave')
        elif status_filter == 'weekend':
            base_qs = base_qs.filter(
                Q(date__week_day__in=[1, 7]) &
                (Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False))
            )
        else:
            base_qs = base_qs.filter(status=status_filter)

    # Order by date (latest first) and updated_at
    base_qs = base_qs.order_by('-date', '-updated_at')

    # Remove duplicates: Keep only the latest record (by updated_at) for each date
    seen = {}
    unique_records = []
    for record in base_qs:
        key = record.date
        if key not in seen:
            seen[key] = record
            unique_records.append(record)
        else:
            existing_record = seen[key]
            if record.updated_at > existing_record.updated_at:
                unique_records.remove(existing_record)
                seen[key] = record
                unique_records.append(record)

    # Re-sort after deduplication
    unique_records.sort(key=lambda x: -x.date.toordinal())

    # Pagination
    per_page = int(request.GET.get('per_page', 50))
    if per_page not in [10, 25, 50, 100, 200]:
        per_page = 50

    paginator = Paginator(unique_records, per_page)
    page = request.GET.get('page', 1)
    try:
        attendance_records = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        attendance_records = paginator.page(1)

    # Attach holiday info for rendering
    _attach_holiday_fields(attendance_records)

    # Calculate statistics for this employee
    all_attendance = Attendance.objects.filter(employee=employee).exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    today_attendance = all_attendance.filter(date=today).first()
    monthly_attendance = all_attendance.filter(date__gte=current_month, date__lte=today)
    monthly_present = monthly_attendance.filter(
        Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
    ).count()

    # Calculate total working days in the month (excluding weekends) up to today
    from datetime import timedelta
    working_days = 0
    current_date = current_month
    while current_date <= today:
        # Count only weekdays (Monday=0 to Friday=4)
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)

    # Use working days as the denominator for accurate attendance rate
    monthly_total = working_days if working_days > 0 else 1
    monthly_attendance_rate = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0

    total_attendance = all_attendance.count()
    total_present = all_attendance.filter(
        Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
    ).count()

    # Check if employee is viewing their own profile
    is_own_profile = current_employee and current_employee.id == employee.id if current_employee else False

    return render(request, 'pages/employee_attendance.html', {
        'employee': employee,
        'attendance_records': attendance_records,
        'attendance_records_paginated': attendance_records,
        'today': today,
        'per_page': per_page,
        'date_from': date_from,
        'date_to': date_to,
        'status_filter': status_filter,
        'user_role': user_role,
        'is_admin': is_admin_user,
        'is_own_profile': is_own_profile,
        'attendance_stats': {
            'monthly_present': monthly_present,
            'monthly_total': monthly_total,
            'monthly_rate': round(monthly_attendance_rate, 1),
            'today_attendance': today_attendance,
            'total_attendance': total_attendance,
            'total_present': total_present,
        },
    })


@login_required
def attendance_dashboard(request):
    """Legacy function - redirect to main attendance view"""
    return redirect('attendance')

@login_required
def attendance_list(request):
    """Legacy function - redirect to main attendance view"""
    return redirect('attendance')

@login_required
@hr_or_admin_required
def mark_attendance(request):
    if request.method == 'POST':
        try:
            attendance_id = request.POST.get('attendance_id')
            employee_id = request.POST.get('employee')
            attendance_date = request.POST.get('date')
            check_in = request.POST.get('check_in')
            check_out = request.POST.get('check_out')
            status = request.POST.get('status', 'present')
            leave_type = request.POST.get('leave_type', '')
            overtime_hours = request.POST.get('overtime_hours', 0)
            notes = request.POST.get('notes', '')

            # Check if user can mark attendance for others (admin/hr/superuser)
            can_mark_for_others = request.user.is_superuser
            if not can_mark_for_others:
                try:
                    profile = request.user.profile
                    can_mark_for_others = profile.role in ['admin', 'hr']
                except UserProfile.DoesNotExist:
                    can_mark_for_others = False

            # For non-admin/hr/superuser, ensure they can only mark attendance for themselves
            if not can_mark_for_others:
                current_employee = get_current_employee(request)
                if not current_employee or str(current_employee.id) != employee_id:
                    messages.error(request, 'You can only mark attendance for yourself.')
                    return redirect('attendance')

            employee = get_object_or_404(Employees, pk=employee_id)
            attendance_date = validate_date(attendance_date)
            check_in_time = datetime.strptime(check_in, '%H:%M').time() if check_in else None
            check_out_time = datetime.strptime(check_out, '%H:%M').time() if check_out else None
            overtime_hours = float(overtime_hours or 0)

            if attendance_id:
                # For non-admin/hr/superuser, ensure they can only edit their own records
                if not can_mark_for_others:
                    current_employee = get_current_employee(request)
                    attendance = get_object_or_404(Attendance, pk=attendance_id, employee=current_employee)
                else:
                    attendance = get_object_or_404(Attendance, pk=attendance_id)

                attendance.employee = employee
                attendance.date = attendance_date
                attendance.check_in_time = check_in_time
                attendance.check_out_time = check_out_time

                # Get simplified status from form (present/absent/leave)
                simplified_status = status

                # Recalculate durations based on new times
                attendance.calculate_durations()

                # Handle status based on form selection
                if simplified_status == 'leave':
                    # Status is "leave" - set to leave and save leave_type
                    attendance.status = 'leave'
                    attendance.leave_type = leave_type if leave_type else None
                    attendance._explicit_status = True
                elif simplified_status == 'absent':
                    # If status is "absent", set to absent (or leave if leave_type exists)
                    if leave_type:
                        attendance.status = 'leave'
                        attendance.leave_type = leave_type
                    else:
                        attendance.status = 'absent'
                        attendance.leave_type = None
                    attendance._explicit_status = True
                else:
                    # If status is "present", auto-determine the proper status based on times
                    attendance.status = attendance.auto_determine_status()
                    attendance.leave_type = None  # Clear leave_type for present status
                    attendance._explicit_status = True

                attendance.overtime_hours = overtime_hours
                attendance.notes = notes

                # Indicate that status was explicitly set by the user/view so model won't auto-overwrite it
                attendance._explicit_status = True
                attendance.save()
                messages.success(request, f'Attendance updated for {employee.firstname}')
            else:
                # Check if attendance record already exists (e.g., from auto-absent logic)
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=attendance_date,
                    defaults={
                        'check_in_time': check_in_time,
                        'check_out_time': check_out_time,
                        'status': 'present',  # Temporary, will be recalculated
                        'overtime_hours': overtime_hours,
                        'notes': notes
                    }
                )

                # If record already exists, update it
                if not created:
                    attendance.check_in_time = check_in_time
                    attendance.check_out_time = check_out_time
                    attendance.overtime_hours = overtime_hours
                    attendance.notes = notes

                # Get simplified status from form (present/absent/leave)
                simplified_status = status

                # Recalculate durations based on times
                attendance.calculate_durations()

                # Handle status based on form selection
                if simplified_status == 'leave':
                    # Status is "leave" - set to leave and save leave_type
                    attendance.status = 'leave'
                    attendance.leave_type = leave_type if leave_type else None
                    attendance._explicit_status = True
                elif simplified_status == 'absent':
                    # If status is "absent", set to absent (or leave if leave_type exists)
                    if leave_type:
                        attendance.status = 'leave'
                        attendance.leave_type = leave_type
                    else:
                        attendance.status = 'absent'
                        attendance.leave_type = None
                    attendance._explicit_status = True
                else:
                    # If status is "present", auto-determine the proper status based on times
                    attendance.status = attendance.auto_determine_status()
                    attendance.leave_type = None  # Clear leave_type for present status
                    attendance._explicit_status = True

                attendance.save()

                if created:
                    messages.success(request, f'Attendance marked for {employee.firstname}')
                else:
                    messages.success(request, f'Attendance updated for {employee.firstname}')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('attendance')

@login_required
@hr_or_admin_required
def update_attendance(request, pk):
    """Update attendance - Only admin/HR can update attendance records"""
    attendance_record = get_object_or_404(Attendance, pk=pk)

    if request.method == 'POST':
        try:
            if request.POST.get('check_in'):
                attendance_record.check_in_time = datetime.strptime(request.POST.get('check_in'), '%H:%M').time()
            else:
                attendance_record.check_in_time = None
            if request.POST.get('check_out'):
                attendance_record.check_out_time = datetime.strptime(request.POST.get('check_out'), '%H:%M').time()
            else:
                attendance_record.check_out_time = None

            # Get simplified status from form (present/absent/leave)
            simplified_status = request.POST.get('status', 'present')
            leave_type = request.POST.get('leave_type', '')

            # Recalculate durations based on new times
            attendance_record.calculate_durations()

            # Handle status based on form selection
            if simplified_status == 'leave':
                # Status is "leave" - set to leave and save leave_type
                attendance_record.status = 'leave'
                attendance_record.leave_type = leave_type if leave_type else None
                attendance_record._explicit_status = True
            elif simplified_status == 'absent':
                # If status is "absent", set to absent (or leave if leave_type exists)
                if leave_type:
                    attendance_record.status = 'leave'
                    attendance_record.leave_type = leave_type
                else:
                    attendance_record.status = 'absent'
                    attendance_record.leave_type = None
                attendance_record._explicit_status = True
            else:
                # If status is "present", auto-determine the proper status based on times
                # This will set status to late, overtime, early-in, early-out, or present
                attendance_record.status = attendance_record.auto_determine_status()
                attendance_record.leave_type = None  # Clear leave_type for present status
                attendance_record._explicit_status = True

            attendance_record.overtime_hours = float(request.POST.get('overtime_hours', 0))
            attendance_record.notes = request.POST.get('notes', '')

            attendance_record.save()
            messages.success(request, 'Attendance record updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating attendance: {str(e)}')
    return redirect('attendance')

@login_required
@hr_or_admin_required
def delete_attendance(request, pk):
    """Delete attendance - Only admin/HR can delete attendance records"""
    attendance_record = get_object_or_404(Attendance, pk=pk)

    employee_name = str(attendance_record.employee)
    dt = attendance_record.date
    attendance_record.delete()
    messages.success(request, f'Attendance record for {employee_name} on {dt} deleted successfully!')
    return redirect('attendance')

@login_required
@hr_or_admin_required
def get_attendance_json(request, pk):
    """Get attendance JSON - Only admin/HR can access for editing purposes"""
    attendance_record = get_object_or_404(Attendance, pk=pk)

    # Determine form status (present/absent/leave)
    if attendance_record.status == 'leave':
        form_status = 'leave'
    elif attendance_record.simplified_status == 'present':
        form_status = 'present'
    else:
        form_status = 'absent'

    data = {
        'id': attendance_record.id,
        'employee_id': attendance_record.employee.id,
        'employee_name': str(attendance_record.employee),
        'date': attendance_record.date.strftime('%Y-%m-%d'),
        'check_in': attendance_record.check_in_time.strftime('%H:%M') if attendance_record.check_in_time else '',
        'check_out': attendance_record.check_out_time.strftime('%H:%M') if attendance_record.check_out_time else '',
        'status': form_status,  # Return form status (present/absent/leave) for form
        'status_display': attendance_record.simplified_status_display,
        'original_status': attendance_record.status,  # Keep original for reference
        'leave_type': attendance_record.leave_type or '',  # Add leave_type for form
        'overtime_hours': float(attendance_record.overtime_hours),
        'duration': attendance_record.duration,
        'overtime_display': attendance_record.overtime_display,
        'notes': attendance_record.notes or '',
        'late_in': attendance_record.late_in,
        'late_in_display': attendance_record.late_in_display,
        'early_out': attendance_record.early_out,
        'early_out_display': attendance_record.early_out_display,
    }
    return JsonResponse(data)

@login_required
def attendance_statistics(request):
    """Attendance statistics - properly scoped for all users"""
    today = timezone.now().date()
    current_month = today.replace(day=1)
    last_month = (current_month - timedelta(days=1)).replace(day=1)

    # Check user role
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Base queryset - properly scoped
    if is_admin_user or request.user.is_superuser:
        current_month_records = Attendance.objects.filter(date__gte=current_month, date__lte=today)
        last_month_records = Attendance.objects.filter(date__gte=last_month, date__lt=current_month)
        employees = Employees.objects.filter(status=1)
    else:
        current_employee = get_current_employee(request)
        if current_employee:
            current_month_records = Attendance.objects.filter(employee=current_employee, date__gte=current_month, date__lte=today)
            last_month_records = Attendance.objects.filter(employee=current_employee, date__gte=last_month, date__lt=current_month)
            employees = Employees.objects.filter(pk=current_employee.pk)
        else:
            current_month_records = Attendance.objects.none()
            last_month_records = Attendance.objects.none()
            employees = Employees.objects.none()

    # Exclude dummy/test data from statistics
    exclude_dummy = Q(
        Q(employee__code__icontains='test') |
        Q(employee__code__icontains='dummy') |
        Q(employee__code__icontains='sample') |
        Q(employee__firstname__icontains='test') |
        Q(employee__firstname__icontains='dummy') |
        Q(employee__firstname__icontains='sample') |
        Q(employee__lastname__icontains='test') |
        Q(employee__lastname__icontains='dummy') |
        Q(employee__lastname__icontains='sample') |
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )
    current_month_records = current_month_records.exclude(exclude_dummy)
    last_month_records = last_month_records.exclude(exclude_dummy)

    employee_stats = []

    for employee in employees:
        current_present = current_month_records.filter(
            employee=employee
        ).filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        current_total = current_month_records.filter(employee=employee).count()
        current_rate = (current_present / current_total * 100) if current_total > 0 else 0

        last_present = last_month_records.filter(
            employee=employee
        ).filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        last_total = last_month_records.filter(employee=employee).count()
        last_rate = (last_present / last_total * 100) if last_total > 0 else 0

        employee_stats.append({
            'employee': employee,
            'current_rate': round(current_rate, 1),
            'last_rate': round(last_rate, 1),
            'trend': 'up' if current_rate > last_rate else 'down' if current_rate < last_rate else 'stable'
        })

    employee_stats.sort(key=lambda x: x['current_rate'], reverse=True)
    return render(request, 'pages/attendance_statistics.html', {
        'employee_stats': employee_stats,
        'current_month': current_month,
        'last_month': last_month
    })

@login_required
def export_attendance(request):
    """Export attendance - properly scoped"""
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    employee_id = request.GET.get('employee')

    # Check user role
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except:
        user_role = 'employee'

    # Base queryset - properly scoped
    if is_admin_user or request.user.is_superuser:
        attendance_records = Attendance.objects.select_related('employee')
    else:
        current_employee = get_current_employee(request)
        if current_employee:
            attendance_records = Attendance.objects.select_related('employee').filter(employee=current_employee)
        else:
            attendance_records = Attendance.objects.none()

    # Exclude dummy/test data
    attendance_records = attendance_records.exclude(
        Q(employee__code__icontains='test') |
        Q(employee__code__icontains='dummy') |
        Q(employee__code__icontains='sample') |
        Q(employee__firstname__icontains='test') |
        Q(employee__firstname__icontains='dummy') |
        Q(employee__firstname__icontains='sample') |
        Q(employee__lastname__icontains='test') |
        Q(employee__lastname__icontains='dummy') |
        Q(employee__lastname__icontains='sample') |
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )

    from_date = validate_date(date_from)
    to_date = validate_date(date_to)
    if from_date:
        attendance_records = attendance_records.filter(date__gte=from_date)
    if to_date:
        attendance_records = attendance_records.filter(date__lte=to_date)

    # For non-admin users, ignore employee_id parameter (they can only export their own data)
    if employee_id and is_admin_user:
        allowed_emp = get_object_or_404(Employees, pk=employee_id)
        attendance_records = attendance_records.filter(employee=allowed_emp)

    # Filter out weekend records without attendance (employee didn't arrive on weekend)
    attendance_records = attendance_records.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    # Order by date and updated_at to get latest records first, then remove duplicates
    attendance_records = attendance_records.order_by('-date', '-updated_at', 'employee__firstname')

    # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
    seen = {}
    unique_records = []
    for record in attendance_records:
        key = (record.employee_id, record.date)
        if key not in seen:
            seen[key] = record
            unique_records.append(record)
        else:
            # If duplicate found, keep the one with the latest updated_at
            existing_record = seen[key]
            if record.updated_at > existing_record.updated_at:
                # Replace with newer record
                unique_records.remove(existing_record)
                seen[key] = record
                unique_records.append(record)

    # Re-sort after deduplication
    unique_records.sort(key=lambda x: (-x.date.toordinal(), x.employee.firstname))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Employee Code','Employee Name','Department','Date','Check-In Time','Check-Out Time','Status','Work Duration','Overtime Hours','Notes'])

    for r in unique_records:
        writer.writerow([
            r.employee.code or '',
            str(r.employee),
            r.employee.department.name if r.employee.department else '',
            r.date.strftime('%Y-%m-%d'),
            r.check_in_time.strftime('%H:%M') if r.check_in_time else '--',
            r.check_out_time.strftime('%H:%M') if r.check_out_time else '--',
            r.get_status_display(),
            r.duration,
            r.overtime_display,
            r.notes or ''
        ])
    return response

@login_required
def attendance_filter_ajax(request):
    """AJAX filter endpoint - properly scoped for all users"""
    if request.method == 'GET':
        employee_search = request.GET.get('employee', '').strip()
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        status_filter = request.GET.get('status', '').strip()
        team_filter = request.GET.get('team', '').strip()

        # Check user role
        is_admin_user = request.user.is_superuser
        try:
            user_role = request.user.profile.role
            is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
        except:
            user_role = 'employee'

        # Auto-absent: If filtering for today's date, automatically mark missing employees as absent
        today = timezone.now().date()
        from_date = validate_date(date_from)
        to_date = validate_date(date_to)

        # Check if filtering for today (date range includes today)
        # This handles cases where:
        # - date_from=today and date_to=today (exact today)
        # - date_from=today and no date_to (today onwards)
        # - date_from=today and date_to >= today (range including today)
        # - date_to=today and from_date <= today (range ending today)
        is_filtering_today = False
        # Check if today is within the date range (applies to all roles)
        if from_date and to_date:
            # Both dates specified - check if today is in range
            if from_date <= today <= to_date:
                is_filtering_today = True
        elif from_date == today:
            # Only from_date is set and it's today
            is_filtering_today = True
        elif to_date == today:
            # Only to_date is set and it's today
            if not from_date or from_date <= today:
                is_filtering_today = True
        elif not from_date and not to_date:
            # No date filters - don't auto-mark (show all records)
            is_filtering_today = False

        # Base queryset - properly scoped
        if is_admin_user or request.user.is_superuser:
            attendance_records = Attendance.objects.select_related('employee')
        else:
            current_employee = get_current_employee(request)
            if current_employee:
                attendance_records = Attendance.objects.select_related('employee').filter(employee=current_employee)
            else:
                attendance_records = Attendance.objects.none()

        # Apply team filter if provided
        if team_filter:
            attendance_records = attendance_records.filter(employee__team=team_filter)

        # Auto-absent: If filtering for today's date, automatically mark missing employees as absent
        if is_filtering_today:
            # Get employees queryset for auto-absent
            if is_admin_user:
                employees_qs = Employees.objects.filter(status=1).exclude(
                    Q(code__icontains='test') |
                    Q(code__icontains='dummy') |
                    Q(code__icontains='sample') |
                    Q(firstname__icontains='test') |
                    Q(firstname__icontains='dummy') |
                    Q(firstname__icontains='sample') |
                    Q(lastname__icontains='test') |
                    Q(lastname__icontains='dummy') |
                    Q(lastname__icontains='sample')
                )

                # Apply team filter if provided
                if team_filter:
                    employees_qs = employees_qs.filter(team=team_filter)
            else:
                current_employee = get_current_employee(request)
                if current_employee and current_employee.status == 1:
                    employees_qs = Employees.objects.filter(pk=current_employee.pk)
                else:
                    employees_qs = Employees.objects.none()

            # Auto-mark absent for today - this creates records for all relevant employees without attendance
            if employees_qs.exists():
                auto_mark_absent_for_date(today, employees_qs, team_filter if team_filter else None)

                # Refresh attendance_records queryset to include newly created records
                # Use a fresh queryset to ensure we get all records including newly created ones
                if is_admin_user or request.user.is_superuser:
                    attendance_records = Attendance.objects.select_related('employee').all()
                else:
                    current_employee = get_current_employee(request)
                    if current_employee:
                        attendance_records = Attendance.objects.select_related('employee').filter(employee=current_employee)
                    else:
                        attendance_records = Attendance.objects.none()

            # Re-apply team filter and exclusions
            if team_filter:
                attendance_records = attendance_records.filter(employee__team=team_filter)

            # Re-apply exclusions
            attendance_records = attendance_records.exclude(
                Q(employee__code__icontains='test') |
                Q(employee__code__icontains='dummy') |
                Q(employee__code__icontains='sample') |
                Q(employee__firstname__icontains='test') |
                Q(employee__firstname__icontains='dummy') |
                Q(employee__firstname__icontains='sample') |
                Q(employee__lastname__icontains='test') |
                Q(employee__lastname__icontains='dummy') |
                Q(employee__lastname__icontains='sample') |
                Q(notes__icontains='test') |
                Q(notes__icontains='dummy') |
                Q(notes__icontains='sample')
            )

        # Exclude dummy/test data (if not already excluded above)
        if not is_filtering_today:
            attendance_records = attendance_records.exclude(
                Q(employee__code__icontains='test') |
                Q(employee__code__icontains='dummy') |
                Q(employee__code__icontains='sample') |
                Q(employee__firstname__icontains='test') |
                Q(employee__firstname__icontains='dummy') |
                Q(employee__firstname__icontains='sample') |
                Q(employee__lastname__icontains='test') |
                Q(employee__lastname__icontains='dummy') |
                Q(employee__lastname__icontains='sample') |
                Q(notes__icontains='test') |
                Q(notes__icontains='dummy') |
                Q(notes__icontains='sample')
            )

        # Filter out weekend records without attendance (employee didn't arrive on weekend)
        attendance_records = attendance_records.exclude(
            Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
        )

        # Apply employee search (scoped by role earlier)
        if employee_search:
            attendance_records = attendance_records.filter(
                Q(employee__firstname__icontains=employee_search) |
                Q(employee__lastname__icontains=employee_search) |
                Q(employee__code__icontains=employee_search)
            )

        # Apply date filters precisely
        # If both dates are provided, filter by range
        if from_date and to_date:
            attendance_records = attendance_records.filter(date__gte=from_date, date__lte=to_date)
        elif from_date:
            # Only from_date - filter from that date onwards
            attendance_records = attendance_records.filter(date__gte=from_date)
        elif to_date:
            # Only to_date - filter up to that date
            attendance_records = attendance_records.filter(date__lte=to_date)

        # Apply status filter if provided
        if status_filter and status_filter != 'all':
            if status_filter == 'present':
                # Present = anyone with check-in OR check-out (they showed up)
                attendance_records = attendance_records.filter(
                    Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
                )
            elif status_filter == 'absent':
                # Absent includes: absent, leave
                # Exclude weekend records (they're neither present nor absent)
                attendance_records = attendance_records.filter(
                    status__in=['absent', 'leave']
                ).exclude(status='weekend')
            elif status_filter == 'late':
                # Late arrivals
                attendance_records = attendance_records.filter(status='late')
            elif status_filter == 'overtime':
                # Overtime: records with status='overtime' OR overtime_hours > 0
                attendance_records = attendance_records.filter(
                    Q(status='overtime') | Q(overtime_hours__gt=0)
                )
            elif status_filter == 'leave':
                # On leave
                attendance_records = attendance_records.filter(status='leave')
            elif status_filter == 'weekend':
                # Weekend Work: show all records where the date is a weekend AND has check-in/check-out
                # This matches the summary count logic - only employees who actually worked on weekends
                # Optimize: if filtering a single date that's a weekend, filter directly
                if from_date and to_date and from_date == to_date and from_date.weekday() >= 5:
                    # Single weekend date - filter directly
                    attendance_records = attendance_records.filter(
                        Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
                    )
                else:
                    # Date range or single weekday - need to check each date
                    # First filter for records with check-in/check-out
                    records_with_attendance = attendance_records.filter(
                        Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
                    )
                    # Then filter for weekend dates (Saturday=5, Sunday=6)
                    weekend_ids = []
                    for rec in records_with_attendance.values_list('id', 'date'):
                        if rec[1].weekday() >= 5:  # Saturday=5, Sunday=6
                            weekend_ids.append(rec[0])
                    attendance_records = attendance_records.filter(id__in=weekend_ids)
            else:
                # Fallback to original behavior for backward compatibility
                attendance_records = attendance_records.filter(status=status_filter)

        # Order by date and updated_at to get latest records first, then remove duplicates
        attendance_records = attendance_records.order_by('-date', '-updated_at', 'employee__firstname')

        # Convert to list to handle duplicates
        attendance_list = list(attendance_records)

        # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
        seen = {}
        unique_records = []
        for record in attendance_list:
            key = (record.employee_id, record.date)
            if key not in seen:
                seen[key] = record
                unique_records.append(record)
            else:
                # If duplicate found, keep the one with the latest updated_at
                existing_record = seen[key]
                if record.updated_at > existing_record.updated_at:
                    # Replace with newer record
                    unique_records.remove(existing_record)
                    seen[key] = record
                    unique_records.append(record)

        # Re-sort after deduplication
        unique_records.sort(key=lambda x: (-x.date.toordinal(), x.employee.firstname))

        # Pagination for AJAX requests
        per_page = int(request.GET.get('per_page', 50))
        if per_page not in [10, 25, 50, 100, 200]:
            per_page = 50

        paginator = Paginator(unique_records, per_page)
        page = request.GET.get('page', 1)
        try:
            paginated_records = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            paginated_records = paginator.page(1)

        # Attach holiday info for JSON response without N+1 queries
        holiday_map = _holiday_name_by_date([r.date for r in paginated_records])

        # Return complete data with all required fields
        data = []
        for rec in paginated_records:
            try:
                # Safely get late_in and early_out values
                late_in_seconds = 0
                if rec.late_in:
                    try:
                        late_in_seconds = rec.late_in.total_seconds()
                    except (AttributeError, TypeError):
                        late_in_seconds = 0

                early_out_seconds = 0
                if rec.early_out:
                    try:
                        early_out_seconds = rec.early_out.total_seconds()
                    except (AttributeError, TypeError):
                        early_out_seconds = 0

                # Safely get property values
                duration = '--'
                try:
                    duration = rec.duration or '--'
                except:
                    duration = '--'

                overtime_display = '--'
                try:
                    overtime_display = rec.overtime_display or '--'
                except:
                    overtime_display = '--'

                late_in_display = ''
                try:
                    late_in_display = rec.late_in_display or ''
                except:
                    late_in_display = ''

                early_out_display = ''
                try:
                    early_out_display = rec.early_out_display or ''
                except:
                    early_out_display = ''

                # Get simplified status (Present/Absent)
                simplified_status = rec.simplified_status
                simplified_status_display = rec.simplified_status_display

                # Get leave type display
                leave_type_display = ''
                try:
                    if rec.leave_type:
                        leave_type_display = rec.get_leave_type_display()
                except:
                    leave_type_display = ''

                # Get team display value properly
                team_display = 'No Team'
                if rec.employee.team and rec.employee.team.strip():
                    try:
                        team_display = rec.employee.get_team_display()
                        # If get_team_display returns the default choice label, treat as no team
                        if team_display == '-- Select Team --':
                            team_display = 'No Team'
                    except:
                        team_display = rec.employee.team if rec.employee.team.strip() else 'No Team'

                data.append({
                    'id': rec.id,
                    'employee_name': f"{rec.employee.firstname} {rec.employee.lastname or ''}".strip(),
                    'employee_firstname': rec.employee.firstname or '',
                    'employee_lastname': rec.employee.lastname or '',
                    'employee_code': rec.employee.code or '',
                    'team': rec.employee.team or '',
                    'team_display': team_display,
                    'date': rec.date.strftime('%Y-%m-%d'),
                    'is_weekend': rec.date.weekday() >= 5,  # For backward compatibility
                    'is_weekend_date': rec.is_weekend_date,  # Use model property
                    'is_holiday_date': bool(holiday_map.get(rec.date)),
                    'holiday_name': holiday_map.get(rec.date, ''),
                    'check_in': rec.check_in_time.strftime('%H:%M') if rec.check_in_time else '--',
                    'check_out': rec.check_out_time.strftime('%H:%M') if rec.check_out_time else '--',
                    'status': rec.status or 'absent',
                    'status_display': rec.get_status_display() if rec.status else 'Absent',
                    'simplified_status': simplified_status,
                    'simplified_status_display': simplified_status_display,
                    'duration': duration,
                    'overtime_display': overtime_display,
                    'notes': rec.notes or '',
                    'late_in': late_in_seconds,
                    'late_in_display': late_in_display,
                    'early_out': early_out_seconds,
                    'early_out_display': early_out_display,
                    'leave_type': rec.leave_type or '',
                    'leave_type_display': leave_type_display,
                })
            except Exception as e:
                # Log error but continue processing other records
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error serializing attendance record {rec.id}: {str(e)}")
                continue

        return JsonResponse({
            'records': data,
            'pagination': {
                'current_page': paginated_records.number,
                'total_pages': paginated_records.paginator.num_pages,
                'total_count': paginated_records.paginator.count,
                'has_previous': paginated_records.has_previous(),
                'has_next': paginated_records.has_next(),
                'per_page': per_page,
            }
        })
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Attendance PDF Export
@login_required
def generate_attendance_pdf(request):
    """
    Professional Attendance PDF:
      - A4 Landscape
      - Auto-fit table width (prevents side cutting)
      - Filters: employee, team, date_from, date_to, attendance_type/status
      - Security: admins export all; employees export only themselves
    """

    # ---------------------------
    # Role & scoping
    # ---------------------------
    is_admin_user = request.user.is_superuser
    try:
        user_role = request.user.profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except Exception:
        user_role = 'employee'

    # If your project has get_current_employee, use it; fallback to request.user.employee
    try:
        current_employee = get_current_employee(request)
    except Exception:
        current_employee = getattr(request.user, "employee", None)

    # ---------------------------
    # Read filters
    # ---------------------------
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_to_raw = (request.GET.get('date_to') or '').strip()

    employee_input = (request.GET.get('employee') or request.GET.get('search') or '').strip()
    team_filter = (request.GET.get('team') or '').strip()

    attendance_type = (request.GET.get('attendance_type') or request.GET.get('status') or 'all').strip().lower()
    if not attendance_type:
        attendance_type = 'all'

    # ---------------------------
    # Parse dates (YYYY-MM-DD and MM/DD/YYYY)
    # ---------------------------
    def _parse_date(s: str):
        if not s:
            return None
        s = s.strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        return None

    date_from = _parse_date(date_from_raw)
    date_to = _parse_date(date_to_raw)

    # ---------------------------
    # Base employees queryset (exclude test/dummy)
    # ---------------------------
    employees_qs = Employees.objects.filter(status=1).exclude(
        Q(code__icontains='test') |
        Q(code__icontains='dummy') |
        Q(code__icontains='sample') |
        Q(firstname__icontains='test') |
        Q(firstname__icontains='dummy') |
        Q(firstname__icontains='sample') |
        Q(lastname__icontains='test') |
        Q(lastname__icontains='dummy') |
        Q(lastname__icontains='sample')
    )

    # Employee user security: can export only themselves
    if not is_admin_user and not request.user.is_superuser:
        if not current_employee:
            return HttpResponse("Employee profile not linked to your account.", status=403)
        employees_qs = employees_qs.filter(pk=current_employee.pk)

        # ignore any passed filters for safety
        employee_input = ""
        team_filter = ""

    # Team filter
    if team_filter:
        employees_qs = employees_qs.filter(team=team_filter)

    # Employee filter: code exact/contains OR pk exact OR name contains
    if employee_input:
        emp_q = (
            Q(code__iexact=employee_input) |
            Q(code__icontains=employee_input) |
            Q(firstname__icontains=employee_input) |
            Q(lastname__icontains=employee_input)
        )
        if employee_input.isdigit():
            emp_q |= Q(pk=int(employee_input))
        employees_qs = employees_qs.filter(emp_q)

    employees_qs = employees_qs.distinct()

    # ---------------------------
    # Attendance queryset
    # ---------------------------
    attendance_qs = Attendance.objects.select_related(
        'employee', 'employee__department', 'employee__position'
    ).filter(employee__in=employees_qs)

    # Date range filter
    if date_from and date_to:
        attendance_qs = attendance_qs.filter(date__range=[date_from, date_to])
    elif date_from:
        attendance_qs = attendance_qs.filter(date__gte=date_from)
    elif date_to:
        attendance_qs = attendance_qs.filter(date__lte=date_to)

    # ✅ Helper: worked on that date?
    def _worked(record):
        return bool(record.check_in_time or record.check_out_time)

    # ✅ Helper: weekend date?
    def _is_weekend_date(d):
        return d.weekday() >= 5  # Sat/Sun

    # Status filter (your model) - KEEP same structure but improve weekend logic
    if attendance_type == 'present':
        # ✅ Present if ANY check-in/out exists (includes weekend work automatically)
        attendance_qs = attendance_qs.filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).exclude(status='leave')

    elif attendance_type == 'absent':
        # ✅ Absent = no check-in/out AND status absent OR weekend with no work
        attendance_qs = attendance_qs.filter(
            Q(status='absent', check_in_time__isnull=True, check_out_time__isnull=True) |
            Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
        )

    elif attendance_type == 'leave':
        attendance_qs = attendance_qs.filter(status='leave')

    elif attendance_type == 'weekend':
        # ✅ Weekend ONLY if weekend date AND employee worked (check-in/out exists)
        attendance_qs = attendance_qs.filter(
            Q(date__week_day__in=[1, 7]) & (Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False))
        )

    # Exclude dummy notes
    attendance_qs = attendance_qs.exclude(
        Q(notes__icontains='test') |
        Q(notes__icontains='dummy') |
        Q(notes__icontains='sample')
    )

    # Filter out weekend records without attendance (employee didn't arrive on weekend)
    attendance_qs = attendance_qs.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    ).order_by('date', '-updated_at', 'employee__firstname')

    # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
    seen = {}
    unique_attendance = []
    for att in attendance_qs:
        key = (att.employee_id, att.date)
        if key not in seen:
            seen[key] = att
            unique_attendance.append(att)
        else:
            # If duplicate found, keep the one with the latest updated_at
            existing_record = seen[key]
            if att.updated_at > existing_record.updated_at:
                # Replace with newer record
                unique_attendance.remove(existing_record)
                seen[key] = att
                unique_attendance.append(att)

    # Re-sort after deduplication
    unique_attendance.sort(key=lambda x: (x.date.toordinal(), x.employee.firstname))
    attendance_qs = unique_attendance

    # ---------------------------
    # PDF setup (Landscape + safe margins)
    # ---------------------------
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=8,
        alignment=1,
        textColor=colors.HexColor('#2c3e50')
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=10,
        alignment=1,
        textColor=colors.HexColor('#34495e')
    )

    elements.append(Paragraph("ATTENDANCE REPORT", title_style))

    subtitle_text = f"Date Range: {date_from or '--'} to {date_to or '--'}"
    if employee_input:
        subtitle_text += f" | Employee: {employee_input}"
    if team_filter:
        subtitle_text += f" | Team: {team_filter}"
    if attendance_type and attendance_type != 'all':
        subtitle_text += f" | Status: {attendance_type.title()}"

    elements.append(Paragraph(subtitle_text, subtitle_style))
    elements.append(Spacer(1, 0.12 * inch))

    # ---------------------------
    # Table data
    # ---------------------------
    table_data = [[
        '#', 'Date', 'Emp ID', 'Name', 'Department', 'Position',
        'In', 'Out', 'Late In', 'Early Out', 'Late Sit', 'Status'
    ]]

    total_extra_hours = timedelta()
    total_late_sitting = timedelta()
    total_late_in = timedelta()
    total_early_out = timedelta()

    status_counts = {'Present': 0, 'Absent': 0, 'Leave': 0, 'Holiday': 0, 'Weekend': 0}

    def format_duration(td):
        if not td:
            return '--'
        secs = td.total_seconds()
        if secs <= 0:
            return '--'
        mins = int(secs // 60)
        h = mins // 60
        m = mins % 60
        return f"{h}h" if h > 0 else (f"{m}m" if m > 0 else '--')

    for idx, record in enumerate(attendance_qs, start=1):
        # ✅ Determine weekend by DATE (auto)
        weekend_date = _is_weekend_date(record.date)
        worked = _worked(record)

        # ✅ If weekend but NOT worked -> SKIP from PDF (your requirement)
        if weekend_date and not worked:
            continue

        # display status (keep your existing behavior)
        display_status = record.simplified_status_display  # Present/Absent/Leave

        # ✅ Weekend worked -> mention weekend properly
        if weekend_date and worked:
            display_status = 'Weekend'  # keep same label you already use

        status_counts[display_status] = status_counts.get(display_status, 0) + 1

        if record.late_sitting:
            total_late_sitting += record.late_sitting
            if record.simplified_status == 'present':
                total_extra_hours += record.late_sitting

        if record.late_in:
            total_late_in += record.late_in
        if record.early_out:
            total_early_out += record.early_out

        check_in = record.check_in_time.strftime('%H:%M') if record.check_in_time else '--'
        check_out = record.check_out_time.strftime('%H:%M') if record.check_out_time else '--'

        employee_name = f"{record.employee.firstname} {record.employee.lastname or ''}".strip()
        department = record.employee.department.name if record.employee.department else '--'
        position = record.employee.position.name if record.employee.position else '--'

        table_data.append([
            str(len(table_data)),  # ✅ keeps numbering correct even after skip
            record.date.strftime('%Y-%m-%d'),
            record.employee.code or str(record.employee.pk),
            employee_name,
            department,
            position,
            check_in,
            check_out,
            format_duration(record.late_in),
            format_duration(record.early_out),
            format_duration(record.late_sitting),
            display_status
        ])

    # ---------------------------
    # Column widths (base) + AUTO-FIT to page width (prevents cut)
    # ---------------------------
    col_widths = [
        22, 70, 55, 110, 90, 90, 45, 45, 55, 60, 55, 65
    ]

    available_width = doc.width
    total_col_width = sum(col_widths)
    if total_col_width > available_width:
        scale = available_width / total_col_width
        col_widths = [w * scale for w in col_widths]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # ---------------------------
    # Table style (professional)
    # ---------------------------
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bdc3c7')),

        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),

        ('ALIGN', (3, 1), (3, -1), 'LEFT'),
        ('ALIGN', (4, 1), (5, -1), 'LEFT'),

        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8f9fa'), colors.white]),
    ])

    # ✅ Color the Status column + highlight Weekend row more
    for i in range(1, len(table_data)):
        st = table_data[i][11]
        if st == 'Present':
            c = colors.HexColor('#27ae60')
        elif st == 'Absent':
            c = colors.HexColor('#e74c3c')
        elif st in ['Leave', 'Holiday']:
            c = colors.HexColor('#3498db')
        elif st == 'Weekend':
            c = colors.HexColor('#f39c12')
            # ✅ highlight weekend row background slightly
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fff3e0'))
        else:
            c = colors.black

        table_style.add('TEXTCOLOR', (11, i), (11, i), c)
        table_style.add('FONTNAME', (11, i), (11, i), 'Helvetica-Bold')

    table.setStyle(table_style)
    elements.append(table)

    # ---------------------------
    # Summary section
    # ---------------------------
    elements.append(Spacer(1, 0.25 * inch))

    def format_timedelta_compact(td):
        if not td:
            return "0h"
        total_seconds = td.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    summary_data = [
        ['SUMMARY', 'COUNT', 'HOURS'],
        ['Total Records', str(max(0, len(table_data) - 1)), ''],
        ['Present', str(status_counts.get('Present', 0)), ''],
        ['Absent', str(status_counts.get('Absent', 0)), ''],
        ['Leave', str(status_counts.get('Leave', 0)), ''],
        ['Holidays', str(status_counts.get('Holiday', 0)), ''],
        ['Weekends', str(status_counts.get('Weekend', 0)), ''],
        ['Extra Hours', '', format_timedelta_compact(total_extra_hours)],
        ['Late Sitting', '', format_timedelta_compact(total_late_sitting)],
        ['Late In', '', format_timedelta_compact(total_late_in)],
        ['Early Out', '', format_timedelta_compact(total_early_out)],
    ]

    summary_table = Table(summary_data, colWidths=[130, 70, 90])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#bdc3c7')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))

    elements.append(Paragraph("Summary", ParagraphStyle(
        'SummaryTitle', parent=styles['Heading2'], fontSize=11, spaceAfter=6
    )))
    elements.append(summary_table)

    # Footer
    elements.append(Spacer(1, 0.1 * inch))
    generated_at = timezone.now().strftime('%Y-%m-%d %H:%M')
    elements.append(Paragraph(
        f"Generated: {generated_at}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.gray)
    ))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    # ✅ Filename: include user name + current date
    safe_from = date_from.strftime("%Y-%m-%d") if date_from else "na"
    safe_to = date_to.strftime("%Y-%m-%d") if date_to else "na"

    current_date_str = timezone.now().strftime("%Y-%m-%d")

    # username (safe)
    username = (request.user.get_full_name() or request.user.username or "user").strip().replace(" ", "_")

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_{username}_{current_date_str}_{safe_from}_to_{safe_to}.pdf"'
    )
    return response


# Holiday Management
@login_required
@hr_or_admin_required
def holiday_list(request):
    """List all holiday dates as JSON"""
    from datetime import date as date_type
    today = date_type.today()
    holidays = HolidayDate.objects.all().order_by('-date')
    data = [{
        'id': h.id,
        'date': h.date.strftime('%Y-%m-%d'),
        'name': h.name,
        'description': h.description or '',
        'is_past': h.date < today,
    } for h in holidays]
    return JsonResponse({'holidays': data})


@login_required
@hr_or_admin_required
@require_POST
def holiday_add(request):
    """Add a new holiday date"""
    try:
        date_str = request.POST.get('date', '')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not date_str or not name:
            return JsonResponse({'success': False, 'error': 'Date and name are required'})

        holiday_date = parse_date(date_str)
        if not holiday_date:
            return JsonResponse({'success': False, 'error': 'Invalid date format'})

        # Check if holiday already exists for this date
        if HolidayDate.objects.filter(date=holiday_date).exists():
            return JsonResponse({'success': False, 'error': 'A holiday already exists for this date'})

        holiday = HolidayDate.objects.create(
            date=holiday_date,
            name=name,
            description=description,
            created_by=request.user
        )

        # Sync attendance records to mark this date as holiday
        from datetime import timedelta
        sync_start = holiday_date - timedelta(days=1)
        sync_end = holiday_date + timedelta(days=1)
        sync_attendance_with_holidays(date_range_start=sync_start, date_range_end=sync_end)

        return JsonResponse({
            'success': True,
            'holiday': {
                'id': holiday.id,
                'date': holiday.date.strftime('%Y-%m-%d'),
                'name': holiday.name,
                'description': holiday.description or '',
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@hr_or_admin_required
@require_POST
def holiday_edit(request, pk):
    """Edit an existing holiday date"""
    try:
        holiday = get_object_or_404(HolidayDate, pk=pk)
        old_date = holiday.date  # Store old date before update

        date_str = request.POST.get('date', '')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not date_str or not name:
            return JsonResponse({'success': False, 'error': 'Date and name are required'})

        holiday_date = parse_date(date_str)
        if not holiday_date:
            return JsonResponse({'success': False, 'error': 'Invalid date format'})

        # Check if another holiday exists for this date
        if HolidayDate.objects.filter(date=holiday_date).exclude(pk=pk).exists():
            return JsonResponse({'success': False, 'error': 'A holiday already exists for this date'})

        holiday.date = holiday_date
        holiday.name = name
        holiday.description = description
        holiday.save()

        # Sync attendance records if date changed
        if old_date != holiday_date:
            from datetime import timedelta
            # Sync both old and new dates
            sync_start = min(old_date, holiday_date) - timedelta(days=1)
            sync_end = max(old_date, holiday_date) + timedelta(days=1)
            sync_attendance_with_holidays(date_range_start=sync_start, date_range_end=sync_end)

        return JsonResponse({
            'success': True,
            'holiday': {
                'id': holiday.id,
                'date': holiday.date.strftime('%Y-%m-%d'),
                'name': holiday.name,
                'description': holiday.description or '',
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def fix_all_holiday_records():
    """
    Fix all attendance records that have status='holiday' but the date is no longer a holiday.
    This can be called after deleting holidays to clean up the database.
    """
    from EMSwebsite.models import Attendance, HolidayDate
    from django.db import transaction

    # Get all current holiday dates
    current_holidays = set(HolidayDate.objects.values_list('date', flat=True))

    # Get all records with holiday status
    holiday_records = Attendance.objects.filter(status='holiday')

    fixed_count = 0

    with transaction.atomic():
        for record in holiday_records.select_for_update():
            # Check if this date is still a holiday
            if record.date in current_holidays:
                continue  # Still a holiday, skip

            # This date is NO LONGER a holiday - fix it
            if record.check_in_time or record.check_out_time:
                # Employee had attendance - mark as present
                record.status = 'present'
            else:
                # No attendance - mark as absent
                record.status = 'absent'

            record._explicit_status = True

            # Clear holiday-related notes
            if record.notes and 'holiday' in record.notes.lower():
                record.notes = ''

            record.save(update_fields=['status', 'notes', 'updated_at'])
            fixed_count += 1

    return fixed_count


@login_required
@hr_or_admin_required
@require_POST
def holiday_delete(request, pk):
    """Delete a holiday date"""
    try:
        from EMSwebsite.models import Attendance
        from datetime import timedelta
        from django.db import transaction

        holiday = get_object_or_404(HolidayDate, pk=pk)
        holiday_date = holiday.date  # Store date before deletion

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Delete the holiday first
            holiday.delete()

            # Get all attendance records for this date with holiday status
            # Query all records for this date, not just those with holiday status
            # (in case status wasn't set correctly)
            all_records_for_date = Attendance.objects.filter(date=holiday_date)

            updated_count = 0
            for record in all_records_for_date:
                # Only update if status is 'holiday' OR if notes contain holiday info
                should_update = False

                if record.status == 'holiday':
                    should_update = True
                elif record.notes and 'holiday' in record.notes.lower():
                    # Also update records that have holiday in notes but wrong status
                    should_update = True

                if should_update:
                    # Determine new status based on attendance data
                    if record.check_in_time or record.check_out_time:
                        # Employee had attendance - mark as present
                        record.status = 'present'
                    else:
                        # No attendance - mark as absent
                        record.status = 'absent'

                    record._explicit_status = True
                    # Clear holiday-related notes
                    if record.notes and 'holiday' in record.notes.lower():
                        record.notes = ''

                    # Save with update_fields for better performance
                    record.save(update_fields=['status', 'notes', 'updated_at'])
                    updated_count += 1

            # Also run sync to catch any edge cases
            sync_start = holiday_date - timedelta(days=1)
            sync_end = holiday_date + timedelta(days=1)
            sync_attendance_with_holidays(date_range_start=sync_start, date_range_end=sync_end)

            # Also fix any other records that might have holiday status incorrectly
            additional_fixed = fix_all_holiday_records()

        return JsonResponse({
            'success': True,
            'updated_records': updated_count + additional_fixed,
            'message': f'Updated {updated_count + additional_fixed} attendance record(s)'
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error deleting holiday: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})


