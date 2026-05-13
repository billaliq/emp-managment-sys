# views/helpers.py — shared utilities and role decorators
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Q, Avg, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta, date, time
from django.views.decorators.http import require_http_methods, require_POST
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from functools import wraps
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


# ===========================
#   ACCESS HELPERS
# ===========================

def validate_date(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

def has_valid_attendance_exception(employee, check_date):
    """
    Check if an employee has a valid exception that prevents them from being marked absent.
    Returns True if employee has a valid exception (approved leave, weekend, etc.)
    """
    # Check if it's a weekend (Saturday=5, Sunday=6)
    if check_date.weekday() >= 5:
        return True

    # Check if employee has an approved leave request covering this date
    approved_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=check_date,
        end_date__gte=check_date
    ).exists()

    if approved_leaves:
        return True

    # Check if there's already an attendance record (might be marked as leave, etc.)
    existing_record = Attendance.objects.filter(employee=employee, date=check_date).first()
    if existing_record:
        # If already marked as leave, don't override
        if existing_record.status == 'leave':
            return True

    return False

def auto_mark_absent_for_date(check_date, employees_queryset=None, team_filter=None):
    """
    Automatically mark employees as absent for a given date if they don't have attendance records
    and don't have valid exceptions (approved leave, weekend, holiday, etc.)

    Args:
        check_date: The date to check attendance for
        employees_queryset: Optional queryset of employees to check (if None, checks all active employees)
        team_filter: Optional team filter to apply

    Returns:
        Number of records created (absent + leave + weekend)
    """
    from EMSwebsite.models import Employees, HolidayDate

    # If it's a holiday, don't mark anyone as absent
    if HolidayDate.is_holiday(check_date):
        return 0

    is_weekend = check_date.weekday() >= 5

    # Get employees to check
    if employees_queryset is None:
        employees_queryset = Employees.objects.filter(status=1).exclude(
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
        employees_queryset = employees_queryset.filter(team=team_filter)

    # Get employees who already have attendance records for this date
    existing_attendance_employee_ids = Attendance.objects.filter(
        date=check_date
    ).values_list('employee_id', flat=True).distinct()

    # Get employees without attendance records
    employees_without_attendance = employees_queryset.exclude(
        id__in=existing_attendance_employee_ids
    )

    absent_count = 0
    leave_count = 0
    weekend_count = 0

    for emp in employees_without_attendance:
        # Check if it's a weekend
        if is_weekend:
            # For weekends, only create records if employee has approved leave
            # Do NOT create records for weekends without attendance (employee didn't arrive)
            approved_leave = LeaveRequest.objects.filter(
                employee=emp,
                status='approved',
                start_date__lte=check_date,
                end_date__gte=check_date
            ).first()

            if approved_leave:
                # Create leave record for approved leave even on weekends
                try:
                    att = Attendance(
                        employee=emp,
                        date=check_date,
                        status='leave',
                        notes=f"Approved {approved_leave.get_leave_type_display()}: {approved_leave.reason[:100]}"
                    )
                    att._explicit_status = True
                    att.save()
                    leave_count += 1
                except IntegrityError:
                    pass
            # If no approved leave and no attendance, don't create any record for weekend
            # (Employee didn't arrive on weekend - should not show absent or present)
        else:
            # For working days, check for approved leave first
            approved_leave = LeaveRequest.objects.filter(
                employee=emp,
                status='approved',
                start_date__lte=check_date,
                end_date__gte=check_date
            ).first()

            if approved_leave:
                # Create leave record for approved leave
                try:
                    att = Attendance(
                        employee=emp,
                        date=check_date,
                        status='leave',
                        notes=f"Approved {approved_leave.get_leave_type_display()}: {approved_leave.reason[:100]}"
                    )
                    att._explicit_status = True
                    att.save()
                    leave_count += 1
                except IntegrityError:
                    pass
            else:
                # No valid exception, mark as absent on working days
                try:
                    att = Attendance(
                        employee=emp,
                        date=check_date,
                        status='absent'
                    )
                    att._explicit_status = True
                    att.save()
                    absent_count += 1
                except IntegrityError:
                    pass
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error creating absent record for {emp.id} on {check_date}: {str(e)}")
                    pass

    return absent_count + leave_count + weekend_count

def sync_attendance_with_holidays(date_range_start=None, date_range_end=None):
    """
    Update existing attendance records to reflect holiday status.
    This is useful when holidays are added after attendance records are created.

    Args:
        date_range_start: Optional start date to check (defaults to checking all records)
        date_range_end: Optional end date to check (defaults to checking all records)

    Returns:
        Number of records updated
    """
    from EMSwebsite.models import Employees, HolidayDate
    from django.db import ProgrammingError

    try:
        # Get all holidays in the date range
        holiday_qs = HolidayDate.objects.all()
        if date_range_start:
            holiday_qs = holiday_qs.filter(date__gte=date_range_start)
        if date_range_end:
            holiday_qs = holiday_qs.filter(date__lte=date_range_end)

        if not holiday_qs.exists():
            return 0

        # Create a set of holiday dates for quick lookup
        holiday_dates = {h.date: h for h in holiday_qs}
    except (ProgrammingError, Exception):
        # HolidayDate table doesn't exist
        return 0

    updated_count = 0

    # Get all attendance records that might need updating
    attendance_qs = Attendance.objects.all()
    if date_range_start:
        attendance_qs = attendance_qs.filter(date__gte=date_range_start)
    if date_range_end:
        attendance_qs = attendance_qs.filter(date__lte=date_range_end)

    # For each attendance record, check if the date is a holiday
    for attendance in attendance_qs:
        try:
            is_holiday_date = HolidayDate.is_holiday(attendance.date)

            if is_holiday_date:
                # This date IS a holiday - add holiday info to notes but keep actual status
                holiday = HolidayDate.get_holiday(attendance.date)
                holiday_note = holiday.name if holiday else "Holiday"
                needs_update = False

                # Update notes to include holiday info if not already present
                if attendance.notes:
                    if holiday_note not in attendance.notes:
                        attendance.notes = f"{attendance.notes} | {holiday_note}"
                        needs_update = True
                else:
                    attendance.notes = holiday_note
                    needs_update = True

                # If no check-in/check-out, mark as 'holiday' status
                if not attendance.check_in_time and not attendance.check_out_time:
                    if attendance.status != 'holiday':
                        attendance.status = 'holiday'
                        needs_update = True

                # Save only if something changed
                if needs_update:
                    attendance._explicit_status = True
                    attendance.save()
                    updated_count += 1
            else:
                # This date is NO LONGER a holiday - need to update records that were marked as holiday
                if attendance.status == 'holiday':
                    # This was a holiday record but the holiday was removed
                    needs_update = False

                    # Determine new status based on attendance data
                    if attendance.check_in_time or attendance.check_out_time:
                        # Employee had attendance on what was a holiday - mark as present
                        attendance.status = 'present'
                        needs_update = True
                    else:
                        # No attendance - mark as absent
                        attendance.status = 'absent'
                        needs_update = True

                    if needs_update:
                        attendance._explicit_status = True
                        # Clear notes that were likely set for holidays
                        if attendance.notes and 'holiday' in attendance.notes.lower():
                            attendance.notes = ''
                        attendance.save()
                        updated_count += 1
        except (ProgrammingError, Exception):
            continue

    return updated_count

def get_current_employee(request):
    """Get the current employee linked to the user"""
    # Try to get employee from UserProfile first
    try:
        profile = request.user.profile
        if profile.employee:
            return profile.employee
    except (UserProfile.DoesNotExist, AttributeError):
        pass

    # Fallback: try to get employee from Employees.user relationship
    try:
        if hasattr(request.user, 'employee') and request.user.employee:
            return request.user.employee
    except AttributeError:
        pass

    return None

def scope_by_user(qs, request, field: str = 'employee'):
    """
    Superuser -> qs unchanged.
    Others -> filter rows tied to their employee via `field`.
    """
    if request.user.is_superuser:
        return qs
    me = get_current_employee(request)
    if not me:
        return qs.none()
    return qs.filter(**{field: me})

def only_me_employee_qs(request):
    """
    Employees queryset:
      - superuser: all
      - others: just their own employee row (or none if not linked)
    """
    if request.user.is_superuser:
        return Employees.objects.all()
    me = get_current_employee(request)
    return Employees.objects.filter(pk=getattr(me, 'pk', None)) if me else Employees.objects.none()


# ===========================
#   ROLE DECORATORS
# ===========================

def role_required(*roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # Check superuser first - they have access to everything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            try:
                user_profile = request.user.profile
                if user_profile.role in roles:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'You do not have permission to access this page.')
                    return redirect('dashboard' if user_profile.is_employee() else 'dashboard')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found. Please contact administrator.')
                return redirect('login')
        return wrapped_view
    return decorator

def admin_required(view_func):
    return role_required('admin')(view_func)

def hr_or_admin_required(view_func):
    return role_required('admin', 'hr')(view_func)

def finance_or_admin_required(view_func):
    """Decorator to allow finance, admin, or superuser access"""
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        try:
            profile = request.user.profile
            if profile.role in ['finance', 'admin']:
                return view_func(request, *args, **kwargs)
        except:
            pass
        from django.contrib import messages
        messages.error(request, 'Access denied. Finance, Admin, or Superuser access required.')
        from django.shortcuts import redirect
        return redirect('dashboard')
    return wrapper

