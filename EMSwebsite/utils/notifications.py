"""
Utility functions for creating system notifications
"""
from django.contrib.auth.models import User
from django.utils import timezone
from EMSwebsite.models import Notification, Employees


def create_notification(recipient, notification_type, title, message, related_object_id=None, related_object_type=None):
    """
    Create a notification for a user

    Args:
        recipient: User object or Employee object (will get user from employee)
        notification_type: One of 'increment', 'birthday', 'payroll', 'leave', 'system', 'attendance'
        title: Notification title
        message: Notification message
        related_object_id: Optional ID of related object
        related_object_type: Optional type of related object
    """
    # Handle Employee objects
    if isinstance(recipient, Employees):
        if not recipient.user:
            return None  # Employee has no user account
        recipient = recipient.user

    if not isinstance(recipient, User):
        return None

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_object_type=related_object_type,
            is_read=False
        )
        return notification
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        return None


def notify_admins(notification_type, title, message, related_object_id=None, related_object_type=None):
    """
    Create notifications for all admin users

    Args:
        notification_type: One of the notification types
        title: Notification title
        message: Notification message
        related_object_id: Optional ID of related object
        related_object_type: Optional type of related object
    """
    admin_users = User.objects.filter(
        is_superuser=True
    ) | User.objects.filter(
        profile__role__in=['admin', 'hr']
    )

    notifications_created = 0
    for admin_user in admin_users.distinct():
        if create_notification(admin_user, notification_type, title, message, related_object_id, related_object_type):
            notifications_created += 1

    return notifications_created


def notify_employee(employee, notification_type, title, message, related_object_id=None, related_object_type=None):
    """
    Create a notification for a specific employee

    Args:
        employee: Employee object
        notification_type: One of the notification types
        title: Notification title
        message: Notification message
        related_object_id: Optional ID of related object
        related_object_type: Optional type of related object
    """
    return create_notification(employee, notification_type, title, message, related_object_id, related_object_type)

