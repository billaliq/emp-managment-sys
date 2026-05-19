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


# Employee Profile
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


# Employee CRUD
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
                emp.location = data.get("location", "EB's Technology") or emp.location
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
                    if not emp.location: emp.location = data.get("location", "EB's Technology") or emp.location
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
                    emp.location = data.get("location", "EB's Technology") or emp.location
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
                # Reload to get temp_password set by the signal
                emp.refresh_from_db()
                username = emp.user.username if emp.user else 'N/A'
                messages.success(
                    request,
                    f"✅ Employee {emp.code} added successfully! "
                    f"Login credentials have been generated (Username: <strong>{username}</strong>). "
                    f"View the full credentials in the employee profile."
                )
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
        from EMSwebsite.models import generate_secure_password
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
