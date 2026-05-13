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