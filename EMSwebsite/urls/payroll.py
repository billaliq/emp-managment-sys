from django.urls import path
from EMSwebsite.controllers.payroll import (
    payroll, process_payroll, update_payroll_record, payroll_record_detail,
    request_salary_slip, approve_salary_slip, payroll_print,
    payroll_export_csv, payroll_export_excel, add_increment,
    api_get_payrolls, api_process_payroll, api_update_payroll_record,
    api_add_increment, api_get_increments,
    search_employees_payroll, bulk_salary_disbursement,
    get_disbursement_details, list_disbursements,
)

urlpatterns = [
    path('payroll/', payroll, name='payroll'),
    path('payroll/process/', process_payroll, name='process_payroll'),
    path('payroll/record/update/<int:pk>/', update_payroll_record, name='update_payroll_record'),
    path('payroll/record/<int:pk>/', payroll_record_detail, name='payroll_record_detail'),
    path('payroll/print/', payroll_print, name='payroll_print'),
    path('payroll/print/<int:pk>/', payroll_print, name='payroll_print_record'),
    path('payroll/record/<int:pk>/request-slip/', request_salary_slip, name='request_salary_slip'),
    path('payroll/slip-request/<int:pk>/approve/', approve_salary_slip, name='approve_salary_slip'),
    path('payroll/export/csv/', payroll_export_csv, name='payroll_export_csv'),
    path('payroll/export/excel/', payroll_export_excel, name='payroll_export_excel'),
    path('increments/add/', add_increment, name='add_increment'),

    # Payroll API
    path('api/payrolls/', api_get_payrolls, name='api_get_payrolls'),
    path('api/process-payroll/', api_process_payroll, name='api_process_payroll'),
    path('api/payroll-record/<int:pk>/update/', api_update_payroll_record, name='api_update_payroll_record'),
    path('api/increments/', api_get_increments, name='api_get_increments'),
    path('api/add-increment/', api_add_increment, name='api_add_increment'),

    # Salary Disbursement
    path('api/payroll/search-employees/', search_employees_payroll, name='search_employees_payroll'),
    path('api/payroll/bulk-disbursement/', bulk_salary_disbursement, name='bulk_salary_disbursement'),
    path('api/payroll/disbursements/', list_disbursements, name='list_disbursements'),
    path('api/payroll/disbursement/<str:disbursement_id>/', get_disbursement_details, name='get_disbursement_details'),
]
