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
