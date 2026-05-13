from django.urls import path
from EMSwebsite.views.notifications import (
    api_notifications, mark_all_notifications_read, mark_notification_read,
)

urlpatterns = [
    path('api/notifications/', api_notifications, name='api_notifications'),
    path('api/notifications/mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/notifications/<int:notification_id>/mark-read/', mark_notification_read, name='mark_notification_read'),
]
