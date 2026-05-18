"""
Management command to generate dummy employees with attendance records.
Usage: python manage.py generate_dummy_employees
       python manage.py generate_dummy_employees --count 50
       python manage.py generate_dummy_employees --clear
"""

import random
import sys
from datetime import date, timedelta, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from EMSwebsite.models.employee import Department, Position, Employees
from EMSwebsite.models.attendance import Attendance

# ── Name pools ────────────────────────────────────────────────────────────────
MALE_NAMES = [
    'Ahmed', 'Ali', 'Bilal', 'Hassan', 'Hussain', 'Ibrahim', 'Imran',
    'Kamran', 'Kashif', 'Muhammad', 'Nadeem', 'Omar', 'Qasim', 'Rashid',
    'Saeed', 'Tariq', 'Usman', 'Waseem', 'Yasir', 'Zain', 'Zubair',
    'Faisal', 'Hamza', 'Junaid', 'Khurram', 'Luqman', 'Mohsin', 'Naveed',
]
FEMALE_NAMES = [
    'Ayesha', 'Fatima', 'Hina', 'Kiran', 'Maria', 'Nida', 'Rabia',
    'Sana', 'Sara', 'Shazia', 'Sobia', 'Tahira', 'Uzma', 'Zainab',
    'Amina', 'Farah', 'Hira', 'Iqra', 'Laiba', 'Maham', 'Nimra',
]
LAST_NAMES = [
    'Ahmed', 'Ali', 'Khan', 'Malik', 'Hassan', 'Hussain', 'Iqbal',
    'Raza', 'Shah', 'Sheikh', 'Butt', 'Chaudhry', 'Mirza', 'Qureshi',
    'Rashid', 'Siddiqui', 'Tariq', 'Yousaf', 'Zaman', 'Abbas',
]
FATHER_NAMES = [
    'Abdul Rahman', 'Muhammad Akbar', 'Ghulam Hussain', 'Syed Raza',
    'Chaudhry Aslam', 'Sheikh Imran', 'Haji Bashir', 'Malik Tariq',
]

DEPARTMENTS_DATA = [
    {'name': 'Information Technology', 'description': 'Software development and IT support'},
    {'name': 'Human Resources',        'description': 'Recruitment, payroll, and employee relations'},
    {'name': 'Finance & Accounts',     'description': 'Financial planning and accounting'},
    {'name': 'Marketing',              'description': 'Brand management and digital marketing'},
    {'name': 'Operations',             'description': 'Day-to-day business operations'},
    {'name': 'Sales',                  'description': 'Client acquisition and revenue generation'},
]

POSITIONS_DATA = [
    'Software Developer', 'Senior Software Developer', 'Junior Developer',
    'Frontend Developer', 'Backend Developer', 'Full Stack Developer',
    'QA Engineer', 'DevOps Engineer', 'UI/UX Designer',
    'Project Manager', 'Business Analyst', 'Data Analyst',
    'HR Manager', 'HR Executive', 'Accountant', 'Finance Manager',
    'Marketing Manager', 'Sales Executive', 'System Administrator',
]

BANKS        = ['HBL', 'UBL', 'MCB', 'Allied Bank', 'Bank Alfalah', 'Meezan Bank', 'Faysal Bank']
TEAMS        = ['Sir Faisal', 'Sir Zubair', 'Sir Govinda', 'Sir Suhail', 'HR', 'Accounts']
WORK_MODES   = ['Onsite', 'Remote', 'Hybrid']
EMP_TYPES    = ['Full Time', 'Part Time']
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']
MARITAL      = ['Single', 'Married']
CITIES       = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Faisalabad']
SECTORS      = ['A', 'B', 'C', 'D', 'E', 'F']
BRANCHES     = ['Main', 'Gulshan', 'DHA', 'Model Town', 'Clifton']

ATT_WEIGHTS  = (['present'] * 65 + ['late'] * 15 +
                ['absent'] * 10 + ['early-out'] * 5 + ['leave'] * 5)
LEAVE_TYPES  = ['sick', 'personal', 'annual', 'casual']


def _addr(city=None):
    city = city or random.choice(CITIES)
    return f"House {random.randint(1,500)}, Street {random.randint(1,100)}, Sector {random.choice(SECTORS)}, {city}"


def _phone():
    return f"03{random.randint(10,49)}{random.randint(1000000,9999999)}"


def _cnic():
    return f"{random.randint(10000,99999)}-{random.randint(1000000,9999999)}-{random.randint(1,9)}"


def _next_code():
    existing = set(Employees.objects.values_list('code', flat=True))
    code = 1001
    while str(code) in existing:
        code += 1
    return str(code)


def _log(cmd, msg):
    cmd.stdout.write(msg)
    sys.stdout.flush()


class Command(BaseCommand):
    help = 'Generate dummy employees with 30 days of attendance'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=50)
        parser.add_argument('--clear', action='store_true',
                            help='Delete previously generated dummy employees (codes 1001-9999)')

    def handle(self, *args, **options):
        count = options['count']

        # ── Optional clear ────────────────────────────────────────────────────
        if options['clear']:
            dummy_codes = [
                c for c in Employees.objects.values_list('code', flat=True)
                if str(c).isdigit() and 1001 <= int(c) <= 9999
            ]
            deleted, _ = Employees.objects.filter(code__in=dummy_codes).delete()
            _log(self, self.style.WARNING(f'Deleted {deleted} dummy employees.'))

        # ── Departments ───────────────────────────────────────────────────────
        departments = []
        for d in DEPARTMENTS_DATA:
            obj, _ = Department.objects.get_or_create(
                name=d['name'],
                defaults={'description': d['description'], 'status': 'active'}
            )
            departments.append(obj)
        _log(self, f'Departments ready: {len(departments)}')

        # ── Positions ─────────────────────────────────────────────────────────
        positions = []
        for p in POSITIONS_DATA:
            obj, _ = Position.objects.get_or_create(name=p, defaults={'status': 'active'})
            positions.append(obj)
        _log(self, f'Positions ready: {len(positions)}')

        # ── Employees (one transaction per employee) ──────────────────────────
        today     = timezone.now().date()
        created   = 0
        failed    = 0
        employees = []

        _log(self, f'Creating {count} employees...')

        for i in range(count):
            gender    = random.choice(['Male', 'Female'])
            firstname = random.choice(MALE_NAMES if gender == 'Male' else FEMALE_NAMES)
            lastname  = random.choice(LAST_NAMES)
            city      = random.choice(CITIES)
            dob       = today - timedelta(days=random.randint(8030, 14600))
            hired     = today - timedelta(days=random.randint(60, 1095))
            salary    = random.randint(35_000, 250_000)

            try:
                with transaction.atomic():
                    code = _next_code()
                    emp  = Employees.objects.create(
                        code              = code,
                        firstname         = firstname,
                        lastname          = lastname,
                        father_name       = random.choice(FATHER_NAMES),
                        national_id       = _cnic(),
                        gender            = gender,
                        marital_status    = random.choice(MARITAL),
                        blood_group       = random.choice(BLOOD_GROUPS),
                        dob               = dob,
                        contact_1         = _phone(),
                        contact_2         = _phone(),
                        emergency_contact = _phone(),
                        emergency_contact_person = f"{random.choice(MALE_NAMES)} {random.choice(LAST_NAMES)}",
                        email             = f"{firstname.lower()}.{lastname.lower()}{code}@gmail.com",
                        official_email    = f"{firstname.lower()}.{lastname.lower()}@aliq.tech",
                        present_address   = _addr(city),
                        permanent_address = _addr(city),
                        location          = "EB's Technology",
                        work_mode         = random.choice(WORK_MODES),
                        employment_type   = random.choice(EMP_TYPES),
                        team              = random.choice(TEAMS),
                        department        = random.choice(departments),
                        position          = random.choice(positions),
                        job_title         = random.choice(POSITIONS_DATA),
                        reporting_to      = f"{random.choice(MALE_NAMES)} {random.choice(LAST_NAMES)}",
                        date_hired        = hired,
                        salary            = salary,
                        bank_name         = random.choice(BANKS),
                        branch_name       = f"{random.choice(BRANCHES)} Branch",
                        account_title     = f"{firstname} {lastname}",
                        account_number    = str(random.randint(10_000_000_000, 99_999_999_999)),
                        status            = 1,
                    )
                employees.append(emp)
                created += 1
            except Exception as e:
                failed += 1
                _log(self, self.style.ERROR(f'  [skip] employee {i+1}: {e}'))
                continue

            if created % 10 == 0:
                _log(self, f'  {created}/{count} employees created...')

        _log(self, self.style.SUCCESS(f'Employees done: {created} created, {failed} failed.'))

        # ── Attendance (30 weekdays per employee) ─────────────────────────────
        _log(self, 'Generating attendance records...')
        att_ok   = 0
        att_skip = 0

        for emp in employees:
            for days_ago in range(30, 0, -1):
                att_date = today - timedelta(days=days_ago)

                if att_date.weekday() >= 5:         # skip weekends
                    continue
                if att_date < emp.date_hired:       # skip pre-hire days
                    continue
                if Attendance.objects.filter(employee=emp, date=att_date).exists():
                    att_skip += 1
                    continue

                status     = random.choice(ATT_WEIGHTS)
                check_in   = None
                check_out  = None
                leave_type = None

                if status == 'absent':
                    pass
                elif status == 'leave':
                    leave_type = random.choice(LEAVE_TYPES)
                elif status == 'late':
                    mins = random.randint(20, 90)
                    check_in  = time(9 + mins // 60, mins % 60)
                    check_out = time(random.randint(17, 19), random.randint(0, 59))
                elif status == 'early-out':
                    check_in  = time(9, random.randint(0, 14))
                    check_out = time(random.randint(14, 17), random.randint(0, 59))
                else:
                    check_in  = time(8, random.randint(45, 59)) if random.random() < 0.3 else time(9, random.randint(0, 14))
                    check_out = time(random.randint(18, 20), random.randint(0, 59))

                try:
                    Attendance.objects.create(
                        employee       = emp,
                        date           = att_date,
                        check_in_time  = check_in,
                        check_out_time = check_out,
                        leave_type     = leave_type,
                    )
                    att_ok += 1
                except Exception:
                    att_skip += 1

        _log(self, self.style.SUCCESS(
            f'Attendance done: {att_ok} records created, {att_skip} skipped.\n'
            f'-----------------------------------------\n'
            f'  Employees  : {created}\n'
            f'  Attendance : {att_ok} records\n'
            f'-----------------------------------------'
        ))
