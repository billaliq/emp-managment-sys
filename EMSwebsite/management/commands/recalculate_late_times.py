"""
Management command to recalculate late_in times for all attendance records.
This fixes the late time calculation to use 9:15 AM instead of 9:00 AM.

Usage: python manage.py recalculate_late_times
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from EMSwebsite.models import Attendance


class Command(BaseCommand):
    help = 'Recalculate late_in times for all attendance records using 9:15 AM threshold'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Get all attendance records with check-in times
        attendance_records = Attendance.objects.filter(
            check_in_time__isnull=False
        ).select_related('employee')

        total_records = attendance_records.count()
        updated_count = 0

        self.stdout.write(
            self.style.SUCCESS(
                f'\nFound {total_records} attendance records with check-in times.\n'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No records will be updated\n')
            )

        with transaction.atomic():
            for record in attendance_records:
                # Store old value for comparison
                old_late_in = record.late_in

                # Recalculate durations (this will use the new 9:15 AM threshold)
                record.calculate_durations()

                # Check if late_in changed
                if old_late_in != record.late_in:
                    updated_count += 1

                    if dry_run:
                        old_display = self._format_duration(old_late_in) if old_late_in else 'None'
                        new_display = self._format_duration(record.late_in) if record.late_in else 'None'
                        self.stdout.write(
                            f'Would update: {record.employee.code} - {record.date} '
                            f'(Late: {old_display} -> {new_display})'
                        )
                    else:
                        # Save the record (this will also recalculate status)
                        record.save()

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nWould update {updated_count} out of {total_records} records.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully updated {updated_count} out of {total_records} records.'
                )
            )

    def _format_duration(self, delta):
        """Format timedelta as hours and minutes"""
        if not delta:
            return '0h 0m'
        total_seconds = delta.total_seconds()
        total_minutes = int(total_seconds // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f'{hours}h {minutes:02d}m'

