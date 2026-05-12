"""
Custom forms for EIS application
"""
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Employees

User = get_user_model()


class CustomPasswordResetForm(PasswordResetForm):
    """
    Custom password reset form that finds users by email from:
    1. User model email field
    2. Employee model email or official_email fields
    """

    def get_users(self, email):
        """
        Override to find users by email from multiple sources
        """
        # First, try to find users by their email field
        active_users = User.objects.filter(
            email__iexact=email,
            is_active=True
        )

        if active_users.exists():
            return active_users

        # If not found, try to find by Employee email fields
        employees = Employees.objects.filter(
            (Q(email__iexact=email) | Q(official_email__iexact=email)) &
            Q(user__isnull=False) &
            Q(user__is_active=True)
        )

        # Get users from employees
        users_from_employees = User.objects.filter(
            id__in=employees.values_list('user_id', flat=True),
            is_active=True
        )

        return users_from_employees

