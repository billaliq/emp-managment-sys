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
from django.contrib.auth.models import User
import re
import secrets
import string


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

    use_custom_timings = models.BooleanField(
        default=False,
        help_text="Enable custom office timings for this department. If disabled, uses global attendance settings."
    )
    office_start_time = models.TimeField(
        null=True, blank=True,
        help_text="Department check-in time (e.g., 09:00). Leave empty to use global settings."
    )
    office_end_time = models.TimeField(
        null=True, blank=True,
        help_text="Department check-out time (e.g., 18:00). Leave empty to use global settings."
    )
    grace_period_minutes = models.PositiveIntegerField(
        null=True, blank=True,
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
        try:
            from .attendance import AttendanceSettings
            s = AttendanceSettings.objects.first()
            if s:
                return s.work_start_time
        except:
            pass
        return time(9, 0)

    def get_office_end_time(self):
        """Get office end time - department-specific or global default"""
        if self.use_custom_timings and self.office_end_time:
            return self.office_end_time
        try:
            from .attendance import AttendanceSettings
            s = AttendanceSettings.objects.first()
            if s:
                return s.work_end_time
        except:
            pass
        return time(18, 0)

    def get_grace_period_minutes(self):
        """Get grace period - department-specific or global default"""
        if self.use_custom_timings and self.grace_period_minutes is not None:
            return self.grace_period_minutes
        try:
            from .attendance import AttendanceSettings
            s = AttendanceSettings.objects.first()
            if s:
                return s.grace_period_minutes
        except:
            pass
        return 15

    def get_late_threshold(self):
        """Calculate late threshold time based on office start time and grace period"""
        office_start = self.get_office_start_time()
        grace_minutes = self.get_grace_period_minutes()
        start_datetime = datetime.combine(timezone.now().date(), office_start)
        late_threshold_datetime = start_datetime + timedelta(minutes=grace_minutes)
        return late_threshold_datetime.time()

    def get_late_sitting_threshold(self):
        """Calculate late sitting threshold (typically 30 minutes after office end time)"""
        office_end = self.get_office_end_time()
        end_datetime = datetime.combine(timezone.now().date(), office_end)
        late_sitting_datetime = end_datetime + timedelta(minutes=30)
        return late_sitting_datetime.time()


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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee', blank=True, null=True)
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
    location = models.CharField(max_length=100, default="Aliq Technology's")
    work_mode = models.CharField(max_length=10, choices=[('Onsite', 'Onsite'), ('Remote', 'Remote'), ('Hybrid', 'Hybrid')], default='Onsite')
    employment_type = models.CharField(max_length=10, choices=[('Full Time', 'Full Time'), ('Part Time', 'Part Time')], default='Full Time')
    date_hired = models.DateField(blank=True, null=True)
    date_permanent = models.DateField(blank=True, null=True)
    registration_no = models.CharField(max_length=100, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, related_name='employees_set', blank=True, null=True)
    position = models.ForeignKey('Position', on_delete=models.SET_NULL, related_name='employees_set', blank=True, null=True)
    reporting_to = models.CharField(max_length=100, blank=True, null=True)
    salary = models.IntegerField(default=0)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    branch_name = models.CharField(max_length=100, blank=True, null=True)
    account_title = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)

    last_increment_date = models.DateField(blank=True, null=True, help_text="Date of last salary increment")
    next_increment_date = models.DateField(blank=True, null=True, help_text="Calculated next increment date (6 months from last increment or joining date)")
    increment_cycle_months = models.IntegerField(default=6, help_text="Number of months between increments")

    status = models.IntegerField(choices=STATUS_CHOICES, default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)
    profile_submitted = models.BooleanField(default=False, verbose_name="Profile Submitted", help_text="Indicates if the employee has submitted their profile information")
    temp_password = models.CharField(max_length=128, blank=True, null=True, editable=False, help_text="Temporary storage for generated password - cleared after display")

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


# ---------- User auto-creation helpers ----------

def generate_secure_password(length=12):
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"
    password = [secrets.choice(uppercase), secrets.choice(lowercase), secrets.choice(digits), secrets.choice(special)]
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


def _sanitize_username(base: str) -> str:
    base = (base or "").strip().lower()
    base = re.sub(r'[^a-z0-9_]+', '', base)
    return base[:150] if base else "user"


def _unique_username_from_firstname(firstname: str, fallback: str = "user") -> str:
    root = _sanitize_username(firstname) or _sanitize_username(fallback)
    if not User.objects.filter(username=root).exists():
        return root
    for i in range(1, 1000):
        candidate = f"{root}{i}"
        if len(candidate) > 150:
            candidate = candidate[:150]
        if not User.objects.filter(username=candidate).exists():
            return candidate
    ts = timezone.now().strftime("%Y%m%d%H%M%S")
    candidate = (root[:140] + ts)[:150]
    return candidate


@receiver(post_save, sender=Employees)
def calculate_next_increment_date(sender, instance, created, **kwargs):
    if instance.date_hired and not instance.next_increment_date:
        try:
            from dateutil.relativedelta import relativedelta
            try:
                from .payroll import IncrementSettings
                increment_settings = IncrementSettings.get_active()
                cycle_months = increment_settings.cycle_months
            except:
                cycle_months = 6
            instance.next_increment_date = instance.date_hired + relativedelta(months=cycle_months)
            Employees.objects.filter(pk=instance.pk).update(next_increment_date=instance.next_increment_date)
        except Exception:
            pass


@receiver(post_save, sender=Employees)
def ensure_user_for_employee(sender, instance, created, **kwargs):
    if not created or instance.user_id:
        return
    username = _unique_username_from_firstname(instance.firstname or "", fallback=instance.code or "user")
    generated_password = generate_secure_password(length=12)
    user = User.objects.create_user(
        username=username, password=generated_password,
        first_name=instance.firstname or "", last_name=instance.lastname or "",
        email=instance.official_email or instance.email or ""
    )
    user.is_active = True
    user.save(update_fields=["is_active"])
    Employees.objects.filter(pk=instance.pk).update(user=user, temp_password=generated_password)


# ===========================
#   USER PROFILE MODEL
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
