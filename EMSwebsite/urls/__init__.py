# EMSwebsite/urls/__init__.py
# Assembles all domain-specific URL modules into one urlpatterns list

from django.urls import path, include
from django.contrib.auth import views as auth_views
from EMSwebsite import forms as EMSwebsite_forms

# Password Reset URLs (using Django's built-in views with custom templates)
password_reset_urls = [
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='pages/password_reset.html',
             email_template_name='pages/password_reset_email.html',
             subject_template_name='pages/password_reset_subject.txt',
             success_url='/password_reset/done/',
             html_email_template_name='pages/password_reset_email.html',
             extra_email_context={'site_name': 'Employee Information System'},
             form_class=EMSwebsite_forms.CustomPasswordResetForm
         ),
         name='password_reset'),

    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='pages/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='pages/password_reset_confirm.html',
             success_url='/reset/done/',
             post_reset_login=False
         ),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='pages/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]

# Import all sub-URL modules
from .auth import urlpatterns as auth_urls
from .employees import urlpatterns as employee_urls
from .attendance import urlpatterns as attendance_urls
from .departments import urlpatterns as department_urls
from .positions import urlpatterns as position_urls
from .teams import urlpatterns as team_urls
from .payroll import urlpatterns as payroll_urls
from .loans import urlpatterns as loan_urls
from .reports import urlpatterns as report_urls
from .settings_urls import urlpatterns as settings_urls_list
from .notifications import urlpatterns as notification_urls
from .ai import urlpatterns as ai_urls
from .devices import urlpatterns as device_urls
from .tasks import urlpatterns as task_urls

# Assemble all URL patterns
urlpatterns = (
    password_reset_urls
    + auth_urls
    + employee_urls
    + attendance_urls
    + department_urls
    + position_urls
    + team_urls
    + payroll_urls
    + loan_urls
    + report_urls
    + settings_urls_list
    + notification_urls
    + ai_urls
    + device_urls
    + task_urls
)
