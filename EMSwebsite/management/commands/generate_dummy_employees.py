"""
Management command to generate dummy employee data for testing
Usage: python manage.py generate_dummy_employees --count 50
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import random
from EMSwebsite.models import Employees, Department, Position

# Sample data for generating realistic employees
FIRST_NAMES = [
    'Ahmed', 'Ali', 'Bilal', 'Hassan', 'Hussain', 'Ibrahim', 'Imran', 'Kamran', 'Kashif', 'Mohammad',
    'Muhammad', 'Nadeem', 'Nasir', 'Omar', 'Qasim', 'Rashid', 'Saeed', 'Tariq', 'Usman', 'Waseem',
    'Yasir', 'Zain', 'Zubair', 'Ayesha', 'Fatima', 'Hina', 'Kiran', 'Maria', 'Nida', 'Rabia',
    'Sana', 'Sara', 'Shazia', 'Sobia', 'Tahira', 'Uzma', 'Zainab', 'Amina', 'Farah', 'Hira'
]

LAST_NAMES = [
    'Ahmed', 'Ali', 'Khan', 'Malik', 'Hassan', 'Hussain', 'Iqbal', 'Raza', 'Shah', 'Sheikh',
    'Butt', 'Chaudhry', 'Mirza', 'Qureshi', 'Rashid', 'Siddiqui', 'Tariq', 'Yousaf', 'Zaman', 'Abbas'
]

JOB_TITLES = [
    'Software Developer', 'Senior Developer', 'Junior Developer', 'Frontend Developer', 'Backend Developer',
    'Full Stack Developer', 'QA Engineer', 'Senior QA Engineer', 'DevOps Engineer', 'UI/UX Designer',
    'Project Manager', 'Product Manager', 'Business Analyst', 'Data Analyst', 'HR Manager',
    'HR Executive', 'Accountant', 'Finance Manager', 'Marketing Manager', 'Sales Executive',
    'Technical Lead', 'Team Lead', 'System Administrator', 'Network Engineer', 'Database Administrator'
]

BANKS = [
    'HBL', 'UBL', 'MCB', 'Allied Bank', 'Bank Alfalah', 'Meezan Bank', 'Faysal Bank', 'Standard Chartered'
]

TEAMS = ['Sir Faisal', 'Sir Zubair', 'Sir Govinda', 'Sir Suhail']
WORK_MODES = ['Onsite', 'Remote', 'Hybrid']
EMPLOYMENT_TYPES = ['Full Time', 'Part Time']
GENDERS = ['Male', 'Female']
MARITAL_STATUSES = ['Single', 'Married']
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']


class Command(BaseCommand):
    help = 'Generate dummy employee data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of employees to generate (default: 50)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing dummy employees before generating new ones'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options['count']
        clear_existing = options.get('clear', False)

        # Get or create departments and positions
        departments = list(Department.objects.all())
        positions = list(Position.objects.all())

        if not departments:
            self.stdout.write(self.style.WARNING('No departments found. Creating default departments...'))
            departments = [
                Department.objects.get_or_create(name='IT')[0],
                Department.objects.get_or_create(name='HR')[0],
                Department.objects.get_or_create(name='Finance')[0],
                Department.objects.get_or_create(name='Marketing')[0],
            ]

        if not positions:
            self.stdout.write(self.style.WARNING('No positions found. Creating default positions...'))
            positions = [
                Position.objects.get_or_create(name='Software Developer')[0],
                Position.objects.get_or_create(name='Senior Developer')[0],
                Position.objects.get_or_create(name='HR Executive')[0],
                Position.objects.get_or_create(name='Accountant')[0],
            ]

        # Clear existing dummy employees if requested
        if clear_existing:
            deleted = Employees.objects.filter(
                code__startswith='EMP'
            ).delete()[0]
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} existing dummy employees.'))

        # Generate employees
        created_count = 0
        skipped_count = 0
        start_code = 1001

        # Find the highest existing employee code
        existing_codes = Employees.objects.filter(code__startswith='EMP').values_list('code', flat=True)
        if existing_codes:
            codes_nums = []
            for code in existing_codes:
                try:
                    num = int(code.replace('EMP', ''))
                    codes_nums.append(num)
                except ValueError:
                    continue
            if codes_nums:
                start_code = max(codes_nums) + 1

        for i in range(count):
            code = f'EMP{start_code + i:04d}'

            # Check if code already exists
            if Employees.objects.filter(code=code).exists():
                skipped_count += 1
                continue

            firstname = random.choice(FIRST_NAMES)
            lastname = random.choice(LAST_NAMES)

            # Generate email
            email = f"{firstname.lower()}.{lastname.lower()}{i}@funprime.com"
            official_email = f"{firstname.lower()}.{lastname.lower()}@funprime.tech"

            # Generate dates
            today = timezone.now().date()
            dob = today - timedelta(days=random.randint(7300, 14600))  # Age between 20-40 years
            date_hired = today - timedelta(days=random.randint(30, 1095))  # Hired between 1 month to 3 years ago

            # Generate salary (between 30k to 200k)
            salary = random.randint(30000, 200000)

            # Create employee
            employee = Employees.objects.create(
                code=code,
                firstname=firstname,
                lastname=lastname,
                email=email,
                official_email=official_email,
                gender=random.choice(GENDERS),
                marital_status=random.choice(MARITAL_STATUSES),
                blood_group=random.choice(BLOOD_GROUPS),
                dob=dob,
                contact_1=f"03{random.randint(10000000, 99999999)}",
                emergency_contact=f"03{random.randint(10000000, 99999999)}",
                emergency_contact_person=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                present_address=f"House {random.randint(1, 999)}, Street {random.randint(1, 50)}, Sector {random.choice(['A', 'B', 'C', 'D'])}",
                permanent_address=f"House {random.randint(1, 999)}, Street {random.randint(1, 50)}, Sector {random.choice(['A', 'B', 'C', 'D'])}",
                team=random.choice(TEAMS),
                department=random.choice(departments),
                position=random.choice(positions),
                job_title=random.choice(JOB_TITLES),
                work_mode=random.choice(WORK_MODES),
                employment_type=random.choice(EMPLOYMENT_TYPES),
                date_hired=date_hired,
                salary=salary,
                bank_name=random.choice(BANKS),
                branch_name=f"{random.choice(['Main', 'Gulshan', 'DHA', 'Model Town'])} Branch",
                account_title=f"{firstname} {lastname}",
                account_number=f"{random.randint(1000000000, 9999999999)}",
                status=1,  # Active
                location="FunPrime Technology",
            )

            created_count += 1

            if created_count % 10 == 0:
                self.stdout.write(f'Created {created_count} employees...')

        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully created {created_count} dummy employees!\n'
            f'Skipped {skipped_count} employees (duplicate codes).\n'
            f'Employee codes range: EMP{start_code:04d} to EMP{start_code + created_count - 1:04d}'
        ))

