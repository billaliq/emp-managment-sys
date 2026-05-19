from django.urls import path
from EMSwebsite.controllers.tasks import (
    task_list, task_create, task_delete,
    task_update_status, run_assignment, assignment_result,
)

urlpatterns = [
    path('tasks/', task_list, name='task_list'),
    path('tasks/create/', task_create, name='task_create'),
    path('tasks/<int:task_id>/delete/', task_delete, name='task_delete'),
    path('tasks/<int:task_id>/status/', task_update_status, name='task_update_status'),
    path('tasks/run-assignment/', run_assignment, name='run_assignment'),
    path('tasks/assignment-result/', assignment_result, name='assignment_result'),
]
