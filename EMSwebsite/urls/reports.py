from django.urls import path
from EMSwebsite.views.reports import (
    reports_dashboard, generate_report, view_report, download_report,
    delete_report, generate_from_template, get_report_status, get_recent_reports,
)

urlpatterns = [
    path('reports/', reports_dashboard, name='reports'),
    path('reports/view/<uuid:report_id>/', view_report, name='view_report'),
    path('reports/generate/', generate_report, name='generate_report'),
    path('reports/download/<uuid:report_id>/', download_report, name='download_report'),
    path('reports/delete/<uuid:report_id>/', delete_report, name='delete_report'),
    path('reports/template/<int:template_id>/', generate_from_template, name='generate_from_template'),
    path('reports/status/<uuid:report_id>/', get_report_status, name='get_report_status'),
    path('reports/recent/', get_recent_reports, name='get_recent_reports'),
]
