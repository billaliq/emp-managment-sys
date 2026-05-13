from django.urls import path
from EMSwebsite.views.departments import (
    departments, department_create, department_update, department_delete,
    get_department_json, get_department_employees, assign_employees_to_department,
)

urlpatterns = [
    path('departments/', departments, name='departments'),
    path('departments/create/', department_create, name='department_create'),
    path('departments/update/<int:pk>/', department_update, name='department_update'),
    path('departments/delete/<int:pk>/', department_delete, name='department_delete'),
    path('departments/<int:pk>/', get_department_json, name='get_department_json'),
    path('departments/<int:pk>/employees/', get_department_employees, name='get_department_employees'),
    path('departments/<int:pk>/assign/', assign_employees_to_department, name='assign_employees_to_department'),
]
