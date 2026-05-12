from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models import Sum
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
import re

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models import Sum
from decimal import Decimal
from django.contrib.auth.models import User

# Department Model (moved to top to avoid forward reference issues)
class Department(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateField(default=timezone.now)
    updated_at = models.DateField(auto_now=True)

    # Department-specific office timings (optional - falls back to global settings if not set)
    use_custom_timings = models.BooleanField(
        default=False,
        help_text="Enable custom office timings for this department. If disabled, uses global attendance settings."
    )
    office_start_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Department check-in time (e.g., 09:00). Leave empty to use global settings."
    )
    office_end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Department check-out time (e.g., 18:00). Leave empty to use global settings."
    )
    grace_period_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Grace period in minutes for late arrival (e.g., 15). Leave empty to use global settings."
    )

    def __str__(self):
        return self.name

    @property
    def employee_count_property(self):
        return self.employees_set.count()

    @property
    def employee_count(self):
        """Alias for employee_count_property for compatibility"""
        return self.employees_set.count()

    def get_office_start_time(self):
        """Get office start time - department-specific or global default"""
        if self.use_custom_timings and self.office_start_time:
            return self.office_start_time
        # Fallback to global settings
        try:
            settings = AttendanceSettings.objects.first()
            if settings:
                return settings.work_start_time
        except:
            pass
        # Ultimate fallback
        return time(9, 0)

    def get_office_end_time(self):
        """Get office end time - department-specific or global default"""
        if self.use_custom_timings and self.office_end_time:
            return self.office_end_time
        # Fallback to global settings
        try:
            settings = AttendanceSettings.objects.first()
            if settings:
                return settings.work_end_time
        except:
            pass
        # Ultimate fallback
        return time(18, 0)

    def get_grace_period_minutes(self):
        """Get grace period - department-specific or global default"""
        if self.use_custom_timings and self.grace_period_minutes is not None:
            return self.grace_period_minutes
        # Fallback to global settings
        try:
            settings = AttendanceSettings.objects.first()
            if settings:
                return settings.grace_period_minutes
        except:
            pass
        # Ultimate fallback
        return 15

    def get_late_threshold(self):
        """Calculate late threshold time based on office start time and grace period"""
        office_start = self.get_office_start_time()
        grace_minutes = self.get_grace_period_minutes()
        from datetime import timedelta
        start_datetime = datetime.combine(timezone.now().date(), office_start)
        late_threshold_datetime = start_datetime + timedelta(minutes=grace_minutes)
        return late_threshold_datetime.time()

    def get_late_sitting_threshold(self):
        """Calculate late sitting threshold (typically 30 minutes after office end time)"""
        office_end = self.get_office_end_time()
        from datetime import timedelta
        end_datetime = datetime.combine(timezone.now().date(), office_end)
        late_sitting_datetime = end_datetime + timedelta(minutes=30)
        return late_sitting_datetime.time()


# Position Model (moved to top to avoid forward reference issues)
class Position(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    date_added = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


# Main Employee Model
class Employees(models.Model):
    STATUS_CHOICES = [
        (1, 'Active'),
        (2, 'Inactive'),
    ]
    TEAM_CHOICES = [
        ('', '-- Select Team --'),
        ('Sir Ahsan', 'Sir Ahsan'),
        ('Sir Faisal', 'Sir Faisal'),
        ('Sir Zubair', 'Sir Zubair'),
        ('Sir Govinda', 'Sir Govinda'),
        ('Sir Suhail', 'Sir Suhail'),
        ('HR', 'HR'),
        ('Social media', 'Social media'),
        ('Ecommerce', 'Ecommerce'),
        ('Accounts', 'Accounts'),
        ('Admin', 'Admin'),
        ('Sir Faizan', 'Sir Faizan'),
        ('Sir Ahtisham', 'Sir Ahtisham'),
    ]

    # 🔗 Link to Django auth user (so request.user.employee works)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee',
        blank=True,
        null=True
    )

    team = models.CharField(max_length=50, choices=TEAM_CHOICES, blank=True, null=True, verbose_name='Team')
    code = models.CharField(max_length=20, unique=True, verbose_name="Employee ID")
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100, blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    national_id = models.CharField(max_length=25, blank=True, null=True)
    contact_1 = models.CharField(max_length=20, blank=True, null=True)
    contact_2 = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_person = models.CharField(max_length=100, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    marital_status = models.CharField(max_length=20, blank=True, null=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    official_email = models.EmailField(blank=True, null=True)
    present_address = models.TextField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    location = models.CharField(max_length=100, default="FunPrime Technology")
    work_mode = models.CharField(max_length=10, choices=[('Onsite', 'Onsite'), ('Remote', 'Remote'), ('Hybrid', 'Hybrid')], default='Onsite')
    employment_type = models.CharField(max_length=10, choices=[('Full Time', 'Full Time'), ('Part Time', 'Part Time')], default='Full Time')
    date_hired = models.DateField(blank=True, null=True)
    date_permanent = models.DateField(blank=True, null=True)
    registration_no = models.CharField(max_length=100, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    department = models.ForeignKey('Department',on_delete=models.SET_NULL,related_name='employees_set',blank=True,null=True)
    position = models.ForeignKey('Position', on_delete=models.SET_NULL, related_name='employees_set', blank=True, null=True)
    reporting_to = models.CharField(max_length=100, blank=True, null=True)
    salary = models.IntegerField(default=0)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    branch_name = models.CharField(max_length=100, blank=True, null=True)
    account_title = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)

    # Increment tracking fields
    last_increment_date = models.DateField(blank=True, null=True, help_text="Date of last salary increment")
    next_increment_date = models.DateField(blank=True, null=True, help_text="Calculated next increment date (6 months from last increment or joining date)")
    increment_cycle_months = models.IntegerField(default=6, help_text="Number of months between increments")

    status = models.IntegerField(choices=STATUS_CHOICES, default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)
    profile_submitted = models.BooleanField(default=False, verbose_name="Profile Submitted", help_text="Indicates if the employee has submitted their profile information")

    # Temporary field to store generated password (cleared after first access)
    temp_password = models.CharField(max_length=128, blank=True, null=True, editable=False, help_text="Temporary storage for generated password - cleared after display")

    # Document fields
    cnic_copy = models.FileField(upload_to='employee_documents/cnic/', blank=True, null=True)
    passport_size_photo = models.ImageField(upload_to='employee_documents/photos/', blank=True, null=True)
    updated_resume = models.FileField(upload_to='employee_documents/resumes/', blank=True, null=True)
    educational_certificate = models.FileField(upload_to='employee_documents/education/', blank=True, null=True)
    experience_letter = models.FileField(upload_to='employee_documents/experience/', blank=True, null=True)
    offer_letter_signed = models.FileField(upload_to='employee_documents/offer_letters/', blank=True, null=True)
    nda_form_signed = models.FileField(upload_to='employee_documents/nda_forms/', blank=True, null=True)

    def clean(self):
        super().clean()
        if self.code and not self.code.isdigit():
            raise ValidationError({'code': 'Employee ID must contain only digits (e.g. 1001) for device compatibility.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firstname} {self.lastname or ''}"

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"


class EmployeeAdditionalDocument(models.Model):
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE, related_name="additional_documents")
    label = models.CharField(max_length=255)
    file = models.FileField(upload_to="employee_documents/additional/")
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Additional Document"
        verbose_name_plural = "Additional Documents"

    def __str__(self):
        return f"{self.label} ({self.employee.code})"


# ---------- User auto-creation for new Employees ----------

import secrets
import string

def generate_secure_password(length=12):
    """
    Generate a secure random password with:
    - Uppercase letters
    - Lowercase letters
    - Digits
    - Special characters
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"

    # Ensure at least one character from each set
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    # Fill the rest randomly
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def _sanitize_username(base: str) -> str:
    """
    Allow letters, numbers, underscore; lower-case; trim to 150 chars (Django max).
    If empty after sanitizing, fall back to 'user'.
    """
    base = (base or "").strip().lower()
    base = re.sub(r'[^a-z0-9_]+', '', base)
    return base[:150] if base else "user"


def _unique_username_from_firstname(firstname: str, fallback: str = "user") -> str:
    """
    Try firstname, then firstname + digits, finally fallback variants.
    """
    from django.contrib.auth.models import User
    root = _sanitize_username(firstname) or _sanitize_username(fallback)

    # Try plain root
    if not User.objects.filter(username=root).exists():
        return root

    # Try with numeric suffix
    for i in range(1, 1000):
        candidate = f"{root}{i}"
        if len(candidate) > 150:
            candidate = candidate[:150]
        if not User.objects.filter(username=candidate).exists():
            return candidate

    # Absolute fallback: timestamp-based (very rare)
    from django.utils import timezone
    ts = timezone.now().strftime("%Y%m%d%H%M%S")
    candidate = (root[:140] + ts)[:150]
    return candidate


@receiver(post_save, sender=Employees)
def calculate_next_increment_date(sender, instance: Employees, created, **kwargs):
    """Calculate next increment date when employee is created or date_hired is updated"""
    if instance.date_hired and not instance.next_increment_date:
        try:
            from dateutil.relativedelta import relativedelta
            # Import here to avoid circular import (IncrementSettings is defined later)
            try:
                increment_settings = IncrementSettings.get_active()
                cycle_months = increment_settings.cycle_months
            except:
                cycle_months = 6  # Default to 6 months if settings don't exist yet

            instance.next_increment_date = instance.date_hired + relativedelta(months=cycle_months)
            # Save without triggering signals again
            Employees.objects.filter(pk=instance.pk).update(next_increment_date=instance.next_increment_date)
        except Exception:
            pass  # Silently fail if there's any error


@receiver(post_save, sender=Employees)
def ensure_user_for_employee(sender, instance: Employees, created, **kwargs):
    """
    When an Employee is created, create and link a Django User automatically:
      username = firstname (unique-ified)
      password = securely generated random password
    If a user is already linked, do nothing.
    """
    # Only act on create and when not already linked
    if not created or instance.user_id:
        return

    # Build username from firstname; ensure uniqueness
    username = _unique_username_from_firstname(instance.firstname or "", fallback=instance.code or "user")

    # Generate secure password
    generated_password = generate_secure_password(length=12)

    # Create user with secure password (Django's create_user automatically hashes it)
    user = User.objects.create_user(
        username=username,
        password=generated_password,
        first_name=instance.firstname or "",
        last_name=instance.lastname or "",
        email=instance.official_email or instance.email or ""
    )
    user.is_active = True
    user.save(update_fields=["is_active"])

    # Store the generated password temporarily so admin can retrieve it
    # Link back to employee and store password (single-field save to avoid re-triggering expensive work)
    Employees.objects.filter(pk=instance.pk).update(user=user, temp_password=generated_password)

# ===========================
#   USER PROFILE MODEL (Role-based Access)
# ===========================
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('hr', 'HR Manager'),
        ('finance', 'Finance Manager'),
        ('employee', 'Employee'),
        ('manager', 'Department Manager'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    employee = models.OneToOneField(Employees, on_delete=models.CASCADE, null=True, blank=True, related_name='user_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def is_admin(self):
        return self.role == 'admin'

    def is_hr(self):
        return self.role == 'hr'

    def is_employee(self):
        return self.role == 'employee'

    def is_manager(self):
        return self.role == 'manager'

    def is_finance(self):
        return self.role == 'finance'

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


# Optional: Keep the simple Employee model for department heads if needed
class Employee(models.Model):
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.firstname} {self.lastname or ''}".strip()


# Update Department model to include head reference
Department.add_to_class('head', models.ForeignKey(
    Employees, on_delete=models.SET_NULL, null=True, blank=True, related_name="headed_departments"
))


class DepartmentEmployee(models.Model):
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE, related_name="department_assignments")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="employee_assignments")
    joined_at = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.employee} → {self.department}"


# ... REST OF YOUR MODELS (Attendance, Team, etc.) remain exactly the same ...


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
        ('', 'No Leave'),  # Default empty value
    ]

    employee = models.ForeignKey(
        'Employees',  # Use string reference to avoid circular imports
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField()

    # Time tracking (keep your existing fields)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)

    # Status and duration fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    # New fields from your desired structure
    timetable = models.CharField(max_length=50, blank=True, null=True)
    actual_work = models.DurationField(blank=True, null=True)
    required_work = models.DurationField(blank=True, null=True)
    late_in = models.DurationField(blank=True, null=True)
    early_out = models.DurationField(blank=True, null=True)
    break_time = models.DurationField(blank=True, null=True)
    late_sitting = models.DurationField(blank=True, null=True)

    # Leave type (replaces multiple boolean fields)
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, blank=True, null=True)

    # Overtime and notes (keep your existing fields)
    overtime_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.00
    )
    reason = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Timestamps (keep your existing fields)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'Employees',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
        # Get timings from employee's department if available
        if self.employee and self.employee.department:
            dept = self.employee.department
            office_start = dept.get_office_start_time()
            office_end = dept.get_office_end_time()
            grace_minutes = dept.get_grace_period_minutes()
            late_threshold = dept.get_late_threshold()
            late_sitting_threshold = dept.get_late_sitting_threshold()
        else:
            # Fallback to global settings
            try:
                settings = AttendanceSettings.objects.first()
                if settings:
                    office_start = settings.work_start_time
                    office_end = settings.work_end_time
                    grace_minutes = settings.grace_period_minutes
                    # Calculate late threshold
                    start_datetime = datetime.combine(timezone.now().date(), office_start)
                    late_threshold_datetime = start_datetime + timedelta(minutes=grace_minutes)
                    late_threshold = late_threshold_datetime.time()
                    # Calculate late sitting threshold (30 minutes after office end)
                    end_datetime = datetime.combine(timezone.now().date(), office_end)
                    late_sitting_datetime = end_datetime + timedelta(minutes=30)
                    late_sitting_threshold = late_sitting_datetime.time()
                else:
                    # Ultimate fallback
                    office_start = time(9, 0)
                    office_end = time(18, 0)
                    late_threshold = time(9, 15)
                    late_sitting_threshold = time(18, 30)
            except:
                # Ultimate fallback
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
        # Get department-specific or global office timings
        timings = self.get_office_timings()
        office_start = timings['office_start']
        office_end = timings['office_end']
        late_threshold = timings['late_threshold']
        late_sitting_threshold = timings['late_sitting_threshold']

        # Reset durations
        self.late_in = timedelta(0)
        self.early_out = timedelta(0)
        self.late_sitting = timedelta(0)

        if self.check_in_time or self.check_out_time:
            today = self.date if hasattr(self, 'date') and self.date else timezone.now().date()

            # Calculate late_in: check-in after late threshold
            if self.check_in_time:
                if self.check_in_time > late_threshold:
                    # Calculate late time from late threshold - per company/department policy
                    check_in_dt = datetime.combine(today, self.check_in_time)
                    late_threshold_dt = datetime.combine(today, late_threshold)
                    self.late_in = check_in_dt - late_threshold_dt
                else:
                    self.late_in = timedelta(0)

            # Calculate early_out: check-out before office end time
            if self.check_out_time:
                if self.check_out_time < office_end:
                    check_out_dt = datetime.combine(today, self.check_out_time)
                    office_end_dt = datetime.combine(today, office_end)
                    self.early_out = office_end_dt - check_out_dt
                else:
                    self.early_out = timedelta(0)

            # Calculate late_sitting: check-out after late sitting threshold
            if self.check_out_time:
                if self.check_out_time > late_sitting_threshold:
                    check_out_dt = datetime.combine(today, self.check_out_time)
                    late_sitting_start_dt = datetime.combine(today, late_sitting_threshold)
                    self.late_sitting = check_out_dt - late_sitting_start_dt
                else:
                    self.late_sitting = timedelta(0)

            # Calculate actual work duration if both times are present
            if self.check_in_time and self.check_out_time:
                check_in = datetime.combine(today, self.check_in_time)
                check_out = datetime.combine(today, self.check_out_time)

                # Handle overnight shifts
                if check_out < check_in:
                    check_out += timedelta(days=1)

                # Calculate actual work duration (subtract break time)
                work_duration = check_out - check_in
                if self.break_time:
                    work_duration -= self.break_time

                self.actual_work = work_duration

    def auto_determine_status(self):
        """
        Automatically determine status based on attendance rules:
        - Uses department-specific office timings if available, otherwise global settings
        - If check-in/check-out exists: mark Present (unless other conditions apply)
        - If no check-in/check-out: mark Absent
        - Check-in after late threshold: mark Late
        - Check-out before office end time: mark Early Out
        - Check-out after late sitting threshold: mark Late Sitting
        - Weekend with check-in/check-out: mark as 'weekend' (but treated as present)
        """
        # Check if it's a weekend date
        is_weekend = self.is_weekend_date

        # Get department-specific or global office timings
        timings = self.get_office_timings()
        office_start = timings['office_start']
        office_end = timings['office_end']
        late_threshold = timings['late_threshold']
        late_sitting_threshold = timings['late_sitting_threshold']

        # If employee is on leave, mark as leave
        if self.leave_type:
            return 'leave'

        # If no check-in and no check-out
        if not self.check_in_time and not self.check_out_time:
            # On weekend without attendance data, don't mark as anything (should not create record)
            # But if record exists, mark as weekend for backward compatibility
            if is_weekend:
                return 'weekend'
            return 'absent'

        # If there's check-in or check-out data on weekend, treat as present (not weekend)
        # Determine status based on timings (same as weekdays)
        if is_weekend:
            # Weekend with attendance: determine status based on timings, but treat as present
            # Continue to determine specific status (late, early-out, etc.) for weekend work
            pass  # Continue to timing-based status determination below

        # Now determine the specific status based on timings (applies to both weekdays and weekends)

        # Priority 1: Check for late sitting (check-out after late sitting threshold)
        # This takes highest priority as it's a specific condition
        if self.check_out_time and self.check_out_time > late_sitting_threshold:
            return 'late-sitting'

        # Priority 2: Check for early out (check-out before office end time)
        # This takes priority over late arrival
        if self.check_out_time and self.check_out_time < office_end:
            return 'early-out'

        # Priority 3: Check for late arrival (check-in after late threshold)
        # Only applies if check-out is between office end and late sitting threshold, or no check-out
        if self.check_in_time and self.check_in_time > late_threshold:
            return 'late'

        # Priority 4: Check for early arrival (check-in before office start time)
        if self.check_in_time and self.check_in_time < office_start:
            return 'early-in'

        # Default: Present (has check-in/check-out and meets all timing requirements)
        return 'present'

    @property
    def duration(self):
        """Calculate work duration in hours and minutes"""
        if self.actual_work:
            total_seconds = self.actual_work.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif self.check_in_time and self.check_out_time:
            # Fallback calculation if actual_work is not set
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
        """Calculate work duration in decimal hours"""
        if self.actual_work:
            return round(self.actual_work.total_seconds() / 3600, 2)
        return 0.0

    @staticmethod
    def _format_hm(delta):
        """Return duration as 'Hh MMm' or empty string."""
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
        """Display overtime hours in h:m format"""
        if self.overtime_hours > 0:
            hours = int(self.overtime_hours)
            minutes = int((self.overtime_hours % 1) * 60)
            return f"{hours}h {minutes:02d}m"
        return "--"

    @property
    def late_in_display(self):
        """Display late-in time as hours and minutes (e.g., 0h 11m)"""
        return self._format_hm(self.late_in)

    @property
    def early_out_display(self):
        """Display early-out time in minutes"""
        return self._format_hm(self.early_out)

    @property
    def is_weekend_date(self):
        """Check if the attendance date falls on a weekend (Saturday or Sunday)"""
        return self.date.weekday() >= 5  # Saturday=5, Sunday=6

    @property
    def simplified_status(self):
        """
        Returns 'present', 'absent', or 'leave' based on the current status.
        Present: present, late, early-in, early-out, overtime, late-sitting, weekend (with attendance)
        Leave: leave
        Absent: absent, weekend (without attendance)
        """
        # Handle leave status separately
        if self.status == 'leave':
            return 'leave'

        # If it's a weekend status
        if self.status == 'weekend':
            # Weekend records should only exist if employee didn't arrive (old data)
            # If there's check-in or check-out data, it shouldn't be 'weekend' status (should be 'present', 'late', etc.)
            # But for backward compatibility, if weekend record has attendance data, treat as present
            if self.check_in_time or self.check_out_time:
                return 'present'
            # Weekend without attendance: don't show as absent or present
            # Return a special value that views can filter out
            return 'weekend_no_attendance'  # This will be filtered out in views

        # Regular statuses
        if self.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'late-sitting']:
            return 'present'
        elif self.status == 'absent':
            return 'absent'
        else:
            # Default to absent if status is unclear
            return 'absent'

    @property
    def simplified_status_display(self):
        """Returns 'Present', 'Absent', or 'Leave' for display"""
        status = self.simplified_status
        if status == 'weekend_no_attendance':
            return None  # Weekend without attendance - don't display
        if status == 'present':
            return 'Present'
        elif status == 'leave':
            return 'Leave'
        else:
            return 'Absent'

    def save(self, *args, **kwargs):
        # Auto-calculate durations before saving
        self.calculate_durations()

        # Auto-determine status when attendance data (check-in/check-out) is entered
        # If check-in/check-out data exists, always auto-determine status (even if previously set)
        # This ensures that when attendance data is added to an absent record, it gets updated
        has_attendance_data = self.check_in_time or self.check_out_time

        if has_attendance_data:
            # If check-in/check-out exists, automatically determine status
            # This overrides any previous status (including absent) when data is present
            self.status = self.auto_determine_status()
            # Clear the explicit status flag since we're auto-determining based on data
            self._explicit_status = False
        elif not getattr(self, "_explicit_status", False):
            # Only auto-determine if status hasn't been explicitly set by user/admin
            # and there's no attendance data
            if not self.status:
                # If no check-in/check-out and no status, mark as absent
                self.status = 'absent'

        # Auto-calculate overtime from late_sitting
        if self.late_sitting and self.late_sitting.total_seconds() > 0:
            self.overtime_hours = round(self.late_sitting.total_seconds() / 3600, 2)

        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Validate attendance record"""
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


# Keep your existing AttendanceSettings and LeaveRequest models unchanged
class AttendanceSettings(models.Model):
    """Global attendance settings"""
    work_start_time = models.TimeField(default='09:00')
    work_end_time = models.TimeField(default='18:00')
    grace_period_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Grace period in minutes for late arrival"
    )
    minimum_work_hours = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=8.0,
        help_text="Minimum required work hours per day"
    )
    overtime_threshold_hours = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=8.0,
        help_text="Hours after which overtime starts"
    )
    weekend_work_allowed = models.BooleanField(default=True)
    auto_checkout_enabled = models.BooleanField(
        default=False,
        help_text="Automatically check out employees at end of work day"
    )
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
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_holiday_dates',
        verbose_name="Created By"
    )

    class Meta:
        verbose_name = "Holiday Date"
        verbose_name_plural = "Holiday Dates"
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} ({self.date})"

    @staticmethod
    def is_holiday(check_date):
        """Check if a given date is a holiday"""
        return HolidayDate.objects.filter(date=check_date).exists()

    @staticmethod
    def get_holiday(check_date):
        """Get the holiday for a given date, if any"""
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

    employee = models.ForeignKey(
        'Employees',
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        'Employees',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests'
    )
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
        """Calculate leave duration in days"""
        return (self.end_date - self.start_date).days + 1

    def clean(self):
        """Validate leave request"""
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError("End date cannot be before start date.")

            if self.start_date < timezone.now().date():
                raise ValidationError("Leave cannot be applied for past dates.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)



#Team related
# models.py - Add these team-related models

class Team(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    leader = models.ForeignKey(
        Employees,
        on_delete=models.SET_NULL,
        null=True,
        related_name='led_teams'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='teams'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def members_count(self):
        return self.members.count()

    @property
    def projects_count(self):
        return self.projects.count()

    @property
    def capacity(self):
        """Calculate team capacity based on member availability"""
        if self.members_count == 0:
            return 0

        # Simple implementation: use active members count as capacity proxy
        return self.members_count

    class Meta:
        ordering = ['name']


class TeamMember(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members'
    )
    employee = models.ForeignKey(
        Employees,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    role = models.CharField(max_length=100, blank=True, null=True)
    joined_at = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('team', 'employee')
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.employee} in {self.team}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    start_date = models.DateField()
    end_date = models.DateField()
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


# ===========================
#   PAYROLL MODELS
# ===========================

class Payroll(models.Model):
    PAY_PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('bi-weekly', 'Bi-Weekly'),
        ('weekly', 'Weekly'),
    ]

    pay_period = models.CharField(max_length=20, choices=PAY_PERIOD_CHOICES)
    pay_date = models.DateField()
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_pay_period_display()} - {self.pay_date}"


class PayrollRecord(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    ]

    payroll = models.ForeignKey('Payroll', on_delete=models.CASCADE, related_name='records', null=True, blank=True)
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pay_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee} - {self.pay_date} ({self.status})"


class SalarySlipRequest(models.Model):
    """Employee salary slip requests linked to individual payroll records."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.CASCADE,
        related_name='salary_slip_requests',
    )
    employee = models.ForeignKey(
        Employees,
        on_delete=models.CASCADE,
        related_name='salary_slip_requests',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_slip_requests_made',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_slip_requests_decided',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} → {self.payroll_record} ({self.status})"


class SalaryIncrement(models.Model):
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE)
    old_salary = models.DecimalField(max_digits=12, decimal_places=2)
    new_salary = models.DecimalField(max_digits=12, decimal_places=2)
    increase_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    increase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Absolute increase amount")
    effective_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    is_automatic = models.BooleanField(default=False, help_text="True if increment was applied automatically by system")
    notification_sent = models.BooleanField(default=False, help_text="True if notifications were sent for this increment")

    def __str__(self):
        return f"{self.employee} increment to {self.new_salary} on {self.effective_date}"

    class Meta:
        ordering = ['-effective_date', '-applied_at']


class SalaryDisbursement(models.Model):
    """Track bulk salary disbursement transactions via bank API"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('partial', 'Partially Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('bank_api', 'Bank API'),
        ('manual', 'Manual Transfer'),
        ('other', 'Other'),
    ]

    disbursement_id = models.CharField(max_length=100, unique=True, help_text="Unique transaction ID from bank API")
    payroll = models.ForeignKey('Payroll', on_delete=models.CASCADE, related_name='disbursements', null=True, blank=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursements_initiated')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_employees = models.IntegerField(default=0)
    successful_payments = models.IntegerField(default=0)
    failed_payments = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='bank_api')
    bank_api_response = models.JSONField(null=True, blank=True, help_text="Response from bank API")
    bank_api_request = models.JSONField(null=True, blank=True, help_text="Request sent to bank API")
    error_message = models.TextField(blank=True, null=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-initiated_at']

    def __str__(self):
        return f"Disbursement {self.disbursement_id} - {self.get_status_display()}"


class SalaryDisbursementRecord(models.Model):
    """Individual employee payment record within a disbursement"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    disbursement = models.ForeignKey(SalaryDisbursement, on_delete=models.CASCADE, related_name='payment_records')
    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name='disbursement_records')
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="Transaction ID from bank")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    bank_response = models.JSONField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-processed_at']
        unique_together = ['disbursement', 'payroll_record']

    def __str__(self):
        return f"{self.employee} - {self.amount} ({self.get_status_display()})"


# ===========================
#   SYSTEM SETTINGS MODEL
# ===========================

class SystemSettings(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"), ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("ar", "Arabic"), ("ur", "Urdu")
    ]
    DATE_FORMAT_CHOICES = [("mm/dd/yyyy", "MM/DD/YYYY"), ("dd/mm/yyyy", "DD/MM/YYYY"), ("yyyy-mm-dd", "YYYY-MM-DD")]
    TIME_FORMAT_CHOICES = [("12h", "12-hour"), ("24h", "24-hour")]
    THEME_CHOICES = [
        ("default", "Default"),
        ("indigo", "Indigo"),
        ("emerald", "Emerald"),
        ("crimson", "Crimson"),
    ]
    FONT_SIZE_CHOICES = [("small", "Small"), ("medium", "Medium"), ("large", "Large")]
    SIDEBAR_WIDTH_CHOICES = [("compact", "Compact"), ("normal", "Normal"), ("wide", "Wide")]

    # General Settings
    TIMEZONE = models.CharField(max_length=20, default="utc+0")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    date_format = models.CharField(max_length=12, choices=DATE_FORMAT_CHOICES, default="yyyy-mm-dd")
    time_format = models.CharField(max_length=3, choices=TIME_FORMAT_CHOICES, default="24h")

    # Appearance Settings
    dark_mode = models.BooleanField(default=False)
    theme = models.CharField(max_length=32, choices=THEME_CHOICES, default="default")
    font_size = models.CharField(max_length=8, choices=FONT_SIZE_CHOICES, default="medium")
    sidebar_width = models.CharField(max_length=8, choices=SIDEBAR_WIDTH_CHOICES, default="normal")

    # Notification Settings (stored as JSON for flexibility)
    notification_settings = models.JSONField(default=dict, blank=True, help_text="Email, push, and in-app notification preferences")

    # Security Settings (stored as JSON)
    security_settings = models.JSONField(default=dict, blank=True, help_text="Security preferences including 2FA, session management")

    # Privacy Settings (stored as JSON)
    privacy_settings = models.JSONField(default=dict, blank=True, help_text="Privacy preferences and data sharing settings")

    # Backup Settings (stored as JSON)
    backup_settings = models.JSONField(default=dict, blank=True, help_text="Backup and restore configuration")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "System Settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def get_notification_setting(self, key, default=False):
        """Get a notification setting value"""
        return self.notification_settings.get(key, default)

    def set_notification_setting(self, key, value):
        """Set a notification setting value"""
        if not self.notification_settings:
            self.notification_settings = {}
        self.notification_settings[key] = value
        self.save()

    def get_security_setting(self, key, default=False):
        """Get a security setting value"""
        return self.security_settings.get(key, default)

    def set_security_setting(self, key, value):
        """Set a security setting value"""
        if not self.security_settings:
            self.security_settings = {}
        self.security_settings[key] = value
        self.save()

    def get_privacy_setting(self, key, default=False):
        """Get a privacy setting value"""
        return self.privacy_settings.get(key, default)

    def set_privacy_setting(self, key, value):
        """Set a privacy setting value"""
        if not self.privacy_settings:
            self.privacy_settings = {}
        self.privacy_settings[key] = value
        self.save()


# ===========================
#   INCREMENT SETTINGS MODEL
# ===========================

class IncrementSettings(models.Model):
    """Dynamic increment settings that can be updated by admin/finance"""
    increment_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=5.00,
        help_text="Default percentage increase for 6-month increments"
    )
    increment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Fixed increment amount (if set, overrides percentage). Set to 0 to use percentage."
    )
    use_percentage = models.BooleanField(
        default=True,
        help_text="If True, use percentage. If False, use fixed amount."
    )
    cycle_months = models.IntegerField(
        default=6,
        help_text="Number of months between increments"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable automatic increments"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_increment_settings'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.use_percentage:
            return f"{self.increment_percentage}% increment every {self.cycle_months} months"
        else:
            return f"${self.increment_amount} increment every {self.cycle_months} months"

    @classmethod
    def get_active(cls):
        """Get the active increment settings"""
        obj = cls.objects.filter(is_active=True).first()
        if not obj:
            # Create default if none exists
            obj = cls.objects.create()
        return obj

    class Meta:
        verbose_name = "Increment Setting"
        verbose_name_plural = "Increment Settings"
        ordering = ['-updated_at']


# ===========================
#   NOTIFICATION MODEL
# ===========================

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

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
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



# ===========================
#   LOAN POOL MODELS
# ===========================

class LoanPool(models.Model):
    """Company loan pool management"""
    name = models.CharField(max_length=100, default="Company Loan Pool")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00)
    available_amount = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        Employees,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_loan_pools'
    )

    class Meta:
        verbose_name = "Loan Pool"
        verbose_name_plural = "Loan Pools"

    def __str__(self):
        return f"{self.name} - ${self.available_amount} available"

    @property
    def utilized_amount(self):
        return self.total_amount - self.available_amount

    @property
    def utilization_percentage(self):
        if self.total_amount > 0:
            return (self.utilized_amount / self.total_amount) * 100
        return 0

    def can_approve_loan(self, amount):
        """Check if loan can be approved based on available pool"""
        return self.available_amount >= amount

    def approve_loan(self, amount):
        """Reduce available amount when loan is approved"""
        if self.can_approve_loan(amount):
            self.available_amount -= amount
            self.save()
            return True
        return False

    def release_loan_amount(self, amount):
        """Release amount back to pool when loan is repaid or cancelled"""
        self.available_amount += amount
        self.save()

    def increase_pool(self, amount):
        """Increase the total and available pool amount"""
        self.total_amount += amount
        self.available_amount += amount
        self.save()

    def decrease_pool(self, amount):
        """Decrease the total pool amount (only if not utilized)"""
        if self.available_amount >= amount:
            self.total_amount -= amount
            self.available_amount -= amount
            self.save()
            return True
        return False


class LoanPoolTransaction(models.Model):
    """Track all loan pool transactions"""
    TRANSACTION_TYPES = [
        ('initial', 'Initial Pool'),
        ('increase', 'Pool Increase'),
        ('decrease', 'Pool Decrease'),
        ('loan_approval', 'Loan Approval'),
        ('loan_repayment', 'Loan Repayment'),
        ('loan_cancellation', 'Loan Cancellation'),
    ]

    pool = models.ForeignKey(LoanPool, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    created_by = models.ForeignKey(
        Employees,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_pool_transactions'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Loan Pool Transaction"
        verbose_name_plural = "Loan Pool Transactions"

    def __str__(self):
        return f"{self.get_transaction_type_display()} - ${self.amount}"


# ===========================
#   LOAN MODELS
# ===========================

class Loan(models.Model):
    LOAN_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(
        Employees,
        on_delete=models.CASCADE,
        related_name='loans'
    )
    loan_pool = models.ForeignKey(
        LoanPool,
        on_delete=models.CASCADE,
        related_name='loans',
        null=True,
        blank=True
    )
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    number_of_installments = models.PositiveIntegerField()
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    purpose = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=LOAN_STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        Employees,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_loans'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    is_partial_loan = models.BooleanField(default=False, help_text="True if loan amount was reduced due to pool constraints")
    original_requested_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Original amount requested before pool constraints")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def __str__(self):
        return f"{self.employee} - ${self.loan_amount} ({self.status})"

    def clean(self):
        """Validate loan constraints"""
        # Check if employee has active loan
        if self.status in ['approved', 'active']:
            active_loans = Loan.objects.filter(
                employee=self.employee,
                status__in=['approved', 'active']
            ).exclude(id=self.id)
            if active_loans.exists():
                raise ValidationError("Employee already has an active loan. Only one active loan per employee is allowed.")

        # Check loan amount against salary (1.5x monthly salary)
        if self.employee.salary and self.loan_amount:
            max_allowed = Decimal(self.employee.salary) * Decimal('1.5')
            if self.loan_amount > max_allowed:
                raise ValidationError(f"Loan amount cannot exceed 1.5 times monthly salary (${max_allowed:.2f})")

        # Check if loan pool has sufficient funds
        if self.loan_pool and not self.loan_pool.can_approve_loan(self.loan_amount):
            raise ValidationError(f"Insufficient funds in loan pool. Available: ${self.loan_pool.available_amount}")

    def save(self, *args, **kwargs):
        # Calculate total amount and monthly payment if not set
        if not self.total_amount:
            interest_amount = (self.loan_amount * self.interest_rate) / 100
            self.total_amount = self.loan_amount + interest_amount

        if not self.monthly_payment and self.number_of_installments > 0:
            self.monthly_payment = self.total_amount / self.number_of_installments

        # Set end date if not provided
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + timedelta(days=self.number_of_installments * 30)

        self.clean()
        super().save(*args, **kwargs)

    def can_approve_with_pool_constraints(self):
        """Check if loan can be approved considering pool constraints"""
        if not self.loan_pool:
            return True, self.loan_amount

        if self.loan_pool.can_approve_loan(self.loan_amount):
            return True, self.loan_amount
        else:
            # Offer partial loan
            return False, self.loan_pool.available_amount

    def approve_with_pool_constraints(self):
        """Approve loan with pool constraints, potentially reducing amount"""
        if not self.loan_pool:
            self.status = 'approved'
            self.save()
            return True, self.loan_amount

        can_approve, approved_amount = self.can_approve_with_pool_constraints()

        if can_approve:
            # Full amount approved
            self.loan_pool.approve_loan(self.loan_amount)
            self.status = 'approved'
            self.save()
            return True, self.loan_amount
        elif approved_amount > 0:
            # Partial loan approved
            self.original_requested_amount = self.loan_amount
            self.loan_amount = approved_amount
            self.is_partial_loan = True
            # Recalculate totals for partial amount
            interest_amount = (self.loan_amount * self.interest_rate) / 100
            self.total_amount = self.loan_amount + interest_amount
            self.monthly_payment = self.total_amount / self.number_of_installments
            self.loan_pool.approve_loan(self.loan_amount)
            self.status = 'approved'
            self.save()
            return True, approved_amount
        else:
            return False, 0

    @property
    def amount_repaid(self):
        return self.repayments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def remaining_balance(self):
        return self.total_amount - self.amount_repaid

    @property
    def progress_percentage(self):
        if self.total_amount > 0:
            return (self.amount_repaid / self.total_amount) * 100
        return 0

    @property
    def installments_paid(self):
        return self.repayments.count()

    @property
    def installments_remaining(self):
        return max(0, self.number_of_installments - self.installments_paid)


class LoanRepayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('payroll_deduction', 'Payroll Deduction'),
    ]

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name='repayments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        Employees,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_repayments'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "Loan Repayment"
        verbose_name_plural = "Loan Repayments"

    def __str__(self):
        return f"{self.loan.employee} - ${self.amount} - {self.payment_date}"

    def clean(self):
        if self.amount > self.loan.remaining_balance:
            raise ValidationError("Payment amount exceeds remaining loan balance.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

        # Release amount back to pool when loan is fully repaid
        if self.loan.loan_pool and self.loan.remaining_balance <= 0:
            self.loan.status = 'completed'
            self.loan.save()


#============================
#   REPORT MODELS
#==========================
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import os

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

    # Report options
    include_charts = models.BooleanField(default=True)
    include_summary = models.BooleanField(default=True)
    include_raw_data = models.BooleanField(default=False)

    # File details
    file_path = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.CharField(max_length=50, null=True, blank=True)

    # Metadata
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    # Report data (JSON field for storing report statistics)
    report_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-generated_on']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.generated_on.strftime('%Y-%m-%d')}"

    def get_file_size_display(self):
        """Return human-readable file size"""
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
        """Mark report as completed"""
        self.status = 'completed'
        self.completed_on = timezone.now()
        if self.file_path:
            self.file_size = self.get_file_size_display()
        self.save()

    def mark_failed(self, error_message):
        """Mark report as failed"""
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

    # Template configuration
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
        """Increment usage count and update last generated time"""
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

    # Recipients
    email_recipients = models.TextField(help_text="Comma-separated email addresses")

    # Schedule details
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


# ===========================
#   AI EMPLOYEE ASSISTANT MODELS
# ===========================

class Policy(models.Model):
    """Company policy management"""
    CATEGORY_CHOICES = [
        ('hr', 'HR Policy'),
        ('leave', 'Leave Policy'),
        ('loan', 'Loan Policy'),
        ('code_of_conduct', 'Code of Conduct'),
        ('benefits', 'Benefits'),
        ('attendance', 'Attendance Policy'),
        ('safety', 'Safety Policy'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    effective_date = models.DateField()
    description = models.TextField(blank=True, null=True, help_text="Short description of the policy")
    document = models.FileField(upload_to='policies/', blank=True, null=True, help_text="Policy document (PDF, DOCX, etc.)")
    summary = models.TextField(help_text="AI-extracted or manually entered policy summary")
    key_points = models.JSONField(default=list, blank=True, help_text="List of key points from the policy")
    version = models.CharField(max_length=50, default='1.0', help_text="Policy version number")
    version_notes = models.TextField(blank=True, null=True, help_text="Notes about this version or update")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_policies'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_policies'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_date', '-created_at']
        verbose_name = "Policy"
        verbose_name_plural = "Policies"

    def __str__(self):
        return f"{self.title} (v{self.version})"

    def get_category_display_name(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)


class Complaint(models.Model):
    """Employee complaints and queries"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    employee = models.ForeignKey(
        Employees,
        on_delete=models.CASCADE,
        related_name='complaints'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints'
    )
    related_department = models.CharField(max_length=100, blank=True, null=True, help_text="Department name if not in system")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    response = models.TextField(blank=True, null=True, help_text="HR/Admin response to the complaint")
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_complaints'
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Complaint"
        verbose_name_plural = "Complaints"

    def __str__(self):
        return f"{self.employee} - {self.title} ({self.get_status_display()})"


class AIChatMessage(models.Model):
    """Store AI assistant chat history"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_chat_messages'
    )
    message = models.TextField()
    response = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User Message'),
            ('assistant', 'Assistant Response'),
            ('system', 'System Message'),
        ],
        default='user'
    )
    context = models.JSONField(default=dict, blank=True, help_text="Additional context for the conversation")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']
        verbose_name = "AI Chat Message"
        verbose_name_plural = "AI Chat Messages"

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# ===========================
#   ZKTECO DEVICE MODELS
# ===========================

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

    # Device info (populated after connection)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    device_name = models.CharField(max_length=100, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    device_model = models.CharField(max_length=50, blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_connected = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)

    # Settings
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
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE, related_name='device_attendance_logs', null=True, blank=True)
    user_id = models.CharField(max_length=50, help_text="User ID from device")
    user_name = models.CharField(max_length=200, blank=True, null=True, help_text="User name from device")

    # Event details
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='unknown')
    timestamp = models.DateTimeField(help_text="Event timestamp from device")
    verification_mode = models.IntegerField(default=0, help_text="Verification mode (0=password, 1=fingerprint, 15=face, etc.)")

    # Processed attendance record (if synced)
    attendance_record = models.ForeignKey(
        'Attendance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_logs'
    )

    # Metadata
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
    employee = models.ForeignKey(Employees, on_delete=models.CASCADE, related_name='enrollment_logs')
    enrollment_type = models.CharField(max_length=20, choices=ENROLLMENT_TYPES)

    # Enrollment details
    template_index = models.IntegerField(null=True, blank=True, help_text="Template index on device")
    template_data = models.BinaryField(null=True, blank=True, help_text="Template data (if stored)")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_enrollments'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Enrollment Log"
        verbose_name_plural = "Enrollment Logs"
        ordering = ['-started_at']
        unique_together = [['device', 'employee', 'enrollment_type', 'template_index']]

    def __str__(self):
        return f"{self.employee} - {self.get_enrollment_type_display()} ({self.get_status_display()})"