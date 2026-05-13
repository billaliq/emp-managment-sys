# EMSwebsite/services/attendance_service.py
"""
Attendance business logic — holiday mapping, auto-absent marking, and holiday sync.

These functions are request-independent and can be called from views, management
commands, signal handlers, or Celery tasks.
"""

import logging
from datetime import timedelta
from django.db import IntegrityError, ProgrammingError
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Holiday Helpers
# ---------------------------------------------------------------------------

def get_holiday_map(dates):
    """
    Build a mapping {date -> holiday_name} for the given set/list of dates.
    Avoids N+1 queries by loading holidays once for the date range.

    Args:
        dates: An iterable of date objects.

    Returns:
        dict mapping date -> holiday name string.
    """
    from EMSwebsite.models import HolidayDate

    dates = {d for d in (dates or []) if d}
    if not dates:
        return {}

    try:
        min_d, max_d = min(dates), max(dates)
    except Exception:
        return {}

    try:
        holidays = list(
            HolidayDate.objects.filter(date__gte=min_d, date__lte=max_d).only("name", "date")
        )
    except Exception:
        return {}

    if not holidays:
        return {}

    holiday_dict = {h.date: h.name for h in holidays}
    return {d: holiday_dict[d] for d in dates if d in holiday_dict}


def attach_holiday_fields(records):
    """
    Attach ``is_holiday_date`` and ``holiday_name`` attributes to each attendance
    record in-place for template rendering.

    Args:
        records: An iterable of Attendance model instances.
    """
    try:
        dates = {r.date for r in records if getattr(r, "date", None)}
    except Exception:
        dates = set()
        try:
            for r in list(records):
                if getattr(r, "date", None):
                    dates.add(r.date)
        except Exception:
            dates = set()

    holiday_map = get_holiday_map(dates)

    try:
        for r in records:
            name = holiday_map.get(getattr(r, "date", None))
            setattr(r, "is_holiday_date", bool(name))
            setattr(r, "holiday_name", name or "")
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Auto-absent & Exception Logic
# ---------------------------------------------------------------------------

def check_attendance_exception(employee, check_date):
    """
    Return True if the employee has a valid exception preventing an *absent* mark
    (approved leave, weekend, existing leave record).

    Args:
        employee: An Employees model instance.
        check_date: A date object.

    Returns:
        bool
    """
    from EMSwebsite.models import LeaveRequest, Attendance

    # Weekend
    if check_date.weekday() >= 5:
        return True

    # Approved leave covering this date
    if LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=check_date,
        end_date__gte=check_date,
    ).exists():
        return True

    # Existing leave-status record
    existing = Attendance.objects.filter(employee=employee, date=check_date).first()
    if existing and existing.status == 'leave':
        return True

    return False


def mark_absent_for_date(check_date, employees_queryset=None, team_filter=None):
    """
    Automatically mark employees as *absent* for ``check_date`` if they lack
    attendance records and have no valid exceptions.

    Args:
        check_date: date object.
        employees_queryset: Optional pre-filtered queryset.  Defaults to all
            active non-test employees.
        team_filter: Optional team string to further filter employees.

    Returns:
        int — total records created (absent + leave).
    """
    from EMSwebsite.models import Employees, HolidayDate, Attendance, LeaveRequest

    if HolidayDate.is_holiday(check_date):
        return 0

    is_weekend = check_date.weekday() >= 5

    if employees_queryset is None:
        employees_queryset = Employees.objects.filter(status=1).exclude(
            Q(code__icontains='test') | Q(code__icontains='dummy') |
            Q(code__icontains='sample') | Q(firstname__icontains='test') |
            Q(firstname__icontains='dummy') | Q(firstname__icontains='sample') |
            Q(lastname__icontains='test') | Q(lastname__icontains='dummy') |
            Q(lastname__icontains='sample')
        )

    if team_filter:
        employees_queryset = employees_queryset.filter(team=team_filter)

    existing_ids = Attendance.objects.filter(
        date=check_date
    ).values_list('employee_id', flat=True).distinct()

    missing = employees_queryset.exclude(id__in=existing_ids)
    absent_count = leave_count = 0

    for emp in missing:
        approved_leave = LeaveRequest.objects.filter(
            employee=emp, status='approved',
            start_date__lte=check_date, end_date__gte=check_date,
        ).first()

        if is_weekend:
            if approved_leave:
                try:
                    att = Attendance(
                        employee=emp, date=check_date, status='leave',
                        notes=f"Approved {approved_leave.get_leave_type_display()}: {approved_leave.reason[:100]}",
                    )
                    att._explicit_status = True
                    att.save()
                    leave_count += 1
                except IntegrityError:
                    pass
        else:
            if approved_leave:
                try:
                    att = Attendance(
                        employee=emp, date=check_date, status='leave',
                        notes=f"Approved {approved_leave.get_leave_type_display()}: {approved_leave.reason[:100]}",
                    )
                    att._explicit_status = True
                    att.save()
                    leave_count += 1
                except IntegrityError:
                    pass
            else:
                try:
                    att = Attendance(employee=emp, date=check_date, status='absent')
                    att._explicit_status = True
                    att.save()
                    absent_count += 1
                except IntegrityError:
                    pass
                except Exception as e:
                    logger.error("Error creating absent record for %s on %s: %s", emp.id, check_date, e)

    return absent_count + leave_count


# ---------------------------------------------------------------------------
#  Holiday ↔ Attendance Sync
# ---------------------------------------------------------------------------

def sync_holidays_with_attendance(date_range_start=None, date_range_end=None):
    """
    Reconcile existing attendance records against the current holiday calendar.
    Records on holiday dates (without check-in/out) are set to ``'holiday'``
    status; records whose holiday was deleted revert to ``'absent'`` or ``'present'``.

    Args:
        date_range_start: Optional date lower-bound.
        date_range_end: Optional date upper-bound.

    Returns:
        int — number of attendance records updated.
    """
    from EMSwebsite.models import HolidayDate, Attendance

    try:
        holiday_qs = HolidayDate.objects.all()
        if date_range_start:
            holiday_qs = holiday_qs.filter(date__gte=date_range_start)
        if date_range_end:
            holiday_qs = holiday_qs.filter(date__lte=date_range_end)
        if not holiday_qs.exists():
            return 0
        holiday_dates = {h.date: h for h in holiday_qs}
    except (ProgrammingError, Exception):
        return 0

    attendance_qs = Attendance.objects.all()
    if date_range_start:
        attendance_qs = attendance_qs.filter(date__gte=date_range_start)
    if date_range_end:
        attendance_qs = attendance_qs.filter(date__lte=date_range_end)

    updated = 0
    for att in attendance_qs:
        try:
            is_holiday = HolidayDate.is_holiday(att.date)
            needs_update = False

            if is_holiday:
                holiday = HolidayDate.get_holiday(att.date)
                holiday_note = holiday.name if holiday else "Holiday"
                if att.notes:
                    if holiday_note not in att.notes:
                        att.notes = f"{att.notes} | {holiday_note}"
                        needs_update = True
                else:
                    att.notes = holiday_note
                    needs_update = True
                if not att.check_in_time and not att.check_out_time and att.status != 'holiday':
                    att.status = 'holiday'
                    needs_update = True
            else:
                if att.status == 'holiday':
                    att.status = 'present' if (att.check_in_time or att.check_out_time) else 'absent'
                    if att.notes and 'holiday' in att.notes.lower():
                        att.notes = ''
                    needs_update = True

            if needs_update:
                att._explicit_status = True
                att.save()
                updated += 1
        except (ProgrammingError, Exception):
            continue

    return updated


# ---------------------------------------------------------------------------
#  Attendance Statistics
# ---------------------------------------------------------------------------

def get_attendance_statistics(queryset):
    """
    Compute summary statistics from an attendance queryset.

    Args:
        queryset: A filtered Attendance queryset.

    Returns:
        dict with keys: total, present, absent, late, on_leave, overtime_hours.
    """
    total = queryset.count()
    present = queryset.filter(status__in=['present', 'early-in', 'late-sitting']).count()
    absent = queryset.filter(status='absent').count()
    late = queryset.filter(status='late').count()
    on_leave = queryset.filter(status='leave').count()
    overtime = queryset.aggregate(total_ot=Sum('overtime_hours'))['total_ot'] or 0

    return {
        'total': total,
        'present': present,
        'absent': absent,
        'late': late,
        'on_leave': on_leave,
        'overtime_hours': float(overtime),
        'attendance_rate': round((present / total) * 100, 1) if total > 0 else 0,
    }
