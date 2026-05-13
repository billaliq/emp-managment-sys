from django.urls import path
from EMSwebsite.views.devices import (
    device_management, device_enrollment, attendance_live,
    fetch_and_save_employees, fetch_and_save_attendance, check_device_status,
    api_device_create, api_device_delete, api_device_test_connection,
    api_device_push_user, api_device_enroll_fingerprint, api_device_cancel_enrollment,
    api_device_enroll_face, api_device_verify_enrollment,
    api_device_status, api_device_logs,
)

urlpatterns = [
    # Biometric Device Integration
    path('fetch-employees/', fetch_and_save_employees, name='fetch_employees'),
    path('device-status/', check_device_status, name='device_status'),
    path('import-attendance/', fetch_and_save_attendance, name='import_attendance'),

    # ZKTeco Device Management
    path('device/management/', device_management, name='device_management'),
    path('device/', device_management, name='device_management_alias'),
    path('device/enrollment/', device_enrollment, name='device_enrollment'),
    path('attendance/live/', attendance_live, name='attendance_live'),

    # Device API endpoints
    path('api/device/create/', api_device_create, name='api_device_create'),
    path('api/device/<int:device_id>/delete/', api_device_delete, name='api_device_delete'),
    path('api/device/test-connection/', api_device_test_connection, name='api_device_test_connection'),
    path('api/device/push-user/', api_device_push_user, name='api_device_push_user'),
    path('api/device/enroll-fingerprint/', api_device_enroll_fingerprint, name='api_device_enroll_fingerprint'),
    path('api/device/cancel-enrollment/', api_device_cancel_enrollment, name='api_device_cancel_enrollment'),
    path('api/device/enroll-face/', api_device_enroll_face, name='api_device_enroll_face'),
    path('api/device/verify-enrollment/', api_device_verify_enrollment, name='api_device_verify_enrollment'),
    path('api/device/<int:device_id>/status/', api_device_status, name='api_device_status'),
    path('api/device/<int:device_id>/logs/', api_device_logs, name='api_device_logs'),
]
