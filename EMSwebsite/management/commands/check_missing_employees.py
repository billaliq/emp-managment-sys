"""
Management command to check for missing employee IDs in the system.
This command will check if specific employee IDs exist in the database.

Usage:
    python manage.py check_missing_employees
    python manage.py check_missing_employees --create-placeholders
    python manage.py check_missing_employees --ids 6030,6031,6032
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from EMSwebsite.models import Employees
from django.utils import timezone


class Command(BaseCommand):
    help = 'Check for missing employee IDs in the system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            type=str,
            help='Comma-separated list of employee IDs to check (e.g., "6030,6031,6032")',
        )
        parser.add_argument(
            '--create-placeholders',
            action='store_true',
            help='Create placeholder employee records for missing IDs',
        )
        parser.add_argument(
            '--status',
            type=int,
            default=2,
            help='Status for created placeholder employees (1=Active, 2=Inactive). Default: 2 (Inactive)',
        )

    def handle(self, *args, **options):
        # Default list of employee IDs to check (from user's report)
        default_ids = ['6030', '6031', '6032', '6033', '6034', '6035', '6036', '6037', '6038', '6039',
                      '6041', '6042', '6043', '6044', '6045', '6046', '6047', '6048', '6049']

        # Get IDs from command line or use defaults
        ids_input = options.get('ids')
        if ids_input:
            employee_ids = [id.strip() for id in ids_input.split(',')]
        else:
            employee_ids = default_ids

        self.stdout.write(self.style.SUCCESS(f'\nChecking {len(employee_ids)} employee ID(s)...\n'))

        # Check which IDs exist
        existing_ids = []
        missing_ids = []

        for emp_id in employee_ids:
            try:
                employee = Employees.objects.filter(code=str(emp_id)).first()
                if employee:
                    existing_ids.append({
                        'code': employee.code,
                        'name': f"{employee.firstname} {employee.lastname or ''}".strip(),
                        'status': 'Active' if employee.status == 1 else 'Inactive',
                        'id': employee.id
                    })
                else:
                    missing_ids.append(emp_id)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error checking ID {emp_id}: {str(e)}'))
                missing_ids.append(emp_id)

        # Report results
        self.stdout.write(self.style.SUCCESS(f'\n[FOUND] Found {len(existing_ids)} existing employee(s):'))
        for emp in existing_ids:
            self.stdout.write(f'  - ID {emp["code"]}: {emp["name"]} ({emp["status"]})')

        if missing_ids:
            self.stdout.write(self.style.WARNING(f'\n[MISSING] Missing {len(missing_ids)} employee ID(s):'))
            for emp_id in missing_ids:
                self.stdout.write(f'  - {emp_id}')
        else:
            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] All employee IDs exist in the system!'))

        # Option to create placeholders
        if missing_ids and options.get('create_placeholders'):
            status = options.get('status', 2)
            self.stdout.write(self.style.WARNING(f'\nCreating placeholder employees for {len(missing_ids)} missing ID(s)...'))

            created_count = 0
            with transaction.atomic():
                for emp_id in missing_ids:
                    try:
                        # Check if ID was created by another process
                        if Employees.objects.filter(code=str(emp_id)).exists():
                            self.stdout.write(self.style.WARNING(f'  - ID {emp_id} already exists, skipping'))
                            continue

                        # Create placeholder employee
                        employee = Employees.objects.create(
                            code=str(emp_id),
                            firstname=f'Placeholder {emp_id}',
                            lastname='',
                            status=status,
                            date_added=timezone.now()
                        )
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f'  [OK] Created placeholder for ID {emp_id}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  [ERROR] Error creating ID {emp_id}: {str(e)}'))

            if created_count > 0:
                self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Successfully created {created_count} placeholder employee(s)'))
                self.stdout.write(self.style.WARNING('\nNote: These are placeholder records. Please update them with actual employee information.'))
        elif missing_ids:
            self.stdout.write(self.style.WARNING('\nTip: Use --create-placeholders to create placeholder records for missing IDs'))

        self.stdout.write('')

