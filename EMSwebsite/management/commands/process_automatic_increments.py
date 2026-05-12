"""
Management command to process automatic salary increments.
Checks for employees who have reached their 6-month increment date and applies increments.

Run this daily via cron or scheduled task.

Usage:
    python manage.py process_automatic_increments
    python manage.py process_automatic_increments --dry-run
    python manage.py process_automatic_increments --date 2024-01-15
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from decimal import Decimal
from EISwebsite.models import (
    Employees, SalaryIncrement, IncrementSettings, Notification, UserProfile
)
from django.contrib.auth.models import User
from EISwebsite.utils.increment_notifications import send_increment_notifications


class Command(BaseCommand):
    help = 'Process automatic salary increments for employees who have reached their increment date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually applying increments (for testing)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Process increments for a specific date (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument(
            '--employee-id',
            type=int,
            help='Process increment for a specific employee ID only',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        target_date_str = options.get('date')
        employee_id = options.get('employee_id')

        # Determine the target date
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Invalid date format: {target_date_str}. Use YYYY-MM-DD'))
                return
        else:
            target_date = date.today()

        self.stdout.write(f'Processing automatic increments for date: {target_date.strftime("%Y-%m-%d")}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        # Get active increment settings
        increment_settings = IncrementSettings.get_active()

        if not increment_settings.is_active:
            self.stdout.write(self.style.WARNING('Automatic increments are currently disabled in settings.'))
            return

        # Build query for employees eligible for increment
        query = Employees.objects.filter(status=1)  # Only active employees

        if employee_id:
            query = query.filter(id=employee_id)
            if not query.exists():
                self.stdout.write(self.style.ERROR(f'Employee with ID {employee_id} not found or not active.'))
                return

        # Find employees whose next_increment_date is today or has passed
        eligible_employees = []

        for employee in query:
            # Calculate next increment date if not set
            if not employee.next_increment_date:
                # Use last_increment_date if available, otherwise use date_hired
                base_date = employee.last_increment_date or employee.date_hired
                if base_date:
                    from dateutil.relativedelta import relativedelta
                    employee.next_increment_date = base_date + relativedelta(months=increment_settings.cycle_months)
                    if not dry_run:
                        employee.save(update_fields=['next_increment_date'])
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping {employee.firstname} {employee.lastname or ""} ({employee.code}): No joining date or last increment date'
                        )
                    )
                    continue

            # Check if increment date has been reached
            if employee.next_increment_date <= target_date:
                eligible_employees.append(employee)

        if not eligible_employees:
            self.stdout.write(self.style.SUCCESS('No employees are eligible for increment on this date.'))
            return

        self.stdout.write(f'Found {len(eligible_employees)} employee(s) eligible for increment.')

        processed_count = 0
        failed_count = 0

        for employee in eligible_employees:
            try:
                with transaction.atomic():
                    # Get current salary
                    old_salary = Decimal(employee.salary or 0)

                    if old_salary <= 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipping {employee.firstname} {employee.lastname or ""} ({employee.code}): Current salary is 0 or not set'
                            )
                        )
                        continue

                    # Calculate new salary based on settings
                    if increment_settings.use_percentage:
                        increase_percent = increment_settings.increment_percentage
                        increase_amount = old_salary * (increase_percent / Decimal('100'))
                        new_salary = old_salary + increase_amount
                    else:
                        increase_amount = increment_settings.increment_amount
                        new_salary = old_salary + increase_amount
                        increase_percent = (increase_amount / old_salary) * Decimal('100') if old_salary > 0 else Decimal('0')

                    # Round to 2 decimal places
                    new_salary = round(new_salary, 2)
                    increase_amount = round(increase_amount, 2)
                    increase_percent = round(increase_percent, 2)

                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Would apply increment to {employee.firstname} {employee.lastname or ""} ({employee.code}): '
                                f'${old_salary} → ${new_salary} (+{increase_percent}% / +${increase_amount})'
                            )
                        )
                        processed_count += 1
                    else:
                        # Create increment record
                        increment = SalaryIncrement.objects.create(
                            employee=employee,
                            old_salary=old_salary,
                            new_salary=new_salary,
                            increase_percent=increase_percent,
                            increase_amount=increase_amount,
                            effective_date=target_date,
                            reason=f'Automatic {increment_settings.cycle_months}-month increment',
                            is_automatic=True,
                            notification_sent=False
                        )

                        # Update employee salary and increment dates
                        employee.salary = int(new_salary)  # Employees.salary is IntegerField
                        employee.last_increment_date = target_date

                        # Calculate next increment date
                        from dateutil.relativedelta import relativedelta
                        employee.next_increment_date = target_date + relativedelta(months=increment_settings.cycle_months)

                        employee.save(update_fields=['salary', 'last_increment_date', 'next_increment_date'])

                        # Send notifications
                        try:
                            send_increment_notifications(increment)
                            increment.notification_sent = True
                            increment.save(update_fields=['notification_sent'])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Increment applied and notifications sent for {employee.firstname} {employee.lastname or ""} ({employee.code})'
                                )
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'✓ Increment applied but notification failed for {employee.firstname} {employee.lastname or ""} ({employee.code}): {str(e)}'
                                )
                            )

                        processed_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed to process increment for {employee.firstname} {employee.lastname or ""} ({employee.code}): {str(e)}'
                    )
                )
                failed_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Summary: {processed_count} increment(s) processed, {failed_count} failed'
            )
        )













