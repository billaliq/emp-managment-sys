from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Employees, Loan, LoanPool, LoanPoolTransaction, LeaveRequest, Attendance, Team, PayrollRecord, SalaryDisbursement, SalaryIncrement
from decimal import Decimal
from .utils.notifications import create_notification, notify_admins, notify_employee


@receiver(pre_delete, sender=Employees)
def handle_employee_resignation(sender, instance, **kwargs):
    """
    Handle employee resignation by cancelling active loans and releasing pool funds
    """
    # Get active loans for the employee
    active_loans = Loan.objects.filter(
        employee=instance,
        status__in=['approved', 'active']
    )

    for loan in active_loans:
        # Cancel the loan
        loan.status = 'cancelled'
        loan.save()

        # Release funds back to pool
        if loan.loan_pool:
            loan.loan_pool.release_loan_amount(loan.loan_amount)

            # Create transaction record
            LoanPoolTransaction.objects.create(
                pool=loan.loan_pool,
                transaction_type='loan_cancellation',
                amount=loan.loan_amount,
                description=f'Loan cancelled due to employee resignation: {instance.firstname} {instance.lastname}',
                created_by=None  # System action
            )


@receiver(post_save, sender=Loan)
def handle_loan_status_change(sender, instance, created, **kwargs):
    """
    Handle loan status changes and pool updates, and send notifications
    """
    try:
        # Track previous status if this is an update
        previous_status = None
        if not created and hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status

        if created:
            # New loan created - notify admins
            notify_admins(
                'system',
                'New Loan Application',
                f"{instance.employee.firstname} {instance.employee.lastname or ''} has applied for a loan of ${instance.loan_amount:.2f}.",
                instance.id,
                'Loan'
            )
        else:
            # Loan updated - check for status changes
            if previous_status and previous_status != instance.status:
                if instance.status == 'approved':
                    # Notify employee about approval
                    notify_employee(
                        instance.employee,
                        'system',
                        'Loan Approved',
                        f"Your loan application of ${instance.loan_amount:.2f} has been approved. Monthly payment: ${instance.monthly_payment:.2f}.",
                        instance.id,
                        'Loan'
                    )
                elif instance.status == 'rejected':
                    # Notify employee about rejection
                    notify_employee(
                        instance.employee,
                        'system',
                        'Loan Rejected',
                        f"Your loan application of ${instance.loan_amount:.2f} has been rejected.",
                        instance.id,
                        'Loan'
                    )
                elif instance.status == 'completed':
                    # Notify employee about completion
                    notify_employee(
                        instance.employee,
                        'system',
                        'Loan Completed',
                        f"Your loan of ${instance.loan_amount:.2f} has been fully repaid and completed.",
                        instance.id,
                        'Loan'
                    )

            # If loan is completed, release any remaining funds
            if instance.status == 'completed' and instance.loan_pool:
                remaining_amount = instance.remaining_balance
                if remaining_amount > 0:
                    instance.loan_pool.release_loan_amount(remaining_amount)

                    # Create transaction record
                    LoanPoolTransaction.objects.create(
                        pool=instance.loan_pool,
                        transaction_type='loan_repayment',
                        amount=remaining_amount,
                        description=f'Final loan repayment for {instance.employee.firstname} {instance.employee.lastname}',
                        created_by=None  # System action
                    )
    except Exception as e:
        pass


@receiver(pre_save, sender=Loan)
def track_loan_status_change(sender, instance, **kwargs):
    """Track previous status before save to detect changes"""
    if instance.pk:
        try:
            old_instance = Loan.objects.get(pk=instance.pk)
            instance._previous_status = old_instance.status
        except Loan.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


# Notification signals for system events
@receiver(post_save, sender=LeaveRequest)
def notify_leave_request(sender, instance, created, **kwargs):
    """Create notifications when leave requests are created or status changes"""
    try:
        if created:
            # New leave request - notify admins
            notify_admins(
                'leave',
                'New Leave Request',
                f"{instance.employee.firstname} {instance.employee.lastname or ''} has requested {instance.get_leave_type_display()} from {instance.start_date} to {instance.end_date}.",
                instance.id,
                'LeaveRequest'
            )
        else:
            # Status changed - notify employee
            if instance.status == 'approved':
                notify_employee(
                    instance.employee,
                    'leave',
                    'Leave Request Approved',
                    f"Your {instance.get_leave_type_display()} request from {instance.start_date} to {instance.end_date} has been approved.",
                    instance.id,
                    'LeaveRequest'
                )
            elif instance.status == 'rejected':
                notify_employee(
                    instance.employee,
                    'leave',
                    'Leave Request Rejected',
                    f"Your {instance.get_leave_type_display()} request from {instance.start_date} to {instance.end_date} has been rejected. Reason: {instance.rejection_reason or 'No reason provided'}.",
                    instance.id,
                    'LeaveRequest'
                )
    except Exception as e:
        # Silently fail to avoid breaking the save operation
        pass


@receiver(post_save, sender=Employees)
def notify_new_employee(sender, instance, created, **kwargs):
    """Create notification when new employee is added or updated"""
    try:
        if created:
            notify_admins(
                'system',
                'New Employee Added',
                f"New employee {instance.firstname} {instance.lastname or ''} ({instance.code}) has been added to the system.",
                instance.id,
                'Employees'
            )
        else:
            # Track important updates
            if hasattr(instance, '_previous_salary') and instance._previous_salary != instance.salary:
                # Salary changed (but not through increment - that has its own notification)
                if not hasattr(instance, '_is_increment_update'):
                    notify_employee(
                        instance,
                        'system',
                        'Salary Updated',
                        f"Your salary has been updated to ${instance.salary:,}.",
                        instance.id,
                        'Employees'
                    )
            if hasattr(instance, '_previous_department_id') and instance._previous_department_id != (instance.department.id if instance.department else None):
                # Department changed
                new_dept = instance.department.name if instance.department else 'No Department'
                notify_employee(
                    instance,
                    'system',
                    'Department Changed',
                    f"Your department has been changed to {new_dept}.",
                    instance.id,
                    'Employees'
                )
    except Exception as e:
        pass


@receiver(pre_save, sender=Employees)
def track_employee_changes(sender, instance, **kwargs):
    """Track previous values before save to detect changes"""
    if instance.pk:
        try:
            old_instance = Employees.objects.get(pk=instance.pk)
            instance._previous_salary = old_instance.salary
            instance._previous_department_id = old_instance.department.id if old_instance.department else None
        except Employees.DoesNotExist:
            instance._previous_salary = None
            instance._previous_department_id = None
    else:
        instance._previous_salary = None
        instance._previous_department_id = None


@receiver(post_save, sender=PayrollRecord)
def notify_payroll_created(sender, instance, created, **kwargs):
    """Notify employee when payroll record is created"""
    try:
        if created:
            notify_employee(
                instance.employee,
                'payroll',
                'Payroll Record Created',
                f"A payroll record has been created for you. Net salary: ${instance.net_salary:,.2f} for {instance.pay_date.strftime('%B %d, %Y')}.",
                instance.id,
                'PayrollRecord'
            )
    except Exception as e:
        pass


@receiver(post_save, sender=SalaryDisbursement)
def notify_salary_disbursement(sender, instance, created, **kwargs):
    """Notify when salary disbursement status changes"""
    try:
        if not created and instance.status == 'completed':
            # Notify all employees who received payment
            payment_records = instance.payment_records.filter(status='success')
            for record in payment_records:
                notify_employee(
                    record.employee,
                    'payroll',
                    'Salary Disbursed',
                    f"Your salary of ${record.amount:,.2f} has been successfully disbursed to your bank account.",
                    instance.id,
                    'SalaryDisbursement'
                )
    except Exception as e:
        pass


@receiver(post_save, sender=SalaryIncrement)
def notify_salary_increment(sender, instance, created, **kwargs):
    """Notify employee when salary increment is created"""
    try:
        if created and not instance.notification_sent:
            # Mark employee update as increment to avoid duplicate notification
            if instance.employee:
                instance.employee._is_increment_update = True
                instance.employee.save()

            notify_employee(
                instance.employee,
                'increment',
                'Salary Increment',
                f"Your salary has been increased from ${instance.old_salary:,.2f} to ${instance.new_salary:,.2f} ({instance.increase_percent}% increase). Effective date: {instance.effective_date.strftime('%B %d, %Y')}.",
                instance.id,
                'SalaryIncrement'
            )
            # Mark notification as sent
            instance.notification_sent = True
            instance.save(update_fields=['notification_sent'])
    except Exception as e:
        pass


@receiver(post_save, sender=Attendance)
def notify_attendance_issues(sender, instance, created, **kwargs):
    """Create notifications for attendance issues and updates"""
    try:
        # Track previous status if this is an update
        previous_status = None
        if not created and hasattr(instance, '_previous_status'):
            previous_status = instance._previous_status

        if created:
            # New attendance record created
            if instance.status == 'absent':
                # Notify employee about absence
                notify_employee(
                    instance.employee,
                    'attendance',
                    'Absence Recorded',
                    f"You have been marked as absent for {instance.date.strftime('%B %d, %Y')}.",
                    instance.id,
                    'Attendance'
                )
            elif instance.status == 'late':
                # Notify employee about late arrival
                check_in_str = instance.check_in_time.strftime('%H:%M') if instance.check_in_time else 'N/A'
                notify_employee(
                    instance.employee,
                    'attendance',
                    'Late Arrival',
                    f"You were late on {instance.date.strftime('%B %d, %Y')}. Check-in time: {check_in_str}.",
                    instance.id,
                    'Attendance'
                )
            elif instance.status == 'early-out':
                # Notify employee about early departure
                check_out_str = instance.check_out_time.strftime('%H:%M') if instance.check_out_time else 'N/A'
                early_out_str = instance.early_out_display if instance.early_out_display else ''
                notify_employee(
                    instance.employee,
                    'attendance',
                    'Early Departure',
                    f"You left early on {instance.date.strftime('%B %d, %Y')}. Check-out time: {check_out_str}. {early_out_str}",
                    instance.id,
                    'Attendance'
                )
            elif instance.status == 'late-sitting':
                # Notify employee about late sitting (positive notification)
                check_out_str = instance.check_out_time.strftime('%H:%M') if instance.check_out_time else 'N/A'
                notify_employee(
                    instance.employee,
                    'attendance',
                    'Late Sitting Recorded',
                    f"You worked late on {instance.date.strftime('%B %d, %Y')}. Check-out time: {check_out_str}.",
                    instance.id,
                    'Attendance'
                )
        else:
            # Attendance record updated - check for status changes
            if previous_status and previous_status != instance.status:
                # Status changed - notify employee
                if instance.status == 'absent' and previous_status != 'absent':
                    notify_employee(
                        instance.employee,
                        'attendance',
                        'Attendance Status Updated',
                        f"Your attendance for {instance.date.strftime('%B %d, %Y')} has been updated to Absent.",
                        instance.id,
                        'Attendance'
                    )
                elif instance.status == 'late' and previous_status != 'late':
                    check_in_str = instance.check_in_time.strftime('%H:%M') if instance.check_in_time else 'N/A'
                    notify_employee(
                        instance.employee,
                        'attendance',
                        'Attendance Status Updated',
                        f"Your attendance for {instance.date.strftime('%B %d, %Y')} has been updated to Late. Check-in: {check_in_str}.",
                        instance.id,
                        'Attendance'
                    )
                elif instance.status == 'early-out' and previous_status != 'early-out':
                    check_out_str = instance.check_out_time.strftime('%H:%M') if instance.check_out_time else 'N/A'
                    notify_employee(
                        instance.employee,
                        'attendance',
                        'Attendance Status Updated',
                        f"Your attendance for {instance.date.strftime('%B %d, %Y')} has been updated to Early Out. Check-out: {check_out_str}.",
                        instance.id,
                        'Attendance'
                    )
    except Exception as e:
        pass


@receiver(pre_save, sender=Attendance)
def track_attendance_status_change(sender, instance, **kwargs):
    """Track previous status before save to detect changes"""
    if instance.pk:
        try:
            old_instance = Attendance.objects.get(pk=instance.pk)
            instance._previous_status = old_instance.status
        except Attendance.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None
