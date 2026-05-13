# EMSwebsite/services/__init__.py
"""
Services layer — encapsulates business logic independently of HTTP request/response.

Each service module provides pure-logic functions that can be called from views,
management commands, signal handlers, or tests without needing a Django request object.
"""

from .attendance_service import (
    get_holiday_map,
    attach_holiday_fields,
    check_attendance_exception,
    mark_absent_for_date,
    sync_holidays_with_attendance,
    get_attendance_statistics,
)

from .payroll_service import (
    calculate_net_salary,
    process_payroll_for_employees,
    calculate_increment,
    get_payroll_summary,
    build_payroll_queryset,
)

from .report_service import (
    get_user_role,
    check_report_access,
    extract_employee_data,
    extract_payroll_data,
    extract_attendance_data,
    extract_department_data,
    extract_leave_data,
    extract_loan_data,
    calculate_date_range,
    build_report_name,
)
