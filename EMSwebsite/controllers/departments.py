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


def departments(request):
    # Annotate departments with employee count
    departments = Department.objects.annotate(
        annotated_employee_count=Count('employees_set')
    ).order_by('name')
    total_departments = departments.count()
    active_departments = departments.filter(status='active').count()
    inactive_departments = departments.filter(status='inactive').count()
    total_employees = Employees.objects.count()

    context = {
        'departments': departments,
        'total_departments': total_departments,
        'active_departments': active_departments,
        'inactive_departments': inactive_departments,
        'total_employees': total_employees,
        'employees': Employees.objects.all().order_by('firstname'),  # NEW: Pass for head select
        # Add is_admin or other if needed
    }
    return render(request, 'pages/departments.html', context)  # Assume template path

@require_POST
@login_required
@hr_or_admin_required
def department_create(request):
    try:
        name = request.POST['name']
        description = request.POST.get('description', '')
        status = request.POST['status']
        head_id = request.POST.get('head')  # NEW: Get head ID

        # Office timing fields
        use_custom_timings = request.POST.get('use_custom_timings') == 'on' or request.POST.get('use_custom_timings') == 'true'
        office_start_time_str = request.POST.get('office_start_time', '').strip()
        office_end_time_str = request.POST.get('office_end_time', '').strip()
        grace_period_minutes_str = request.POST.get('grace_period_minutes', '').strip()

        dept = Department(name=name, description=description, status=status)
        if head_id:
            dept.head = get_object_or_404(Employees, id=head_id)

        # Set office timings if custom timings are enabled
        dept.use_custom_timings = use_custom_timings
        if use_custom_timings:
            if office_start_time_str:
                dept.office_start_time = datetime.strptime(office_start_time_str, '%H:%M').time()
            if office_end_time_str:
                dept.office_end_time = datetime.strptime(office_end_time_str, '%H:%M').time()
            if grace_period_minutes_str:
                dept.grace_period_minutes = int(grace_period_minutes_str)

        dept.save()

        # Serialize with all data (including head and office timings)
        serial = {
            'id': dept.id,
            'name': dept.name,
            'description': dept.description,
            'status': dept.status,
            'created_at': dept.created_at.strftime('%Y-%m-%d'),
            'updated_at': dept.updated_at.strftime('%Y-%m-%d'),
            'employee_count': dept.employee_count,
            'head': {
                'id': dept.head.id,
                'firstname': dept.head.firstname,
                'lastname': dept.head.lastname or ''
            } if dept.head else None,
            'use_custom_timings': dept.use_custom_timings,
            'office_start_time': dept.office_start_time.strftime('%H:%M') if dept.office_start_time else None,
            'office_end_time': dept.office_end_time.strftime('%H:%M') if dept.office_end_time else None,
            'grace_period_minutes': dept.grace_period_minutes
        }
        return JsonResponse({'success': True, 'department': serial})
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Department name already exists.'})
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred: ' + str(e)})

@require_POST
@login_required
@hr_or_admin_required
def department_update(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    try:
        dept.name = request.POST['name']
        dept.description = request.POST.get('description', '')
        dept.status = request.POST['status']
        head_id = request.POST.get('head')  # NEW: Get head ID
        if head_id:
            dept.head = get_object_or_404(Employees, id=head_id)
        else:
            dept.head = None

        # Office timing fields
        use_custom_timings = request.POST.get('use_custom_timings') == 'on' or request.POST.get('use_custom_timings') == 'true'
        office_start_time_str = request.POST.get('office_start_time', '').strip()
        office_end_time_str = request.POST.get('office_end_time', '').strip()
        grace_period_minutes_str = request.POST.get('grace_period_minutes', '').strip()

        # Set office timings if custom timings are enabled
        dept.use_custom_timings = use_custom_timings
        if use_custom_timings:
            if office_start_time_str:
                dept.office_start_time = datetime.strptime(office_start_time_str, '%H:%M').time()
            else:
                dept.office_start_time = None
            if office_end_time_str:
                dept.office_end_time = datetime.strptime(office_end_time_str, '%H:%M').time()
            else:
                dept.office_end_time = None
            if grace_period_minutes_str:
                dept.grace_period_minutes = int(grace_period_minutes_str)
            else:
                dept.grace_period_minutes = None
        else:
            # Clear custom timings if disabled
            dept.office_start_time = None
            dept.office_end_time = None
            dept.grace_period_minutes = None

        dept.save()

        # Serialize same as create
        serial = {
            'id': dept.id,
            'name': dept.name,
            'description': dept.description,
            'status': dept.status,
            'created_at': dept.created_at.strftime('%Y-%m-%d'),
            'updated_at': dept.updated_at.strftime('%Y-%m-%d'),
            'employee_count': dept.employee_count,
            'head': {
                'id': dept.head.id,
                'firstname': dept.head.firstname,
                'lastname': dept.head.lastname or ''
            } if dept.head else None,
            'use_custom_timings': dept.use_custom_timings,
            'office_start_time': dept.office_start_time.strftime('%H:%M') if dept.office_start_time else None,
            'office_end_time': dept.office_end_time.strftime('%H:%M') if dept.office_end_time else None,
            'grace_period_minutes': dept.grace_period_minutes
        }
        return JsonResponse({'success': True, 'department': serial})
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Department name already exists.'})
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred: ' + str(e)})


@login_required
@hr_or_admin_required
def get_department_json(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    data = {
        'id': dept.id,
        'name': dept.name,
        'description': dept.description,
        'status': dept.status,
        'head': {
            'id': dept.head.id,
            'firstname': dept.head.firstname,
            'lastname': dept.head.lastname or ''
        } if dept.head else None,
        'use_custom_timings': dept.use_custom_timings,
        'office_start_time': dept.office_start_time.strftime('%H:%M') if dept.office_start_time else None,
        'office_end_time': dept.office_end_time.strftime('%H:%M') if dept.office_end_time else None,
        'grace_period_minutes': dept.grace_period_minutes
    }
    return JsonResponse(data)

@login_required
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        try:
            name = department.name
            department.delete()
            return JsonResponse({"success": True, "message": f"Department '{name}' deleted successfully"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Error deleting department: {str(e)}"}, status=500)
    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

@login_required
@hr_or_admin_required
def get_department_employees(request, pk):
    """Get list of employees for a department and all available employees"""
    department = get_object_or_404(Department, pk=pk)

    # Get employees already in this department with position info
    assigned_employees = Employees.objects.filter(department=department).select_related('position').values(
        'id', 'code', 'firstname', 'lastname', 'email', 'official_email',
        'position__name', 'status', 'date_hired'
    )

    # Get all employees
    all_employees = Employees.objects.all().values('id', 'code', 'firstname', 'lastname', 'department_id')

    return JsonResponse({
        'assigned': list(assigned_employees),
        'all': list(all_employees),
        'department_name': department.name
    })

@require_POST
@login_required
@hr_or_admin_required
def assign_employees_to_department(request, pk):
    """Assign employees to a department"""
    department = get_object_or_404(Department, pk=pk)

    try:
        employee_ids = request.POST.getlist('employee_ids[]')

        # Update employees to assign them to this department
        if employee_ids:
            Employees.objects.filter(id__in=employee_ids).update(department=department)

        # Get updated count
        employee_count = department.employees_set.count()

        return JsonResponse({
            'success': True,
            'message': f'Successfully assigned {len(employee_ids)} employee(s) to {department.name}',
            'employee_count': employee_count
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
