from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta
from django.contrib.auth.models import User


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('early-in', 'Early-in'),
        ('early-out', 'Early-out'),
        ('leave', 'On Leave'),
        ('overtime', 'Overtime'),
        ('late-sitting', 'Late Sitting'),
        ('weekend', 'Weekend Work'),
    ]

    LEAVE_TYPES = [
        ('sick', 'Sick Leave'),
        ('vacation', 'Vacation'),
        ('personal', 'Personal Leave'),
        ('annual', 'Annual Leave'),
        ('business', 'Business Leave'),
        ('other', 'Other Leave'),
        ('', 'No Leave'),
    ]

    employee = models.ForeignKey(
        'Employees', on_delete=models.CASCADE, related_name='attendance_records'
    )
    date = models.DateField()

    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    timetable = models.CharField(max_length=50, blank=True, null=True)
    actual_work = models.DurationField(blank=True, null=True)
    required_work = models.DurationField(blank=True, null=True)
    late_in = models.DurationField(blank=True, null=True)
    early_out = models.DurationField(blank=True, null=True)
    break_time = models.DurationField(blank=True, null=True)
    late_sitting = models.DurationField(blank=True, null=True)

    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, blank=True, null=True)

    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    reason = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'Employees', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_attendance_records'
    )

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date', 'employee__firstname']
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.status})"

    def get_office_timings(self):
        """Get office timings for this attendance record based on employee's department"""
        if self.employee and self.employee.department:
            dept = self.employee.department
            office_start = dept.get_office_start_time()
            office_end = dept.get_office_end_time()
            late_threshold = dept.get_late_threshold()
            late_sitting_threshold = dept.get_late_sitting_threshold()
        else:
            try:
                s = AttendanceSettings.objects.first()
                if s:
                    office_start = s.work_start_time
                    office_end = s.work_end_time
                    grace_minutes = s.grace_period_minutes
                    start_datetime = datetime.combine(timezone.now().date(), office_start)
                    late_threshold_datetime = start_datetime + timedelta(minutes=grace_minutes)
                    late_threshold = late_threshold_datetime.time()
                    end_datetime = datetime.combine(timezone.now().date(), office_end)
                    late_sitting_datetime = end_datetime + timedelta(minutes=30)
                    late_sitting_threshold = late_sitting_datetime.time()
                else:
                    office_start = time(9, 0)
                    office_end = time(18, 0)
                    late_threshold = time(9, 15)
                    late_sitting_threshold = time(18, 30)
            except:
                office_start = time(9, 0)
                office_end = time(18, 0)
                late_threshold = time(9, 15)
                late_sitting_threshold = time(18, 30)

        return {
            'office_start': office_start,
            'office_end': office_end,
            'late_threshold': late_threshold,
            'late_sitting_threshold': late_sitting_threshold
        }

    def calculate_durations(self):
        """Calculate all duration fields automatically based on check-in/check-out times"""
        timings = self.get_office_timings()
        office_start = timings['office_start']
        office_end = timings['office_end']
        late_threshold = timings['late_threshold']
        late_sitting_threshold = timings['late_sitting_threshold']

        self.late_in = timedelta(0)
        self.early_out = timedelta(0)
        self.late_sitting = timedelta(0)

        if self.check_in_time or self.check_out_time:
            today = self.date if hasattr(self, 'date') and self.date else timezone.now().date()

            if self.check_in_time:
                if self.check_in_time > late_threshold:
                    check_in_dt = datetime.combine(today, self.check_in_time)
                    late_threshold_dt = datetime.combine(today, late_threshold)
                    self.late_in = check_in_dt - late_threshold_dt
                else:
                    self.late_in = timedelta(0)

            if self.check_out_time:
                if self.check_out_time < office_end:
                    check_out_dt = datetime.combine(today, self.check_out_time)
                    office_end_dt = datetime.combine(today, office_end)
                    self.early_out = office_end_dt - check_out_dt
                else:
                    self.early_out = timedelta(0)

            if self.check_out_time:
                if self.check_out_time > late_sitting_threshold:
                    check_out_dt = datetime.combine(today, self.check_out_time)
                    late_sitting_start_dt = datetime.combine(today, late_sitting_threshold)
                    self.late_sitting = check_out_dt - late_sitting_start_dt
                else:
                    self.late_sitting = timedelta(0)

            if self.check_in_time and self.check_out_time:
                check_in = datetime.combine(today, self.check_in_time)
                check_out = datetime.combine(today, self.check_out_time)
                if check_out < check_in:
                    check_out += timedelta(days=1)
                work_duration = check_out - check_in
                if self.break_time:
                    work_duration -= self.break_time
                self.actual_work = work_duration

    def auto_determine_status(self):
        is_weekend = self.is_weekend_date
        timings = self.get_office_timings()
        office_start = timings['office_start']
        office_end = timings['office_end']
        late_threshold = timings['late_threshold']
        late_sitting_threshold = timings['late_sitting_threshold']

        if self.leave_type:
            return 'leave'

        if not self.check_in_time and not self.check_out_time:
            if is_weekend:
                return 'weekend'
            return 'absent'

        if is_weekend:
            pass

        if self.check_out_time and self.check_out_time > late_sitting_threshold:
            return 'late-sitting'
        if self.check_out_time and self.check_out_time < office_end:
            return 'early-out'
        if self.check_in_time and self.check_in_time > late_threshold:
            return 'late'
        if self.check_in_time and self.check_in_time < office_start:
            return 'early-in'
        return 'present'

    @property
    def duration(self):
        if self.actual_work:
            total_seconds = self.actual_work.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif self.check_in_time and self.check_out_time:
            today = timezone.now().date()
            check_in = datetime.combine(today, self.check_in_time)
            check_out = datetime.combine(today, self.check_out_time)
            if check_out < check_in:
                check_out += timedelta(days=1)
            work_duration = check_out - check_in
            total_seconds = work_duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        return "--"

    @property
    def duration_decimal(self):
        if self.actual_work:
            return round(self.actual_work.total_seconds() / 3600, 2)
        return 0.0

    @staticmethod
    def _format_hm(delta):
        if not delta:
            return ""
        try:
            total_seconds = delta.total_seconds()
        except (AttributeError, TypeError):
            return ""
        if total_seconds <= 0:
            return ""
        total_minutes = int(total_seconds // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h {minutes:02d}m"

    @property
    def overtime_display(self):
        if self.overtime_hours > 0:
            hours = int(self.overtime_hours)
            minutes = int((self.overtime_hours % 1) * 60)
            return f"{hours}h {minutes:02d}m"
        return "--"

    @property
    def late_in_display(self):
        return self._format_hm(self.late_in)

    @property
    def early_out_display(self):
        return self._format_hm(self.early_out)

    @property
    def is_weekend_date(self):
        return self.date.weekday() >= 5

    @property
    def simplified_status(self):
        if self.status == 'leave':
            return 'leave'
        if self.status == 'weekend':
            if self.check_in_time or self.check_out_time:
                return 'present'
            return 'weekend_no_attendance'
        if self.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting']:
            return 'present'
        elif self.status == 'absent':
            return 'absent'
        else:
            return 'absent'

    @property
    def simplified_status_display(self):
        status = self.simplified_status
        if status == 'weekend_no_attendance':
            return None
        if status == 'present':
            return 'Present'
        elif status == 'leave':
            return 'Leave'
        else:
            return 'Absent'

    def save(self, *args, **kwargs):
        self.calculate_durations()
        has_attendance_data = self.check_in_time or self.check_out_time
        if has_attendance_data:
            self.status = self.auto_determine_status()
            self._explicit_status = False
        elif not getattr(self, "_explicit_status", False):
            if not self.status:
                self.status = 'absent'
        if self.late_sitting and self.late_sitting.total_seconds() > 0:
            self.overtime_hours = round(self.late_sitting.total_seconds() / 3600, 2)
        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.check_in_time and self.check_out_time:
            today = timezone.now().date()
            check_in = datetime.combine(today, self.check_in_time)
            check_out = datetime.combine(today, self.check_out_time)
            if check_out < check_in:
                check_out += timedelta(days=1)
            duration = check_out - check_in
            if duration.total_seconds() > 86400:
                raise ValidationError("Work duration cannot exceed 24 hours.")
        if self.overtime_hours < 0:
            raise ValidationError("Overtime hours cannot be negative.")


class AttendanceSettings(models.Model):
    """Global attendance settings"""
    work_start_time = models.TimeField(default='09:00')
    work_end_time = models.TimeField(default='18:00')
    grace_period_minutes = models.PositiveIntegerField(default=15, help_text="Grace period in minutes for late arrival")
    minimum_work_hours = models.DecimalField(max_digits=3, decimal_places=1, default=8.0, help_text="Minimum required work hours per day")
    overtime_threshold_hours = models.DecimalField(max_digits=3, decimal_places=1, default=8.0, help_text="Hours after which overtime starts")
    weekend_work_allowed = models.BooleanField(default=True)
    auto_checkout_enabled = models.BooleanField(default=False, help_text="Automatically check out employees at end of work day")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attendance Settings"
        verbose_name_plural = "Attendance Settings"

    def __str__(self):
        return f"Attendance Settings ({self.work_start_time} - {self.work_end_time})"


class HolidayDate(models.Model):
    """Model to store holiday dates"""
    date = models.DateField(unique=True, verbose_name="Holiday Date")
    name = models.CharField(max_length=200, verbose_name="Holiday Name")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_holiday_dates', verbose_name="Created By"
    )

    class Meta:
        verbose_name = "Holiday Date"
        verbose_name_plural = "Holiday Dates"
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} ({self.date})"

    @staticmethod
    def is_holiday(check_date):
        return HolidayDate.objects.filter(date=check_date).exists()

    @staticmethod
    def get_holiday(check_date):
        return HolidayDate.objects.filter(date=check_date).first()


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('sick', 'Sick Leave'),
        ('casual', 'Casual Leave'),
        ('annual', 'Annual Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('emergency', 'Emergency Leave'),
        ('unpaid', 'Unpaid Leave'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leave_requests')
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    applied_on = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_on']
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date} to {self.end_date})"

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    def clean(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError("End date cannot be before start date.")
            if self.start_date < timezone.now().date():
                raise ValidationError("Leave cannot be applied for past dates.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
