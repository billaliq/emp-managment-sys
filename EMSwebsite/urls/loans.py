from django.urls import path
from EMSwebsite.views.loans import (
    loans, create_loan, update_loan_status, add_repayment,
    get_loan_details, get_loan_repayments, export_loans_report,
    manage_loan_pool, get_loan_pool_status, get_employee_loan_eligibility,
)

urlpatterns = [
    path('loans/', loans, name='loans'),
    path('loans/create/', create_loan, name='create_loan'),
    path('loans/update-status/', update_loan_status, name='update_loan_status'),
    path('loans/add-repayment/', add_repayment, name='add_repayment'),
    path('loans/<int:loan_id>/details/', get_loan_details, name='get_loan_details'),
    path('loans/<int:loan_id>/repayments/', get_loan_repayments, name='get_loan_repayments'),
    path('loans/export-report/', export_loans_report, name='export_loans_report'),
    path('loans/pool/manage/', manage_loan_pool, name='manage_loan_pool'),
    path('loans/pool/status/', get_loan_pool_status, name='get_loan_pool_status'),
    path('loans/eligibility/<int:employee_id>/', get_employee_loan_eligibility, name='get_employee_loan_eligibility'),
]
