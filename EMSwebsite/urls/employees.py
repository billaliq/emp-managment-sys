from django.urls import path
from EMSwebsite.views.employees import (
    employee_profile, update_employee_field, update_employee_photo,
    reset_employee_password, get_employee_password, clear_employee_password,
    download_document, update_document, delete_document, create_additional_document,
    employee, add_employee, update_employee, delete_employee,
    get_employee_json, get_employee,
)

urlpatterns = [
    # Employee Profile
    path('employee-profile/', employee_profile, name='employee_profile'),
    path('employee/<str:employee_id>/update-field/', update_employee_field, name='update_employee_field'),
    path('employee/<str:employee_id>/update-photo/', update_employee_photo, name='update_employee_photo'),
    path('employee/<str:employee_id>/reset-password/', reset_employee_password, name='reset_employee_password'),
    path('employee/<str:employee_id>/get-password/', get_employee_password, name='get_employee_password'),
    path('employee/<str:employee_id>/clear-password/', clear_employee_password, name='clear_employee_password'),
    path('employee/<str:employee_id>/document/<str:document_type>/download/', download_document, name='download_document'),
    path('employee/<str:employee_id>/document/<str:document_type>/update/', update_document, name='update_document'),
    path('employee/<str:employee_id>/document/<str:document_type>/delete/', delete_document, name='delete_document'),
    path('employee/<str:employee_id>/additional-document/create/', create_additional_document, name='create_additional_document'),

    # Employee CRUD
    path('employee/', employee, name='employee'),
    path('employee/add/', add_employee, name='add_employee'),
    path('employee/update/<int:pk>/', update_employee, name='update_employee'),
    path('employee/delete/<int:pk>/', delete_employee, name='delete_employee'),
    path('employee/json/<int:pk>/', get_employee_json, name='get_employee_json'),
    path('api/employee/<str:employee_id>/', get_employee, name='get_employee'),
]
