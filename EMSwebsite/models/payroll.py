from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal


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
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE)
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

    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name='salary_slip_requests')
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='salary_slip_requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='salary_slip_requests_made')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='salary_slip_requests_decided')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} → {self.payroll_record} ({self.status})"


class SalaryIncrement(models.Model):
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE)
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
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE)
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


class IncrementSettings(models.Model):
    """Dynamic increment settings that can be updated by admin/finance"""
    increment_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=5.00, help_text="Default percentage increase for 6-month increments")
    increment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Fixed increment amount (if set, overrides percentage). Set to 0 to use percentage.")
    use_percentage = models.BooleanField(default=True, help_text="If True, use percentage. If False, use fixed amount.")
    cycle_months = models.IntegerField(default=6, help_text="Number of months between increments")
    is_active = models.BooleanField(default=True, help_text="Enable/disable automatic increments")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_increment_settings')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.use_percentage:
            return f"{self.increment_percentage}% increment every {self.cycle_months} months"
        else:
            return f"${self.increment_amount} increment every {self.cycle_months} months"

    @classmethod
    def get_active(cls):
        obj = cls.objects.filter(is_active=True).first()
        if not obj:
            obj = cls.objects.create()
        return obj

    class Meta:
        verbose_name = "Increment Setting"
        verbose_name_plural = "Increment Settings"
        ordering = ['-updated_at']
