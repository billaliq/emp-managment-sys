"""
Management command to fix attendance records that have status='holiday'
but the date is no longer a holiday in the database.

Usage: python manage.py fix_holiday_status
       python manage.py fix_holiday_status --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from EMSwebsite.models import Attendance, HolidayDate


class Command(BaseCommand):
    help = 'Fix attendance records with status=holiday for dates that are no longer holidays'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually updating records',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Fix records for a specific date (YYYY-MM-DD format)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_date = options.get('date')

        # Get all attendance records with holiday status
        if specific_date:
            from datetime import datetime
            try:
                target_date = datetime.strptime(specific_date, '%Y-%m-%d').date()
                records_to_fix = Attendance.objects.filter(
                    date=target_date,
                    status='holiday'
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'Invalid date format: {specific_date}. Use YYYY-MM-DD')
                )
                return
        else:
            records_to_fix = Attendance.objects.filter(status='holiday')

        count = records_to_fix.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No records found with status=holiday that need fixing.')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'Found {count} attendance record(s) with status=holiday.')
        )

        # Get all current holiday dates
        current_holidays = set(HolidayDate.objects.values_list('date', flat=True))

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No records will be updated.\n')
            )
            self.stdout.write(f'Current holidays in database: {len(current_holidays)}')
            if current_holidays:
                self.stdout.write(f'Holiday dates: {sorted(current_holidays)[:10]}...')
            self.stdout.write('')

        fixed_count = 0
        skipped_count = 0

        with transaction.atomic():
            for record in records_to_fix.select_for_update():
                # Check if this date is still a holiday
                if record.date in current_holidays:
                    # Date is still a holiday, skip it
                    skipped_count += 1
                    if dry_run:
                        self.stdout.write(
                            f'  SKIP: {record.employee.code} - {record.date} '
                            f'(date is still a holiday)'
                        )
                    continue

                # This date is NO LONGER a holiday - fix it
                old_status = record.status

                # Determine new status based on attendance data
                if record.check_in_time or record.check_out_time:
                    # Employee had attendance - mark as present
                    new_status = 'present'
                else:
                    # No attendance - mark as absent
                    new_status = 'absent'

                if dry_run:
                    self.stdout.write(
                        f'  FIX: {record.employee.code} - {record.date} '
                        f'(status: {old_status} -> {new_status})'
                    )
                    if record.check_in_time or record.check_out_time:
                        self.stdout.write(
                            f'       Check-in: {record.check_in_time}, '
                            f'Check-out: {record.check_out_time}'
                        )
                else:
                    record.status = new_status
                    record._explicit_status = True

                    # Clear holiday-related notes
                    if record.notes and 'holiday' in record.notes.lower():
                        record.notes = ''

                    record.save(update_fields=['status', 'notes', 'updated_at'])

                fixed_count += 1

        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    f'Would fix {fixed_count} record(s), skip {skipped_count} record(s).'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Run without --dry-run to apply changes.'
                )
            )
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully fixed {fixed_count} attendance record(s).'
                )
            )
            if skipped_count > 0:
                self.stdout.write(
                    f'Skipped {skipped_count} record(s) (date is still a holiday).'
                )

