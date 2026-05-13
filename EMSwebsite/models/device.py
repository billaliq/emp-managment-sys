from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class ZKDevice(models.Model):
    """ZKTeco biometric device configuration"""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('connecting', 'Connecting'),
        ('error', 'Error'),
    ]

    name = models.CharField(max_length=100, unique=True, help_text="Device name/identifier")
    ip_address = models.CharField(max_length=50, help_text="Device IP address")
    port = models.IntegerField(default=4370, help_text="Device port (default: 4370)")
    timeout = models.IntegerField(default=5, help_text="Connection timeout in seconds")
    password = models.CharField(max_length=50, blank=True, null=True, help_text="Device admin password (if required). Leave empty if no password.")

    serial_number = models.CharField(max_length=100, blank=True, null=True)
    device_name = models.CharField(max_length=100, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    device_model = models.CharField(max_length=50, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_connected = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, help_text="Enable/disable device monitoring")
    auto_sync = models.BooleanField(default=True, help_text="Automatically sync attendance")
    realtime_enabled = models.BooleanField(default=True, help_text="Enable real-time event monitoring")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ZK Device"
        verbose_name_plural = "ZK Devices"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"

    @property
    def is_online(self):
        return self.status == 'online'


class AttendanceLog(models.Model):
    """Real-time attendance logs from ZK device"""
    EVENT_TYPES = [
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('fingerprint', 'Fingerprint Verification'),
        ('face', 'Face Verification'),
        ('rfid', 'RFID Card'),
        ('password', 'Password'),
        ('unknown', 'Unknown'),
    ]

    device = models.ForeignKey(ZKDevice, on_delete=models.CASCADE, related_name='attendance_logs')
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='device_attendance_logs', null=True, blank=True)
    user_id = models.CharField(max_length=50, help_text="User ID from device")
    user_name = models.CharField(max_length=200, blank=True, null=True, help_text="User name from device")

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='unknown')
    timestamp = models.DateTimeField(help_text="Event timestamp from device")
    verification_mode = models.IntegerField(default=0, help_text="Verification mode (0=password, 1=fingerprint, 15=face, etc.)")

    attendance_record = models.ForeignKey('Attendance', on_delete=models.SET_NULL, null=True, blank=True, related_name='device_logs')

    raw_data = models.JSONField(null=True, blank=True, help_text="Raw event data from device")
    is_processed = models.BooleanField(default=False, help_text="Whether this log has been processed into Attendance record")
    processed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Attendance Log"
        verbose_name_plural = "Attendance Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['device', '-timestamp']),
            models.Index(fields=['employee', '-timestamp']),
            models.Index(fields=['is_processed']),
        ]

    def __str__(self):
        return f"{self.user_name or self.user_id} - {self.get_event_type_display()} @ {self.timestamp}"


class EnrollmentLog(models.Model):
    """Biometric enrollment logs (fingerprint/face)"""
    ENROLLMENT_TYPES = [
        ('fingerprint', 'Fingerprint'),
        ('face', 'Face Recognition'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    device = models.ForeignKey(ZKDevice, on_delete=models.CASCADE, related_name='enrollment_logs')
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='enrollment_logs')
    enrollment_type = models.CharField(max_length=20, choices=ENROLLMENT_TYPES)
    template_index = models.IntegerField(null=True, blank=True, help_text="Template index on device")
    template_data = models.BinaryField(null=True, blank=True, help_text="Template data (if stored)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_enrollments')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Enrollment Log"
        verbose_name_plural = "Enrollment Logs"
        ordering = ['-started_at']
        unique_together = [['device', 'employee', 'enrollment_type', 'template_index']]

    def __str__(self):
        return f"{self.employee} - {self.get_enrollment_type_display()} ({self.get_status_display()})"
