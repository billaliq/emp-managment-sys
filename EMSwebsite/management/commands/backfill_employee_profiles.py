"""
Management command to backfill UserProfile (role=employee) for any Employees
record that has a linked User but no UserProfile.

Run once after deploying this change:
    python manage.py backfill_employee_profiles
"""

from django.core.management.base import BaseCommand
from EMSwebsite.models import Employees, UserProfile


class Command(BaseCommand):
    help = "Create missing UserProfile (role=employee) for existing employee user accounts"

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for emp in Employees.objects.select_related('user').filter(user__isnull=False):
            profile, was_created = UserProfile.objects.get_or_create(
                user=emp.user,
                defaults={'employee': emp, 'role': 'employee'}
            )
            if was_created:
                created += 1
                self.stdout.write(f"  Created profile for {emp.firstname} {emp.lastname or ''} ({emp.user.username})")
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {created}  |  Already existed: {skipped}"
        ))
