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