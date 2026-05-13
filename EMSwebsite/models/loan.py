from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal
from datetime import timedelta


class LoanPool(models.Model):
    """Company loan pool management"""
    name = models.CharField(max_length=100, default="Company Loan Pool")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00)
    available_amount = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_loan_pools')

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
        return self.available_amount >= amount

    def approve_loan(self, amount):
        if self.can_approve_loan(amount):
            self.available_amount -= amount
            self.save()
            return True
        return False

    def release_loan_amount(self, amount):
        self.available_amount += amount
        self.save()

    def increase_pool(self, amount):
        self.total_amount += amount
        self.available_amount += amount
        self.save()

    def decrease_pool(self, amount):
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
    created_by = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_pool_transactions')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Loan Pool Transaction"
        verbose_name_plural = "Loan Pool Transactions"

    def __str__(self):
        return f"{self.get_transaction_type_display()} - ${self.amount}"


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

    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='loans')
    loan_pool = models.ForeignKey(LoanPool, on_delete=models.CASCADE, related_name='loans', null=True, blank=True)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    number_of_installments = models.PositiveIntegerField()
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    purpose = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=LOAN_STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
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
        if self.status in ['approved', 'active']:
            active_loans = Loan.objects.filter(employee=self.employee, status__in=['approved', 'active']).exclude(id=self.id)
            if active_loans.exists():
                raise ValidationError("Employee already has an active loan. Only one active loan per employee is allowed.")
        if self.employee.salary and self.loan_amount:
            max_allowed = Decimal(self.employee.salary) * Decimal('1.5')
            if self.loan_amount > max_allowed:
                raise ValidationError(f"Loan amount cannot exceed 1.5 times monthly salary (${max_allowed:.2f})")
        if self.loan_pool and not self.loan_pool.can_approve_loan(self.loan_amount):
            raise ValidationError(f"Insufficient funds in loan pool. Available: ${self.loan_pool.available_amount}")

    def save(self, *args, **kwargs):
        if not self.total_amount:
            interest_amount = (self.loan_amount * self.interest_rate) / 100
            self.total_amount = self.loan_amount + interest_amount
        if not self.monthly_payment and self.number_of_installments > 0:
            self.monthly_payment = self.total_amount / self.number_of_installments
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + timedelta(days=self.number_of_installments * 30)
        self.clean()
        super().save(*args, **kwargs)

    def can_approve_with_pool_constraints(self):
        if not self.loan_pool:
            return True, self.loan_amount
        if self.loan_pool.can_approve_loan(self.loan_amount):
            return True, self.loan_amount
        else:
            return False, self.loan_pool.available_amount

    def approve_with_pool_constraints(self):
        if not self.loan_pool:
            self.status = 'approved'
            self.save()
            return True, self.loan_amount
        can_approve, approved_amount = self.can_approve_with_pool_constraints()
        if can_approve:
            self.loan_pool.approve_loan(self.loan_amount)
            self.status = 'approved'
            self.save()
            return True, self.loan_amount
        elif approved_amount > 0:
            self.original_requested_amount = self.loan_amount
            self.loan_amount = approved_amount
            self.is_partial_loan = True
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

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_repayments')
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
        if self.loan.loan_pool and self.loan.remaining_balance <= 0:
            self.loan.status = 'completed'
            self.loan.save()
