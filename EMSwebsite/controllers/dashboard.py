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


@login_required
def dashboard(request):
    """
    Global dashboard — unrestricted version.
    All users (including normal users) can view global stats.
    """
    today = timezone.now().date()
    current_employee = get_current_employee(request)

    global_department_stats = list(
        Department.objects.annotate(
            employee_count=Count("employees_set", filter=Q(employees_set__status=1))
        ).values("name", "employee_count")
    )
    global_gender_stats = list(
        Employees.objects.values("gender").annotate(count=Count("id")).order_by("gender")
    )

    try:
        user_role = request.user.profile.role
    except UserProfile.DoesNotExist:
        user_role = 'admin' if request.user.is_superuser else 'employee'

    if user_role == 'employee' and not request.user.is_superuser:
        if current_employee:
            employee_qs = Employees.objects.filter(pk=current_employee.pk).select_related("department", "position")
            attendance_qs = Attendance.objects.filter(employee=current_employee)
            total_employees = employee_qs.count()
            active_employees = employee_qs.filter(status=1).count()
            inactive_employees = employee_qs.filter(status=2).count()
            total_departments = 1 if current_employee.department_id else 0
            total_positions = Position.objects.count()
            # Present = anyone with check-in OR check-out (they showed up)
            present_count = attendance_qs.filter(
                date=today
            ).filter(
                Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
            ).count()
            # Absent = no check-in/out
            absent_count = attendance_qs.filter(
                date=today,
                check_in_time__isnull=True,
                check_out_time__isnull=True
            ).count()

            department_stats_data = (
                [{"name": current_employee.department.name, "employee_count": 1}]
                if current_employee.department
                else []
            ) or global_department_stats

            gender_label = current_employee.gender or None
            gender_stats_data = (
                [{"gender": gender_label, "count": 1}]
                if gender_label
                else []
            ) or global_gender_stats

            recent_employees = employee_qs
            available_departments = (
                Department.objects.filter(pk=current_employee.department_id)
                if current_employee.department_id
                else Department.objects.none()
            )
            available_positions = (
                Position.objects.filter(pk=current_employee.position_id)
                if current_employee.position_id
                else Position.objects.none()
            )
        else:
            employee_qs = Employees.objects.none()
            attendance_qs = Attendance.objects.none()
            total_employees = 0
            active_employees = 0
            inactive_employees = 0
            total_departments = 0
            total_positions = 0
            present_count = 0
            absent_count = 0
            department_stats_data = []
            gender_stats_data = []
            recent_employees = Employees.objects.none()
            available_departments = Department.objects.none()
            available_positions = Position.objects.none()
            messages.warning(request, 'Employee profile not linked. Please contact administrator.')
    else:
        employee_qs = Employees.objects.all()
        attendance_qs = Attendance.objects.all()
        total_employees = employee_qs.count()
        active_employees = employee_qs.filter(status=1).count()
        inactive_employees = employee_qs.filter(status=2).count()
        total_departments = Department.objects.count()
        total_positions = Position.objects.count()
        # Present = anyone with check-in OR check-out (they showed up)
        present_count = attendance_qs.filter(
            date=today
        ).filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        # Absent = no check-in/out
        absent_count = attendance_qs.filter(
            date=today,
            check_in_time__isnull=True,
            check_out_time__isnull=True
        ).count()
        department_stats_data = global_department_stats
        gender_stats_data = global_gender_stats
        recent_employees = employee_qs.select_related("department", "position").order_by("-date_added")[:5]
        available_departments = Department.objects.all()
        available_positions = Position.objects.all()

    # Calculate attendance rate
    if user_role == 'employee' and current_employee:
        # For employee users, calculate monthly attendance rate
        # (This will be recalculated below in employee_attendance_stats, but we need it here for the main rate)
        current_month = today.replace(day=1)
        monthly_attendance = Attendance.objects.filter(
            employee=current_employee,
            date__gte=current_month,
            date__lte=today
        )
        monthly_present = monthly_attendance.filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        monthly_total = monthly_attendance.count()
        attendance_rate = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0
    else:
        # For admin users, calculate monthly attendance rate (more meaningful than just today's rate)
        current_month = today.replace(day=1)
        # Exclude test/dummy data from attendance calculation
        exclude_dummy_q = Q(
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

        # Get active employees (excluding test/dummy)
        active_employees_qs = employee_qs.filter(status=1).exclude(
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
        active_employees_count = active_employees_qs.count()

        # Monthly attendance calculation
        monthly_attendance = attendance_qs.exclude(exclude_dummy_q).filter(
            date__gte=current_month,
            date__lte=today
        )
        monthly_present = monthly_attendance.filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        monthly_total = monthly_attendance.count()

        # Calculate attendance rate
        if monthly_total > 0:
            # Use monthly data if available
            attendance_rate = (monthly_present / monthly_total * 100)
        elif active_employees_count > 0:
            # Fallback: Calculate based on today's attendance vs active employees
            today_attendance = attendance_qs.exclude(exclude_dummy_q).filter(
                date=today
            ).filter(
                Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
            ).count()
            attendance_rate = (today_attendance / active_employees_count * 100)
        else:
            attendance_rate = 0

    # Get attendance records for employees
    employee_attendance_records = None
    employee_attendance_stats = None
    if user_role == 'employee' and current_employee:
        today = timezone.now().date()
        current_month = today.replace(day=1)

        # Get recent attendance records (last 10)
        employee_attendance_records = Attendance.objects.filter(
            employee=current_employee
        ).order_by('-date')[:10]

        # Calculate monthly attendance stats
        monthly_attendance = Attendance.objects.filter(
            employee=current_employee,
            date__gte=current_month,
            date__lte=today
        )
        monthly_present = monthly_attendance.filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()
        monthly_total = monthly_attendance.count()
        monthly_attendance_rate = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0

        # Today's attendance
        today_attendance = Attendance.objects.filter(
            employee=current_employee,
            date=today
        ).first()

        employee_attendance_stats = {
            'monthly_present': monthly_present,
            'monthly_total': monthly_total,
            'monthly_rate': round(monthly_attendance_rate, 1),
            'today_attendance': today_attendance,
        }

    # Birthday logic
    is_birthday_today = False
    upcoming_birthdays = []

    if user_role == 'employee' and current_employee:
        # Check if today is the employee's birthday
        if current_employee.dob:
            is_birthday_today = (current_employee.dob.month == today.month and current_employee.dob.day == today.day)
    else:
        # For admin/HR: Get upcoming birthdays (next 30 days)
        from django.db.models import F
        from django.db.models.functions import ExtractMonth, ExtractDay

        # Get employees whose birthday is today
        today_birthdays = Employees.objects.filter(
            status=1,
            dob__month=today.month,
            dob__day=today.day
        )

        # We need a more complex query for "next 30 days" that handles year wrap-around
        # For simplicity and performance with moderate dataset, we can fetch name/dob and process in python
        # BUT explicitly selecting only needed fields to reduce memory usage

        users_with_birthdays = Employees.objects.filter(
            status=1,
            dob__isnull=False
        ).values('id', 'firstname', 'lastname', 'dob', 'code', 'email')

        upcoming_birthdays = []
        for emp_data in users_with_birthdays:
            dob = emp_data['dob']
            try:
                this_year_bday = dob.replace(year=today.year)
            except ValueError:
                this_year_bday = dob.replace(year=today.year, day=28)

            if this_year_bday < today:
                try:
                    this_year_bday = dob.replace(year=today.year + 1)
                except ValueError:
                    this_year_bday = dob.replace(year=today.year + 1, day=28)

            days_until = (this_year_bday - today).days

            if 0 <= days_until <= 30:
                # Reconstruct a minimal object for the template to use
                # The template expects 'employee' object with firstname, lastname
                emp_obj = type('EmployeeStruct', (), emp_data)

                upcoming_birthdays.append({
                    'employee': emp_obj,
                    'date': this_year_bday,
                    'days_until': days_until,
                    'is_today': days_until == 0,
                })

        upcoming_birthdays.sort(key=lambda x: x['days_until'])

    context = {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "inactive_employees": inactive_employees,
        "total_departments": total_departments,
        "total_positions": total_positions,
        "present_employees": present_count,
        "absent_employees": absent_count,
        "attendance_rate": round(attendance_rate, 2),
        "recent_employees": recent_employees,
        "department_stats": department_stats_data,
        "gender_stats": gender_stats_data,
        "departments": available_departments,
        "positions": available_positions,
        "user_role": user_role,
        "current_employee": current_employee,
        "employee_attendance_records": employee_attendance_records,
        "employee_attendance_stats": employee_attendance_stats,
        "is_birthday_today": is_birthday_today,
        "upcoming_birthdays": upcoming_birthdays,
    }

    return render(request, "pages/dashboard.html", context)

