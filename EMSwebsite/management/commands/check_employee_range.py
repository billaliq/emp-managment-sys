"""
Management command to check employee ID ranges and find gaps.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from EMSwebsite.models import Employees


class Command(BaseCommand):
    help = 'Check employee ID ranges and find gaps'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-id',
            type=int,
            default=6000,
            help='Minimum employee ID to check',
        )
        parser.add_argument(
            '--max-id',
            type=int,
            default=6100,
            help='Maximum employee ID to check',
        )

    def handle(self, *args, **options):
        min_id = options.get('min_id', 6000)
        max_id = options.get('max_id', 6100)

        # Exclude dummy/test/sample employees
        exclude_q = Q(
            Q(code__icontains='test') |
            Q(code__icontains='dummy') |
            Q(code__icontains='sample') |
            Q(code__startswith='EMP') |
            Q(firstname__icontains='test') |
            Q(firstname__icontains='dummy') |
            Q(firstname__icontains='sample')
        )

        # Get all employees with numeric codes in the range
        all_employees = Employees.objects.exclude(exclude_q).filter(
            code__regex=r'^\d+$'
        ).order_by('code')

        # Find highest employee ID
        highest = None
        for emp in all_employees:
            try:
                code_num = int(emp.code)
                if min_id <= code_num <= max_id:
                    if highest is None or code_num > highest:
                        highest = code_num
            except ValueError:
                continue

        self.stdout.write(f'\nChecking employee ID range: {min_id} to {max_id}\n')

        if highest:
            self.stdout.write(self.style.SUCCESS(f'Highest employee ID found: {highest}'))
        else:
            self.stdout.write(self.style.WARNING('No employees found in the specified range'))

        # Check for missing IDs in the range
        existing_ids = set()
        for emp in all_employees:
            try:
                code_num = int(emp.code)
                if min_id <= code_num <= max_id:
                    existing_ids.add(code_num)
            except ValueError:
                continue

        missing_ids = []
        for i in range(min_id, max_id + 1):
            if i not in existing_ids:
                missing_ids.append(i)

        if missing_ids:
            self.stdout.write(self.style.WARNING(f'\nMissing {len(missing_ids)} employee ID(s) in range:'))
            # Group consecutive missing IDs
            if len(missing_ids) > 20:
                self.stdout.write(f'  (Showing first 20 of {len(missing_ids)} missing IDs)')
                for mid in missing_ids[:20]:
                    self.stdout.write(f'  - {mid}')
            else:
                for mid in missing_ids:
                    self.stdout.write(f'  - {mid}')
        else:
            self.stdout.write(self.style.SUCCESS('\nNo missing IDs in the specified range'))

        self.stdout.write('')

