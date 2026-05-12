"""
Management command to fix attendance records that have check-in/check-out data
but are still marked as 'absent'. This command will recalculate the status
based on the attendance data.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from EISwebsite.models import Attendance


class Command(BaseCommand):
    help = 'Fix attendance records that have check-in/check-out data but are marked as absent'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually updating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find all attendance records that have check-in or check-out data
        # but are marked as absent
        records_to_fix = Attendance.objects.filter(
            status='absent'
        ).filter(
            Q(check_in_time__isnull=False) | Q(check_out_time__isnull=False)
        )

        count = records_to_fix.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No records found that need fixing.')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'Found {count} attendance record(s) that need fixing.')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No records will be updated.')
            )
            for record in records_to_fix[:10]:  # Show first 10
                self.stdout.write(
                    f'  - {record.employee} on {record.date}: '
                    f'check-in={record.check_in_time}, check-out={record.check_out_time}'
                )
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more records')
            return

        # Fix the records
        fixed_count = 0
        for record in records_to_fix:
            # Clear the explicit status flag and let save() recalculate
            record._explicit_status = False
            # Save will automatically recalculate status based on check-in/check-out
            record.save()
            fixed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully fixed {fixed_count} attendance record(s).'
            )
        )

