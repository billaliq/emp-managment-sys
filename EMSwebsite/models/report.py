from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Report(models.Model):
    """Model for storing generated reports"""
    REPORT_TYPES = [
        ('employee', 'Employee Report'),
        ('payroll', 'Payroll Report'),
        ('attendance', 'Attendance Report'),
        ('department', 'Department Report'),
        ('leave', 'Leave Report'),
        ('loan', 'Loan Report'),
    ]
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    DATE_RANGE_CHOICES = [
        ('last_week', 'Last Week'),
        ('last_month', 'Last Month'),
        ('last_quarter', 'Last Quarter'),
        ('last_year', 'Last Year'),
        ('custom', 'Custom Range'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    report_name = models.CharField(max_length=200)
    date_range = models.CharField(max_length=50, choices=DATE_RANGE_CHOICES)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='pdf')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    include_charts = models.BooleanField(default=True)
    include_summary = models.BooleanField(default=True)
    include_raw_data = models.BooleanField(default=False)
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.CharField(max_length=50, null=True, blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    report_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-generated_on']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.generated_on.strftime('%Y-%m-%d')}"

    def get_file_size_display(self):
        if not self.file_path:
            return 'N/A'
        try:
            size = self.file_path.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except:
            return self.file_size or 'N/A'

    def mark_completed(self):
        self.status = 'completed'
        self.completed_on = timezone.now()
        if self.file_path:
            self.file_size = self.get_file_size_display()
        self.save()

    def mark_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.completed_on = timezone.now()
        self.save()


class ReportTemplate(models.Model):
    """Model for report templates"""
    REPORT_TYPES = [
        ('employee', 'Employee Report'),
        ('payroll', 'Payroll Report'),
        ('attendance', 'Attendance Report'),
        ('department', 'Department Report'),
        ('leave', 'Leave Report'),
        ('loan', 'Loan Report'),
    ]

    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    description = models.TextField()
    icon_class = models.CharField(max_length=50, default='fas fa-file-alt')
    color = models.CharField(max_length=50, default='#6366f1')
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    last_generated = models.DateTimeField(null=True, blank=True)
    default_format = models.CharField(max_length=20, default='pdf')
    default_date_range = models.CharField(max_length=50, default='last_month')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_templates'
        ordering = ['report_type', 'name']
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'

    def __str__(self):
        return self.name

    def increment_usage(self):
        self.usage_count += 1
        self.last_generated = timezone.now()
        self.save()


class ReportSchedule(models.Model):
    """Model for scheduled reports"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]

    name = models.CharField(max_length=200)
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    is_active = models.BooleanField(default=True)
    email_recipients = models.TextField(help_text="Comma-separated email addresses")
    next_run = models.DateTimeField()
    last_run = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'report_schedules'
        ordering = ['next_run']
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'

    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"
