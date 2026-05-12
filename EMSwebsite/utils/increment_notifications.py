"""
Utility functions for sending increment notifications to employees, admin, and finance.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from EMSwebsite.models import Notification, UserProfile
from django.contrib.auth.models import User


def send_increment_notifications(increment):
    """
    Send notifications about salary increment to:
    1. The employee
    2. Admin users
    3. Finance department users

    Args:
        increment: SalaryIncrement instance
    """
    employee = increment.employee
    employee_name = f"{employee.firstname} {employee.lastname or ''}".strip()

    # Prepare notification details
    title = f"Salary Increment Applied - {employee_name}"
    message = (
        f"Your salary has been automatically incremented.\n\n"
        f"Old Salary: ${increment.old_salary:,.2f}\n"
        f"New Salary: ${increment.new_salary:,.2f}\n"
        f"Increase: ${increment.increase_amount:,.2f} ({increment.increase_percent}%)\n"
        f"Effective Date: {increment.effective_date.strftime('%B %d, %Y')}\n"
        f"Reason: {increment.reason or 'Automatic increment'}."
    )

    # 1. Send notification to employee
    if employee.user:
        Notification.objects.create(
            recipient=employee.user,
            notification_type='increment',
            title=title,
            message=message,
            related_object_id=increment.id,
            related_object_type='SalaryIncrement'
        )

        # Send email to employee
        employee_email = employee.official_email or employee.email
        if employee_email:
            try:
                send_mail(
                    subject=f'💰 Salary Increment - {employee_name}',
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[employee_email],
                    fail_silently=True,
                    html_message=get_increment_email_html(employee_name, increment, is_employee=True)
                )
            except Exception as e:
                print(f"Failed to send email to employee {employee_email}: {str(e)}")

    # 2. Send notifications to all admin users
    admin_users = User.objects.filter(
        is_superuser=True
    ) | User.objects.filter(
        profile__role='admin'
    )

    admin_message = (
        f"Automatic salary increment has been applied to {employee_name} ({employee.code}).\n\n"
        f"Old Salary: ${increment.old_salary:,.2f}\n"
        f"New Salary: ${increment.new_salary:,.2f}\n"
        f"Increase: ${increment.increase_amount:,.2f} ({increment.increase_percent}%)\n"
        f"Effective Date: {increment.effective_date.strftime('%B %d, %Y')}\n"
        f"Reason: {increment.reason or 'Automatic increment'}."
    )

    for admin_user in admin_users.distinct():
        Notification.objects.create(
            recipient=admin_user,
            notification_type='increment',
            title=f"Salary Increment - {employee_name}",
            message=admin_message,
            related_object_id=increment.id,
            related_object_type='SalaryIncrement'
        )

        # Send email to admin
        if admin_user.email:
            try:
                send_mail(
                    subject=f'📊 Salary Increment Applied - {employee_name}',
                    message=admin_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_user.email],
                    fail_silently=True,
                    html_message=get_increment_email_html(employee_name, increment, is_employee=False)
                )
            except Exception as e:
                print(f"Failed to send email to admin {admin_user.email}: {str(e)}")

    # 3. Send notifications to finance department users
    finance_users = User.objects.filter(profile__role='finance')

    finance_message = (
        f"Salary increment has been applied to {employee_name} ({employee.code}). "
        f"Please update payroll records accordingly.\n\n"
        f"Old Salary: ${increment.old_salary:,.2f}\n"
        f"New Salary: ${increment.new_salary:,.2f}\n"
        f"Increase: ${increment.increase_amount:,.2f} ({increment.increase_percent}%)\n"
        f"Effective Date: {increment.effective_date.strftime('%B %d, %Y')}\n"
        f"Reason: {increment.reason or 'Automatic increment'}."
    )

    for finance_user in finance_users:
        Notification.objects.create(
            recipient=finance_user,
            notification_type='increment',
            title=f"Salary Increment - {employee_name}",
            message=finance_message,
            related_object_id=increment.id,
            related_object_type='SalaryIncrement'
        )

        # Send email to finance
        if finance_user.email:
            try:
                send_mail(
                    subject=f'💼 Salary Increment - {employee_name} (Payroll Update Required)',
                    message=finance_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[finance_user.email],
                    fail_silently=True,
                    html_message=get_increment_email_html(employee_name, increment, is_employee=False, is_finance=True)
                )
            except Exception as e:
                print(f"Failed to send email to finance {finance_user.email}: {str(e)}")


def get_increment_email_html(employee_name, increment, is_employee=False, is_finance=False):
    """Generate HTML email template for increment notifications"""

    if is_employee:
        header_text = f"🎉 Congratulations {employee_name}!"
        main_text = (
            f"<p>We're pleased to inform you that your salary has been automatically incremented.</p>"
            f"<p>This increment reflects your continued dedication and valuable contributions to our organization.</p>"
        )
    elif is_finance:
        header_text = "💼 Payroll Update Required"
        main_text = (
            f"<p>A salary increment has been automatically applied. Please update payroll records accordingly.</p>"
        )
    else:
        header_text = "📊 Salary Increment Applied"
        main_text = (
            f"<p>An automatic salary increment has been applied to an employee in the system.</p>"
        )

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
            font-size: 28px;
        }}
        .details {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            font-weight: bold;
            color: #666;
        }}
        .detail-value {{
            color: #333;
        }}
        .highlight {{
            color: #28a745;
            font-weight: bold;
            font-size: 18px;
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
        <h1>{header_text}</h1>
    </div>
    <div class="content">
        {main_text}
        <div class="details">
            <div class="detail-row">
                <span class="detail-label">Employee:</span>
                <span class="detail-value">{employee_name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Previous Salary:</span>
                <span class="detail-value">${increment.old_salary:,.2f}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">New Salary:</span>
                <span class="detail-value highlight">${increment.new_salary:,.2f}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Increase Amount:</span>
                <span class="detail-value highlight">+${increment.increase_amount:,.2f}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Increase Percentage:</span>
                <span class="detail-value highlight">+{increment.increase_percent}%</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Effective Date:</span>
                <span class="detail-value">{increment.effective_date.strftime('%B %d, %Y')}</span>
            </div>
            {f'<div class="detail-row"><span class="detail-label">Reason:</span><span class="detail-value">{increment.reason or "Automatic increment"}</span></div>' if increment.reason else ''}
        </div>
        {f'<p style="margin-top: 20px;">Thank you for your continued dedication and hard work!</p>' if is_employee else ''}
    </div>
    <div class="footer">
        <p><strong>Employee Information System</strong></p>
        <p>FunPrime Technology</p>
        <p style="font-size: 12px; color: #999;">This is an automated notification.</p>
    </div>
</body>
</html>
    """.strip()

    return html













