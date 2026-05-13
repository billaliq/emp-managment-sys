from django.db import models
from django.conf import settings


class Notification(models.Model):
    """System notifications for employees, admin, and finance"""
    NOTIFICATION_TYPES = [
        ('increment', 'Salary Increment'),
        ('birthday', 'Birthday'),
        ('payroll', 'Payroll'),
        ('leave', 'Leave Request'),
        ('attendance', 'Attendance'),
        ('system', 'System Notification'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_object_id = models.IntegerField(null=True, blank=True, help_text="ID of related object (e.g., increment ID)")
    related_object_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of related object")

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', 'created_at']),
        ]
