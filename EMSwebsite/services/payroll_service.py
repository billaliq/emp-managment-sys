# EMSwebsite/services/payroll_service.py
"""
Payroll business logic — salary calculations, payroll processing,
increment computation, and summary statistics.

All functions are request-independent so they can be reused in management
commands, Celery tasks, or API serialisers.
"""

import logging
from decimal import Decimal
from datetime import datetime
from django.db.models import Sum, Avg, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Salary Calculation
# ---------------------------------------------------------------------------

def calculate_net_salary(base_salary, allowances=Decimal('0.00'), deductions=Decimal('0.00')):
    """
    Compute net salary from components.

    Args:
        base_salary: Decimal base amount.
        allowances: Decimal total allowances.
        deductions: Decimal total deductions.

    Returns:
        Decimal net salary.
    """
    return Decimal(base_salary or 0) + Decimal(allowances or 0) - Decimal(deductions or 0)


def calculate_increment(old_salary, new_salary):
    """
    Compute increment percentage and absolute amount.

    Args:
        old_salary: Decimal previous salary.
        new_salary: Decimal new salary.

    Returns:
        tuple(Decimal percent, Decimal amount)
    """
    old = Decimal(old_salary or 0)
    new = Decimal(new_salary or 0)
    amount = new - old
    percent = (amount * Decimal('100.0') / old) if old > 0 else Decimal('0.00')
    return percent, amount


# ---------------------------------------------------------------------------
#  Payroll Processing
# ---------------------------------------------------------------------------

def process_payroll_for_employees(payroll, employees_queryset):
    """
    Create PayrollRecord rows for every employee in the queryset.

    Args:
        payroll: A Payroll model instance (already saved).
        employees_queryset: Queryset of Employees to include.

    Returns:
        int — number of records created.
    """
    from EMSwebsite.models import PayrollRecord

    created = 0
    for emp in employees_queryset:
        base = Decimal(emp.salary or 0)
        net = calculate_net_salary(base)
        PayrollRecord.objects.create(
            payroll=payroll,
            employee=emp,
            base_salary=base,
            allowances=Decimal('0.00'),
            deductions=Decimal('0.00'),
            net_salary=net,
            pay_date=payroll.pay_date,
            status='pending',
        )
        created += 1
    return created


# ---------------------------------------------------------------------------
#  Query Building
# ---------------------------------------------------------------------------

def build_payroll_queryset(base_qs, *, search=None, employee_id=None,
                           department_id=None, status=None,
                           month=None, year=None, is_admin=False):
    """
    Apply standard payroll filters to a PayrollRecord queryset.

    Args:
        base_qs: Starting PayrollRecord queryset.
        search: Free-text search string (employee name/code/email).
        employee_id: Filter to a specific employee PK.
        department_id: Filter to a specific department PK.
        status: One of 'paid', 'pending', 'failed'.
        month: Integer month (1-12).
        year: Integer year.
        is_admin: Whether the calling user has admin/HR/finance privileges.

    Returns:
        Filtered queryset.
    """
    qs = base_qs

    if search and is_admin:
        qs = qs.filter(
            Q(employee__code__icontains=search) |
            Q(employee__firstname__icontains=search) |
            Q(employee__lastname__icontains=search) |
            Q(employee__email__icontains=search)
        )

    if employee_id and is_admin:
        try:
            qs = qs.filter(employee_id=int(employee_id))
        except (ValueError, TypeError):
            pass

    if department_id and is_admin:
        try:
            qs = qs.filter(employee__department_id=int(department_id))
        except (ValueError, TypeError):
            pass

    if status and status in ('paid', 'pending', 'failed'):
        qs = qs.filter(status=status)

    if month and year:
        try:
            qs = qs.filter(pay_date__year=int(year), pay_date__month=int(month))
        except (ValueError, TypeError):
            pass

    return qs


# ---------------------------------------------------------------------------
#  Summary / Statistics
# ---------------------------------------------------------------------------

def get_payroll_summary(queryset):
    """
    Compute payroll summary stats from a PayrollRecord queryset.

    Args:
        queryset: Filtered PayrollRecord queryset.

    Returns:
        dict with keys: total_payroll, employees_paid, average_salary,
        pending_approvals, total_records.
    """
    agg = queryset.aggregate(
        total=Sum('net_salary'),
        avg=Avg('net_salary'),
    )

    return {
        'total_payroll': agg['total'] or Decimal('0.00'),
        'average_salary': agg['avg'] or Decimal('0.00'),
        'employees_paid': queryset.filter(status='paid').values('employee').distinct().count(),
        'pending_approvals': queryset.filter(status='pending').count(),
        'total_records': queryset.count(),
    }
