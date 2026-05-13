# your_app/management/commands/employee.py

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from ...models import Employees, generate_secure_password  # relative import from the same app
import re
from django.utils import timezone


def _sanitize_username(base: str) -> str:
    """
    Allow letters, numbers, underscore; lower-case; trim to 150 chars (Django max).
    If empty after sanitizing, fall back to 'user'.
    """
    base = (base or "").strip().lower()
    base = re.sub(r'[^a-z0-9_]+', '', base)
    return base[:150] if base else "user"


def _unique_username_from_firstname(firstname: str, fallback: str = "user") -> str:
    """
    Try firstname, then firstname+digits, finally timestamp fallback.
    """
    root = _sanitize_username(firstname) or _sanitize_username(fallback)

    if not User.objects.filter(username=root).exists():
        return root

    for i in range(1, 1000):
        candidate = f"{root}{i}"
        if len(candidate) > 150:
            candidate = candidate[:150]
        if not User.objects.filter(username=candidate).exists():
            return candidate

    ts = timezone.now().strftime("%Y%m%d%H%M%S")
    candidate = (root[:140] + ts)[:150]
    return candidate


class Command(BaseCommand):
    help = (
        "Manage employee-user links.\n\n"
        "Usage:\n"
        "  python manage.py employee add            # create users for all Employees without a linked user\n"
        "  python manage.py employee add --code E1  # create user only for the given employee code\n"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["add"],
            help="Action to perform. 'add' will create Users for Employees missing a linked user.",
        )
        parser.add_argument(
            "--code",
            dest="code",
            default=None,
            help="(Optional) Employee code to process only a single employee.",
        )
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help="(Optional) Password to set for newly created users. If not provided, a secure random password will be generated for each employee.",
        )
        parser.add_argument(
            "--use-default",
            action="store_true",
            dest="use_default",
            default=False,
            help="Use default password instead of generating secure passwords (not recommended for production).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        action = options["action"]
        code = options.get("code")
        use_default = options.get("use_default", False)
        provided_password = options.get("password")

        # Use provided password, or generate secure one, or use default if flag is set
        if provided_password:
            password = provided_password
            use_same_password = True  # Use same password for all
        elif use_default:
            password = "Aliqtechnology@1122"
            use_same_password = True
        else:
            password = None  # Will generate unique password for each
            use_same_password = False

        if action != "add":
            raise CommandError("Unsupported action. Only 'add' is supported.")

        if code:
            employees_qs = Employees.objects.filter(code=code)
            if not employees_qs.exists():
                raise CommandError(f"No employee found with code '{code}'.")
            employees_qs = employees_qs.filter(user__isnull=True)
        else:
            employees_qs = Employees.objects.filter(user__isnull=True)

        if not employees_qs.exists():
            self.stdout.write(self.style.WARNING("No employees without users were found. Nothing to do."))
            return

        created = 0
        for emp in employees_qs.select_for_update():
            username = _unique_username_from_firstname(emp.firstname or "", fallback=emp.code or "user")
            email = emp.official_email or emp.email or ""

            # Generate or use provided password
            if use_same_password:
                emp_password = password
            else:
                emp_password = generate_secure_password(length=12)

            # Create the Django auth user
            user = User.objects.create_user(
                username=username,
                password=emp_password,
                first_name=emp.firstname or "",
                last_name=emp.lastname or "",
                email=email,
            )
            user.is_active = True
            user.save(update_fields=["is_active"])

            # Link user -> employee and store password temporarily
            emp.user = user
            emp.temp_password = emp_password
            emp.save(update_fields=["user", "temp_password"])

            created += 1
            if use_same_password:
                self.stdout.write(self.style.SUCCESS(f"Linked user '{username}' -> employee '{emp.code}' (password: {emp_password})"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Linked user '{username}' -> employee '{emp.code}' (password: {emp_password})"))

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created} user(s)."))
