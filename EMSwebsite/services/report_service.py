# EMSwebsite/services/report_service.py
"""
Report business logic — role-based access control, data extraction for each
report type, date-range calculation, and report naming.

All functions accept simple Python arguments (user/employee objects, dates,
dicts) rather than Django request objects so they can be reused in management
commands, scheduled tasks, or tests.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Role & Access Helpers
# ---------------------------------------------------------------------------

def get_user_role(user):
    """
    Determine the effective role of a Django User.

    Args:
        user: A Django User instance.

    Returns:
        str — one of 'admin', 'hr', 'finance', 'manager', 'employee'.
    """
    if user.is_superuser:
        return 'admin'
    try:
        return user.profile.role
    except Exception:
        return 'employee'


# Report-type access matrix
_ACCESS_MATRIX = {
    'admin':    ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
    'hr':       ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
    'finance':  ['payroll', 'loan'],
    'manager':  ['employee', 'attendance', 'department', 'leave'],
    'employee': ['employee', 'attendance', 'leave', 'loan'],
}


def check_report_access(user, report_type):
    """
    Check whether *user* is allowed to generate/view a *report_type*.

    Args:
        user: Django User instance.
        report_type: str (e.g. 'payroll', 'attendance').

    Returns:
        bool
    """
    role = get_user_role(user)
    allowed = _ACCESS_MATRIX.get(role, ['employee', 'attendance', 'leave'])
    return report_type in allowed


# ---------------------------------------------------------------------------
#  Date Range Calculation
# ---------------------------------------------------------------------------

def calculate_date_range(date_range_key, custom_start=None, custom_end=None):
    """
    Convert a named date-range key into concrete (start_date, end_date).

    Args:
        date_range_key: One of 'last_week', 'last_month', 'last_quarter',
                        'last_year', 'custom'.
        custom_start: date object (used when key == 'custom').
        custom_end: date object (used when key == 'custom').

    Returns:
        tuple(date, date)
    """
    end_date = timezone.now().date()
    ranges = {
        'last_week':    timedelta(days=7),
        'last_month':   timedelta(days=30),
        'last_quarter': timedelta(days=90),
        'last_year':    timedelta(days=365),
    }

    if date_range_key == 'custom':
        start = custom_start or (end_date - timedelta(days=30))
        end = custom_end or end_date
        return start, end

    delta = ranges.get(date_range_key, timedelta(days=30))
    return end_date - delta, end_date


def build_report_name(report_type, start_date=None, end_date=None, employee_name=None):
    """
    Build a human-readable report name.

    Args:
        report_type: str (e.g. 'payroll').
        start_date: Optional date.
        end_date: Optional date.
        employee_name: Optional str for employee-specific reports.

    Returns:
        str
    """
    parts = [f"{report_type.title()} Report"]
    if employee_name:
        parts.append(employee_name)
    if start_date and end_date:
        parts.append(f"{start_date} to {end_date}")
    else:
        parts.append(timezone.now().strftime('%Y-%m-%d'))
    return " - ".join(parts)


# ---------------------------------------------------------------------------
#  Data Extraction Functions
# ---------------------------------------------------------------------------

def _get_employee_or_none(user):
    """Internal helper — resolve the Employees row linked to *user*."""
    try:
        profile = user.profile
        if profile.employee:
            return profile.employee
    except Exception:
        pass
    try:
        if hasattr(user, 'employee') and user.employee:
            return user.employee
    except Exception:
        pass
    return None


def extract_employee_data(user, start_date=None, end_date=None, filters=None):
    """
    Extract employee records for a report.

    Args:
        user: Django User (for role-based scoping).
        start_date / end_date: Optional date filters on ``date_hired``.
        filters: Optional dict with keys 'department', 'status', 'position'.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import Employees

    role = get_user_role(user)
    current_emp = _get_employee_or_none(user)

    if role in ('admin', 'hr', 'manager'):
        qs = Employees.objects.all()
    else:
        qs = Employees.objects.filter(pk=current_emp.pk) if current_emp else Employees.objects.none()

    if filters:
        if filters.get('department'):
            qs = qs.filter(department_id=filters['department'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('position'):
            qs = qs.filter(position_id=filters['position'])

    if start_date:
        qs = qs.filter(date_hired__gte=start_date)
    if end_date:
        qs = qs.filter(date_hired__lte=end_date)

    return [
        {
            'code': emp.code,
            'name': f"{emp.firstname} {emp.lastname or ''}".strip(),
            'email': emp.email or emp.official_email or 'N/A',
            'department': emp.department.name if emp.department else 'N/A',
            'position': emp.position.name if emp.position else 'N/A',
            'date_hired': emp.date_hired.strftime('%Y-%m-%d') if emp.date_hired else 'N/A',
            'status': 'Active' if emp.status == 1 else 'Inactive',
            'salary': emp.salary,
            'contact': emp.contact_1 or 'N/A',
        }
        for emp in qs
    ]


def extract_payroll_data(user, start_date, end_date, filters=None):
    """
    Extract payroll records for a report.

    Args:
        user: Django User.
        start_date / end_date: date bounds.
        filters: Optional dict with key 'department'.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import Payroll

    role = get_user_role(user)
    if role not in ('admin', 'hr', 'finance'):
        return []

    payrolls = Payroll.objects.filter(pay_date__gte=start_date, pay_date__lte=end_date)
    if filters and filters.get('department'):
        payrolls = payrolls.filter(records__employee__department_id=filters['department']).distinct()

    data = []
    for p in payrolls:
        for rec in p.records.select_related('employee'):
            data.append({
                'pay_period': p.pay_period,
                'pay_date': p.pay_date.strftime('%Y-%m-%d'),
                'employee_code': rec.employee.code if rec.employee else 'N/A',
                'employee_name': f"{rec.employee.firstname} {rec.employee.lastname or ''}".strip() if rec.employee else 'N/A',
                'base_salary': float(rec.base_salary or 0),
                'allowances': float(rec.allowances or 0),
                'deductions': float(rec.deductions or 0),
                'net_salary': float(rec.net_salary or 0),
            })
    return data


def extract_attendance_data(user, start_date, end_date, filters=None):
    """
    Extract attendance records for a report.

    Args:
        user: Django User.
        start_date / end_date: date bounds.
        filters: Optional dict with keys 'department', 'status', 'employee',
                 'attendance_detail'.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import Attendance
    from datetime import timedelta as td

    role = get_user_role(user)
    current_emp = _get_employee_or_none(user)

    if role in ('admin', 'hr', 'manager'):
        qs = Attendance.objects.filter(date__gte=start_date, date__lte=end_date)
    elif current_emp:
        qs = Attendance.objects.filter(employee=current_emp, date__gte=start_date, date__lte=end_date)
    else:
        return []

    if filters:
        if filters.get('department'):
            qs = qs.filter(employee__department_id=filters['department'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('employee'):
            qs = qs.filter(employee_id=filters['employee'])
        detail = filters.get('attendance_detail')
        if detail == 'late_only':
            qs = qs.filter(Q(late_in__isnull=False) | Q(status__in=['late', 'late-coming']))
        elif detail == 'weekend_only':
            qs = qs.filter(status='weekend')
        elif detail == 'late_sitting_only':
            qs = qs.filter(late_sitting__isnull=False).exclude(late_sitting=td(0))

    qs = qs.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    ).select_related('employee', 'employee__department').order_by('-date', '-updated_at', 'employee__firstname')

    # Deduplicate per employee+date keeping the latest update
    seen = {}
    unique = []
    for att in qs:
        key = (att.employee_id, att.date)
        if key not in seen:
            seen[key] = att
            unique.append(att)
        elif att.updated_at > seen[key].updated_at:
            unique.remove(seen[key])
            seen[key] = att
            unique.append(att)

    def _fmt_delta(delta):
        if not delta or delta.total_seconds() <= 0:
            return ''
        mins = int(delta.total_seconds() // 60)
        return f"{mins // 60}h {mins % 60:02d}m"

    return [
        {
            'date': a.date.strftime('%Y-%m-%d'),
            'employee_code': a.employee.code,
            'employee_name': f"{a.employee.firstname} {a.employee.lastname or ''}".strip(),
            'department': a.employee.department.name if a.employee.department else 'N/A',
            'check_in': a.check_in_time.strftime('%H:%M') if a.check_in_time else 'N/A',
            'check_out': a.check_out_time.strftime('%H:%M') if a.check_out_time else 'N/A',
            'status': a.get_status_display(),
            'work_duration': a.duration,
            'overtime': a.overtime_display,
            'late_in': a.late_in_display,
            'early_out': _fmt_delta(a.early_out) or 'N/A',
            'late_sitting': _fmt_delta(a.late_sitting) or 'N/A',
            'leave_type': a.get_leave_type_display() if a.leave_type else 'N/A',
            'notes': a.notes or 'N/A',
        }
        for a in unique
    ]


def extract_department_data(user, start_date=None, end_date=None, filters=None):
    """
    Extract department statistics for a report.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import Department

    role = get_user_role(user)
    if role not in ('admin', 'hr', 'manager'):
        return []

    departments = Department.objects.filter(status='active')
    data = []
    for dept in departments:
        emps = dept.employees_set.filter(status=1)
        total_salary = emps.aggregate(total=Sum('salary'))['total'] or 0
        count = emps.count()
        data.append({
            'department_name': dept.name,
            'employee_count': count,
            'total_salary': float(total_salary),
            'average_salary': float(total_salary / count) if count > 0 else 0,
            'description': dept.description,
        })
    return data


def extract_leave_data(user, start_date, end_date, filters=None):
    """
    Extract leave request records for a report.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import LeaveRequest

    role = get_user_role(user)
    current_emp = _get_employee_or_none(user)

    if role in ('admin', 'hr', 'manager'):
        qs = LeaveRequest.objects.filter(start_date__lte=end_date, end_date__gte=start_date)
    elif current_emp:
        qs = LeaveRequest.objects.filter(employee=current_emp, start_date__lte=end_date, end_date__gte=start_date)
    else:
        return []

    if filters:
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('leave_type'):
            qs = qs.filter(leave_type=filters['leave_type'])
        if filters.get('department'):
            qs = qs.filter(employee__department_id=filters['department'])

    return [
        {
            'employee_code': lv.employee.code,
            'employee_name': f"{lv.employee.firstname} {lv.employee.lastname or ''}".strip(),
            'leave_type': lv.get_leave_type_display(),
            'start_date': lv.start_date.strftime('%Y-%m-%d'),
            'end_date': lv.end_date.strftime('%Y-%m-%d'),
            'duration_days': lv.duration_days,
            'status': lv.get_status_display(),
            'applied_on': lv.applied_on.strftime('%Y-%m-%d %H:%M'),
            'approved_by': (
                f"{lv.approved_by.firstname} {lv.approved_by.lastname or ''}".strip()
                if lv.approved_by else 'N/A'
            ),
        }
        for lv in qs.select_related('employee', 'approved_by')
    ]


def extract_loan_data(user, start_date, end_date, filters=None):
    """
    Extract loan records for a report.

    Returns:
        list[dict]
    """
    from EMSwebsite.models import Loan

    role = get_user_role(user)
    current_emp = _get_employee_or_none(user)

    if role in ('admin', 'hr', 'finance'):
        qs = Loan.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    elif current_emp:
        qs = Loan.objects.filter(employee=current_emp, created_at__date__gte=start_date, created_at__date__lte=end_date)
    else:
        return []

    if filters:
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('department'):
            qs = qs.filter(employee__department_id=filters['department'])

    data = []
    for loan in qs.select_related('employee'):
        total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0
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
            'remaining': float(loan.total_amount) - float(total_paid),
            'installments': loan.number_of_installments,
            'monthly_payment': float(loan.monthly_payment) if loan.monthly_payment else 0,
        })
    return data
