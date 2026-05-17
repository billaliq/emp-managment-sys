from django.urls import path
from EMSwebsite.controllers.attendance import (
    attendance, employee_attendance, generate_attendance_pdf, attendance_dashboard,
    attendance_list, mark_attendance, update_attendance, delete_attendance,
    get_attendance_json, attendance_statistics, export_attendance, attendance_filter_ajax,
    holiday_list, holiday_add, holiday_edit, holiday_delete,
)

urlpatterns = [
    path('attendance/', attendance, name='attendance'),
    path('attendance/employee/<int:employee_id>/', employee_attendance, name='employee_attendance'),
    path('attendance/pdf/', generate_attendance_pdf, name='attendance_pdf'),
    path('attendance/dashboard/', attendance_dashboard, name='attendance_dashboard'),
    path('attendance/list/', attendance_list, name='attendance_list'),
    path('attendance/mark/', mark_attendance, name='mark_attendance'),
    path('attendance/update/<int:pk>/', update_attendance, name='update_attendance'),
    path('attendance/delete/<int:pk>/', delete_attendance, name='delete_attendance'),
    path('attendance/json/<int:pk>/', get_attendance_json, name='get_attendance_json'),
    path('attendance/statistics/', attendance_statistics, name='attendance_statistics'),
    path('attendance/export/', export_attendance, name='export_attendance'),
    path('attendance/filter-ajax/', attendance_filter_ajax, name='attendance_filter_ajax'),

    # Holiday Dates Management
    path('holidays/list/', holiday_list, name='holiday_list'),
    path('holidays/add/', holiday_add, name='holiday_add'),
    path('holidays/edit/<int:pk>/', holiday_edit, name='holiday_edit'),
    path('holidays/delete/<int:pk>/', holiday_delete, name='holiday_delete'),
]
