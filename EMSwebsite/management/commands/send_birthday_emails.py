"""
Management command to send birthday emails to employees.
Run this daily via cron or scheduled task.

Usage:
    python manage.py send_birthday_emails
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import date
from EMSwebsite.models import Employees


class Command(BaseCommand):
    help = 'Send birthday email notifications to employees whose birthday is today'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending emails (for testing)',
        )
        parser.add_argument(
            '--test-email',
            type=str,
            help='Send a test email to the specified address instead of checking birthdays',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        test_email = options.get('test_email')

        if test_email:
            # Send a test email
            self.stdout.write(self.style.WARNING(f'Sending test email to {test_email}...'))
            try:
                send_mail(
                    subject='🎉 Happy Birthday! - Test Email',
                    message=self._get_birthday_message('Test Employee'),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[test_email],
                    fail_silently=False,
                    html_message=self._get_birthday_html_message('Test Employee'),
                )
                self.stdout.write(self.style.SUCCESS(f'Test email sent successfully to {test_email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send test email: {str(e)}'))
            return

        # Get today's date
        today = date.today()
        self.stdout.write(f'Checking for birthdays on {today.strftime("%Y-%m-%d")}...')

        # Find employees whose birthday is today
        # We need to check month and day, ignoring the year
        employees_with_birthday = Employees.objects.filter(
            dob__month=today.month,
            dob__day=today.day,
            status=1,  # Only active employees
        ).exclude(
            dob__isnull=True
        ).exclude(
            email__isnull=True,
            official_email__isnull=True
        )

        if not employees_with_birthday.exists():
            self.stdout.write(self.style.WARNING('No employees have birthdays today.'))
            return

        self.stdout.write(f'Found {employees_with_birthday.count()} employee(s) with birthdays today.')

        sent_count = 0
        failed_count = 0

        for employee in employees_with_birthday:
            # Use official_email if available, otherwise use email
            recipient_email = employee.official_email or employee.email

            if not recipient_email:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipping {employee.firstname} {employee.lastname or ""} ({employee.code}): No email address'
                    )
                )
                continue

            # Calculate age
            age = today.year - employee.dob.year - ((today.month, today.day) < (employee.dob.month, employee.dob.day))

            # Get employee name
            employee_name = f"{employee.firstname} {employee.lastname or ''}".strip()

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[DRY RUN] Would send birthday email to {employee_name} ({recipient_email}) - Age: {age}'
                    )
                )
                sent_count += 1
            else:
                try:
                    send_mail(
                        subject=f'🎉 Happy Birthday {employee.firstname}!',
                        message=self._get_birthday_message(employee_name, age),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient_email],
                        fail_silently=False,
                        html_message=self._get_birthday_html_message(employee_name, age, employee),
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Birthday email sent to {employee_name} ({recipient_email})'
                        )
                    )
                    sent_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Failed to send email to {employee_name} ({recipient_email}): {str(e)}'
                        )
                    )
                    failed_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Summary: {sent_count} email(s) sent, {failed_count} failed'))

    def _get_birthday_message(self, name, age=None):
        """Generate plain text birthday message"""
        age_text = f" You're turning {age} today!" if age else ""
        return f"""
Dear {name},

🎉 Happy Birthday!{age_text}

We hope your special day is filled with joy, laughter, and wonderful moments.
Thank you for being an important part of our team!

Wishing you a fantastic year ahead filled with success and happiness.

Best regards,
Employee Information System
EB's Technology
        """.strip()

    def _get_birthday_html_message(self, name, age=None, employee=None):
        """Generate HTML birthday message"""
        age_text = f"<p style='font-size: 18px; color: #666;'>You're turning <strong>{age}</strong> today!</p>" if age else ""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .container {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            padding: 30px;
            color: white;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 5px;
            margin-top: 20px;
            color: #333;
        }}
        h1 {{
            color: white;
            margin: 0;
            font-size: 32px;
        }}
        .emoji {{
            font-size: 48px;
            text-align: center;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #eee;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎉 Happy Birthday {name}!</h1>
        {age_text}
    </div>
    <div class="content">
        <div class="emoji">🎂 🎈 🎁</div>
        <p>Dear {name},</p>
        <p>We hope your special day is filled with <strong>joy, laughter, and wonderful moments</strong>.</p>
        <p>Thank you for being an important part of our team! Your dedication and hard work make a real difference.</p>
        <p>Wishing you a <strong>fantastic year ahead</strong> filled with success, happiness, and all your heart desires.</p>
        <p style="margin-top: 30px;">Have a wonderful celebration! 🎊</p>
    </div>
    <div class="footer">
        <p><strong>Employee Information System</strong></p>
        <p> EB's Technology</p>
        <p style="font-size: 12px; color: #999;">This is an automated birthday notification.</p>
    </div>
</body>
</html>
        """.strip()

        return html

