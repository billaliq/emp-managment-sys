from django.urls import path
from EMSwebsite.controllers.auth import login_view, logout_view, test_email, send_birthday_emails_manual
from EMSwebsite.controllers.dashboard import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('test-email/', test_email, name='test_email'),
    path('send-birthday-emails/', send_birthday_emails_manual, name='send_birthday_emails'),
]
