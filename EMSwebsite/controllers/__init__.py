# EMSwebsite/views/__init__.py
# Re-export all view functions for backward compatibility

from .helpers import (
    validate_date, get_current_employee, scope_by_user, only_me_employee_qs,
    role_required, admin_required, hr_or_admin_required, finance_or_admin_required,
    has_valid_attendance_exception, auto_mark_absent_for_date, sync_attendance_with_holidays,
)

from .auth import login_view, logout_view, test_email, send_birthday_emails_manual

from .dashboard import dashboard

from .positions import positions, add_position, update_position, delete_position

from .employees import (
    employee_profile, download_document, update_document, delete_document,
    create_additional_document, employee, add_employee, update_employee,
    delete_employee, get_employee, get_employee_json, update_employee_field,
    update_employee_photo, reset_employee_password, get_employee_password,
    clear_employee_password, generate_next_employee_id,
)

from .attendance import (
    attendance, employee_attendance, attendance_dashboard, attendance_list,
    mark_attendance, update_attendance, delete_attendance, get_attendance_json,
    attendance_statistics, export_attendance, attendance_filter_ajax,
    generate_attendance_pdf,
    holiday_list, holiday_add, holiday_edit, holiday_delete,
)

from .departments import (
    departments, department_create, department_update, department_delete,
    get_department_json, get_department_employees, assign_employees_to_department,
)

from .teams import (
    team, add_team, team_details, team_members_attendance, update_team,
    add_team_members, remove_team_member, available_employees, add_project,
    delete_team, employee_details,
)

from .payroll import (
    payroll, process_payroll, update_payroll_record, payroll_record_detail,
    request_salary_slip, approve_salary_slip, payroll_print,
    payroll_export_csv, payroll_export_excel, add_increment,
    api_get_payrolls, api_process_payroll, api_update_payroll_record,
    api_add_increment, api_get_increments,
    search_employees_payroll, bulk_salary_disbursement,
    process_bank_api_disbursement, get_disbursement_details, list_disbursements,
)

from .loans import (
    loans, create_loan, update_loan_status, add_repayment,
    get_loan_details, get_loan_repayments, export_loans_report,
    manage_loan_pool, get_loan_pool_status, get_employee_loan_eligibility,
)

from .reports import (
    reports_dashboard as reports, generate_report, view_report, download_report,
    delete_report, generate_from_template, get_report_status, get_recent_reports,
)

from .settings_views import (
    settings, update_settings_ajax, get_settings_ajax,
    get_increment_settings, update_increment_settings,
)

from .notifications import (
    api_notifications, mark_all_notifications_read, mark_notification_read,
)

from .ai_assistant import (
    ai_assistant, ai_chat_api,
)

from .complaints import (
    policy_management, submit_complaint, view_complaints, respond_to_complaint,
)

from .devices import (
    device_management, device_enrollment, attendance_live,
    fetch_and_save_employees, fetch_and_save_attendance, check_device_status,
    start_sync_on_django_start,
    api_device_create, api_device_delete, api_device_test_connection,
    api_device_push_user, api_device_enroll_fingerprint, api_device_cancel_enrollment,
    api_device_enroll_face, api_device_verify_enrollment,
    api_device_status, api_device_logs,
)
