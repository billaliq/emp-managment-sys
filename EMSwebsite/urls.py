from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import forms as EMSwebsite_forms
from django.conf import settings
from django.conf.urls.static import static
from .views import *

urlpatterns = [
        # urls.py (add to urlpatterns)
        # Forced reload for ZK updates (debug logging)
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('test-email/', views.test_email, name='test_email'),
    path('send-birthday-emails/', views.send_birthday_emails_manual, name='send_birthday_emails'),

    # Password Reset URLs
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='pages/password_reset.html',
             email_template_name='pages/password_reset_email.html',
             subject_template_name='pages/password_reset_subject.txt',
             success_url='/password_reset/done/',
             html_email_template_name='pages/password_reset_email.html',
             extra_email_context={'site_name': 'Employee Information System'},
             form_class=EMSwebsite_forms.CustomPasswordResetForm
         ),
         name='password_reset'),

    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='pages/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='pages/password_reset_confirm.html',
             success_url='/reset/done/',
             post_reset_login=False
         ),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='pages/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # Basic pages
    path('', views.dashboard, name='dashboard'),
    path('employee/', views.employee, name='employee'),
    path('positions/', views.positions, name='positions'),
    path('payroll/', views.payroll, name='payroll'),
    path('payroll/process/', views.process_payroll, name='process_payroll'),
    path('payroll/record/update/<int:pk>/', views.update_payroll_record, name='update_payroll_record'),
    path('payroll/record/<int:pk>/', views.payroll_record_detail, name='payroll_record_detail'),
    path('payroll/print/', views.payroll_print, name='payroll_print'),
    path('payroll/print/<int:pk>/', views.payroll_print, name='payroll_print_record'),
    path('payroll/record/<int:pk>/request-slip/', views.request_salary_slip, name='request_salary_slip'),
    path('payroll/slip-request/<int:pk>/approve/', views.approve_salary_slip, name='approve_salary_slip'),
    path('payroll/export/csv/', views.payroll_export_csv, name='payroll_export_csv'),
    path('payroll/export/excel/', views.payroll_export_excel, name='payroll_export_excel'),
    path('increments/add/', views.add_increment, name='add_increment'),
    path('loans/', views.loans, name='loans'),
    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),
    path('team/', views.team, name='team'),
    path('departments/', views.departments, name='departments'),

    #Employee Profile
    path('employee-profile/', views.employee_profile, name='employee_profile'),
    path('employee/<str:employee_id>/update-field/', views.update_employee_field, name='update_employee_field'),
    path('employee/<str:employee_id>/update-photo/', views.update_employee_photo, name='update_employee_photo'),
    path('employee/<str:employee_id>/reset-password/', views.reset_employee_password, name='reset_employee_password'),
    path('employee/<str:employee_id>/get-password/', views.get_employee_password, name='get_employee_password'),
    path('employee/<str:employee_id>/clear-password/', views.clear_employee_password, name='clear_employee_password'),
    path(
        'employee/<str:employee_id>/document/<str:document_type>/download/',
        views.download_document,
        name='download_document',
    ),
    path(
        'employee/<str:employee_id>/document/<str:document_type>/update/',
        views.update_document,
        name='update_document',
    ),
    path(
        'employee/<str:employee_id>/document/<str:document_type>/delete/',
        views.delete_document,
        name='delete_document',
    ),
    path(
        'employee/<str:employee_id>/additional-document/create/',
        views.create_additional_document,
        name='create_additional_document',
    ),

    # Employee CRUD
    path('employee/add/', views.add_employee, name='add_employee'),
    path('employee/update/<int:pk>/', views.update_employee, name='update_employee'),
    path('employee/delete/<int:pk>/', views.delete_employee, name='delete_employee'),
    path('employee/json/<int:pk>/', views.get_employee_json, name='get_employee_json'),
    path('api/employee/<str:employee_id>/', views.get_employee, name='get_employee'),

    # Department CRUD
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/update/<int:pk>/', views.department_update, name='department_update'),
    path('departments/delete/<int:pk>/', views.department_delete, name='department_delete'),
    path('departments/<int:pk>/', views.get_department_json, name='get_department_json'),
    path('departments/<int:pk>/employees/', views.get_department_employees, name='get_department_employees'),
    path('departments/<int:pk>/assign/', views.assign_employees_to_department, name='assign_employees_to_department'),

    # Attendance routes - CORRECTED
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/employee/<int:employee_id>/', views.employee_attendance, name='employee_attendance'),

    # ✅ Attendance PDF export
    path('attendance/pdf/', views.generate_attendance_pdf, name='attendance_pdf'),
    path('attendance/dashboard/', views.attendance_dashboard, name='attendance_dashboard'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/update/<int:pk>/', views.update_attendance, name='update_attendance'),
    path('attendance/delete/<int:pk>/', views.delete_attendance, name='delete_attendance'),
    path('attendance/json/<int:pk>/', views.get_attendance_json, name='get_attendance_json'),
    path('attendance/statistics/', views.attendance_statistics, name='attendance_statistics'),
    path('attendance/export/', views.export_attendance, name='export_attendance'),
    path('attendance/filter-ajax/', views.attendance_filter_ajax, name='attendance_filter_ajax'),

    # Holiday Dates Management
    path('holidays/list/', views.holiday_list, name='holiday_list'),
    path('holidays/add/', views.holiday_add, name='holiday_add'),
    path('holidays/edit/<int:pk>/', views.holiday_edit, name='holiday_edit'),
    path('holidays/delete/<int:pk>/', views.holiday_delete, name='holiday_delete'),

    # Position CRUD
    path('positions/add/', views.add_position, name='add_position'),
    path('positions/update/<int:pk>/', views.update_position, name='update_position'),
    path('positions/delete/<int:pk>/', views.delete_position, name='delete_position'),

    # Team URLs
    path('teams/', views.team, name='teams'),
    path('teams/add/', views.add_team, name='add_team'),
    path('teams/<int:team_id>/details/', views.team_details, name='team_details'),
    path('teams/<int:team_id>/attendance/', views.team_members_attendance, name='team_members_attendance'),
    path('teams/update/', views.update_team, name='update_team'),
    path('teams/add-members/', views.add_team_members, name='add_team_members'),
    path('teams/remove-member/', views.remove_team_member, name='remove_team_member'),
    path('teams/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('teams/add-project/', views.add_project, name='add_project'),
    path('employees/available/', views.available_employees, name='available_employees'),

    # Payroll URLs
    path('api/payrolls/', views.api_get_payrolls, name='api_get_payrolls'),
    path('api/process-payroll/', views.api_process_payroll, name='api_process_payroll'),
    path('api/payroll-record/<int:pk>/update/', views.api_update_payroll_record, name='api_update_payroll_record'),
    path('api/increments/', views.api_get_increments, name='api_get_increments'),
    path('api/add-increment/', views.api_add_increment, name='api_add_increment'),

    # Salary Disbursement URLs (Bank API Integration)
    path('api/payroll/search-employees/', views.search_employees_payroll, name='search_employees_payroll'),
    path('api/payroll/bulk-disbursement/', views.bulk_salary_disbursement, name='bulk_salary_disbursement'),
    path('api/payroll/disbursements/', views.list_disbursements, name='list_disbursements'),
    path('api/payroll/disbursement/<str:disbursement_id>/', views.get_disbursement_details, name='get_disbursement_details'),

    # Loan URLs
    path('loans/create/', views.create_loan, name='create_loan'),
    path('loans/update-status/', views.update_loan_status, name='update_loan_status'),
    path('loans/add-repayment/', views.add_repayment, name='add_repayment'),
    path('loans/<int:loan_id>/details/', views.get_loan_details, name='get_loan_details'),
    path('loans/<int:loan_id>/repayments/', views.get_loan_repayments, name='get_loan_repayments'),
    path('loans/export-report/', views.export_loans_report, name='export_loans_report'),

    # Loan Pool Management URLs
    path('loans/pool/manage/', views.manage_loan_pool, name='manage_loan_pool'),
    path('loans/pool/status/', views.get_loan_pool_status, name='get_loan_pool_status'),
    path('loans/eligibility/<int:employee_id>/', views.get_employee_loan_eligibility, name='get_employee_loan_eligibility'),

    # Reports sub-routes (these should be under reports/ prefix)
    path('reports/view/<uuid:report_id>/', views.view_report, name='view_report'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/download/<uuid:report_id>/', views.download_report, name='download_report'),
    path('reports/delete/<uuid:report_id>/', views.delete_report, name='delete_report'),
    path('reports/template/<int:template_id>/', views.generate_from_template, name='generate_from_template'),
    path('reports/status/<uuid:report_id>/', views.get_report_status, name='get_report_status'),
    path('reports/recent/', views.get_recent_reports, name='get_recent_reports'),

    # Settings AJAX endpoints
    path('api/settings/update/', views.update_settings_ajax, name='update_settings_ajax'),
    path('api/settings/get/', views.get_settings_ajax, name='get_settings_ajax'),

    # Increment Settings endpoints
    path('api/increment-settings/', views.get_increment_settings, name='get_increment_settings'),
    path('api/increment-settings/update/', views.update_increment_settings, name='update_increment_settings'),

    # Biometric Device Integration
    path('fetch-employees/', fetch_and_save_employees, name='fetch_employees'),
    path('device-status/', check_device_status, name='device_status'),
    path('import-attendance/', fetch_and_save_attendance, name='import_attendance'),

    # AI Employee Assistant
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    path('api/ai-chat/', views.ai_chat_api, name='ai_chat_api'),

    # Policy Management (Admin/HR only)
    path('policies/', views.policy_management, name='policy_management'),

    # Complaints
    path('complaints/', views.view_complaints, name='view_complaints'),
    path('complaints/submit/', views.submit_complaint, name='submit_complaint'),
    path('complaints/<int:complaint_id>/respond/', views.respond_to_complaint, name='respond_to_complaint'),

    # ZKTeco Device Management
    path('device/management/', views.device_management, name='device_management'),

    path('device/', views.device_management, name='device_management'),  # Alias for easier access
    path('device/enrollment/', views.device_enrollment, name='device_enrollment'),
    path('attendance/live/', views.attendance_live, name='attendance_live'),

    # Device API endpoints
    path('api/device/create/', views.api_device_create, name='api_device_create'),
    path('api/device/<int:device_id>/delete/', views.api_device_delete, name='api_device_delete'),
    path('api/device/test-connection/', views.api_device_test_connection, name='api_device_test_connection'),
    path('api/device/push-user/', views.api_device_push_user, name='api_device_push_user'),
    path('api/device/enroll-fingerprint/', views.api_device_enroll_fingerprint, name='api_device_enroll_fingerprint'),
    path('api/device/cancel-enrollment/', views.api_device_cancel_enrollment, name='api_device_cancel_enrollment'),
    path('api/device/enroll-face/', views.api_device_enroll_face, name='api_device_enroll_face'),
    path('api/device/verify-enrollment/', views.api_device_verify_enrollment, name='api_device_verify_enrollment'),
    path('api/device/<int:device_id>/status/', views.api_device_status, name='api_device_status'),
    path('api/device/<int:device_id>/logs/', views.api_device_logs, name='api_device_logs'),


]
