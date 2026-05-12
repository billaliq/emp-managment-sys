# context_processors.py
"""Reusable context helpers for templates."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone, timesince
from datetime import timedelta

from .models import UserProfile, Employees, Report, Payroll, SystemSettings, Notification, Attendance, LeaveRequest

def user_role_context(request):
    """Expose the authenticated user's role (and employee if linked)."""

    user = getattr(request, "user", None)
    role = "anonymous"
    employee = None
    is_admin = False

    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return {"user_role": role, "current_employee": employee, "is_admin": is_admin}

    if getattr(user, "is_superuser", False):
        role = "admin"
        is_admin = True
    else:
        try:
            profile = user.profile
            role = profile.role
            # Try to get employee from UserProfile first
            employee = profile.employee if profile.employee else None
            # Fallback: try to get employee from Employees.user relationship
            if not employee and hasattr(user, 'employee') and user.employee:
                employee = user.employee
            is_admin = (role == "admin")
        except UserProfile.DoesNotExist:
            role = "employee"
            # Fallback: try to get employee from Employees.user relationship
            employee = getattr(user, "employee", None)

    return {"user_role": role, "current_employee": employee, "is_admin": is_admin}

def get_notifications(request):
    """Get notifications from the Notification model for the current user"""
    if not request.user.is_authenticated:
        return {
            'notifications': [],
            'notification_count': 0
        }

    # Get unread notifications from database (last 30 days)
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Get notifications for this user
    db_notifications = Notification.objects.filter(
        recipient=request.user,
        created_at__gte=thirty_days_ago
    ).order_by('-created_at')[:20]  # Limit to 20 most recent

    notifications = []

    # Convert database notifications to display format
    for notif in db_notifications:
        # Determine icon and color based on notification type
        icon_map = {
            'increment': 'fa-dollar-sign',
            'birthday': 'fa-birthday-cake',
            'payroll': 'fa-calendar-check',
            'leave': 'fa-umbrella-beach',
            'system': 'fa-exclamation-circle',
            'attendance': 'fa-clock',
        }

        color_map = {
            'increment': '#10b981',  # Green
            'birthday': '#f59e0b',   # Yellow/Orange
            'payroll': '#3b82f6',    # Blue
            'leave': '#8b5cf6',      # Purple
            'system': '#6b7280',     # Gray
            'attendance': '#ef4444', # Red
        }

        notifications.append({
            'id': notif.id,
            'icon': icon_map.get(notif.notification_type, 'fa-bell'),
            'color': color_map.get(notif.notification_type, '#6b7280'),
            'title': notif.title,
            'message': notif.message,
            'time': timesince.timesince(notif.created_at),
            'unread': not notif.is_read,
            'type': notif.notification_type,
        })

    # Also add dynamic notifications (birthdays, etc.) for admin users
    try:
        user_role = request.user.profile.role
        is_admin = request.user.is_superuser or user_role in ['admin', 'hr']
    except:
        is_admin = request.user.is_superuser

    if is_admin:
        today = now.date()

        # Birthday notifications for today
        birthdays = Employees.objects.filter(
            dob__month=today.month,
            dob__day=today.day,
            dob__isnull=False,
            status=1
        )
        for emp in birthdays:
            # Check if notification already exists
            existing = Notification.objects.filter(
                recipient=request.user,
                notification_type='birthday',
                title='Birthday Alert',
                message__icontains=emp.firstname,
                created_at__date=today
            ).exists()

            if not existing:
                notifications.append({
                    'icon': 'fa-birthday-cake',
                    'color': '#f59e0b',
                    'title': 'Birthday Alert',
                    'message': f"{emp.firstname} {emp.lastname or ''} has a birthday today! Wish them well.",
                    'time': 'Today',
                    'unread': True,
                    'type': 'birthday',
                })

    # Compute unread count
    unread_count = sum(1 for n in notifications if n.get('unread', False))

    return {
        'notifications': notifications,
        'notification_count': unread_count
    }

def system_settings_context(request):
    """Expose system settings to all templates for global appearance control"""
    try:
        settings = SystemSettings.get_solo()
        return {
            'system_settings': settings
        }
    except Exception:
        # Return default settings if there's an error
        return {
            'system_settings': None
        }