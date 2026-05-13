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
            'Test Email from EMS',
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

