# views.py — role-scoped drop-in
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
from datetime import datetime, timedelta, date
from django.shortcuts import get_object_or_404

from EISwebsite.context_processors import get_notifications

from .models import (
    Employees, Department, Position, Attendance, AttendanceSettings, LeaveRequest, HolidayDate,
    Team, TeamMember, Project, Payroll, PayrollRecord, SalaryIncrement, SystemSettings,
    Loan, LoanRepayment, LoanPool, LoanPoolTransaction, UserProfile, SalaryDisbursement, SalaryDisbursementRecord,
    IncrementSettings, Notification, EmployeeAdditionalDocument, SalarySlipRequest,
    Policy, Complaint, AIChatMessage
)

import json
import csv
import re
from django.views.decorators.http import require_http_methods, require_POST
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from functools import wraps

import logging
logger = logging.getLogger(__name__)
import atexit
from datetime import datetime, time

import pytz
# Optional dependency for background scheduling
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    IntervalTrigger = None

from django.http import JsonResponse
from django.utils import timezone

# Optional dependency for biometric device integration
try:
    from zk import ZK
    from zk.user import User as ZKUser
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False
    ZK = None

from .models import Employees, Attendance, ZKDevice, AttendanceLog
from .device_utils import ZKDeviceManager

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
    from .models import Employees, HolidayDate

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
    from .models import Employees, HolidayDate
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




#============================
# Employee profile view
#============================
@login_required
def employee_profile(request):
    employee = None
    can_search = True
    profile_error = None

    # Check superuser first
    if request.user.is_superuser:
        role = 'admin'
        profile = None
    else:
        try:
            profile = request.user.profile
            role = profile.role
        except UserProfile.DoesNotExist:
            profile = None
            role = 'employee'

    # Employee users should only see their own profile (no search)
    if role == 'employee' and not request.user.is_superuser:
        can_search = False
        # Use the improved get_current_employee function
        employee = get_current_employee(request)
        if not employee:
            profile_error = "Employee profile not linked. Please contact administrator."
        else:
            # For employees, ensure they see their own profile
            # If they try to access another employee's profile via query, ignore it
            query = request.GET.get('q')
            if query and query != employee.code:
                # Employee trying to access another employee's profile - redirect to their own
                messages.warning(request, 'You can only view your own profile.')
                return redirect(f'/employee-profile/?q={employee.code}')
            # If no query or query matches their code, show their profile
            # The employee is already set from get_current_employee above
            # Refresh employee from database to get latest data
            if employee:
                employee = Employees.objects.select_related('department', 'position').get(pk=employee.pk)
    else:
        # Admin/HR users can search for any employee (use q for both list filtering and exact match)
        query = request.GET.get('q', '').strip()
        if query:
            employee = Employees.objects.select_related('department', 'position').filter(code__iexact=query).first()
        elif not query:
            # If no query, try to get current employee for admin/hr viewing their own profile
            current_emp = get_current_employee(request)
            if current_emp:
                employee = Employees.objects.select_related('department', 'position').get(pk=current_emp.pk)

    # Determine if user can edit/delete documents (admin, hr, or superuser)
    can_edit_documents = request.user.is_superuser or (profile and profile.role in ['admin', 'hr'])
    # Determine if user can edit profile fields
    can_edit_profile = request.user.is_superuser or (profile and profile.role in ['admin', 'hr'])

    # Get all employees for table (only for admin/hr/superuser)
    all_employees = None
    all_employees_paginated = None
    per_page = int(request.GET.get('per_page', 25))
    if can_search:  # Only show table if user can search (admin/hr/superuser)
        employees_qs = Employees.objects.select_related('department', 'position').order_by('code').all()
        if query:
            employees_qs = employees_qs.filter(
                Q(code__icontains=query) |
                Q(firstname__icontains=query) |
                Q(lastname__icontains=query) |
                Q(email__icontains=query) |
                Q(official_email__icontains=query) |
                Q(department__name__icontains=query) |
                Q(position__name__icontains=query) |
                Q(job_title__icontains=query)
            )
        paginator = Paginator(employees_qs, per_page)
        page_number = request.GET.get('page', 1)
        try:
            all_employees_paginated = paginator.page(page_number)
            all_employees = all_employees_paginated
        except PageNotAnInteger:
            all_employees_paginated = paginator.page(1)
            all_employees = all_employees_paginated
        except EmptyPage:
            all_employees_paginated = paginator.page(paginator.num_pages)
            all_employees = all_employees_paginated

    # Check if employee profile is submitted (for employees viewing their own profile)
    is_profile_submitted = False
    if employee and not can_edit_documents:
        is_profile_submitted = employee.profile_submitted

    # Get attendance records for the employee
    attendance_records = None
    attendance_stats = None
    if employee:
        today = timezone.now().date()
        current_month = today.replace(day=1)

        # Get recent attendance records (last 30 days)
        attendance_records = Attendance.objects.filter(
            employee=employee
        ).order_by('-date')[:30]

        # Calculate monthly attendance stats
        monthly_attendance = Attendance.objects.filter(
            employee=employee,
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
            employee=employee,
            date=today
        ).first()

        # Total stats
        total_attendance = Attendance.objects.filter(employee=employee).count()
        total_present = Attendance.objects.filter(
            employee=employee
        ).filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        ).count()

        attendance_stats = {
            'monthly_present': monthly_present,
            'monthly_total': monthly_total,
            'monthly_rate': round(monthly_attendance_rate, 1),
            'today_attendance': today_attendance,
            'total_attendance': total_attendance,
            'total_present': total_present,
        }

    # Check for generated password in session (from add_employee view)
    generated_password = None
    generated_username = None
    if employee and (request.user.is_superuser or (profile and profile.role in ['admin', 'hr'])):
        # Check session for password (from newly created employee)
        session_key = f'employee_{employee.id}_password'
        username_key = f'employee_{employee.id}_username'
        if session_key in request.session:
            generated_password = request.session.pop(session_key)
            generated_username = request.session.pop(username_key, employee.user.username if employee.user else '')
            # Save to temp_password field for persistent display
            if generated_password:
                employee.temp_password = generated_password
                employee.save(update_fields=['temp_password'])
        # Also check temp_password field if available (persistent storage)
        elif employee.temp_password:
            generated_password = employee.temp_password
            generated_username = employee.user.username if employee.user else ''
        # If no temp_password but user exists, we can't show password (it's hashed)
        elif employee.user:
            generated_username = employee.user.username

    context = {
        'employee': employee,
        'can_search': can_search,
        'profile_error': profile_error,
        'can_edit_documents': can_edit_documents,
        'can_edit_profile': can_edit_profile,
        'user_role': role,
        'is_admin': request.user.is_superuser or (profile and profile.role == 'admin' if profile else False),
        'departments': Department.objects.all().order_by('name') if can_edit_profile else [],
        'positions': Position.objects.all().order_by('name') if can_edit_profile else [],
        'all_employees': all_employees,
        'all_employees_paginated': all_employees_paginated,
        'per_page': per_page,
        'is_profile_submitted': is_profile_submitted,
        'attendance_records': attendance_records,
        'attendance_stats': attendance_stats,
        'generated_password': generated_password,
        'generated_username': generated_username,
    }

    return render(request, 'pages/employee_profile.html', context)


# ===========================
#   EMPLOYEE DOCUMENT MANAGEMENT
# ===========================

@login_required
def download_document(request, employee_id, document_type):
    """Download employee document"""
    employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)

    # Handle additional documents by id pattern additional_<id>
    if document_type.startswith('additional_'):
        try:
            doc_id = int(document_type.replace('additional_', ''))
            additional_doc = employee.additional_documents.filter(id=doc_id).first()
        except (ValueError, TypeError):
            additional_doc = None

        if not additional_doc:
            messages.error(request, 'Additional document not found.')
            return redirect('employee_profile')

        try:
            response = HttpResponse(additional_doc.file.read(), content_type='application/octet-stream')
            filename = f"{employee.code}_additional_{doc_id}_{additional_doc.file.name.split('/')[-1]}"
            response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
            return response
        except Exception as e:
            messages.error(request, f'Error downloading document: {str(e)}')
            return redirect('employee_profile')

    document_map = {
        'photo': employee.photo,
        'cnic_copy': employee.cnic_copy,
        'passport_size_photo': employee.passport_size_photo,
        'updated_resume': employee.updated_resume,
        'educational_certificate': employee.educational_certificate,
        'experience_letter': employee.experience_letter,
        'offer_letter_signed': employee.offer_letter_signed,
        'nda_form_signed': employee.nda_form_signed,
    }

    if document_type not in document_map:
        messages.error(request, 'Invalid document type.')
        return redirect('employee_profile')

    document = document_map[document_type]
    if not document:
        messages.error(request, 'Document not found.')
        return redirect('employee_profile')

    try:
        response = HttpResponse(document.read(), content_type='application/octet-stream')
        filename = f"{employee.code}_{document_type}_{document.name.split('/')[-1]}"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f'Error downloading document: {str(e)}')
        return redirect('employee_profile')

@login_required
@require_http_methods(["POST"])
def update_document(request, employee_id, document_type):
    """Update employee document - Only admin/HR/superuser can update, or employee before submission"""
    # Check if user is admin/hr/superuser
    is_admin_user = request.user.is_superuser
    profile = None
    user_role = 'employee'

    if not is_admin_user:
        try:
            profile = request.user.profile
            user_role = profile.role
            is_admin_user = user_role in ['admin', 'hr']
        except UserProfile.DoesNotExist:
            pass

    # For admin/hr/superuser, allow access to any employee
    try:
        if is_admin_user:
            employee = get_object_or_404(Employees, code=employee_id)
        else:
            try:
                if profile and profile.role in ['admin', 'hr']:
                    employee = get_object_or_404(Employees, code=employee_id)
                else:
                    employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)
            except UserProfile.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'User profile not found'})
    except Exception as e:
        # Handle any errors when looking up employee (e.g., invalid code format)
        return JsonResponse({'success': False, 'error': f'Employee not found. Please ensure you are using the correct employee ID.'})

    # Accept file from generic key or specific key
    file_obj = request.FILES.get('document_file') or request.FILES.get(document_type)
    if not file_obj:
        return JsonResponse({'success': False, 'error': 'No file provided'})

    # Handle additional document update
    if document_type.startswith('additional_'):
        try:
            doc_id = int(document_type.replace('additional_', ''))
            additional_doc = employee.additional_documents.filter(id=doc_id).first()
        except (ValueError, TypeError):
            additional_doc = None

        if not additional_doc:
            return JsonResponse({'success': False, 'error': 'Additional document not found'})

        try:
            if additional_doc.file:
                additional_doc.file.delete(save=False)
            additional_doc.file = file_obj
            additional_doc.save()
            return JsonResponse({
                'success': True,
                'message': f'{additional_doc.label or "Additional Document"} updated successfully!',
                'file_url': additional_doc.file.url
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    document_map = {
        'photo': 'photo',
        'cnic_copy': 'cnic_copy',
        'passport_size_photo': 'passport_size_photo',
        'updated_resume': 'updated_resume',
        'educational_certificate': 'educational_certificate',
        'experience_letter': 'experience_letter',
        'offer_letter_signed': 'offer_letter_signed',
        'nda_form_signed': 'nda_form_signed',
    }

    # Check if employee has submitted their profile (for regular employees only)
    # Allow uploading missing documents even if profile is locked
    if not is_admin_user and employee.profile_submitted:
        # Check if the document being uploaded is missing
        doc_field = document_map.get(document_type)
        if doc_field:
            current_doc = getattr(employee, doc_field, None)
            if current_doc:
                return JsonResponse({
                    'success': False,
                    'error': f'{document_type.replace("_", " ").title()} already exists. You cannot replace existing documents. Please contact administrator for modifications.'
                })
        # If document is missing, allow upload

    if document_type not in document_map:
        return JsonResponse({'success': False, 'error': 'Invalid document type'})

    try:
        # Delete old file if exists
        old_file = getattr(employee, document_type)
        if old_file:
            old_file.delete(save=False)

        # Save new file
        setattr(employee, document_type, file_obj)
        employee.save()

        return JsonResponse({
            'success': True,
            'message': f'{document_type.replace("_", " ").title()} updated successfully!',
            'file_url': getattr(employee, document_type).url
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def delete_document(request, employee_id, document_type):
    """Delete employee document - Only admin/HR/superuser can delete"""
    # Check if user is employee (not admin/hr/superuser)
    if not request.user.is_superuser:
        try:
            profile = request.user.profile
            if profile.role == 'employee':
                return JsonResponse({'success': False, 'error': 'You do not have permission to delete documents. Only administrators can delete documents.'})
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'You do not have permission to delete documents. Only administrators can delete documents.'})

    # For admin/hr/superuser, allow access to any employee
    if request.user.is_superuser:
        employee = get_object_or_404(Employees, code=employee_id)
    else:
        try:
            profile = request.user.profile
            if profile.role in ['admin', 'hr']:
                employee = get_object_or_404(Employees, code=employee_id)
            else:
                employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User profile not found'})

    # Handle additional document deletion
    if document_type.startswith('additional_'):
        try:
            doc_id = int(document_type.replace('additional_', ''))
            additional_doc = employee.additional_documents.filter(id=doc_id).first()
        except (ValueError, TypeError):
            additional_doc = None

        if not additional_doc:
            return JsonResponse({'success': False, 'error': 'Additional document not found'})

        try:
            additional_doc.file.delete(save=False)
            additional_doc.delete()
            return JsonResponse({'success': True, 'message': 'Additional document deleted successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    document_map = {
        'photo': 'photo',
        'cnic_copy': 'cnic_copy',
        'passport_size_photo': 'passport_size_photo',
        'updated_resume': 'updated_resume',
        'educational_certificate': 'educational_certificate',
        'experience_letter': 'experience_letter',
        'offer_letter_signed': 'offer_letter_signed',
        'nda_form_signed': 'nda_form_signed',
    }

    if document_type not in document_map:
        return JsonResponse({'success': False, 'error': 'Invalid document type'})

    try:
        file_field = getattr(employee, document_type)
        if file_field:
            file_field.delete(save=False)
            setattr(employee, document_type, None)
            employee.save()

            return JsonResponse({
                'success': True,
                'message': f'{document_type.replace("_", " ").title()} deleted successfully!'
            })
        else:
            return JsonResponse({'success': False, 'error': 'Document not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_additional_document(request, employee_id):
    """
    Create a new additional document for an employee.

    - Admin/HR/superuser can add documents for any employee.
    - Regular employees can add documents for themselves (even if profile is submitted).
    """
    is_admin_user = request.user.is_superuser
    profile = None

    if not is_admin_user:
        try:
            profile = request.user.profile
            is_admin_user = profile.role in ['admin', 'hr']
        except UserProfile.DoesNotExist:
            profile = None

    # Resolve target employee
    try:
        if is_admin_user:
            employee = get_object_or_404(Employees, code=employee_id)
        else:
            try:
                # Regular users can only create additional documents for themselves
                employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)
            except UserProfile.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'User profile not found'})
    except Exception as e:
        # Handle any errors when looking up employee (e.g., invalid code format)
        return JsonResponse({'success': False, 'error': f'Employee not found. Please ensure you are using the correct employee ID.'})

    label = (request.POST.get('label') or '').strip() or 'Additional Document'
    file_obj = request.FILES.get('document_file')

    if not file_obj:
        return JsonResponse({'success': False, 'error': 'No file provided'})

    try:
        additional_doc = EmployeeAdditionalDocument.objects.create(
            employee=employee,
            label=label,
            file=file_obj,
        )

        doc_slug = f"additional_{additional_doc.id}"

        return JsonResponse({
            'success': True,
            'message': f'"{additional_doc.label}" uploaded successfully!',
            'id': additional_doc.id,
            'label': additional_doc.label,
            'file_url': additional_doc.file.url,
            'document_slug': doc_slug,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def login_view(request):
    """Handle user login with role-based redirection"""
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.is_admin() or profile.is_hr():
                return redirect('dashboard')
            else:
                return redirect('dashboard')
        except UserProfile.DoesNotExist:
            return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Refresh user from database to ensure we have the latest username
                user.refresh_from_db()
                login(request, user)
                request.session.set_expiry(0 if not remember_me else 1209600)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                try:
                    profile = user.profile
                    next_url = request.GET.get('next', 'dashboard' if (profile.is_admin() or profile.is_hr()) else 'dashboard')
                    return redirect(next_url)
                except UserProfile.DoesNotExist:
                    # Superusers don't need a UserProfile - they can use the system without one
                    if user.is_superuser:
                        return redirect('dashboard')
                    else:
                        # Check if user has an Employee record linked
                        try:
                            employee = user.employee
                            if employee:
                                # Automatically create UserProfile for employee users
                                profile = UserProfile.objects.create(
                                    user=user,
                                    employee=employee,
                                    role='employee'
                                )
                                next_url = request.GET.get('next', 'dashboard')
                                return redirect(next_url)
                        except AttributeError:
                            pass

                        # No employee linked - show warning
                        messages.warning(request, 'User profile not configured. Contact administrator.')
                        return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password. Please try again.')
        else:
            messages.error(request, 'Please fill in all required fields.')
    return render(request, 'pages/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')

def test_email(request):
    """Test email functionality - for debugging"""
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            'Test Email from EIS',
            'This is a test email to verify email configuration.',
            settings.DEFAULT_FROM_EMAIL or 'noreply@example.com',
            ['test@example.com'],
            fail_silently=False,
        )
        messages.success(request, 'Test email sent successfully! Check your console or email folder.')
    except Exception as e:
        messages.error(request, f'Email sending failed: {str(e)}')
    return redirect('login')

@login_required
def send_birthday_emails_manual(request):
    """Manually trigger birthday email sending - Admin/HR only"""
    # Check if user is admin/hr/superuser
    is_admin_user = request.user.is_superuser
    if not is_admin_user:
        try:
            profile = request.user.profile
            is_admin_user = profile.role in ['admin', 'hr']
        except:
            pass

    if not is_admin_user:
        messages.error(request, 'You do not have permission to send birthday emails.')
        return redirect('dashboard')

    from django.core.management import call_command
    from io import StringIO
    import sys

    # Capture command output
    old_stdout = sys.stdout
    sys.stdout = buffer = StringIO()

    try:
        call_command('send_birthday_emails')
        output = buffer.getvalue()
        sys.stdout = old_stdout

        # Parse output to show results
        if 'sent' in output.lower() or 'Found' in output:
            messages.success(request, f'Birthday emails processed successfully! Check output: {output[:200]}')
        else:
            messages.info(request, f'Birthday email check completed: {output[:200]}')
    except Exception as e:
        sys.stdout = old_stdout
        messages.error(request, f'Error sending birthday emails: {str(e)}')

    return redirect('dashboard')


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


# ===========================
#   POSITIONS
# ===========================

@login_required
def positions(request):
    pos_qs = Position.objects.all().order_by("-date_added")
    total_positions = pos_qs.count()
    active_positions = pos_qs.filter(status="active").count()
    total_employees = only_me_employee_qs(request).count()  # scoped employee count

    return render(request, "pages/positions.html", {
        "positions": pos_qs,
        "total_positions": total_positions,
        "active_positions": active_positions,
        "total_employees": total_employees,
    })

@login_required
def add_position(request):
    if request.method == "POST":
        try:
            Position.objects.create(
                name=request.POST.get("name"),
                description=request.POST.get("description"),
                status=request.POST.get("status", "active")
            )
            messages.success(request, "Position created successfully!")
        except Exception as e:
            messages.error(request, f"Error creating position: {e}")
    return redirect("positions")

@login_required
def update_position(request, pk):
    position = get_object_or_404(Position, pk=pk)
    if request.method == "POST":
        try:
            position.name = request.POST.get("name")
            position.description = request.POST.get("description")
            position.status = request.POST.get("status", "active")
            position.save()
            messages.success(request, f"Position '{position.name}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating position: {e}")
    return redirect("positions")

@login_required
def delete_position(request, pk):
    position = get_object_or_404(Position, pk=pk)
    name = position.name
    position.delete()
    messages.success(request, f"Position '{name}' deleted successfully!")
    return redirect("positions")


# ===========================
#   PAYROLL (PAGE + APIs)
# ===========================

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
        from .models import Department
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
def reports(request):
    # Previously returned a static template with no context.
    # Delegate to the DB-backed reports_dashboard view so the page shows real-time data.
    return reports_dashboard(request)

@login_required
@admin_required
def settings(request):
    """Settings page view"""
    s = SystemSettings.get_solo()

    # Initialize default JSON settings if empty
    if not s.notification_settings:
        s.notification_settings = {
            'email_enabled': True,
            'email_security': True,
            'email_updates': True,
            'email_promo': False,
            'push_enabled': True,
            'push_new_user': True,
            'push_messages': True,
            'push_reminders': False,
            'in_app_enabled': True,
            'in_app_sounds': True,
            'in_app_preview': True,
        }
        s.save()

    if not s.security_settings:
        s.security_settings = {
            'two_factor_auth': False,
            'session_timeout': 30,
            'password_expiry_days': 90,
        }
        s.save()

    if not s.privacy_settings:
        s.privacy_settings = {
            'profile_visibility': 'public',
            'data_sharing': False,
            'analytics': True,
        }
        s.save()

    if not s.backup_settings:
        s.backup_settings = {
            'auto_backup': False,
            'backup_frequency': 'daily',
            'retention_days': 30,
        }
        s.save()

    return render(request, 'pages/settings.html', {'system_settings': s})

@login_required
@admin_required
@require_http_methods(["POST"])
def update_settings_ajax(request):
    """AJAX endpoint for real-time settings updates"""
    try:
        s = SystemSettings.get_solo()
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        section = data.get('section')
        setting_key = data.get('key')
        setting_value = data.get('value')

        if not section or not setting_key:
            return JsonResponse({'success': False, 'message': 'Missing required parameters'})

        # Handle different sections
        if section == 'general':
            if setting_key == 'language':
                s.language = setting_value
            elif setting_key == 'date_format':
                s.date_format = setting_value
            elif setting_key == 'time_format':
                s.time_format = setting_value
            elif setting_key == 'timezone':
                s.TIMEZONE = setting_value
            s.save()

        elif section == 'appearance':
            if setting_key == 'dark_mode':
                s.dark_mode = setting_value in (True, 'true', '1', 'on')
                # Apply dark mode immediately
                if s.dark_mode:
                    request.session['dark_mode'] = True
                else:
                    request.session['dark_mode'] = False
            elif setting_key == 'theme':
                s.theme = setting_value
                request.session['theme'] = setting_value
            elif setting_key == 'font_size':
                s.font_size = setting_value
                request.session['font_size'] = setting_value
            elif setting_key == 'sidebar_width':
                s.sidebar_width = setting_value
                request.session['sidebar_width'] = setting_value
            s.save()

        elif section == 'notifications':
            if not s.notification_settings:
                s.notification_settings = {}
            s.notification_settings[setting_key] = setting_value in (True, 'true', '1', 'on') if isinstance(setting_value, str) else bool(setting_value)
            s.save()

        elif section == 'security':
            if not s.security_settings:
                s.security_settings = {}
            if setting_key == 'two_factor_auth':
                s.security_settings[setting_key] = setting_value in (True, 'true', '1', 'on') if isinstance(setting_value, str) else bool(setting_value)
            elif setting_key in ['session_timeout', 'password_expiry_days']:
                s.security_settings[setting_key] = int(setting_value)
            else:
                s.security_settings[setting_key] = setting_value
            s.save()

        elif section == 'privacy':
            if not s.privacy_settings:
                s.privacy_settings = {}
            if setting_key in ['data_sharing', 'analytics']:
                s.privacy_settings[setting_key] = setting_value in (True, 'true', '1', 'on') if isinstance(setting_value, str) else bool(setting_value)
            else:
                s.privacy_settings[setting_key] = setting_value
            s.save()

        elif section == 'backup':
            if not s.backup_settings:
                s.backup_settings = {}
            if setting_key == 'auto_backup':
                s.backup_settings[setting_key] = setting_value in (True, 'true', '1', 'on') if isinstance(setting_value, str) else bool(setting_value)
            else:
                s.backup_settings[setting_key] = setting_value
            s.save()

        return JsonResponse({
            'success': True,
            'message': 'Setting updated successfully',
            'value': setting_value
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error updating setting: {str(e)}'
        })

@login_required
@admin_required
def get_settings_ajax(request):
    """Get current settings as JSON"""
    try:
        s = SystemSettings.get_solo()
        return JsonResponse({
            'success': True,
            'settings': {
                'general': {
                    'language': s.language,
                    'date_format': s.date_format,
                    'time_format': s.time_format,
                    'timezone': s.TIMEZONE,
                },
                'appearance': {
                    'dark_mode': s.dark_mode,
                    'theme': s.theme,
                    'font_size': s.font_size,
                    'sidebar_width': s.sidebar_width,
                },
                'notifications': s.notification_settings or {},
                'security': s.security_settings or {},
                'privacy': s.privacy_settings or {},
                'backup': s.backup_settings or {},
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error retrieving settings: {str(e)}'
        })


# ===========================
#   INCREMENT SETTINGS VIEWS
# ===========================

@login_required
@finance_or_admin_required
def get_increment_settings(request):
    """Get current increment settings"""
    try:
        settings = IncrementSettings.get_active()
        return JsonResponse({
            'success': True,
            'settings': {
                'increment_percentage': str(settings.increment_percentage),
                'increment_amount': str(settings.increment_amount),
                'use_percentage': settings.use_percentage,
                'cycle_months': settings.cycle_months,
                'is_active': settings.is_active,
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None,
                'updated_by': settings.updated_by.get_full_name() if settings.updated_by else None,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error retrieving increment settings: {str(e)}'
        })


@login_required
@finance_or_admin_required
@require_http_methods(["POST"])
def update_increment_settings(request):
    """Update increment settings"""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        settings = IncrementSettings.get_active()

        if 'increment_percentage' in data:
            settings.increment_percentage = Decimal(data['increment_percentage'])
        if 'increment_amount' in data:
            settings.increment_amount = Decimal(data['increment_amount'])
        if 'use_percentage' in data:
            settings.use_percentage = data['use_percentage'] in (True, 'true', '1', 'on')
        if 'cycle_months' in data:
            settings.cycle_months = int(data['cycle_months'])
        if 'is_active' in data:
            settings.is_active = data['is_active'] in (True, 'true', '1', 'on')

        settings.updated_by = request.user
        settings.save()

        return JsonResponse({
            'success': True,
            'message': 'Increment settings updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error updating increment settings: {str(e)}'
        })


# ===========================
#   DEPARTMENTS
# ===========================

@login_required
@hr_or_admin_required  # Assuming role decorator; remove if not needed
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


# ===========================
#   EMPLOYEE CRUD
# ===========================

@login_required
def employee(request):
    employees = only_me_employee_qs(request).select_related("department", "position").order_by("-date_added")
    departments = Department.objects.all()
    positions = Position.objects.all()
    return render(request, "pages/employee.html", {"employees": employees, "departments": departments, "positions": positions})

# Replace the add_employee function in views.py with this:

def generate_next_employee_id():
    """
    Generate the next employee ID by getting the last real (non-dummy) employee's code number and adding 1.
    Excludes dummy/test/sample employees and employees with codes starting with "EMP".
    Returns a 3-digit zero-padded string (e.g., "001", "002", "003").
    If no real employees exist, returns "001".
    """
    # Exclude dummy/test/sample employees
    exclude_dummy_q = Q(
        Q(code__icontains='test') |
        Q(code__icontains='dummy') |
        Q(code__icontains='sample') |
        Q(code__startswith='EMP') |  # Dummy employees from generate_dummy_employees command
        Q(firstname__icontains='test') |
        Q(firstname__icontains='dummy') |
        Q(firstname__icontains='sample') |
        Q(lastname__icontains='test') |
        Q(lastname__icontains='dummy') |
        Q(lastname__icontains='sample')
    )

    # Get the last real employee ordered by date_added (most recently added real employee)
    last_employee = Employees.objects.exclude(exclude_dummy_q).order_by('-date_added').first()

    # If no real employees found, try ordering by ID as fallback
    if not last_employee:
        last_employee = Employees.objects.exclude(exclude_dummy_q).order_by('-id').first()

    # If no real employees exist, start with 001
    if not last_employee or not last_employee.code:
        return "001"

    # Extract the numeric part from the last employee's code
    last_code = last_employee.code.strip()

    # Check if the code is purely numeric
    if last_code.isdigit():
        # If it's numeric, convert to int, add 1, and format
        last_number = int(last_code)
        next_number = last_number + 1
        return f"{next_number:03d}"
    else:
        # If code is not purely numeric, try to extract numeric part
        # For example, "EMP001" -> extract "001", "110" -> extract "110"
        numbers = re.findall(r'\d+', last_code)
        if numbers:
            # Use the last number found in the code
            last_number = int(numbers[-1])
            next_number = last_number + 1
            return f"{next_number:03d}"
        else:
            # If no numbers found, start with 001
            return "001"

@login_required
def add_employee(request):
    # Check user role and permissions
    is_admin_user = request.user.is_superuser
    profile = None
    user_role = 'employee'

    if not is_admin_user:
        try:
            profile = request.user.profile
            user_role = profile.role
            is_admin_user = user_role in ['admin', 'hr']
        except UserProfile.DoesNotExist:
            pass

    # Get current employee if user is an employee
    current_employee = None
    if not is_admin_user:
        current_employee = getattr(request.user, 'employee', None)
        if not current_employee and profile:
            current_employee = getattr(profile, 'employee', None)

    # Check if employee has already submitted (for employee users only)
    is_locked = False
    missing_documents = []
    if current_employee and not is_admin_user:
        is_locked = current_employee.profile_submitted

        # Check for missing documents
        document_fields = {
            'cnic_copy': 'CNIC Copy',
            'passport_size_photo': 'Passport Size Photo',
            'updated_resume': 'Updated Resume',
            'educational_certificate': 'Educational Certificate',
            'experience_letter': 'Experience Letter',
            'offer_letter_signed': 'Signed Offer Letter',
            'nda_form_signed': 'Signed NDA Form'
        }

        for field, label in document_fields.items():
            if not getattr(current_employee, field, None):
                missing_documents.append({'field': field, 'label': label})

    if request.method == "POST":
        # Check if this is an update (employee_id provided) or new creation
        employee_id = request.POST.get("employee_id")

        # Get data and files early so they can be used in validation
        data = request.POST
        files = request.FILES

        try:
            # If employee_id provided, update existing employee
            if employee_id:
                if not is_admin_user:
                    # Employees can only update their own record
                    if current_employee and str(current_employee.id) != str(employee_id):
                        messages.error(request, "❌ You can only update your own profile.")
                        return redirect("add_employee")

                emp = get_object_or_404(Employees, id=employee_id)
                is_new = False

                # Update is_locked based on the actual employee being edited (for admin editing other employees)
                # For employees, is_locked is already set correctly above
                if is_admin_user:
                    is_locked = False  # Admin/HR can always edit, so is_locked is False for them
                elif not is_admin_user:
                    # For regular employees, check if the profile they're editing is locked
                    is_locked = emp.profile_submitted if emp else False

                # If employee is trying to submit but form is locked, check if they're only filling blank fields or uploading missing documents
                # Admin/HR can always update, so skip this check for them
                if is_locked and not is_admin_user:
                    # Check if any non-document fields that already have values are being changed
                    non_document_fields = ['code', 'firstname', 'lastname', 'father_name', 'dob', 'gender',
                                         'marital_status', 'national_id', 'blood_group', 'contact_1', 'contact_2',
                                         'emergency_contact', 'emergency_contact_person', 'email', 'official_email',
                                         'present_address', 'permanent_address', 'department', 'position', 'job_title',
                                         'date_hired', 'date_permanent', 'registration_no', 'work_mode', 'employment_type',
                                         'reporting_to', 'salary', 'location', 'bank_name', 'branch_name', 'account_title',
                                         'account_number', 'team', 'status']

                    # Only block if trying to change a field that already has a value
                    # Allow filling blank/empty fields
                    has_restricted_changes = False
                    for field in non_document_fields:
                        if field in data:
                            new_value = data.get(field, '').strip()

                            # Handle special cases for foreign key fields
                            if field == 'department':
                                current_value = emp.department_id if emp.department_id else None
                            elif field == 'position':
                                current_value = emp.position_id if emp.position_id else None
                            else:
                                current_value = getattr(emp, field, None)

                            # Convert current value to string for comparison
                            if current_value is None:
                                current_value_str = ''
                            elif isinstance(current_value, (int, float)):
                                current_value_str = str(current_value) if current_value != 0 else ''
                            else:
                                current_value_str = str(current_value).strip() if current_value else ''

                            # Block only if:
                            # 1. Current field has a value (not empty/None/0)
                            # 2. New value is different from current value
                            # 3. New value is not empty (not just clearing the field)
                            # Allow if current field is empty/blank (filling blank fields is allowed)
                            # Only block if trying to change an existing non-empty value
                            if current_value_str and new_value and new_value != current_value_str:
                                has_restricted_changes = True
                                break

                    # Check if documents are being uploaded
                    file_fields = ["cnic_copy", "passport_size_photo", "updated_resume",
                                  "educational_certificate", "experience_letter", "offer_letter_signed", "nda_form_signed"]
                    has_document_upload = any(field in files for field in file_fields)

                    # Block only if trying to change existing non-empty fields
                    # Allow: filling blank fields, uploading missing documents
                    if has_restricted_changes:
                        messages.error(request, "❌ Your profile has already been submitted. You cannot modify existing data. You can only fill blank fields or upload missing documents. Please contact HR/Admin for other changes.")
                        return redirect("add_employee")

                    if has_document_upload:
                        # Check if documents being uploaded are actually missing
                        for field in file_fields:
                            if field in files:
                                current_doc = getattr(emp, field, None)
                                if current_doc:
                                    messages.error(request, f"❌ {field.replace('_', ' ').title()} already exists. You cannot replace existing documents. Please contact HR/Admin.")
                                    return redirect("add_employee")
            else:
                # New employee creation (admin/HR only)
                if not is_admin_user:
                    messages.error(request, "❌ Only administrators can create new employee records.")
                    return redirect("add_employee")

                emp = Employees()
                is_new = True

            # Update fields
            if is_new or is_admin_user:
                # Admin can set all fields
                code_value = data.get("code", "").strip()
                # For new employees, if code is not provided, generate it automatically
                if is_new and not code_value:
                    code_value = generate_next_employee_id()

                # Validate employee ID uniqueness when updating
                if code_value and not is_new:
                    # Check if the new code is already taken by another employee
                    existing_employee = Employees.objects.filter(code=code_value).exclude(id=emp.id).first()
                    if existing_employee:
                        messages.error(request, f"❌ Employee ID '{code_value}' is already assigned to another employee. Please use a unique ID.")
                        return redirect("add_employee")

                if code_value:
                    # Set the new code value
                    emp.code = code_value
                elif is_new:
                    # For new employees, ensure code is set (generate if not provided)
                    emp.code = generate_next_employee_id()
                # If code_value is empty and it's an update, keep the existing code (don't change it)

                emp.team = data.get("team", "") or emp.team
                emp.status = int(data.get("status", emp.status if emp.id else 1))

            # Fields that employees can fill
            # For locked profiles, allow filling blank fields but preserve existing values
            if is_locked and not is_admin_user:
                # Only update if current field is empty/blank
                if not emp.firstname: emp.firstname = data.get("firstname", "").strip() or emp.firstname
                if not emp.lastname: emp.lastname = data.get("lastname", "").strip() or emp.lastname
                if not emp.father_name: emp.father_name = data.get("father_name", "").strip() or emp.father_name
                if not emp.dob: emp.dob = data.get("dob", None) or emp.dob
                if not emp.gender: emp.gender = data.get("gender", "").strip() or emp.gender
                if not emp.marital_status: emp.marital_status = data.get("marital_status", "").strip() or emp.marital_status
                if not emp.national_id: emp.national_id = data.get("national_id", "").strip() or emp.national_id
                if not emp.blood_group: emp.blood_group = data.get("blood_group", "").strip() or emp.blood_group
                if not emp.contact_1: emp.contact_1 = data.get("contact_1", "").strip() or emp.contact_1
                if not emp.contact_2: emp.contact_2 = data.get("contact_2", "").strip() or emp.contact_2
                if not emp.emergency_contact: emp.emergency_contact = data.get("emergency_contact", "").strip() or emp.emergency_contact
                if not emp.emergency_contact_person: emp.emergency_contact_person = data.get("emergency_contact_person", "").strip() or emp.emergency_contact_person
                if not emp.email: emp.email = data.get("email", "").strip() or emp.email
                if not emp.official_email: emp.official_email = data.get("official_email", "").strip() or emp.official_email
                if not emp.present_address: emp.present_address = data.get("present_address", "").strip() or emp.present_address
                if not emp.permanent_address: emp.permanent_address = data.get("permanent_address", "").strip() or emp.permanent_address
            else:
                # Normal update - allow all changes
                emp.firstname = data.get("firstname", "").strip() or emp.firstname
                emp.lastname = data.get("lastname", "").strip() or emp.lastname
                emp.father_name = data.get("father_name", "").strip() or emp.father_name
                emp.dob = data.get("dob", None) or emp.dob
                emp.gender = data.get("gender", "").strip() or emp.gender
                emp.marital_status = data.get("marital_status", "").strip() or emp.marital_status
                emp.national_id = data.get("national_id", "").strip() or emp.national_id
                emp.blood_group = data.get("blood_group", "").strip() or emp.blood_group
                emp.contact_1 = data.get("contact_1", "").strip() or emp.contact_1
                emp.contact_2 = data.get("contact_2", "").strip() or emp.contact_2
                emp.emergency_contact = data.get("emergency_contact", "").strip() or emp.emergency_contact
                emp.emergency_contact_person = data.get("emergency_contact_person", "").strip() or emp.emergency_contact_person
                emp.email = data.get("email", "").strip() or emp.email
                emp.official_email = data.get("official_email", "").strip() or emp.official_email
                emp.present_address = data.get("present_address", "").strip() or emp.present_address
                emp.permanent_address = data.get("permanent_address", "").strip() or emp.permanent_address

            if is_admin_user:
                emp.department_id = data.get("department", None) or emp.department_id
                emp.position_id = data.get("position", None) or emp.position_id
                emp.job_title = data.get("job_title", "").strip() or emp.job_title
                emp.date_hired = data.get("date_hired", None) or emp.date_hired
                emp.date_permanent = data.get("date_permanent", None) or emp.date_permanent
                emp.registration_no = data.get("registration_no", "").strip() or emp.registration_no
                emp.work_mode = data.get("work_mode", "Onsite") or emp.work_mode
                emp.employment_type = data.get("employment_type", "Full Time") or emp.employment_type
                emp.reporting_to = data.get("reporting_to", "").strip() or emp.reporting_to
                emp.salary = int(data.get("salary", 0)) if data.get("salary") else emp.salary
                emp.location = data.get("location", "FunPrime Technology") or emp.location
                emp.bank_name = data.get("bank_name", "").strip() or emp.bank_name
                emp.branch_name = data.get("branch_name", "").strip() or emp.branch_name
                emp.account_title = data.get("account_title", "").strip() or emp.account_title
                emp.account_number = data.get("account_number", "").strip() or emp.account_number
            else:
                # Employees can update these fields
                # For locked profiles, only allow filling blank fields
                if is_locked and not is_admin_user:
                    if not emp.job_title: emp.job_title = data.get("job_title", "").strip() or emp.job_title
                    if not emp.date_hired: emp.date_hired = data.get("date_hired", None) or emp.date_hired
                    if not emp.date_permanent: emp.date_permanent = data.get("date_permanent", None) or emp.date_permanent
                    if not emp.registration_no: emp.registration_no = data.get("registration_no", "").strip() or emp.registration_no
                    if not emp.work_mode: emp.work_mode = data.get("work_mode", "Onsite") or emp.work_mode
                    if not emp.employment_type: emp.employment_type = data.get("employment_type", "Full Time") or emp.employment_type
                    if not emp.reporting_to: emp.reporting_to = data.get("reporting_to", "").strip() or emp.reporting_to
                    if not emp.location: emp.location = data.get("location", "FunPrime Technology") or emp.location
                    if not emp.bank_name: emp.bank_name = data.get("bank_name", "").strip() or emp.bank_name
                    if not emp.branch_name: emp.branch_name = data.get("branch_name", "").strip() or emp.branch_name
                    if not emp.account_title: emp.account_title = data.get("account_title", "").strip() or emp.account_title
                    if not emp.account_number: emp.account_number = data.get("account_number", "").strip() or emp.account_number
                else:
                    # Normal update - allow all changes for employees when not locked
                    emp.job_title = data.get("job_title", "").strip() or emp.job_title
                    emp.date_hired = data.get("date_hired", None) or emp.date_hired
                    emp.date_permanent = data.get("date_permanent", None) or emp.date_permanent
                    emp.registration_no = data.get("registration_no", "").strip() or emp.registration_no
                    emp.work_mode = data.get("work_mode", "Onsite") or emp.work_mode
                    emp.employment_type = data.get("employment_type", "Full Time") or emp.employment_type
                    emp.reporting_to = data.get("reporting_to", "").strip() or emp.reporting_to
                    emp.location = data.get("location", "FunPrime Technology") or emp.location
                    emp.bank_name = data.get("bank_name", "").strip() or emp.bank_name
                    emp.branch_name = data.get("branch_name", "").strip() or emp.branch_name
                    emp.account_title = data.get("account_title", "").strip() or emp.account_title
                    emp.account_number = data.get("account_number", "").strip() or emp.account_number

            # Handle file uploads - check if profile is submitted for employees
            if not is_admin_user and is_locked:
                # Check if any files are being uploaded
                file_fields = ["photo", "cnic_copy", "passport_size_photo", "updated_resume",
                              "educational_certificate", "experience_letter", "offer_letter_signed", "nda_form_signed"]
                has_file_upload = any(field in files for field in file_fields)

                # Allow uploading missing documents even if profile is locked
                if has_file_upload:
                    # Check if documents being uploaded are actually missing
                    for field in file_fields:
                        if field in files:
                            current_doc = getattr(emp, field, None)
                            if current_doc:
                                messages.error(request, f"❌ {field.replace('_', ' ').title()} already exists. You cannot replace existing documents. Please contact HR/Admin.")
                                return redirect("add_employee")
                    # If all documents being uploaded are missing, allow the upload

            # Handle file uploads
            # Allow document uploads even if profile is locked (for missing documents only)
            document_fields_map = {
                'photo': 'photo',
                'cnic_copy': 'cnic_copy',
                'passport_size_photo': 'passport_size_photo',
                'updated_resume': 'updated_resume',
                'educational_certificate': 'educational_certificate',
                'experience_letter': 'experience_letter',
                'offer_letter_signed': 'offer_letter_signed',
                'nda_form_signed': 'nda_form_signed'
            }

            for file_key, field_name in document_fields_map.items():
                if file_key in files:
                    # If profile is locked and employee is uploading, only allow if document is missing
                    if is_locked and not is_admin_user:
                        current_doc = getattr(emp, field_name, None)
                        if current_doc:
                            # Document already exists, don't allow update
                            continue
                    # Allow upload for new documents or if admin
                    setattr(emp, field_name, files[file_key])

            # Mark as submitted if employee is submitting (not admin)
            if not is_admin_user and not is_locked:
                emp.profile_submitted = True

            emp.full_clean()
            emp.save()

            # Save additional documents (dynamic)
            additional_docs_created = 0
            for file_key, uploaded_file in files.items():
                if not file_key.startswith("additional_document_file_"):
                    continue
                # Extract suffix number to find matching label
                suffix = file_key.replace("additional_document_file_", "")
                label_key = f"additional_document_label_{suffix}"
                label_value = data.get(label_key, "").strip() or "Additional Document"

                # If profile is locked for non-admins, allow adding new additional docs (they are always new)
                EmployeeAdditionalDocument.objects.create(
                    employee=emp,
                    label=label_value,
                    file=uploaded_file
                )
                additional_docs_created += 1

            if is_new:
                # Reload employee to get the temp_password set by the signal handler
                emp.refresh_from_db()
                generated_password = emp.temp_password

                if generated_password and is_admin_user:
                    # Display the generated password to admin
                    messages.success(
                        request,
                        f"✅ Employee {emp.code} added successfully! "
                        f"Generated Password: <strong>{generated_password}</strong> "
                        f"(Username: {emp.user.username if emp.user else 'N/A'}) - "
                        f"Please share this password securely with the employee."
                    )
                    # Clear the temporary password after displaying (for security)
                    emp.temp_password = None
                    emp.save(update_fields=['temp_password'])
                else:
                    messages.success(request, f"✅ Employee {emp.code} added successfully!")
            else:
                if not is_admin_user:
                    # Check if only documents were uploaded
                    has_doc_upload = any(field in files for field in ['cnic_copy', 'passport_size_photo', 'updated_resume',
                                                                     'educational_certificate', 'experience_letter',
                                                                     'offer_letter_signed', 'nda_form_signed'])
                    if is_locked and has_doc_upload:
                        messages.success(request, f"✅ Missing documents uploaded successfully! Your profile remains locked for other changes.")
                    else:
                        messages.success(request, f"✅ Your profile information has been submitted successfully!")
                else:
                    messages.success(request, f"✅ Employee {emp.code} updated successfully!")

            # REDIRECT TO PROFILE PAGE WITH SEARCH PARAMETER
            # If new employee and password was generated, include it in the redirect URL for display
            if is_new and generated_password and is_admin_user:
                # Store password in session temporarily for display on profile page
                request.session[f'employee_{emp.id}_password'] = generated_password
                request.session[f'employee_{emp.id}_username'] = emp.user.username if emp.user else ''

            return redirect(f'/employee-profile/?q={emp.code}')

        except ValidationError as e:
            messages.error(request, f"❌ Validation error: {str(e)}")
            return redirect("add_employee")
        except IntegrityError:
            messages.error(request, "❌ Employee ID already exists. Please use a unique ID.")
            return redirect("add_employee")
        except Exception as e:
            messages.error(request, f"❌ Error saving employee: {str(e)}")
            return redirect("add_employee")

    # GET request - show the form
    # Re-check missing documents for template (in case employee was updated)
    if current_employee and not is_admin_user:
        document_fields = {
            'cnic_copy': 'CNIC Copy',
            'passport_size_photo': 'Passport Size Photo',
            'updated_resume': 'Updated Resume',
            'educational_certificate': 'Educational Certificate',
            'experience_letter': 'Experience Letter',
            'offer_letter_signed': 'Signed Offer Letter',
            'nda_form_signed': 'Signed NDA Form'
        }

        missing_documents = []
        for field, label in document_fields.items():
            if not getattr(current_employee, field, None):
                missing_documents.append({'field': field, 'label': label})
    else:
        missing_documents = []

    # Check if admin is loading an employee for editing via query parameter
    employee_to_edit = None
    if is_admin_user:
        edit_code = request.GET.get('edit', '').strip()
        if edit_code:
            try:
                employee_to_edit = Employees.objects.get(code=edit_code)
            except Employees.DoesNotExist:
                pass

    context = {
        "departments": Department.objects.all(),
        "positions": Position.objects.all(),
        "is_admin_user": is_admin_user,
        "user_role": user_role,
        "current_employee": current_employee,
        "is_locked": is_locked,
        "missing_documents": missing_documents,
    }

    # If employee user, pre-fill with their data
    if current_employee and not is_admin_user:
        context["employee"] = current_employee
    elif is_admin_user:
        if employee_to_edit:
            # Admin is editing a specific employee
            context["employee"] = employee_to_edit
        elif not current_employee:
            # For admin users creating a new employee, generate the next employee ID
            context["next_employee_id"] = generate_next_employee_id()

    return render(request, "pages/employee.html", context)


@login_required
def get_employee(request, employee_id):
    employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)
    data = {
        'status': 'success',
        'employee': {
            'code': employee.code,
            'team': employee.team,
            'status': employee.status,
            'firstname': employee.firstname,
            'lastname': employee.lastname,
            'father_name': employee.father_name,
            'dob': employee.dob.strftime('%Y-%m-%d') if employee.dob else '',
            'gender': employee.gender,
            'marital_status': employee.marital_status,
            'national_id': employee.national_id,
            'blood_group': employee.blood_group,
            'contact_1': employee.contact_1,
            'contact_2': employee.contact_2,
            'emergency_contact': employee.emergency_contact,
            'emergency_contact_person': employee.emergency_contact_person,
            'email': employee.email,
            'official_email': employee.official_email,
            'present_address': employee.present_address,
            'permanent_address': employee.permanent_address,
            'department': employee.department_id,
            'position': employee.position_id,
            'job_title': employee.job_title,
            'date_hired': employee.date_hired.strftime('%Y-%m-%d') if employee.date_hired else '',
            'date_permanent': employee.date_permanent.strftime('%Y-%m-%d') if employee.date_permanent else '',
            'registration_no': employee.registration_no,
            'work_mode': employee.work_mode,
            'employment_type': employee.employment_type,
            'reporting_to': employee.reporting_to,
            'salary': employee.salary,
            'location': employee.location,
            'bank_name': employee.bank_name,
            'branch_name': employee.branch_name,
            'account_title': employee.account_title,
            'account_number': employee.account_number,
            'photo': employee.photo.url if employee.photo else '',
        }
    }
    return JsonResponse(data)

@login_required
def update_employee(request, pk):
    employee = get_object_or_404(only_me_employee_qs(request), pk=pk)
    if request.method == "POST":
        try:
            e = employee
            e.firstname = request.POST.get("firstname"); e.lastname = request.POST.get("lastname")
            e.father_name = request.POST.get("father_name"); e.team = request.POST.get("team")
            e.code = request.POST.get("code"); e.national_id = request.POST.get("national_id")
            e.contact_1 = request.POST.get("contact_1"); e.contact_2 = request.POST.get("contact_2")
            e.emergency_contact = request.POST.get("emergency_contact")
            e.emergency_contact_person = request.POST.get("emergency_contact_person")
            e.dob = request.POST.get("dob") or None; e.gender = request.POST.get("gender")
            e.marital_status = request.POST.get("marital_status"); e.blood_group = request.POST.get("blood_group")
            e.email = request.POST.get("email"); e.official_email = request.POST.get("official_email")
            e.present_address = request.POST.get("present_address"); e.permanent_address = request.POST.get("permanent_address")
            e.location = request.POST.get("location"); e.work_mode = request.POST.get("work_mode")
            e.employment_type = request.POST.get("employment_type")
            e.date_hired = request.POST.get("date_hired") or None; e.date_permanent = request.POST.get("date_permanent") or None
            e.registration_no = request.POST.get("registration_no"); e.job_title = request.POST.get("job_title")
            e.reporting_to = request.POST.get("reporting_to")
            e.salary = float(request.POST.get("salary") or 0)
            e.bank_name = request.POST.get("bank_name"); e.branch_name = request.POST.get("branch_name")
            e.account_title = request.POST.get("account_title"); e.account_number = request.POST.get("account_number")
            e.status = int(request.POST.get("status") or 1)

            dep_id = request.POST.get("department"); pos_id = request.POST.get("position")
            if dep_id: e.department_id = dep_id
            if pos_id: e.position_id = pos_id

            for f in ["photo","cnic_copy","passport_size_photo","updated_resume","educational_certificate","experience_letter","offer_letter_signed","nda_form_signed"]:
                if request.FILES.get(f): setattr(e, f, request.FILES.get(f))

            e.save()
            messages.success(request, f"Employee {e.firstname} updated successfully!")
        except ValueError as ve:
            messages.error(request, f"Invalid data provided: {ve}")
        except Exception as ex:
            messages.error(request, f"Error updating employee: {ex}")
    return redirect("employee")

@require_POST
@login_required
def update_employee_field(request, employee_id):
    """Update a single employee field via AJAX - Admin/HR can update any employee, employees can update their own fields"""
    # Check if user is admin/hr/superuser
    is_admin_user = request.user.is_superuser
    profile = None
    user_role = 'employee'

    if not is_admin_user:
        try:
            profile = request.user.profile
            user_role = profile.role
            is_admin_user = user_role in ['admin', 'hr']
        except UserProfile.DoesNotExist:
            pass

    # Get employee - admin/hr can access any, employees only their own
    if is_admin_user:
        employee = get_object_or_404(Employees, code=employee_id)
    else:
        # Regular employees can only update their own profile
        employee = get_object_or_404(only_me_employee_qs(request), code=employee_id)

    try:
        field_name = request.POST.get('field')
        field_value = request.POST.get('value', '').strip()

        # Allowed fields that can be updated
        # Admin/HR can update all fields, employees can only update certain fields
        if is_admin_user:
            # Admin/HR can edit all employee fields
            allowed_fields = [
                'firstname', 'lastname', 'father_name', 'dob', 'gender', 'marital_status',
                'national_id', 'blood_group', 'contact_1', 'contact_2', 'emergency_contact',
                'emergency_contact_person', 'email', 'official_email', 'present_address',
                'permanent_address', 'department', 'position', 'job_title', 'team',
                'date_hired', 'date_permanent', 'registration_no', 'work_mode',
                'employment_type', 'reporting_to', 'salary', 'location', 'bank_name',
                'branch_name', 'account_title', 'account_number', 'status', 'username'
            ]
        else:
            # Employees can only update their own personal info, not department/position/status/username
            allowed_fields = ['email', 'contact_1', 'job_title', 'employment_type']

        if field_name not in allowed_fields:
            return JsonResponse({'success': False, 'error': 'Invalid field name or insufficient permissions'})

        # Special handling for username - update User model
        if field_name == 'username':
            if not employee.user:
                return JsonResponse({'success': False, 'error': 'Employee does not have a user account linked.'})

            # Check if username is already taken by another user
            from django.contrib.auth.models import User
            if User.objects.filter(username=field_value).exclude(pk=employee.user.pk).exists():
                return JsonResponse({'success': False, 'error': f'Username "{field_value}" is already taken. Please choose a different username.'})

            # Validate username (Django requirements)
            if not field_value or len(field_value.strip()) == 0:
                return JsonResponse({'success': False, 'error': 'Username cannot be empty.'})

            if len(field_value) > 150:
                return JsonResponse({'success': False, 'error': 'Username is too long (max 150 characters).'})

            # Update username
            old_username = employee.user.username
            new_username = field_value.strip()

            # Use database transaction to ensure atomic update
            from django.db import transaction
            try:
                with transaction.atomic():
                    # Store the user ID before update
                    user_id = employee.user.pk

                    # Directly update the database to avoid any caching issues
                    # This bypasses any model-level caching
                    rows_updated = User.objects.filter(pk=user_id).update(username=new_username)

                    if rows_updated != 1:
                        raise ValueError(f'Expected to update 1 user, but updated {rows_updated}')

                    # Verify the update was successful by querying the database directly
                    updated_user = User.objects.get(pk=user_id)
                    if updated_user.username != new_username:
                        raise ValueError(f'Username update verification failed. Expected: {new_username}, Got: {updated_user.username}')

                    # Refresh all related objects to clear any caches
                    employee.refresh_from_db()
                    if hasattr(employee, 'user'):
                        employee.user.refresh_from_db()

                    # Double-check by querying again (bypass cache)
                    final_check = User.objects.only('username').get(pk=user_id)
                    if final_check.username != new_username:
                        raise ValueError(f'Final verification failed. Username in DB: {final_check.username}')

                    display_value = new_username
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error updating username: {str(e)}'})
        # Update the field
        elif field_name == 'department':
            if field_value:
                employee.department_id = int(field_value)
            else:
                employee.department = None
        elif field_name == 'position':
            if field_value:
                employee.position_id = int(field_value)
            else:
                employee.position = None
        elif field_name == 'status':
            if field_value not in ['1', '2']:
                return JsonResponse({'success': False, 'error': 'Invalid status value'})
            employee.status = int(field_value)
        elif field_name in ['dob', 'date_hired', 'date_permanent']:
            # Handle date fields - parse from YYYY-MM-DD format
            if field_value:
                try:
                    from datetime import datetime
                    employee.__setattr__(field_name, datetime.strptime(field_value, '%Y-%m-%d').date())
                except ValueError:
                    return JsonResponse({'success': False, 'error': f'Invalid date format for {field_name}. Please use YYYY-MM-DD format.'})
            else:
                employee.__setattr__(field_name, None)
        elif field_name == 'salary':
            # Handle salary as number
            if field_value:
                try:
                    employee.salary = int(float(field_value))
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid salary value. Please provide a valid number.'})
            else:
                employee.salary = 0
        else:
            setattr(employee, field_name, field_value if field_value else None)
            # Save employee if not already saved (username is handled separately)
        if field_name != 'username':
            employee.save()

        # Get updated display value
        if field_name == 'username':
            # display_value already set above
            pass
        elif field_name == 'department' and employee.department:
            display_value = employee.department.name
        elif field_name == 'position' and employee.position:
            display_value = employee.position.name
        elif field_name == 'status':
            display_value = 'Active' if employee.status == 1 else 'Inactive'
        elif field_name in ['dob', 'date_hired', 'date_permanent']:
            # Format date fields for display
            date_obj = getattr(employee, field_name)
            if date_obj:
                display_value = date_obj.strftime('%d %b %Y')
            else:
                display_value = 'Not provided'
        elif not field_value:
            display_value = 'Not provided' if field_name in ['email', 'job_title'] else 'Not assigned'
        else:
            display_value = field_value

        # Special message for username updates
        if field_name == 'username':
            message = f'Username updated successfully from "{old_username}" to "{display_value}". IMPORTANT: The employee must log out and log back in using the NEW username "{display_value}" (the old username "{old_username}" will no longer work).'
        else:
            message = f'{field_name.replace("_", " ").title()} updated successfully!'

        return JsonResponse({
            'success': True,
            'message': message,
            'display_value': display_value
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Invalid value: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating field: {str(e)}'})

@require_POST
@login_required
def update_employee_photo(request, employee_id):
    """Update employee profile picture via AJAX"""
    employee = get_object_or_404(Employees, code=employee_id)

    # Check if user is admin/hr/superuser
    is_admin_user = request.user.is_superuser
    profile = None
    user_role = 'employee'

    if not is_admin_user:
        try:
            profile = request.user.profile
            user_role = profile.role
            is_admin_user = user_role in ['admin', 'hr']
        except UserProfile.DoesNotExist:
            pass

    # Check if employee has submitted their profile (for regular employees only)
    if not is_admin_user and employee.profile_submitted:
        return JsonResponse({
            'success': False,
            'error': 'You have already submitted your documents. You cannot make changes. Please contact administrator for any modifications.'
        })

    try:
        if 'photo' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No photo file provided'})

        photo_file = request.FILES['photo']

        # Validate file type
        if not photo_file.content_type.startswith('image/'):
            return JsonResponse({'success': False, 'error': 'File must be an image'})

        # Validate file size (max 5MB)
        if photo_file.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'Image size must be less than 5MB'})

        # Delete old photo if exists
        if employee.photo:
            employee.photo.delete(save=False)

        # Save new photo
        employee.photo = photo_file
        employee.save()

        return JsonResponse({
            'success': True,
            'message': 'Profile picture updated successfully!',
            'photo_url': employee.photo.url
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating photo: {str(e)}'})

@login_required
@hr_or_admin_required
@require_http_methods(["POST"])
def delete_employee(request, pk):
    """Delete employee - Admin/HR only"""
    # Admin/HR can delete any employee
    if request.user.is_superuser:
        employee = get_object_or_404(Employees, pk=pk)
    else:
        try:
            profile = request.user.profile
            if profile.role in ['admin', 'hr']:
                employee = get_object_or_404(Employees, pk=pk)
            else:
                messages.error(request, 'You do not have permission to delete employees.')
                return redirect('employee_profile')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile not found.')
            return redirect('employee_profile')

    name = f"{employee.firstname} {employee.lastname or ''}"
    employee_code = employee.code
    employee.delete()
    messages.success(request, f"Employee {name} (ID: {employee_code}) deleted successfully!")
    return redirect("employee_profile")

@login_required
@hr_or_admin_required
@require_http_methods(["POST"])
def reset_employee_password(request, employee_id):
    """Reset employee password and generate a new secure password - Admin/HR only"""
    try:
        employee = get_object_or_404(Employees, code=employee_id)

        if not employee.user:
            return JsonResponse({'success': False, 'error': 'Employee does not have a user account linked.'})

        # Generate new secure password
        from EISwebsite.models import generate_secure_password
        new_password = generate_secure_password(length=12)

        # Update the user's password (Django automatically hashes it)
        employee.user.set_password(new_password)
        employee.user.save()

        # Store temporarily so admin can see it
        employee.temp_password = new_password
        employee.save(update_fields=['temp_password'])

        return JsonResponse({
            'success': True,
            'message': 'Password reset successfully!',
            'password': new_password,
            'username': employee.user.username
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@hr_or_admin_required
def get_employee_password(request, employee_id):
    """Get employee's temporary password if available - Admin/HR only"""
    try:
        employee = get_object_or_404(Employees, code=employee_id)

        if not employee.user:
            return JsonResponse({'success': False, 'error': 'Employee does not have a user account linked.'})

        if employee.temp_password:
            return JsonResponse({
                'success': True,
                'password': employee.temp_password,
                'username': employee.user.username,
                'message': 'Password retrieved. It will be cleared after viewing.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No temporary password available. Please reset the password to generate a new one.'
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@hr_or_admin_required
@require_http_methods(["POST"])
def clear_employee_password(request, employee_id):
    """Clear the temporary password after it has been viewed - Admin/HR only"""
    try:
        employee = get_object_or_404(Employees, code=employee_id)
        employee.temp_password = None
        employee.save(update_fields=['temp_password'])
        return JsonResponse({'success': True, 'message': 'Temporary password cleared.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_employee_json(request, pk):
    employee = get_object_or_404(only_me_employee_qs(request), pk=pk)
    data = {
        "id": employee.id,
        "firstname": employee.firstname,
        "lastname": employee.lastname or "",
        "email": employee.email or "",
        "department": employee.department.name if employee.department else "",
        "department_id": employee.department.id if employee.department else "",
        "position": employee.position.name if employee.position else "",
        "position_id": employee.position.id if employee.position else "",
        "salary": str(employee.salary),
        "status": employee.get_status_display(),
        "status_id": employee.status,
    }
    return JsonResponse(data)


# ===========================
#   ATTENDANCE
# ===========================

def _holiday_name_by_date(dates):
    """
    Build a mapping {date -> holiday_name} for the given set/list of dates using the HolidayDate model.
    Avoids N+1 queries by loading holidays once for the date range, then checking in Python.
    """
    from .models import HolidayDate

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


# ===========================
#   HOLIDAY DATES MANAGEMENT
# ===========================

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
    from .models import Attendance, HolidayDate
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
        from .models import Attendance
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


# ===========================
#   TEAMS / PROJECTS
# ===========================

@login_required
def team(request):
    base_qs = Team.objects.select_related('leader', 'department')
    if request.user.is_superuser:
        teams = base_qs.all()
    else:
        me = get_current_employee(request)
        teams = base_qs.filter(Q(leader=me) | Q(members__employee=me, members__is_active=True)).distinct()

    total_teams = teams.count()
    total_members = TeamMember.objects.filter(is_active=True, team__in=teams).count()
    active_projects = Project.objects.filter(status='active', team__in=teams).count()

    # simple demo stats
    team_availability = 85; teams_change = 2; members_change = 5; projects_change = 3; availability_change = 2

    # Get TEAM_CHOICES for dropdown
    from .models import Employees
    team_choices = Employees.TEAM_CHOICES

    return render(request, 'pages/team.html', {
        'teams': teams,
        'stats': {
            'total_teams': total_teams,
            'total_members': total_members,
            'active_projects': active_projects,
            'team_availability': team_availability,
            'teams_change': teams_change,
            'members_change': members_change,
            'projects_change': projects_change,
            'availability_change': availability_change,
        },
        'employees': only_me_employee_qs(request).filter(status=1),
        'departments': Department.objects.all(),
        'team_choices': team_choices,  # TEAM_CHOICES for dropdown
    })

@login_required
@require_http_methods(["POST"])
def add_team(request):
    try:
        data = request.POST
        team_name = data.get('team_name')
        team_lead = data.get('team_lead')  # Can be TEAM_CHOICES value or employee ID
        department_id = data.get('department')
        team_members = data.getlist('team_members')

        if not team_name or not team_lead or not department_id:
            return JsonResponse({'success': False, 'message': 'Team name, leader, and department are required'})

        # Handle team_lead - can be TEAM_CHOICES value (string) or employee ID (integer)
        team_lead_id = None
        try:
            # Try to convert to integer - if it works, it's an employee ID
            team_lead_id = int(team_lead)
            # Verify the employee exists
            employee = Employees.objects.filter(id=team_lead_id).first()
            if not employee:
                return JsonResponse({'success': False, 'message': f'Employee with ID {team_lead_id} not found'})
        except (ValueError, TypeError):
            # It's a string (TEAM_CHOICES value like "Sir Faisal")
            team_lead_name = str(team_lead).strip()

            # Find employee by matching the team_lead name
            # First, try to find by employee's team field matching TEAM_CHOICES
            employee = Employees.objects.filter(
                team=team_lead_name,
                status=1
            ).first()

            # If not found, try to find by name matching
            if not employee:
                # Try matching firstname or full name
                employee = Employees.objects.filter(
                    Q(firstname__icontains=team_lead_name.replace('Sir', '').strip()) |
                    Q(firstname__icontains=team_lead_name) |
                    Q(lastname__icontains=team_lead_name.replace('Sir', '').strip())
                ).filter(status=1).first()

            if not employee:
                return JsonResponse({
                    'success': False,
                    'message': f'No employee found matching team lead: {team_lead_name}'
                })

            team_lead_id = employee.id

        # Non-superusers can only create teams they lead themselves
        if not request.user.is_superuser:
            me = get_current_employee(request)
            if me.id != team_lead_id:
                return JsonResponse({'success': False, 'message': 'Not allowed'}, status=403)

        # Check if team with this name already exists
        if Team.objects.filter(name=team_name).exists():
            return JsonResponse({
                'success': False,
                'message': f'A team with the name "{team_name}" already exists. Please choose a different name.'
            })

        team = Team.objects.create(name=team_name, leader_id=team_lead_id, department_id=department_id)

        # Sync team lead to ensure the employee's team field is set
        if employee.team != team_lead:
            employee.team = team_lead if isinstance(team_lead, str) else employee.team
            employee.save()

        for member_id in team_members:
            TeamMember.objects.create(team=team, employee_id=member_id)

        return JsonResponse({'success': True, 'message': 'Team created successfully', 'team_id': team.id})
    except IntegrityError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Integrity error creating team: {str(e)}', exc_info=True)
        # Check if it's a unique constraint on name
        if 'name' in str(e).lower() or 'UNIQUE constraint' in str(e):
            return JsonResponse({
                'success': False,
                'message': f'A team with the name "{team_name}" already exists. Please choose a different name.'
            })
        return JsonResponse({
            'success': False,
            'message': f'Error creating team: A team with this name or configuration already exists.'
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error creating team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error creating team: {str(e)}'})

@login_required
def team_details(request, team_id):
    try:
        base_qs = Team.objects.select_related('leader', 'department').prefetch_related('members__employee', 'projects')
        if request.user.is_superuser:
            team = get_object_or_404(base_qs, id=team_id)
        else:
            me = get_current_employee(request)
            team = get_object_or_404(base_qs.filter(Q(leader=me) | Q(members__employee=me, members__is_active=True)).distinct(), id=team_id)

        # Get the team lead's TEAM_CHOICES value for the dropdown
        team_lead_name = None
        if team.leader:
            # First, check if the leader's team field matches a TEAM_CHOICES value
            if team.leader.team and team.leader.team in [choice[0] for choice in Employees.TEAM_CHOICES]:
                team_lead_name = team.leader.team
            else:
                # Try to match by name - check if leader's name contains any TEAM_CHOICES name
                leader_name = f"{team.leader.firstname} {team.leader.lastname or ''}".strip().lower()
                for choice_value, choice_display in Employees.TEAM_CHOICES:
                    # Remove "Sir" and spaces for matching
                    choice_name = choice_value.replace('Sir', '').strip().lower()
                    if choice_name in leader_name or leader_name in choice_name:
                        team_lead_name = choice_value
                        break
                    # Also check if firstname matches
                    if team.leader.firstname and choice_name in team.leader.firstname.lower():
                        team_lead_name = choice_value
                        break

        team_data = {
            'id': team.id,
            'name': team.name,
            'status': team.status,
            'leader': {
                'id': team.leader.id if team.leader else None,
                'name': f"{team.leader.firstname} {team.leader.lastname or ''}" if team.leader else 'No Leader',
                'initials': f"{team.leader.firstname[0]}{team.leader.lastname[0] if team.leader and team.leader.lastname else ''}".upper() if team.leader else 'NL',
                'team_lead_name': team_lead_name,  # TEAM_CHOICES value for dropdown
            },
            'department_id': team.department.id if team.department else None,
            'members_count': team.members_count,
            'projects_count': team.projects_count,
            'capacity': team.capacity,
            'members': [],
            'projects': []
        }

        for member in team.members.filter(is_active=True):
            e = member.employee
            team_data['members'].append({
                'id': e.id,
                'name': f"{e.firstname} {e.lastname or ''}",
                'initials': f"{e.firstname[0]}{e.lastname[0] if e.lastname else ''}".upper(),
                'role': member.role or e.job_title or 'Team Member'
            })

        for project in team.projects.all():
            team_data['projects'].append({
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'progress': project.progress,
                'due_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else 'N/A'
            })

        return JsonResponse({'success': True, 'team': team_data})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error retrieving team details: {str(e)}'})

@login_required
def team_members_attendance(request, team_id):
    """
    Get attendance data for all members of a specific team for today
    """
    try:
        today = timezone.now().date()

        # Get team
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Get all active team members
        team_members = TeamMember.objects.filter(team=team, is_active=True).select_related('employee')

        # Get employee IDs
        employee_ids = [tm.employee_id for tm in team_members]

        # Get today's attendance for all team members
        attendance_records = Attendance.objects.filter(
            employee_id__in=employee_ids,
            date=today
        ).select_related('employee')

        # Create attendance map
        attendance_map = {}
        for att in attendance_records:
            attendance_map[att.employee_id] = {
                'status': att.status,
                'status_display': att.get_status_display(),
                'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else None,
                'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else None,
                'is_present': att.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'weekend']
            }

        # Build response with all team members and their attendance
        members_data = []
        for tm in team_members:
            emp = tm.employee
            att_data = attendance_map.get(emp.id, {
                'status': 'absent',
                'status_display': 'Absent',
                'check_in': None,
                'check_out': None,
                'is_present': False
            })

            members_data.append({
                'id': emp.id,
                'name': f"{emp.firstname} {emp.lastname or ''}",
                'attendance': att_data
            })

        return JsonResponse({
            'success': True,
            'team_id': team_id,
            'date': today.strftime('%Y-%m-%d'),
            'members': members_data
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error getting team members attendance: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error getting attendance: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def update_team(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        team_name = data.get('team_name')
        team_lead = data.get('team_lead')
        department = data.get('department')
        status = data.get('status')

        if not team_id:
            return JsonResponse({'success': False, 'message': 'Team ID is required'})

        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Update team name
        if team_name:
            team.name = team_name

        # Update team lead - handle both ID and TEAM_CHOICES value
        if team_lead:
            # Check if team_lead is a TEAM_CHOICES value (string) or an employee ID (integer)
            try:
                # Try to convert to integer - if it works, it's an ID
                team_lead_id = int(team_lead)
                # Verify the employee exists
                employee = Employees.objects.filter(id=team_lead_id).first()
                if not employee:
                    return JsonResponse({'success': False, 'message': f'Employee with ID {team_lead_id} not found'})
                team.leader_id = team_lead_id
            except (ValueError, TypeError):
                # It's a string (TEAM_CHOICES value like "Sir Faisal")
                # Find employee by matching the team_lead name
                team_lead_name = str(team_lead).strip()

                # First, try to find by employee's team field matching TEAM_CHOICES
                employee = Employees.objects.filter(
                    team=team_lead_name,
                    status=1
                ).first()

                # If not found, try to find by name matching
                if not employee:
                    # Try matching firstname or full name
                    employee = Employees.objects.filter(
                        Q(firstname__icontains=team_lead_name.replace('Sir', '').strip()) |
                        Q(firstname__icontains=team_lead_name) |
                        Q(lastname__icontains=team_lead_name.replace('Sir', '').strip())
                    ).filter(status=1).first()

                if not employee:
                    return JsonResponse({
                        'success': False,
                        'message': f'No employee found matching team lead: {team_lead_name}'
                    })

                team.leader_id = employee.id

                # Sync the employee's team field to the TEAM_CHOICES value
                if employee.team != team_lead_name:
                    employee.team = team_lead_name
                    employee.save()

        # Update department
        if department:
            try:
                department_id = int(department)
                team.department_id = department_id
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Invalid department ID'})

        # Update status
        if status in dict(Team.STATUS_CHOICES).keys():
            team.status = status

        team.save()
        return JsonResponse({'success': True, 'message': 'Team updated successfully'})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error updating team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error updating team: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def add_team_members(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        member_ids = data.get('member_ids', [])

        # Validate inputs
        if not team_id:
            return JsonResponse({'success': False, 'message': 'Team ID is required'})

        if not member_ids or len(member_ids) == 0:
            return JsonResponse({'success': False, 'message': 'At least one member must be selected'})

        # Convert to integers
        try:
            team_id = int(team_id)
            member_ids = [int(mid) for mid in member_ids if mid]
        except (ValueError, TypeError) as e:
            return JsonResponse({'success': False, 'message': f'Invalid ID format: {str(e)}'})

        # Get team with permission check
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Add members
        added_count = 0
        skipped_count = 0
        errors = []

        for member_id in member_ids:
            try:
                # Check if employee exists
                employee = Employees.objects.filter(id=member_id).first()
                if not employee:
                    errors.append(f'Employee with ID {member_id} not found')
                    continue

                # Use get_or_create to handle existing members
                team_member, created = TeamMember.objects.get_or_create(
                    team=team,
                    employee_id=member_id,
                    defaults={'is_active': True}
                )

                # If member already exists but is inactive, reactivate them
                if not created:
                    if team_member.is_active:
                        skipped_count += 1
                        continue  # Already an active member
                    else:
                        team_member.is_active = True
                        team_member.save()
                        added_count += 1
                else:
                    added_count += 1
            except IntegrityError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Integrity error adding member {member_id}: {str(e)}')
                errors.append(f'Member {member_id} could not be added due to constraint violation')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error adding member {member_id}: {str(e)}')
                errors.append(f'Error adding member {member_id}: {str(e)}')

        # Build response message
        if errors:
            message = f'{added_count} member(s) added. {len(errors)} error(s) occurred.'
            if skipped_count > 0:
                message += f' {skipped_count} member(s) already in team.'
        else:
            if skipped_count > 0:
                message = f'{added_count} member(s) added. {skipped_count} member(s) already in team.'
            else:
                message = f'{added_count} member(s) added to team successfully'

        response_data = {
            'success': True if added_count > 0 or skipped_count > 0 else False,
            'message': message,
            'added_count': added_count,
            'skipped_count': skipped_count
        }

        if errors:
            response_data['errors'] = errors

        return JsonResponse(response_data)
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'}, status=404)
    except json.JSONDecodeError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'JSON decode error in add_team_members: {str(e)}')
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error adding members to team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error adding members to team: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_team(request, team_id):
    try:
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)
        name = team.name
        team.delete()
        return JsonResponse({'success': True, 'message': f'Team "{name}" deleted successfully'})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'}, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error deleting team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error deleting team: {str(e)}'}, status=500)

@login_required
@require_http_methods(["POST"])
def remove_team_member(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id'); member_id = data.get('member_id')

        base_qs = TeamMember.objects.all() if request.user.is_superuser else TeamMember.objects.filter(
            Q(team__leader=get_current_employee(request)) | Q(team__members__employee=get_current_employee(request), team__members__is_active=True)
        ).distinct()
        team_member = get_object_or_404(base_qs, team_id=team_id, employee_id=member_id)
        team_member.delete()
        return JsonResponse({'success': True, 'message': 'Member removed from team successfully'})
    except TeamMember.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team member not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error removing member from team: {str(e)}'})

@login_required
def available_employees(request):
    try:
        # Get team_id from query parameter (optional - to allow re-adding to current team)
        team_id = request.GET.get('team_id')

        # Get all employees who are active team members in OTHER teams
        if team_id:
            # Exclude members from other teams, but allow re-adding to current team
            team_members = TeamMember.objects.filter(
                is_active=True
            ).exclude(team_id=team_id).values_list('employee_id', flat=True)
        else:
            # Exclude all team members if no team_id provided
            team_members = TeamMember.objects.filter(is_active=True).values_list('employee_id', flat=True)

        base_emps = only_me_employee_qs(request).filter(status=1)
        available_employees = base_emps.exclude(id__in=team_members)

        employees_data = [{'id': e.id, 'name': f"{e.firstname} {e.lastname or ''}", 'role': e.job_title or 'Employee'} for e in available_employees]
        return JsonResponse({'success': True, 'employees': employees_data})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error retrieving available employees: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error retrieving available employees: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def add_project(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        name = data.get('name')
        description = data.get('description', '')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        status = data.get('status', 'active')
        progress = data.get('progress', 0)

        if not team_id or not name:
            return JsonResponse({'success': False, 'message': 'Team and project name are required'})

        try:
            team = Team.objects.get(id=int(team_id))
        except (Team.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid team'}, status=400)

        # Parse dates if provided
        from datetime import datetime
        start = None
        end = None
        try:
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        try:
            progress_val = int(progress)
        except (ValueError, TypeError):
            progress_val = 0

        progress_val = max(0, min(100, progress_val))

        project = Project.objects.create(
            team=team,
            name=name,
            description=description,
            start_date=start or timezone.now().date(),
            end_date=end or timezone.now().date(),
            status=status if status in dict(Project.STATUS_CHOICES).keys() else 'active',
            progress=progress_val,
        )

        return JsonResponse({'success': True, 'message': 'Project created successfully', 'project_id': project.id})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error creating project: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error creating project: {str(e)}'}, status=500)

@login_required
def team_members_attendance(request, team_id):
    """
    Get attendance data for all members of a specific team for today
    """
    try:
        from django.utils import timezone
        today = timezone.now().date()

        # Get team
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Get all active team members
        team_members = TeamMember.objects.filter(team=team, is_active=True).select_related('employee')

        # Get employee IDs
        employee_ids = [tm.employee_id for tm in team_members]

        # Get today's attendance for all team members
        attendance_records = Attendance.objects.filter(
            employee_id__in=employee_ids,
            date=today
        ).select_related('employee')

        # Create attendance map
        attendance_map = {}
        for att in attendance_records:
            attendance_map[att.employee_id] = {
                'status': att.status,
                'status_display': att.get_status_display(),
                'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else None,
                'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else None,
                'is_present': att.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'weekend']
            }

        # Build response with all team members and their attendance
        members_data = []
        for tm in team_members:
            emp = tm.employee
            att_data = attendance_map.get(emp.id, {
                'status': 'absent',
                'status_display': 'Absent',
                'check_in': None,
                'check_out': None,
                'is_present': False
            })

            members_data.append({
                'id': emp.id,
                'name': f"{emp.firstname} {emp.lastname or ''}",
                'attendance': att_data
            })

        return JsonResponse({
            'success': True,
            'team_id': team_id,
            'date': today.strftime('%Y-%m-%d'),
            'members': members_data
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error getting team members attendance: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error getting attendance: {str(e)}'})

@login_required
def employee_details(request, employee_id):
    try:
        employee = get_object_or_404(only_me_employee_qs(request), id=employee_id)
        employee_data = {
            'id': employee.id,
            'name': f"{employee.firstname} {employee.lastname or ''}",
            'email': employee.email or 'N/A',
            'phone': getattr(employee, 'phone', None) or 'N/A',
            'department': employee.department.name if employee.department else 'N/A',
            'position': employee.job_title or 'N/A',
            'join_date': employee.hire_date.strftime('%Y-%m-%d') if getattr(employee, 'hire_date', None) else 'N/A',
            # demo metrics
            'attendance_rate': 95, 'leaves_taken': 5, 'performance_rating': 4.2,
            'attendance_records': [
                {'date': '2025-10-01', 'status': 'Present', 'check_in': '09:00', 'check_out': '17:00'},
                {'date': '2025-10-02', 'status': 'Present', 'check_in': '08:45', 'check_out': '17:15'},
            ]
        }
        return JsonResponse({'success': True, 'member': employee_data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error getting employee details: {str(e)}'})


# ===========================
#   PAYROLL JSON APIs
# ===========================

@login_required
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


# ===========================
#   LOANS (Scoped)
# ===========================

@login_required
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

from .models import Report, ReportTemplate

# ===========================
#   REPORT DATA EXTRACTION FUNCTIONS
# ===========================

def get_user_role(request):
    """Get user role for access control"""
    if request.user.is_superuser:
        return 'admin'
    try:
        return request.user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return 'employee'

def can_access_report(request, report_type):
    """Check if user can access a specific report type"""
    role = get_user_role(request)

    # Access control matrix
    access_matrix = {
        'admin': ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
        'hr': ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
        'finance': ['payroll', 'loan'],
        'manager': ['employee', 'attendance', 'department', 'leave'],
        'employee': ['employee', 'attendance', 'leave', 'loan'],  # Only their own data
    }

    allowed_types = access_matrix.get(role, ['employee', 'attendance', 'leave'])
    return report_type in allowed_types

def extract_employee_report_data(request, start_date=None, end_date=None, filters=None):
    """Extract employee data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        employees = Employees.objects.all()
    else:
        # Employees can only see their own data
        employees = Employees.objects.filter(pk=current_employee.pk) if current_employee else Employees.objects.none()

    # Apply filters
    if filters:
        if filters.get('department'):
            employees = employees.filter(department_id=filters['department'])
        if filters.get('status'):
            employees = employees.filter(status=filters['status'])
        if filters.get('position'):
            employees = employees.filter(position_id=filters['position'])

    # Date filters (for employees hired in date range)
    if start_date:
        employees = employees.filter(date_hired__gte=start_date)
    if end_date:
        employees = employees.filter(date_hired__lte=end_date)

    data = []
    for emp in employees:
        data.append({
            'code': emp.code,
            'name': f"{emp.firstname} {emp.lastname or ''}".strip(),
            'email': emp.email or emp.official_email or 'N/A',
            'department': emp.department.name if emp.department else 'N/A',
            'position': emp.position.name if emp.position else 'N/A',
            'date_hired': emp.date_hired.strftime('%Y-%m-%d') if emp.date_hired else 'N/A',
            'status': 'Active' if emp.status == 1 else 'Inactive',
            'salary': emp.salary,
            'contact': emp.contact_1 or 'N/A',
        })

    return data

def extract_payroll_report_data(request, start_date, end_date, filters=None):
    """Extract payroll data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Access control
    if role not in ['admin', 'hr', 'finance']:
        return []

    # Get payroll records in date range
    payrolls = Payroll.objects.filter(
        pay_date__gte=start_date,
        pay_date__lte=end_date
    )

    if filters and filters.get('department'):
        payrolls = payrolls.filter(records__employee__department_id=filters['department']).distinct()

    data = []
    for payroll in payrolls:
        records = payroll.records.all()
        for record in records:
            data.append({
                'pay_period': payroll.pay_period,
                'pay_date': payroll.pay_date.strftime('%Y-%m-%d'),
                'employee_code': record.employee.code if record.employee else 'N/A',
                'employee_name': f"{record.employee.firstname} {record.employee.lastname or ''}".strip() if record.employee else 'N/A',
                'base_salary': float(record.base_salary) if record.base_salary else 0,
                'allowances': float(record.allowances) if record.allowances else 0,
                'deductions': float(record.deductions) if record.deductions else 0,
                'net_salary': float(record.net_salary) if record.net_salary else 0,
            })

    return data

def extract_attendance_report_data(request, start_date, end_date, filters=None):
    """Extract attendance data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        attendance = Attendance.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
    else:
        # Employees can only see their own attendance
        if current_employee:
            attendance = Attendance.objects.filter(
                employee=current_employee,
                date__gte=start_date,
                date__lte=end_date
            )
        else:
            attendance = Attendance.objects.none()

    # Apply filters
    if filters:
        if filters.get('department'):
            attendance = attendance.filter(employee__department_id=filters['department'])
        if filters.get('status'):
            attendance = attendance.filter(status=filters['status'])
        if filters.get('employee'):
            attendance = attendance.filter(employee_id=filters['employee'])
        # Attendance detail sub-type filters
        detail = filters.get('attendance_detail')
        if detail == 'late_only':
            # Late arrivals: late_in_display not empty OR status in late-related categories
            attendance = attendance.filter(
                Q(late_in_minutes__gt=0) | Q(status__in=['late', 'late-coming'])
            )
        elif detail == 'weekend_only':
            # Saturdays & Sundays: status weekend
            attendance = attendance.filter(status='weekend')
        elif detail == 'late_sitting_only':
            # Late sitting: late_sitting > 0
            attendance = attendance.filter(late_sitting__isnull=False).exclude(late_sitting=timedelta(0))

    # Filter out weekend records without attendance (employee didn't arrive on weekend)
    attendance = attendance.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    # Order by date and updated_at to get latest records first, then remove duplicates
    attendance = attendance.order_by('-date', '-updated_at', 'employee__firstname')

    # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
    seen = {}
    unique_attendance = []
    for att in attendance:
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

    data = []
    for att in unique_attendance:
        # Calculate late sitting display (hh mm)
        late_sitting_display = ''
        if att.late_sitting and att.late_sitting.total_seconds() > 0:
            total_minutes = int(att.late_sitting.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            late_sitting_display = f"{hours}h {minutes:02d}m"

        # Calculate early out display (hh mm)
        early_out_display = ''
        if att.early_out and att.early_out.total_seconds() > 0:
            total_minutes = int(att.early_out.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            early_out_display = f"{hours}h {minutes:02d}m"

        data.append({
            'date': att.date.strftime('%Y-%m-%d'),
            'employee_code': att.employee.code,
            'employee_name': f"{att.employee.firstname} {att.employee.lastname or ''}".strip(),
            'department': att.employee.department.name if att.employee.department else 'N/A',
            'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else 'N/A',
            'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else 'N/A',
            'status': att.get_status_display(),
            'work_duration': att.duration,
            'overtime': att.overtime_display,
            'late_in': att.late_in_display,
            'early_out': early_out_display if early_out_display else 'N/A',
            'late_sitting': late_sitting_display if late_sitting_display else 'N/A',
            'leave_type': att.get_leave_type_display() if att.leave_type else 'N/A',
            'notes': att.notes or 'N/A',
        })

    return data

def extract_department_report_data(request, start_date=None, end_date=None, filters=None):
    """Extract department statistics for report"""
    role = get_user_role(request)

    # Access control
    if role not in ['admin', 'hr', 'manager']:
        return []

    departments = Department.objects.filter(status='active')

    data = []
    for dept in departments:
        employees = dept.employees_set.filter(status=1)  # Active employees
        total_salary = employees.aggregate(total=Sum('salary'))['total'] or 0

        data.append({
            'department_name': dept.name,
            'employee_count': employees.count(),
            'total_salary': float(total_salary),
            'average_salary': float(total_salary / employees.count()) if employees.count() > 0 else 0,
            'description': dept.description,
        })

    return data

def extract_leave_report_data(request, start_date, end_date, filters=None):
    """Extract leave request data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        leaves = LeaveRequest.objects.filter(
            start_date__lte=end_date,
            end_date__gte=start_date
        )
    else:
        # Employees can only see their own leaves
        if current_employee:
            leaves = LeaveRequest.objects.filter(
                employee=current_employee,
                start_date__lte=end_date,
                end_date__gte=start_date
            )
        else:
            leaves = LeaveRequest.objects.none()

    # Apply filters
    if filters:
        if filters.get('status'):
            leaves = leaves.filter(status=filters['status'])
        if filters.get('leave_type'):
            leaves = leaves.filter(leave_type=filters['leave_type'])
        if filters.get('department'):
            leaves = leaves.filter(employee__department_id=filters['department'])

    data = []
    for leave in leaves:
        data.append({
            'employee_code': leave.employee.code,
            'employee_name': f"{leave.employee.firstname} {leave.employee.lastname or ''}".strip(),
            'leave_type': leave.get_leave_type_display(),
            'start_date': leave.start_date.strftime('%Y-%m-%d'),
            'end_date': leave.end_date.strftime('%Y-%m-%d'),
            'duration_days': leave.duration_days,
            'status': leave.get_status_display(),
            'applied_on': leave.applied_on.strftime('%Y-%m-%d %H:%M'),
            'approved_by': f"{leave.approved_by.firstname} {leave.approved_by.lastname or ''}".strip() if leave.approved_by else 'N/A',
        })

    return data

def extract_loan_report_data(request, start_date, end_date, filters=None):
    """Extract loan data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'finance']:
        loans = Loan.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    else:
        # Employees can only see their own loans
        if current_employee:
            loans = Loan.objects.filter(
                employee=current_employee,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
        else:
            loans = Loan.objects.none()

    # Apply filters
    if filters:
        if filters.get('status'):
            loans = loans.filter(status=filters['status'])
        if filters.get('department'):
            loans = loans.filter(employee__department_id=filters['department'])

    data = []
    for loan in loans:
        repayments = loan.repayments.all()
        total_paid = repayments.aggregate(total=Sum('amount'))['total'] or 0
        remaining = float(loan.total_amount) - float(total_paid)

        data.append({
            'loan_id': loan.id,
            'employee_code': loan.employee.code,
            'employee_name': f"{loan.employee.firstname} {loan.employee.lastname or ''}".strip(),
            'application_date': loan.created_at.strftime('%Y-%m-%d') if loan.created_at else 'N/A',
            'loan_amount': float(loan.loan_amount),
            'total_amount': float(loan.total_amount),
            'interest_rate': float(loan.interest_rate),
            'purpose': loan.purpose or 'N/A',
            'status': loan.get_status_display(),
            'total_paid': float(total_paid),
            'remaining': remaining,
            'installments': loan.number_of_installments,
            'monthly_payment': float(loan.monthly_payment) if loan.monthly_payment else 0,
        })

    return data

@login_required
def reports_dashboard(request):
    """Main reports dashboard view with search and filter"""
    user_role = get_user_role(request)

    # Base queryset - employees can only see their own reports
    if user_role == 'employee':
        report_qs = Report.objects.filter(generated_by=request.user)
    else:
        report_qs = Report.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        report_qs = report_qs.filter(
            Q(report_name__icontains=search_query) |
            Q(report_type__icontains=search_query)
        )

    # Filter by report type
    report_type_filter = request.GET.get('report_type', '')
    if report_type_filter:
        report_qs = report_qs.filter(report_type=report_type_filter)

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        report_qs = report_qs.filter(status=status_filter)

    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            report_qs = report_qs.filter(generated_on__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            report_qs = report_qs.filter(generated_on__date__lte=date_to_obj)
        except ValueError:
            pass

    # Calculate statistics
    total_reports = report_qs.count()
    employee_reports = report_qs.filter(report_type='employee').count()
    payroll_reports = report_qs.filter(report_type='payroll').count()
    attendance_reports = report_qs.filter(report_type='attendance').count()
    leave_reports = report_qs.filter(report_type='leave').count()
    loan_reports = report_qs.filter(report_type='loan').count()
    department_reports = report_qs.filter(report_type='department').count()

    # Get available report types based on user role
    available_report_types = []
    for report_type, display_name in Report.REPORT_TYPES:
        if can_access_report(request, report_type):
            available_report_types.append((report_type, display_name))

    stats = {
        'total_reports': total_reports,
        'employee_reports': employee_reports,
        'payroll_reports': payroll_reports,
        'attendance_reports': attendance_reports,
        'leave_reports': leave_reports,
        'loan_reports': loan_reports,
        'department_reports': department_reports,
    }

    # Get templates that user can access
    templates = ReportTemplate.objects.filter(
        is_active=True,
        report_type__in=[rt[0] for rt in available_report_types]
    )

    # Paginate recent reports
    paginator = Paginator(report_qs.order_by('-generated_on'), 20)
    page = request.GET.get('page', 1)
    try:
        recent_reports = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        recent_reports = paginator.page(1)

    # Get departments for filters
    departments = Department.objects.filter(status='active') if user_role in ['admin', 'hr', 'manager'] else []

    # Get employees for filters (for attendance reports)
    employees = []
    if user_role in ['admin', 'hr', 'manager']:
        from .models import Employees
        employees = Employees.objects.filter(status=1).exclude(
            Q(code__icontains='test') |
            Q(code__icontains='dummy') |
            Q(code__icontains='sample')
        ).order_by('firstname', 'lastname')

    context = {
        'stats': stats,
        'templates': templates,
        'recent_reports': recent_reports,
        'user_role': user_role,
        'is_admin': user_role in ['admin', 'hr'],
        'available_report_types': available_report_types,
        'report_types': Report.REPORT_TYPES,
        'status_choices': Report.STATUS_CHOICES,
        'departments': departments,
        'employees': employees,
        'search_query': search_query,
        'report_type_filter': report_type_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'pages/reports.html', context)

@login_required
@require_http_methods(["POST"])
def generate_report(request):
    """Generate a new report with real data"""
    try:
        report_type = request.POST.get('report_type')

        # Check access control
        if not can_access_report(request, report_type):
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to generate this report type.'
            })

        date_range = request.POST.get('date_range')
        format_type = request.POST.get('format')
        include_charts = request.POST.get('include_charts') == 'on'
        include_summary = request.POST.get('include_summary') == 'on'
        include_raw_data = request.POST.get('include_raw_data') == 'on'

        # Get filters
        filters = {}
        if request.POST.get('department'):
            filters['department'] = request.POST.get('department')
        if request.POST.get('status'):
            filters['status'] = request.POST.get('status')
        if request.POST.get('employee'):
            filters['employee'] = request.POST.get('employee')
        # Attendance-specific sub-filter (late, weekend, late sitting)
        if request.POST.get('attendance_detail'):
            filters['attendance_detail'] = request.POST.get('attendance_detail')

        # Calculate date range
        end_date = timezone.now().date()
        if date_range == 'last_week':
            start_date = end_date - timedelta(days=7)
        elif date_range == 'last_month':
            start_date = end_date - timedelta(days=30)
        elif date_range == 'last_quarter':
            start_date = end_date - timedelta(days=90)
        elif date_range == 'last_year':
            start_date = end_date - timedelta(days=365)
        elif date_range == 'custom':
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else end_date - timedelta(days=30)
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else timezone.now().date()
        else:
            start_date = end_date - timedelta(days=30)

        # For reports that don't need date range, set to None
        if report_type in ['employee', 'department']:
            start_date = None
            end_date = None

        # Check for duplicate report creation (same user, same type, within last 5 seconds)
        recent_duplicate = Report.objects.filter(
            generated_by=request.user,
            report_type=report_type,
            generated_on__gte=timezone.now() - timedelta(seconds=5)
        ).first()

        if recent_duplicate:
            return JsonResponse({
                'success': False,
                'message': 'A similar report was just generated. Please wait a moment before generating another.'
            })

        # Create report name
        employee_name = None
        if filters.get('employee'):
            try:
                from .models import Employees
                employee = Employees.objects.get(pk=filters['employee'])
                employee_name = f"{employee.firstname} {employee.lastname or ''}".strip()
            except Employees.DoesNotExist:
                pass

        if employee_name:
            if start_date and end_date:
                report_name = f"{report_type.title()} Report - {employee_name} - {start_date} to {end_date}"
            else:
                report_name = f"{report_type.title()} Report - {employee_name} - {timezone.now().strftime('%Y-%m-%d')}"
        elif start_date and end_date:
            report_name = f"{report_type.title()} Report - {start_date} to {end_date}"
        else:
            report_name = f"{report_type.title()} Report - {timezone.now().strftime('%Y-%m-%d')}"

        # Create report instance
        report = Report.objects.create(
            report_type=report_type,
            report_name=report_name,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            format=format_type,
            include_charts=include_charts,
            include_summary=include_summary,
            include_raw_data=include_raw_data,
            generated_by=request.user,
            status='processing'
        )

        try:
            # Extract real data based on report type
            if report_type == 'employee':
                data = extract_employee_report_data(request, start_date, end_date, filters)
            elif report_type == 'payroll':
                data = extract_payroll_report_data(request, start_date, end_date, filters)
            elif report_type == 'attendance':
                data = extract_attendance_report_data(request, start_date, end_date, filters)
            elif report_type == 'department':
                data = extract_department_report_data(request, start_date, end_date, filters)
            elif report_type == 'leave':
                data = extract_leave_report_data(request, start_date, end_date, filters)
            elif report_type == 'loan':
                data = extract_loan_report_data(request, start_date, end_date, filters)
            else:
                data = []

            # Store data in report
            report.report_data = {
                'data': data,
                'total_records': len(data),
                'filters': filters,
            }
            report.save()

            # Generate report based on format
            if format_type == 'pdf':
                filename = f"report_{report.id}.pdf"
                file_content = generate_pdf_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))
            elif format_type == 'excel':
                filename = f"report_{report.id}.xlsx"
                file_content = generate_excel_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))
            elif format_type == 'csv':
                filename = f"report_{report.id}.csv"
                file_content = generate_csv_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))

            # Mark as completed
            report.mark_completed()

            return JsonResponse({
                'success': True,
                'message': 'Report generated successfully',
                'report_id': str(report.id)
            })

        except Exception as e:
            report.mark_failed(str(e))
            return JsonResponse({
                'success': False,
                'message': f'Error generating report: {str(e)}'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

def generate_pdf_report(report, data=None):
    """Generate PDF report with real data"""
    import importlib

    try:
        # Dynamic import avoids static analysis errors when reportlab is not installed
        canvas_mod = importlib.import_module('reportlab.pdfgen.canvas')
        pagesizes = importlib.import_module('reportlab.lib.pagesizes')
        Canvas = getattr(canvas_mod, 'Canvas')
        letter = getattr(pagesizes, 'letter', (612.0, 792.0))

        buffer = BytesIO()
        p = Canvas(buffer, pagesize=letter)
        y_position = 750

        # Add header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, y_position, report.report_name)
        y_position -= 30

        p.setFont("Helvetica", 12)
        p.drawString(100, y_position, f"Report Type: {report.get_report_type_display()}")
        y_position -= 20

        if report.start_date and report.end_date:
            p.drawString(100, y_position, f"Date Range: {report.start_date} to {report.end_date}")
            y_position -= 20

        p.drawString(100, y_position, f"Generated On: {report.generated_on.strftime('%Y-%m-%d %H:%M')}")
        y_position -= 20

        generated_by_str = (report.generated_by.get_full_name() or report.generated_by.username) if report.generated_by else 'N/A'
        p.drawString(100, y_position, f"Generated By: {generated_by_str}")
        y_position -= 30

        # Add data
        if data and len(data) > 0:
            p.setFont("Helvetica-Bold", 12)
            p.drawString(100, y_position, f"Total Records: {len(data)}")
            y_position -= 30

            # Get column headers from first data item
            if isinstance(data[0], dict):
                headers = list(data[0].keys())
                p.setFont("Helvetica-Bold", 10)
                x = 50
                for header in headers[:6]:  # Limit columns for PDF
                    p.drawString(x, y_position, header.replace('_', ' ').title())
                    x += 100
                y_position -= 20

                # Add data rows
                p.setFont("Helvetica", 9)
                for row in data[:50]:  # Limit rows for PDF
                    if y_position < 50:
                        p.showPage()
                        y_position = 750
                    x = 50
                    for header in headers[:6]:
                        value = str(row.get(header, ''))[:15]  # Truncate long values
                        p.drawString(x, y_position, value)
                        x += 100
                    y_position -= 15
        else:
            p.drawString(100, y_position, "No data available for this report.")

        p.showPage()
        p.save()

        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    except Exception:
        # Fallback: return a plain text bytes payload
        report_data = data if data else []
        fallback_text = (
            f"{report.report_name}\n\n"
            f"Report Type: {report.get_report_type_display()}\n"
            f"Date Range: {report.start_date} to {report.end_date}\n"
            f"Generated On: {report.generated_on.strftime('%Y-%m-%d %H:%M')}\n"
            f"Generated By: {(report.generated_by.get_full_name() or report.generated_by.username) if report.generated_by else 'N/A'}\n"
            f"Total Records: {len(report_data)}\n\n"
        )

        if report_data and len(report_data) > 0:
            if isinstance(report_data[0], dict):
                headers = list(report_data[0].keys())
                fallback_text += "\t".join(headers) + "\n"
                for row in report_data:
                    fallback_text += "\t".join([str(row.get(h, '')) for h in headers]) + "\n"

        fallback_text += "\nNOTE: reportlab is not installed. Install 'reportlab' for proper PDF generation."
        return fallback_text.encode('utf-8')

def generate_excel_report(report, data=None):
    """Generate Excel report with real data"""
    buffer = BytesIO()

    if not data or len(data) == 0:
        # Create empty DataFrame with message
        df = pd.DataFrame({'Message': ['No data available for this report.']})
    else:
        # Convert data to DataFrame
        if isinstance(data[0], dict):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame(data)

    # Use openpyxl as engine for newer pandas versions
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Report Data', index=False)

        # Add summary sheet if include_summary is True
        if report.include_summary and len(data) > 0:
            summary_data = {
                'Metric': ['Total Records', 'Report Type', 'Date Range', 'Generated On'],
                'Value': [
                    len(data),
                    report.get_report_type_display(),
                    f"{report.start_date} to {report.end_date}" if report.start_date and report.end_date else 'N/A',
                    report.generated_on.strftime('%Y-%m-%d %H:%M')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

    excel_data = buffer.getvalue()
    buffer.close()
    return excel_data

def generate_csv_report(report, data=None):
    """Generate CSV report with real data"""
    buffer = BytesIO()
    writer = csv.writer(buffer)

    if not data or len(data) == 0:
        writer.writerow(['Message'])
        writer.writerow(['No data available for this report.'])
    else:
        # Write headers
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            writer.writerow(headers)

            # Write data rows
            for row in data:
                writer.writerow([row.get(header, '') for header in headers])
        else:
            # If data is not dict format, write as-is
            for row in data:
                writer.writerow(row if isinstance(row, list) else [row])

    csv_data = buffer.getvalue()
    buffer.close()
    return csv_data

@login_required
def view_report(request, report_id):
    """View report details"""
    report = get_object_or_404(Report, id=report_id)

    # Check access - employees can only view their own reports
    user_role = get_user_role(request)
    if user_role == 'employee' and report.generated_by != request.user:
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('reports')

    # Generate summary data from report_data if available
    summary = {}
    if report.report_data:
        data = report.report_data.get('data', [])
        total_records = len(data)
        summary['Total Records'] = total_records

        # Calculate statistics based on report type
        if report.report_type == 'payroll' and data:
            total_salary = sum(float(item.get('net_salary', 0)) for item in data if isinstance(item, dict))
            avg_salary = total_salary / total_records if total_records > 0 else 0
            summary['Total Payroll'] = f"${total_salary:,.2f}"
            summary['Average Salary'] = f"${avg_salary:,.2f}"
        elif report.report_type == 'attendance' and data:
            present_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Present')
            summary['Present Days'] = present_count
            summary['Total Records'] = total_records
        elif report.report_type == 'employee' and data:
            active_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Active')
            summary['Active Employees'] = active_count
            summary['Total Employees'] = total_records
        elif report.report_type == 'department' and data:
            total_depts = len(data)
            total_employees = sum(int(item.get('employee_count', 0)) for item in data if isinstance(item, dict))
            summary['Total Departments'] = total_depts
            summary['Total Employees'] = total_employees
        elif report.report_type == 'leave' and data:
            approved_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Approved')
            summary['Approved Leaves'] = approved_count
            summary['Total Requests'] = total_records
        elif report.report_type == 'loan' and data:
            total_loans = len(data)
            total_amount = sum(float(item.get('amount', 0)) for item in data if isinstance(item, dict))
            summary['Total Loans'] = total_loans
            summary['Total Amount'] = f"${total_amount:,.2f}"
    else:
        summary['Total Records'] = 0
        summary['Status'] = 'No data available'

    # Format report data with nice column headers
    report_data = report.report_data.get('data', []) if report.report_data else []
    formatted_data = []
    column_headers = []

    if report_data and len(report_data) > 0 and isinstance(report_data[0], dict):
        # Get headers and format them
        column_headers = [key.replace('_', ' ').title() for key in report_data[0].keys()]

        # Create formatted data with original keys but also store formatted headers
        formatted_data = report_data
    else:
        formatted_data = report_data

    context = {
        'report': report,
        'summary': summary,
        'report_data': formatted_data,
        'column_headers': column_headers
    }

    return render(request, 'pages/view_report.html', context)

@login_required
def download_report(request, report_id):
    """Download report file"""
    report = get_object_or_404(Report, id=report_id)

    if not report.file_path or not report.file_path.name:
        return JsonResponse({'success': False, 'message': 'Report file not found'})

    try:
        response = HttpResponse(report.file_path.read(), content_type='application/octet-stream')
        filename = f"{report.report_name}.{report.format}"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error downloading file: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def delete_report(request, report_id):
    """Delete a report"""
    try:
        # Use try-except instead of get_object_or_404 to return JSON instead of HTML 404
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Report not found.'
            }, status=404)

        # Access control - employees can only delete their own reports
        user_role = get_user_role(request)
        if user_role == 'employee' and report.generated_by != request.user:
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to delete this report.'
            }, status=403)

        # Delete file if exists
        if report.file_path:
            try:
                if default_storage.exists(report.file_path.name):
                    default_storage.delete(report.file_path.name)
            except Exception as file_error:
                # Log but don't fail if file deletion fails
                print(f"Warning: Could not delete report file: {file_error}")

        report.delete()

        return JsonResponse({'success': True, 'message': 'Report deleted successfully'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting report: {str(e)}'
        }, status=500)

@login_required
def generate_from_template(request, template_id):
    """Generate report from template"""
    template = get_object_or_404(ReportTemplate, id=template_id)

    # Increment template usage
    template.increment_usage()

    # Create a new report based on template
    report = Report.objects.create(
        report_type=template.report_type,
        report_name=f"{template.name} - {timezone.now().strftime('%Y-%m-%d')}",
        date_range=template.default_date_range,
        format=template.default_format,
        generated_by=request.user,
        status='processing'
    )

    # Calculate dates based on default date range
    end_date = timezone.now().date()
    if template.default_date_range == 'last_week':
        start_date = end_date - timedelta(days=7)
    elif template.default_date_range == 'last_month':
        start_date = end_date - timedelta(days=30)
    elif template.default_date_range == 'last_quarter':
        start_date = end_date - timedelta(days=90)
    elif template.default_date_range == 'last_year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)

    report.start_date = start_date
    report.end_date = end_date
    report.save()

    # Redirect to view the new report
    return redirect('view_report', report_id=report.id)

# API endpoints for AJAX calls
@login_required
def get_report_status(request, report_id):
    """Get report generation status"""
    report = get_object_or_404(Report, id=report_id)
    return JsonResponse({
        'status': report.status,
        'progress': 100 if report.status == 'completed' else 50,
        'message': 'Report completed' if report.status == 'completed' else 'Processing...'
    })

@login_required
def get_recent_reports(request):
    """Get recent reports for AJAX updates"""
    recent_reports = Report.objects.all().order_by('-generated_on')[:10]

    reports_data = []
    for report in recent_reports:
        reports_data.append({
            'id': str(report.id),
            'report_name': report.report_name,
            'report_type': report.get_report_type_display(),
            'generated_on': report.generated_on.strftime('%M %d, %Y %H:%M'),
            'file_size': report.get_file_size_display(),
            'status': report.status,
            'status_display': report.get_status_display()
        })

    return JsonResponse({'reports': reports_data})

# views.py (add at the end)
@login_required
def api_notifications(request):
    """API endpoint to get notifications for the current user"""
    context = get_notifications(request)
    notifications = context.get('notifications', [])
    unread_count = context.get('notification_count', 0)

    return JsonResponse({
        'notifications': notifications,
        'notification_count': unread_count
    })

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read in the database"""
    try:
        # Mark all unread notifications for this user as read
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)

        return JsonResponse({
            'success': True,
            'message': f'{updated} notifications marked as read'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    try:
        notification = get_object_or_404(
            Notification.objects.filter(recipient=request.user),
            id=notification_id
        )
        notification.is_read = True
        notification.save()

        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)








# ===========================
#   AI EMPLOYEE ASSISTANT VIEWS
# ===========================

@login_required
def ai_assistant(request):
    """Main AI assistant chat interface"""
    from django.db import ProgrammingError

    user = request.user
    try:
        profile = user.profile
        user_role = profile.role
    except UserProfile.DoesNotExist:
        user_role = 'employee'

    # Get recent chat history (last 20 messages)
    # Handle case where AIChatMessage table doesn't exist
    try:
        recent_messages = AIChatMessage.objects.filter(user=user).order_by('-created_at')[:20]
        recent_messages = list(reversed(recent_messages))
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (migration not run)
        recent_messages = []

    # Get available policies for reference
    try:
        policies = Policy.objects.filter(is_active=True).order_by('-effective_date')
    except (ProgrammingError, Exception):
        # Policy table might not exist either
        policies = []

    context = {
        'user_role': user_role,
        'recent_messages': recent_messages,
        'policies': policies,
    }
    return render(request, 'pages/ai_assistant.html', context)


@login_required
@require_POST
def ai_chat_api(request):
    """API endpoint for AI chat responses"""
    import os
    from django.conf import settings

    # Try to import OpenAI (optional dependency)
    try:
        import openai  # type: ignore
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False

    user = request.user
    try:
        profile = user.profile
        user_role = profile.role
    except UserProfile.DoesNotExist:
        user_role = 'employee'

    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Message is required'}, status=400)

    # Get user's employee record if exists
    employee = None
    try:
        employee = user.employee
    except:
        pass

    # Build system prompt based on user role and employee context
    system_prompt = build_ai_system_prompt(user_role, employee)

    # Get compact, structured policies context to keep prompts efficient
    policies_context = get_policies_context(max_items=10)

    # Get recent conversation history
    # Handle case where AIChatMessage table doesn't exist
    from django.db import ProgrammingError
    try:
        recent_history = AIChatMessage.objects.filter(user=user).order_by('-created_at')[:10]
        conversation_history = []
        for msg in reversed(recent_history):
            conversation_history.append({
                'role': 'user' if msg.message_type == 'user' else 'assistant',
                'content': msg.message if msg.message_type == 'user' else msg.response
            })
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (migration not run)
        conversation_history = []

    # Add current message
    conversation_history.append({'role': 'user', 'content': message})

    try:
        # Try to use OpenAI API if configured
        api_key = os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)

        if api_key and OPENAI_AVAILABLE:
            try:
                client = openai.OpenAI(api_key=api_key)

                messages = [
                    {
                        'role': 'system',
                        'content': system_prompt + '\n\n' + policies_context
                    }
                ] + conversation_history

                response = client.chat.completions.create(
                    # Prefer a stronger reasoning model if configured, with sensible default
                    model=os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
                    messages=messages,
                    # Slightly lower temperature for more consistent, policy-aligned answers
                    temperature=0.5,
                    # Keep responses focused and efficient
                    max_tokens=700
                )

                ai_response = response.choices[0].message.content
            except Exception as openai_error:
                logger.warning(f"OpenAI API error: {openai_error}, falling back to rule-based response")
                ai_response = generate_rule_based_response(message, user_role, policies_context)
        else:
            # Fallback to rule-based responses if OpenAI is not configured
            ai_response = generate_rule_based_response(message, user_role, policies_context)

        # Save conversation (if table exists)
        try:
            AIChatMessage.objects.create(
                user=user,
                message=message,
                response=ai_response,
                message_type='user',
                context={'role': user_role}
            )
        except (ProgrammingError, Exception):
            # Table doesn't exist yet (migration not run) - skip saving
            pass

        return JsonResponse({
            'response': ai_response,
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error in AI chat API: {e}")
        # Fallback to rule-based response
        ai_response = generate_rule_based_response(message, user_role, policies_context)

        # Save conversation (if table exists)
        try:
            AIChatMessage.objects.create(
                user=user,
                message=message,
                response=ai_response,
                message_type='user',
                context={'role': user_role, 'error': str(e)}
            )
        except (ProgrammingError, Exception):
            # Table doesn't exist yet (migration not run) - skip saving
            pass

        return JsonResponse({
            'response': ai_response,
            'status': 'success'
        })


def build_ai_system_prompt(user_role, employee=None):
    """
    Build a compact but expressive system prompt based on user role and employee context.

    The goal is:
    - Strong reasoning and problem-solving
    - Clear, efficient answers (no unnecessary fluff)
    - Role-aware behavior (admin/hr vs employee)
    """
    # Basic employee context to help the model personalize and reason better
    employee_context = ""
    if employee is not None:
        emp_name = f"{employee.firstname} {employee.lastname or ''}".strip()
        emp_dept = getattr(getattr(employee, "department", None), "name", None)
        emp_pos = getattr(getattr(employee, "position", None), "name", None)
        context_bits = [f"Name: {emp_name or 'N/A'}", f"Code: {employee.code or employee.pk}"]
        if emp_dept:
            context_bits.append(f"Department: {emp_dept}")
        if emp_pos:
            context_bits.append(f"Position: {emp_pos}")
        employee_context = "Current logged-in employee context: " + ", ".join(context_bits) + "."

    base_prompt = (
        "You are an advanced AI Employee Support Assistant integrated into an Employee Information System.\n"
        "You must: reason carefully about company policies and HR processes, ask clarifying questions when the request\n"
        "is ambiguous, and give step-by-step guidance in a concise, business-appropriate way.\n\n"
        f"{employee_context}\n\n"
        "General behavior rules:\n"
        "- Prefer short, clear paragraphs and bullet points over long essays.\n"
        "- When rules or policies might conflict, explain the trade-offs and suggest what the employee should verify with HR.\n"
        "- When you are unsure or information is missing, explicitly say so and propose what the user should check next.\n"
        "- Do NOT invent company-specific data that is not in the policies context; instead, state assumptions clearly.\n"
    )

    if user_role in ['admin', 'hr']:
        prompt = base_prompt + """
Role: Admin / HR / Super User

You can:
- Explain and reference existing company policies.
- Help plan how to update or add policies, but you do NOT actually perform database changes.
- Suggest what information to collect for new policies (title, category, effective date, summary, key rules).
- Help structure announcements and internal communication to employees about policies, leave, loans, and benefits.

When an admin/HR user is drafting or changing a policy:
- Ask follow-up questions to clarify missing details.
- Propose a clean, structured summary and 3–7 bullet key points.
- Highlight any edge cases employees commonly misunderstand.

When responding:
- Be pragmatic and action-oriented.
- If the request sounds like it needs legal/HR approval, clearly say that final decision belongs to HR/management.
"""
    else:
        prompt = base_prompt + """
Role: Employee Assistant (regular employee user)

You can:
- Answer questions about company policies using the provided policy context.
- Explain leave types, basic loan concepts, and benefits at a high level.
- Guide employees on how to submit complaints and who usually handles them.
- Help employees reason about what to do in tricky situations (e.g., conflicts, attendance or leave issues) while
  reminding them that final decisions belong to HR/management.

You CANNOT:
- Add or modify policies.
- Approve or deny loans, benefits, or complaints.
- Access or reveal confidential employee data.

Response style:
- Professional, respectful, and supportive.
- Focus on the concrete next steps the employee should take in the system or with HR/management.
"""

    # Encourage internal reasoning without exposing chain-of-thought
    prompt += (
        "\nInternal reasoning guidelines (do NOT show this directly to the user):\n"
        "- Break down complex questions into smaller parts, reason step-by-step internally, and then give a polished answer.\n"
        "- If a question mixes multiple topics (e.g., leave + loans), address them in a structured way.\n"
        "- Prefer deterministic answers aligned with policies over creative writing.\n"
    )

    return prompt


def get_policies_context(max_items=10):
    """
    Get a compact, structured policies context for the AI.

    To keep prompts efficient, we only include up to `max_items` of the most recent active policies,
    with short summaries that are easy for the model to use for reasoning.
    """
    policies = Policy.objects.filter(is_active=True).order_by('-effective_date')[:max_items]
    if not policies:
        return "Policies context: No active policies are currently defined in the system."

    context_lines = ["Policies context (for AI reasoning, not shown directly to the user):"]
    for idx, policy in enumerate(policies, start=1):
        category = getattr(policy, "get_category_display_name", None)
        category_name = category() if callable(category) else getattr(policy, "category", "Unspecified")
        summary = (policy.summary or "").strip()
        short_summary = summary[:220] + ("..." if len(summary) > 220 else "")
        context_lines.append(
            f"{idx}. {policy.title} "
            f"(Category: {category_name}, Effective: {policy.effective_date}): {short_summary}"
        )

    return "\n".join(context_lines)


def generate_rule_based_response(message, user_role, policies_context):
    """Generate rule-based response when AI API is not available"""
    message_lower = message.lower()

    # Policy-related queries
    if any(word in message_lower for word in ['policy', 'policies', 'rule', 'rules', 'regulation']):
        policies = Policy.objects.filter(is_active=True)
        if policies.exists():
            response = "Here are the available company policies:\n\n"
            for policy in policies[:5]:
                response += f"• {policy.title} ({policy.get_category_display_name()})\n"
                response += f"  Effective: {policy.effective_date}\n"
                response += f"  Summary: {policy.summary[:150]}...\n\n"
            response += "Would you like more details about any specific policy?"
        else:
            response = "No policies are currently available. Please contact HR for policy information."

    # Loan-related queries
    elif any(word in message_lower for word in ['loan', 'borrow', 'lending']):
        response = """Loan Information:
- Loan eligibility: Up to 1.5x your monthly salary
- Required documents: Application form, salary slip
- Repayment: Monthly installments as per agreement
- Approval: Handled by HR/Finance department

For specific loan applications, please contact HR or Finance department."""

    # Leave-related queries
    elif any(word in message_lower for word in ['leave', 'vacation', 'holiday', 'time off']):
        response = """Leave Policy Information:
- Leave types: Sick, Casual, Annual, Maternity, Paternity, Emergency, Unpaid
- Application: Submit leave request through the system
- Approval: Requires manager/HR approval
- For detailed leave policy, please check the Leave Policy document or contact HR."""

    # Complaint-related queries
    elif any(word in message_lower for word in ['complaint', 'grievance', 'issue', 'problem']):
        response = """I can help you submit a complaint. Please provide:
1. Complaint title
2. Description of the issue
3. Related department (if applicable)

Would you like to submit a complaint now?"""

    # Benefits-related queries
    elif any(word in message_lower for word in ['benefit', 'benefits', 'perk', 'perks']):
        response = """Benefits Information:
- Benefits are managed by HR department
- Common benefits may include: Health insurance, Retirement plans, Professional development
- For specific benefits information, please contact HR or check the Benefits Policy document."""

    # Default response
    else:
        response = """I'm here to help you with:
- Company policies and rules
- Leave information
- Loan information
- Benefits information
- Submitting complaints

How can I assist you today?"""

    return response


@login_required
@hr_or_admin_required
def policy_management(request):
    """Policy management page (Admin/HR only)"""
    from django.db import ProgrammingError

    # Get policies with error handling for missing table
    try:
        policies = Policy.objects.all().order_by('-created_at')
    except (ProgrammingError, Exception):
        # Policy table doesn't exist yet (migration not run)
        policies = Policy.objects.none()
        messages.warning(request, 'Policy table not found. Please run migrations: python manage.py migrate')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            try:
                title = request.POST.get('title')
                category = request.POST.get('category')
                effective_date = request.POST.get('effective_date')
                description = request.POST.get('description', '')
                summary = request.POST.get('summary', '')
                version = request.POST.get('version', '1.0')
                version_notes = request.POST.get('version_notes', '')

                policy = Policy.objects.create(
                    title=title,
                    category=category,
                    effective_date=effective_date,
                    description=description,
                    summary=summary,
                    version=version,
                    version_notes=version_notes,
                    created_by=request.user
                )
            except (ProgrammingError, Exception) as e:
                messages.error(request, f'Error creating policy: Policy table not found. Please run migrations: python manage.py migrate')
                return redirect('policy_management')

            # Handle document upload
            if 'document' in request.FILES:
                policy.document = request.FILES['document']
                policy.save()

            # Extract key points if summary provided
            if summary:
                key_points = [point.strip() for point in summary.split('.') if point.strip()][:10]
                policy.key_points = key_points
                policy.save()

            messages.success(request, f'Policy "{title}" has been saved successfully and is now available to employees.')
            return redirect('policy_management')

        elif action == 'update':
            try:
                policy_id = request.POST.get('policy_id')
                policy = get_object_or_404(Policy, id=policy_id)
            except (ProgrammingError, Exception) as e:
                messages.error(request, f'Error updating policy: Policy table not found. Please run migrations: python manage.py migrate')
                return redirect('policy_management')

            policy.title = request.POST.get('title', policy.title)
            policy.category = request.POST.get('category', policy.category)
            policy.effective_date = request.POST.get('effective_date', policy.effective_date)
            policy.description = request.POST.get('description', policy.description)
            policy.summary = request.POST.get('summary', policy.summary)
            policy.version = request.POST.get('version', policy.version)
            policy.version_notes = request.POST.get('version_notes', policy.version_notes)
            policy.updated_by = request.user

            if 'document' in request.FILES:
                policy.document = request.FILES['document']

            policy.save()
            messages.success(request, f'Policy "{policy.title}" has been updated successfully.')
            return redirect('policy_management')

        elif action == 'delete':
            try:
                policy_id = request.POST.get('policy_id')
                policy = get_object_or_404(Policy, id=policy_id)
                policy.delete()
                messages.success(request, 'Policy deleted successfully.')
            except (ProgrammingError, Exception) as e:
                messages.error(request, f'Error deleting policy: Policy table not found. Please run migrations: python manage.py migrate')
            return redirect('policy_management')

    # Get categories with error handling
    try:
        categories = Policy.CATEGORY_CHOICES
    except (AttributeError, Exception):
        categories = []

    context = {
        'policies': policies,
        'categories': categories,
    }
    return render(request, 'pages/policy_management.html', context)


@login_required
@require_POST
def submit_complaint(request):
    """Submit employee complaint"""
    # Use get_current_employee to properly get the employee record
    employee = get_current_employee(request)
    if not employee:
        return JsonResponse({'error': 'Employee record not found. Please contact administrator.'}, status=400)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    department_id = request.POST.get('department_id', '')
    related_department = request.POST.get('related_department', '').strip()

    if not title or not description:
        return JsonResponse({'error': 'Title and description are required'}, status=400)

    department = None
    if department_id:
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            pass

    # Handle case where Complaint table doesn't exist
    from django.db import ProgrammingError
    try:
        complaint = Complaint.objects.create(
            employee=employee,
            title=title,
            description=description,
            department=department,
            related_department=related_department if not department else None,
            status='submitted'
        )

        messages.success(request, 'Your complaint has been submitted successfully. HR will review it shortly.')
        return JsonResponse({
            'status': 'success',
            'message': 'Complaint submitted successfully',
            'complaint_id': complaint.id
        })
    except (ProgrammingError, Exception) as e:
        return JsonResponse({
            'error': 'Complaint table not found. Please run migrations: python manage.py migrate'
        }, status=500)


@login_required
def view_complaints(request):
    """View complaints (employees see their own, admin/hr see all)"""
    user = request.user

    # Check user role - include superuser
    is_admin_user = user.is_superuser
    try:
        profile = user.profile
        user_role = profile.role
        is_admin_user = is_admin_user or user_role in ['admin', 'hr', 'finance']
    except UserProfile.DoesNotExist:
        # If no profile exists, check if superuser - if so, treat as admin
        if user.is_superuser:
            user_role = 'admin'
            is_admin_user = True
        else:
            user_role = 'employee'
            is_admin_user = False

    # Admin/HR/Superuser see all complaints
    # Handle case where Complaint table doesn't exist
    from django.db import ProgrammingError
    try:
        if is_admin_user:
            complaints = Complaint.objects.select_related('employee', 'department', 'responded_by').all().order_by('-created_at')
        else:
            # Employees see only their own complaints
            employee = get_current_employee(request)
            if employee:
                complaints = Complaint.objects.select_related('employee', 'department', 'responded_by').filter(employee=employee).order_by('-created_at')
            else:
                complaints = Complaint.objects.none()
    except (ProgrammingError, Exception):
        # Complaint table doesn't exist yet (migration not run)
        complaints = Complaint.objects.none()
        messages.warning(request, 'Complaint table not found. Please run migrations: python manage.py migrate')

    context = {
        'complaints': complaints,
        'user_role': user_role,
        'is_admin': is_admin_user,
    }
    return render(request, 'pages/complaints.html', context)


@login_required
@hr_or_admin_required
@require_POST
def respond_to_complaint(request, complaint_id):
    """HR/Admin response to complaint"""
    from django.db import ProgrammingError

    # Handle case where Complaint table doesn't exist
    try:
        complaint = get_object_or_404(Complaint, id=complaint_id)
    except (ProgrammingError, Exception) as e:
        return JsonResponse({
            'error': 'Complaint table not found. Please run migrations: python manage.py migrate'
        }, status=500)

    response_text = request.POST.get('response', '').strip()

    if not response_text:
        return JsonResponse({'error': 'Response is required'}, status=400)

    try:
        complaint.response = response_text
        complaint.status = 'resolved'
        complaint.responded_by = request.user
        complaint.responded_at = timezone.now()
        complaint.save()

        messages.success(request, 'Response has been saved and complaint marked as resolved.')
        return JsonResponse({
            'status': 'success',
            'message': 'Response saved successfully'
        })
    except (ProgrammingError, Exception) as e:
        return JsonResponse({
            'error': 'Error saving response. Complaint table not found. Please run migrations: python manage.py migrate'
        }, status=500)

from django.http import HttpResponse
from django.db.models import Q

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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


# ===========================
#   ZKTECO DEVICE MANAGEMENT
# ===========================

@login_required
@hr_or_admin_required
def device_management(request):
    """Device management page - add, edit, delete devices"""
    from .models import ZKDevice

    devices = ZKDevice.objects.all().order_by('-created_at')

    context = {
        'devices': devices,
    }
    return render(request, 'pages/device/management.html', context)


@login_required
@hr_or_admin_required
def device_enrollment(request):
    """Device enrollment page - select employee and enroll"""
    from .models import ZKDevice, Employees, EnrollmentLog

    devices = ZKDevice.objects.filter(is_active=True)
    employees = Employees.objects.filter(status=1).order_by('firstname')

    # Get recent enrollments
    recent_enrollments = EnrollmentLog.objects.select_related('device', 'employee', 'initiated_by').order_by('-started_at')[:20]

    context = {
        'devices': devices,
        'employees': employees,
        'recent_enrollments': recent_enrollments,
    }
    return render(request, 'pages/device/enrollment.html', context)


@login_required
@hr_or_admin_required
def attendance_live(request):
    """Live attendance monitoring page"""
    from .models import ZKDevice, AttendanceLog

    devices = ZKDevice.objects.filter(is_active=True)
    today_logs = AttendanceLog.objects.filter(
        timestamp__date=timezone.now().date()
    ).select_related('device', 'employee').order_by('-timestamp')[:100]

    context = {
        'devices': devices,
        'today_logs': today_logs,
    }
    return render(request, 'pages/attendance/live.html', context)


# ===========================
#   CORE FETCH & SYNC LOGIC
# ===========================

def fetch_and_save_employees(request):
    """
    Fetch employees from ALL active ZKDevices and save to DB.
    """
    if not ZK_AVAILABLE:
        return JsonResponse({"status": "error", "message": "pyzk library not installed"}, status=500)

    devices = ZKDevice.objects.filter(is_active=True)
    if not devices.exists():
        return JsonResponse({"status": "error", "message": "No active devices found in database"}, status=404)

    total_created = 0
    all_created_users = []
    errors = []

    for device_obj in devices:
        try:
            manager = ZKDeviceManager(device_obj)
            ok, msg, conn = manager.connect()

            if not ok:
                errors.append(f"{device_obj.name}: Connection failed - {msg}")
                continue

            try:
                users = manager.get_users()
            except Exception as e:
                errors.append(f"{device_obj.name}: Failed to get users - {e}")
                manager.disconnect()
                continue

            created_count = 0

            for user in users:
                logger.info(f"Processing device user: {user.user_id} - {user.name}")

                # Skip incomplete entries
                if not user.user_id:
                    logger.warning(f"Skipping user with empty user_id: {user.name}")
                    continue

                user_id_str = str(user.user_id).strip()
                if not user_id_str:
                    logger.warning(f"Skipping user with empty stripped user_id: {user.name}")
                    continue

                # Basic username + company email from device name
                name_str = user.name.strip() if user.name else f"Emp_{user_id_str}"
                username = name_str.split()[0].lower()
                official_email = f"{username}{user_id_str}@funprimetechnology.com" # Ensure uniqueness

                # Avoid duplicates: we use `code` as the unique fingerprint id
                if Employees.objects.filter(code=user_id_str).exists():
                    logger.info(f"User {user_id_str} already exists. Skipping.")
                    continue

                try:
                    # Create minimal employee with ONLY data we have from device
                    emp = Employees.objects.create(
                        code=user_id_str,                # Employee ID from device
                        firstname=name_str,              # Full name from device
                        lastname="",                     # Not available → keep empty
                        official_email=official_email,   # Generated company email
                        date_hired=date.today(),         # Default
                        status=1,                        # Active
                        # Set defaults for FKs if they exist, otherwise leave null
                        department_id=1 if Department.objects.filter(id=1).exists() else None,
                        position_id=1 if Position.objects.filter(id=1).exists() else None,
                    )

                    # The post_save signal on Employees will auto-create the auth User

                    all_created_users.append({
                        "device": device_obj.name,
                        "id": emp.id,
                        "name": emp.firstname,
                        "code": emp.code
                    })
                    created_count += 1
                    logger.info(f"Created employee: {emp.firstname} ({emp.code})")

                except Exception as create_err:
                     err_msg = f"Failed to create employee {name_str} ({user_id_str}): {create_err}"
                     logger.error(err_msg)
                     errors.append(err_msg)

            total_created += created_count
            manager.disconnect()

        except Exception as e:
            errors.append(f"{device_obj.name}: Unexpected error - {str(e)}")
            logger.error(f"Error fetching employees from {device_obj.name}: {e}")

    message = f"Imported {total_created} new employees."
    if errors:
        message += f" Errors: {'; '.join(errors)}"

    return JsonResponse({
        "status": "success" if total_created > 0 else ("warning" if errors else "success"),
        "message": message,
        "employees": all_created_users,
        "errors": errors
    })


def fetch_and_save_attendance(request=None):
    """
    Fetch attendance from ALL active ZKDevices and save to DB.
    Can be used as:
    - a Django view: /import-attendance/  → returns JsonResponse
    - a background job (scheduler)       → request will be None
    """
    logger.info("*********** Fetching Attendance ***********")

    if not ZK_AVAILABLE:
        if request:
            return JsonResponse({"status": "error", "message": "pyzk library not installed"}, status=500)
        return

    devices = ZKDevice.objects.filter(is_active=True)
    if not devices.exists():
        msg = "No active devices found."
        logger.warning(msg)
        if request:
             return JsonResponse({"status": "warning", "message": msg})
        return

    total_processed = 0
    total_new = 0
    errors = []

    for device_obj in devices:
        try:
            logger.info(f"Connecting to {device_obj.name}...")
            manager = ZKDeviceManager(device_obj)
            ok, msg, conn = manager.connect()

            if not ok:
                err = f"{device_obj.name}: {msg}"
                logger.error(err)
                errors.append(err)
                continue

            try:
                attendance_data = manager.get_attendance()
            except Exception as e:
                err = f"{device_obj.name}: Failed to get attendance - {e}"
                logger.error(err)
                errors.append(err)
                manager.disconnect()
                continue

            device_processed = 0
            device_new = 0

            # Group by (employee, date) to process simplified logic
            attendance_by_employee = {}

            for record in attendance_data:
                # Map device user_id -> Employees.code
                user_id_str = str(record.user_id).strip()

                # Check if employee exists
                # OPTIMIZATION: In production, load all employees code->id map once before loop
                try:
                    emp = Employees.objects.get(code=user_id_str)
                except Employees.DoesNotExist:
                    # Fallback: If user_id is numeric, try to find a match ignoring leading zeros (e.g. "1" matches "001")
                    found_fallback = False
                    if user_id_str.isdigit():
                        # 1. Try regex match for DB "001" when Device is "1"
                        emp = Employees.objects.filter(code__iregex=r'^[0]*' + user_id_str + '$').first()
                        if emp:
                            found_fallback = True
                            logger.info(f"Matched device user {user_id_str} to employee {emp.code}")

                        # 2. Try stripping device zeros for DB "1" when Device is "001"
                        if not found_fallback:
                            try:
                                clean_id = str(int(user_id_str))
                                emp = Employees.objects.get(code=clean_id)
                                found_fallback = True
                                logger.info(f"Matched device user {user_id_str} to employee {emp.code} (stripped zeros)")
                            except Employees.DoesNotExist:
                                pass

                    if not found_fallback:
                        logger.warning(f"Skipping attendance for unknown user_id: {user_id_str} on device {device_obj.name}")
                        continue

                timestamp = record.timestamp

                # Ensure timezone-aware datetime
                if timezone.is_naive(timestamp):
                    tz = pytz.timezone('Asia/Karachi') # Should be configurable from settings
                    timestamp = timezone.make_aware(timestamp, tz)

                # Save raw log first (Audit trail / Backup)
                # Using update_or_create to avoid duplicates if re-fetched
                # We assume (device, employee, timestamp) is unique enough
                try:
                    log, created = AttendanceLog.objects.get_or_create(
                        device=device_obj,
                        employee=emp,
                        timestamp=timestamp,
                        defaults={
                            'user_id': user_id_str,
                            'event_type': 'check_in' if getattr(record, 'punch', 0) in [0, 4, 3] else 'check_out', # APPROXIMATION
                            'verification_mode': getattr(record, 'verify_mode', 0),
                            'raw_data': {'uid': getattr(record, 'uid', None), 'punch': getattr(record, 'punch', 0)}
                        }
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to save AttendanceLog: {log_err}")

                # Prepare for aggregation
                date_obj = timestamp.date()
                time_obj = timestamp.time()
                key = (emp.id, date_obj)
                attendance_by_employee.setdefault(key, []).append(time_obj)

                device_processed += 1

            # Process aggregated data for Attendance table
            for (emp_id, date_obj), punch_times in attendance_by_employee.items():
                if not punch_times:
                    continue

                punch_times.sort()

                # Deduplicate punches within 2 mins
                filtered_punches = []
                prev_punch = None
                for punch in punch_times:
                    if prev_punch is None:
                        filtered_punches.append(punch)
                        prev_punch = punch
                    else:
                        delta_minutes = (
                            datetime.combine(date_obj, punch) -
                            datetime.combine(date_obj, prev_punch)
                        ).total_seconds() / 60
                        if delta_minutes >= 2:
                            filtered_punches.append(punch)
                            prev_punch = punch

                # Get or Create Attendance Record
                try:
                    att, created = Attendance.objects.get_or_create(
                        employee_id=emp_id,
                        date=date_obj,
                    )
                except Exception as e:
                    logger.error(f"Error getting attendance record: {e}")
                    continue

                # If finalized, maybe skip? For now, we update.
                updated = False

                # Thresholds (Should ideally come from Employee -> Department -> Settings)
                # We use the method on the model or simple defaults
                thresholds = att.get_office_timings()
                check_in_threshold = thresholds['office_start'] # e.g. 9:00
                check_out_threshold = thresholds['office_end']  # e.g. 18:00

                # Logic: Flexible Min/Max update to support incremental sync
                if filtered_punches:
                    for punch in filtered_punches:
                        # 1. Update Check-In (Earliest punch is always Check-In)
                        if not att.check_in_time or punch < att.check_in_time:
                            att.check_in_time = punch
                            updated = True

                    # 2. Update Check-Out (Latest punch > Check-In is Check-Out)
                    for punch in filtered_punches:
                        if att.check_in_time and punch > att.check_in_time:
                             if not att.check_out_time or punch > att.check_out_time:
                                att.check_out_time = punch
                                updated = True

                if updated or created:
                    att.calculate_durations() # updates late_in, early_out based on new times
                    status = att.auto_determine_status()
                    if status:
                         att.status = status
                    att.save()
                    device_new += 1

            manager.disconnect()
            total_processed += device_processed
            total_new += device_new
            logger.info(f"{device_obj.name}: Processed {device_processed} logs, Updated {device_new} records.")

        except Exception as e:
            err = f"{device_obj.name}: Global error - {e}"
            logger.error(err)
            errors.append(err)

    result_msg = f"Processed {total_processed} records across {len(devices)} devices. Updated {total_new} entries."
    logger.info(result_msg)

    if request:
        return JsonResponse({
            "status": "success" if not errors else "warning",
            "message": result_msg,
            "errors": errors
        })


def start_sync_on_django_start():
    """
    Start a background scheduler that syncs attendance
    from the device every 2 minutes.
    Call this from AppConfig.ready().
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("APScheduler not available. Background attendance sync disabled.")
        return

    try:
        tz = pytz.timezone('Asia/Karachi')
        scheduler = BackgroundScheduler(timezone=tz)

        trigger = IntervalTrigger(seconds=120, timezone=tz)

        scheduler.add_job(
            func=fetch_and_save_attendance,
            trigger=trigger,
            id='attendance_sync_job',
            name='Fetch and save attendance data every 2 minutes',
            replace_existing=True,
        )

        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
    except Exception as e:
        logger.error(f"Failed to start attendance sync scheduler: {e}")


def check_device_status(request):
    """
    Check status of a specific device.
    Requires device_id parameter.
    If no device_id provided, returns error to prevent timeout on default IP.
    """
    device_id = request.GET.get('device_id')

    if not device_id:
        return JsonResponse({
            "status": "error",
            "message": "Device ID required"
        }, status=400)

    if not ZK_AVAILABLE:
        return JsonResponse({"status": "error", "message": "ZK library not installed"}, status=500)

    try:
        from .models import ZKDevice
        device = ZKDevice.objects.get(id=device_id)

        zk = ZK(device.ip_address, port=device.port, timeout=5)
        conn = zk.connect()
        # Just check connection, don't disable/enable which disrupts service!
        conn.disconnect()

        return JsonResponse({"status": "success", "message": f"Device {device.name} is online."})
    except Exception as e:
        logger.error(f"Error in device connection: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ===========================
#   DEVICE API VIEWS
# ===========================

# API Views for Device Operations


@login_required
@hr_or_admin_required
@require_POST
def api_device_push_user(request):
    """API: Push user to device"""
    from .models import ZKDevice, Employees
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')

        # Use explicit getters to avoid HTML 404 pages
        try:
            device = ZKDevice.objects.get(id=device_id, is_active=True)
        except ZKDevice.DoesNotExist:
             return JsonResponse({'success': False, 'message': 'Device not found or inactive'}, status=404)

        try:
            employee = Employees.objects.get(id=employee_id)
        except Employees.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found'}, status=404)

        manager = ZKDeviceManager(device)
        success, message = manager.push_user(employee)

        manager.disconnect()

        if success:
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        # Catch any other error (including unexpected ones) and return JSON
        return JsonResponse({'success': False, 'message': f"Internal Error: {str(e)}"}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_enroll_fingerprint(request):
    """API: Start fingerprint enrollment"""
    from .models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        # Check if enrollment already exists (handle unique constraint)
        enrollment, created = EnrollmentLog.objects.get_or_create(
            device=device,
            employee=employee,
            enrollment_type='fingerprint',
            template_index=template_index,
            defaults={
                'status': 'in_progress',
                'initiated_by': request.user,
                'started_at': timezone.now(),
            }
        )

        # If enrollment already exists, update it to restart
        if not created:
            # If it's already in progress, allow restarting
            enrollment.status = 'in_progress'
            enrollment.error_message = None
            enrollment.completed_at = None
            enrollment.started_at = timezone.now()
            enrollment.initiated_by = request.user
            enrollment.save()

        manager = ZKDeviceManager(device)
        success, message = manager.start_fingerprint_enrollment(employee, template_index)

        if success:
            enrollment.status = 'in_progress'
            enrollment.save()

            # Verify user is registered on device before disconnecting
            user_exists, verify_msg = manager.verify_user_exists(employee)
            if user_exists:
                logger.info(f"User {employee.code} confirmed registered on device {device.name}")
            else:
                logger.warning(f"User {employee.code} may not be registered: {verify_msg}")

            manager.disconnect()

            # Broadcast via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'device_events',
                    {
                        'type': 'enrollment_update',
                        'data': {
                            'id': enrollment.id,
                            'employee': employee.code,
                            'type': 'fingerprint',
                            'status': 'in_progress',
                            'message': message
                        }
                    }
                )

            return JsonResponse({'success': True, 'message': message, 'enrollment_id': enrollment.id})
        else:
            enrollment.status = 'failed'
            enrollment.error_message = message
            enrollment.save()
            manager.disconnect()
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_enroll_face(request):
    """API: Start face enrollment"""
    from .models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        # Check if enrollment already exists (handle unique constraint)
        enrollment, created = EnrollmentLog.objects.get_or_create(
            device=device,
            employee=employee,
            enrollment_type='face',
            template_index=template_index,
            defaults={
                'status': 'in_progress',
                'initiated_by': request.user,
                'started_at': timezone.now(),
            }
        )

        # If enrollment already exists, update it to restart
        if not created:
            # If it's already in progress, allow restarting
            enrollment.status = 'in_progress'
            enrollment.error_message = None
            enrollment.completed_at = None
            enrollment.started_at = timezone.now()
            enrollment.initiated_by = request.user
            enrollment.save()

        manager = ZKDeviceManager(device)
        success, message = manager.start_face_enrollment(employee, template_index)

        if success:
            enrollment.status = 'in_progress'
            enrollment.save()
            manager.disconnect()

            # Broadcast via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'device_events',
                    {
                        'type': 'enrollment_update',
                        'data': {
                            'id': enrollment.id,
                            'employee': employee.code,
                            'type': 'face',
                            'status': 'in_progress',
                            'message': message
                        }
                    }
                )

            return JsonResponse({'success': True, 'message': message, 'enrollment_id': enrollment.id})
        else:
            enrollment.status = 'failed'
            enrollment.error_message = message
            enrollment.save()
            manager.disconnect()
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
def api_device_verify_enrollment(request):
    """API: Verify fingerprint enrollment completion"""
    from .models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json
    import traceback

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        manager = ZKDeviceManager(device)
        success, message = manager.verify_fingerprint_enrollment(employee, template_index)
        manager.disconnect()

        if success:
            # Update enrollment log if exists
            try:
                enrollment = EnrollmentLog.objects.get(
                    device=device,
                    employee=employee,
                    enrollment_type='fingerprint',
                    template_index=template_index,
                    status='in_progress'
                )
                enrollment.status = 'completed'
                enrollment.completed_at = timezone.now()
                enrollment.save()

                # Broadcast completion via WebSocket
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        'device_events',
                        {
                            'type': 'enrollment_update',
                            'data': {
                                'id': enrollment.id,
                                'employee': employee.code,
                                'type': 'fingerprint',
                                'status': 'completed',
                                'message': message
                            }
                        }
                    )
            except EnrollmentLog.DoesNotExist:
                pass

            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        logger.error(f"Error verifying enrollment: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
def api_device_test_connection(request):
    """API: Test device connection"""
    from .device_utils import ZKDeviceManager
    from .models import ZKDevice

    ip = (request.GET.get('ip') or '').strip()
    port = int(request.GET.get('port') or 4370)
    password = (request.GET.get('password') or '').strip() or None

    if not ip:
        return JsonResponse({'success': False, 'message': 'IP address required'}, status=400)

    # Create temporary device object for testing
    class TempDevice:
        def __init__(self, ip, port, timeout, password):
            self.ip_address = ip
            self.port = port
            self.timeout = timeout
            self.password = password
            self.status = 'offline'
            self.last_error = None
            self.device_name = None
            self.serial_number = None

        def save(self, update_fields=None):
            pass

    temp_device = TempDevice(ip, port, 5, password)
    manager = ZKDeviceManager(temp_device)
    success, message, conn = manager.connect()

    if success:
        manager.disconnect()
        return JsonResponse({
            'success': True,
            'message': f'Connection successful to {ip}:{port}',
            'device_name': temp_device.device_name,
            'serial_number': temp_device.serial_number
        })
    else:
        return JsonResponse({
            'success': False,
            'message': message
        })


@login_required
@hr_or_admin_required

def api_device_status(request, device_id):
    """API: Get device status (JSON safe)"""

    from .models import ZKDevice
    from .device_utils import ZKDeviceManager

    # 🔐 Manual auth check (JSON response instead of redirect)
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required"
        }, status=401)

    try:
        device = get_object_or_404(ZKDevice, id=device_id)

        manager = ZKDeviceManager(device)
        success, message, conn = manager.connect()

        data = {
            "success": True,
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "port": device.port,
            "status": device.status,
            "is_online": success,
            "last_connected": device.last_connected.isoformat() if device.last_connected else None,
            "last_error": device.last_error,
            "message": message,
        }

        if conn:
            manager.disconnect()

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)



@login_required
@hr_or_admin_required
def api_device_logs(request, device_id):
    """API: Get device logs"""
    from .models import ZKDevice, AttendanceLog

    device = get_object_or_404(ZKDevice, id=device_id)

    # Get recent logs
    limit = int(request.GET.get('limit', 50))
    logs = AttendanceLog.objects.filter(device=device).select_related('employee').order_by('-timestamp')[:limit]

    logs_data = []
    for log in logs:
        logs_data.append({
            'id': log.id,
            'user_id': log.user_id,
            'user_name': log.user_name,
            'employee_code': log.employee.code if log.employee else None,
            'employee_name': f"{log.employee.firstname} {log.employee.lastname or ''}".strip() if log.employee else None,
            'event_type': log.event_type,
            'timestamp': log.timestamp.isoformat(),
            'verification_mode': log.verification_mode,
            'is_processed': log.is_processed,
        })

    return JsonResponse({'logs': logs_data})


@login_required
@hr_or_admin_required
@require_POST
def api_device_create(request):
    """API: Create new device"""
    from .models import ZKDevice
    import json

    try:
        data = json.loads(request.body)
        # Safely handle None values - convert to string first to avoid NoneType errors
        name = str(data.get('name') or '').strip()
        ip_address = str(data.get('ip_address') or '').strip()
        port = int(data.get('port') or 4370)
        timeout = int(data.get('timeout') or 5)
        password_value = data.get('password')
        password = str(password_value).strip() if password_value else None
        if password == '':
            password = None

        if not name or not ip_address:
            return JsonResponse({'success': False, 'message': 'Name and IP address are required'}, status=400)

        # Check if device with same name exists
        if ZKDevice.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'message': f'Device with name "{name}" already exists'}, status=400)

        device = ZKDevice.objects.create(
            name=name,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            password=password,
            is_active=True,
            realtime_enabled=True
        )

        return JsonResponse({
            'success': True,
            'message': f'Device "{name}" created successfully',
            'device': {
                'id': device.id,
                'name': device.name,
                'ip_address': device.ip_address,
                'port': device.port
            }
        })

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating device: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_delete(request, device_id):
    """API: Delete device"""
    from .models import ZKDevice

    try:
        device = get_object_or_404(ZKDevice, id=device_id)
        device_name = device.name
        device.delete()
        return JsonResponse({'success': True, 'message': f'Device "{device_name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_cancel_enrollment(request):
    """API: Cancel current enrollment process"""
    from .models import ZKDevice
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')

        # Use explicit check to allow 'get_object_or_404' to work or handle manually if imports issue
        # Assuming get_object_or_404 is valid as per file analysis
        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)

        manager = ZKDeviceManager(device)
        success, message = manager.cancel_enrollment()
        manager.disconnect()

        if success:
             # Find any in-progress enrollments for this device and mark as cancelled
            from .models import EnrollmentLog
            EnrollmentLog.objects.filter(
                device=device,
                status='in_progress'
            ).update(
                status='failed',
                error_message='Cancelled by user',
                completed_at=timezone.now()
            )

            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)