"""
Management command to sync employees from ZK biometric device to Django database.

Usage:
    python manage.py sync_zk_employees
    python manage.py sync_zk_employees --dry-run
    python manage.py sync_zk_employees --device-ip 36.50.12.191 --port 1752
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date
from EISwebsite.models import Employees

# Try to import ZK library
try:
    from zk import ZK
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False
    ZK = None


class Command(BaseCommand):
    help = 'Sync employees from ZK biometric device to Django database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually creating employees',
        )
        parser.add_argument(
            '--device-ip',
            type=str,
            default='36.50.12.191',
            help='ZK device IP address (default: 36.50.12.191)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=1752,
            help='ZK device port (default: 1752)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='Connection timeout in seconds (default: 15)',
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only sync employees that are missing from the database',
        )

    def handle(self, *args, **options):
        if not ZK_AVAILABLE:
            self.stdout.write(
                self.style.ERROR(
                    'ZK library is not installed. Please install it with: pip install pyzk'
                )
            )
            return

        dry_run = options.get('dry_run', False)
        device_ip = options.get('device_ip', '36.50.12.191')
        port = options.get('port', 1752)
        timeout = options.get('timeout', 15)
        missing_only = options.get('missing_only', False)

        self.stdout.write(self.style.SUCCESS(f'\nConnecting to ZK device at {device_ip}:{port}...'))

        try:
            zk = ZK(device_ip, port=port, timeout=timeout)
            conn = zk.connect()
            conn.disable_device()

            self.stdout.write(self.style.SUCCESS('Connected successfully. Fetching users...'))

            users = conn.get_users()
            self.stdout.write(self.style.SUCCESS(f'Found {len(users)} user(s) on device.\n'))

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE - No employees will be created\n'))

            new_employees = []
            skipped_existing = []
            skipped_incomplete = []

            for user in users:
                # Skip incomplete entries
                if not user.user_id or not user.name:
                    skipped_incomplete.append({
                        'user_id': user.user_id or 'N/A',
                        'name': user.name or 'N/A'
                    })
                    continue

                user_id_str = str(user.user_id)
                user_name = user.name.strip()

                # Check if employee already exists
                if Employees.objects.filter(code=user_id_str).exists():
                    if missing_only:
                        skipped_existing.append({
                            'code': user_id_str,
                            'name': user_name
                        })
                    continue

                # Prepare employee data
                username = user_name.split()[0].lower() if user_name else f"user{user_id_str}"
                official_email = f"{username}@funprimetechnology.com"

                if not dry_run:
                    # Create employee
                    try:
                        with transaction.atomic():
                            emp = Employees.objects.create(
                                code=user_id_str,
                                firstname=user_name,
                                lastname="",
                                official_email=official_email,
                                date_hired=date.today(),
                                status=1  # Active
                            )
                            new_employees.append({
                                'code': emp.code,
                                'name': emp.firstname,
                                'email': emp.official_email,
                                'id': emp.id
                            })
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error creating employee {user_id_str}: {str(e)}')
                        )
                else:
                    # Dry run - just collect info
                    new_employees.append({
                        'code': user_id_str,
                        'name': user_name,
                        'email': official_email,
                        'id': 'N/A (dry run)'
                    })

            conn.enable_device()
            conn.disconnect()

            # Report results
            self.stdout.write(self.style.SUCCESS(f'\n[RESULTS]'))
            self.stdout.write(f'  New employees to create: {len(new_employees)}')
            if skipped_existing:
                self.stdout.write(f'  Existing employees skipped: {len(skipped_existing)}')
            if skipped_incomplete:
                self.stdout.write(f'  Incomplete entries skipped: {len(skipped_incomplete)}')

            if new_employees:
                self.stdout.write(self.style.SUCCESS(f'\n[NEW EMPLOYEES]'))
                for emp in new_employees:
                    self.stdout.write(f'  - ID {emp["code"]}: {emp["name"]} ({emp["email"]})')

            if skipped_existing and missing_only:
                self.stdout.write(self.style.WARNING(f'\n[EXISTING EMPLOYEES] (skipped)'))
                for emp in skipped_existing[:10]:  # Show first 10
                    self.stdout.write(f'  - ID {emp["code"]}: {emp["name"]}')
                if len(skipped_existing) > 10:
                    self.stdout.write(f'  ... and {len(skipped_existing) - 10} more')

            if skipped_incomplete:
                self.stdout.write(self.style.WARNING(f'\n[INCOMPLETE ENTRIES] (skipped)'))
                for entry in skipped_incomplete[:5]:  # Show first 5
                    self.stdout.write(f'  - User ID: {entry["user_id"]}, Name: {entry["name"]}')
                if len(skipped_incomplete) > 5:
                    self.stdout.write(f'  ... and {len(skipped_incomplete) - 5} more')

            if not dry_run and new_employees:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n[SUCCESS] Successfully synced {len(new_employees)} employee(s) from ZK device!'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        '\nNote: Employee user accounts will be auto-created by the post_save signal.'
                    )
                )
            elif dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        '\n[DRY RUN] No employees were actually created. Run without --dry-run to sync.'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[ERROR] Failed to sync from ZK device: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))

        self.stdout.write('')

