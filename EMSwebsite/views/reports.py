from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Avg, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime, timedelta, date, time
from django.views.decorators.http import require_http_methods, require_POST
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
import json
import csv
import re
import logging

logger = logging.getLogger(__name__)

from EMSwebsite.models import (
    Employees, Department, Position, Attendance, AttendanceSettings, LeaveRequest, HolidayDate,
    Team, TeamMember, Project, Payroll, PayrollRecord, SalaryIncrement, SystemSettings,
    Loan, LoanRepayment, LoanPool, LoanPoolTransaction, UserProfile, SalaryDisbursement, SalaryDisbursementRecord,
    IncrementSettings, Notification, EmployeeAdditionalDocument, SalarySlipRequest,
    Policy, Complaint, AIChatMessage, ZKDevice, AttendanceLog,
    Report, ReportTemplate, ReportSchedule,
)
from .helpers import (
    validate_date, get_current_employee, scope_by_user, only_me_employee_qs,
    role_required, admin_required, hr_or_admin_required, finance_or_admin_required,
    has_valid_attendance_exception, auto_mark_absent_for_date, sync_attendance_with_holidays,
)
from EMSwebsite.context_processors import get_notifications


try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

def get_user_role(request):
    """Get user role for access control"""
    if request.user.is_superuser:
        return 'admin'
    try:
        return request.user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return 'employee'

def can_access_report(request, report_type):
    """Check if user can access a specific report type"""
    role = get_user_role(request)

    # Access control matrix
    access_matrix = {
        'admin': ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
        'hr': ['employee', 'payroll', 'attendance', 'department', 'leave', 'loan'],
        'finance': ['payroll', 'loan'],
        'manager': ['employee', 'attendance', 'department', 'leave'],
        'employee': ['employee', 'attendance', 'leave', 'loan'],  # Only their own data
    }

    allowed_types = access_matrix.get(role, ['employee', 'attendance', 'leave'])
    return report_type in allowed_types

def extract_employee_report_data(request, start_date=None, end_date=None, filters=None):
    """Extract employee data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        employees = Employees.objects.all()
    else:
        # Employees can only see their own data
        employees = Employees.objects.filter(pk=current_employee.pk) if current_employee else Employees.objects.none()

    # Apply filters
    if filters:
        if filters.get('department'):
            employees = employees.filter(department_id=filters['department'])
        if filters.get('status'):
            employees = employees.filter(status=filters['status'])
        if filters.get('position'):
            employees = employees.filter(position_id=filters['position'])

    # Date filters (for employees hired in date range)
    if start_date:
        employees = employees.filter(date_hired__gte=start_date)
    if end_date:
        employees = employees.filter(date_hired__lte=end_date)

    data = []
    for emp in employees:
        data.append({
            'code': emp.code,
            'name': f"{emp.firstname} {emp.lastname or ''}".strip(),
            'email': emp.email or emp.official_email or 'N/A',
            'department': emp.department.name if emp.department else 'N/A',
            'position': emp.position.name if emp.position else 'N/A',
            'date_hired': emp.date_hired.strftime('%Y-%m-%d') if emp.date_hired else 'N/A',
            'status': 'Active' if emp.status == 1 else 'Inactive',
            'salary': emp.salary,
            'contact': emp.contact_1 or 'N/A',
        })

    return data

def extract_payroll_report_data(request, start_date, end_date, filters=None):
    """Extract payroll data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Access control
    if role not in ['admin', 'hr', 'finance']:
        return []

    # Get payroll records in date range
    payrolls = Payroll.objects.filter(
        pay_date__gte=start_date,
        pay_date__lte=end_date
    )

    if filters and filters.get('department'):
        payrolls = payrolls.filter(records__employee__department_id=filters['department']).distinct()

    data = []
    for payroll in payrolls:
        records = payroll.records.all()
        for record in records:
            data.append({
                'pay_period': payroll.pay_period,
                'pay_date': payroll.pay_date.strftime('%Y-%m-%d'),
                'employee_code': record.employee.code if record.employee else 'N/A',
                'employee_name': f"{record.employee.firstname} {record.employee.lastname or ''}".strip() if record.employee else 'N/A',
                'base_salary': float(record.base_salary) if record.base_salary else 0,
                'allowances': float(record.allowances) if record.allowances else 0,
                'deductions': float(record.deductions) if record.deductions else 0,
                'net_salary': float(record.net_salary) if record.net_salary else 0,
            })

    return data

def extract_attendance_report_data(request, start_date, end_date, filters=None):
    """Extract attendance data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        attendance = Attendance.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
    else:
        # Employees can only see their own attendance
        if current_employee:
            attendance = Attendance.objects.filter(
                employee=current_employee,
                date__gte=start_date,
                date__lte=end_date
            )
        else:
            attendance = Attendance.objects.none()

    # Apply filters
    if filters:
        if filters.get('department'):
            attendance = attendance.filter(employee__department_id=filters['department'])
        if filters.get('status'):
            attendance = attendance.filter(status=filters['status'])
        if filters.get('employee'):
            attendance = attendance.filter(employee_id=filters['employee'])
        # Attendance detail sub-type filters
        detail = filters.get('attendance_detail')
        if detail == 'late_only':
            # Late arrivals: late_in_display not empty OR status in late-related categories
            attendance = attendance.filter(
                Q(late_in_minutes__gt=0) | Q(status__in=['late', 'late-coming'])
            )
        elif detail == 'weekend_only':
            # Saturdays & Sundays: status weekend
            attendance = attendance.filter(status='weekend')
        elif detail == 'late_sitting_only':
            # Late sitting: late_sitting > 0
            attendance = attendance.filter(late_sitting__isnull=False).exclude(late_sitting=timedelta(0))

    # Filter out weekend records without attendance (employee didn't arrive on weekend)
    attendance = attendance.exclude(
        Q(status='weekend', check_in_time__isnull=True, check_out_time__isnull=True)
    )

    # Order by date and updated_at to get latest records first, then remove duplicates
    attendance = attendance.order_by('-date', '-updated_at', 'employee__firstname')

    # Remove duplicates: Keep only the latest record (by updated_at) for each employee-date combination
    seen = {}
    unique_attendance = []
    for att in attendance:
        key = (att.employee_id, att.date)
        if key not in seen:
            seen[key] = att
            unique_attendance.append(att)
        else:
            # If duplicate found, keep the one with the latest updated_at
            existing_record = seen[key]
            if att.updated_at > existing_record.updated_at:
                # Replace with newer record
                unique_attendance.remove(existing_record)
                seen[key] = att
                unique_attendance.append(att)

    data = []
    for att in unique_attendance:
        # Calculate late sitting display (hh mm)
        late_sitting_display = ''
        if att.late_sitting and att.late_sitting.total_seconds() > 0:
            total_minutes = int(att.late_sitting.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            late_sitting_display = f"{hours}h {minutes:02d}m"

        # Calculate early out display (hh mm)
        early_out_display = ''
        if att.early_out and att.early_out.total_seconds() > 0:
            total_minutes = int(att.early_out.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            early_out_display = f"{hours}h {minutes:02d}m"

        data.append({
            'date': att.date.strftime('%Y-%m-%d'),
            'employee_code': att.employee.code,
            'employee_name': f"{att.employee.firstname} {att.employee.lastname or ''}".strip(),
            'department': att.employee.department.name if att.employee.department else 'N/A',
            'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else 'N/A',
            'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else 'N/A',
            'status': att.get_status_display(),
            'work_duration': att.duration,
            'overtime': att.overtime_display,
            'late_in': att.late_in_display,
            'early_out': early_out_display if early_out_display else 'N/A',
            'late_sitting': late_sitting_display if late_sitting_display else 'N/A',
            'leave_type': att.get_leave_type_display() if att.leave_type else 'N/A',
            'notes': att.notes or 'N/A',
        })

    return data

def extract_department_report_data(request, start_date=None, end_date=None, filters=None):
    """Extract department statistics for report"""
    role = get_user_role(request)

    # Access control
    if role not in ['admin', 'hr', 'manager']:
        return []

    departments = Department.objects.filter(status='active')

    data = []
    for dept in departments:
        employees = dept.employees_set.filter(status=1)  # Active employees
        total_salary = employees.aggregate(total=Sum('salary'))['total'] or 0

        data.append({
            'department_name': dept.name,
            'employee_count': employees.count(),
            'total_salary': float(total_salary),
            'average_salary': float(total_salary / employees.count()) if employees.count() > 0 else 0,
            'description': dept.description,
        })

    return data

def extract_leave_report_data(request, start_date, end_date, filters=None):
    """Extract leave request data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'manager']:
        leaves = LeaveRequest.objects.filter(
            start_date__lte=end_date,
            end_date__gte=start_date
        )
    else:
        # Employees can only see their own leaves
        if current_employee:
            leaves = LeaveRequest.objects.filter(
                employee=current_employee,
                start_date__lte=end_date,
                end_date__gte=start_date
            )
        else:
            leaves = LeaveRequest.objects.none()

    # Apply filters
    if filters:
        if filters.get('status'):
            leaves = leaves.filter(status=filters['status'])
        if filters.get('leave_type'):
            leaves = leaves.filter(leave_type=filters['leave_type'])
        if filters.get('department'):
            leaves = leaves.filter(employee__department_id=filters['department'])

    data = []
    for leave in leaves:
        data.append({
            'employee_code': leave.employee.code,
            'employee_name': f"{leave.employee.firstname} {leave.employee.lastname or ''}".strip(),
            'leave_type': leave.get_leave_type_display(),
            'start_date': leave.start_date.strftime('%Y-%m-%d'),
            'end_date': leave.end_date.strftime('%Y-%m-%d'),
            'duration_days': leave.duration_days,
            'status': leave.get_status_display(),
            'applied_on': leave.applied_on.strftime('%Y-%m-%d %H:%M'),
            'approved_by': f"{leave.approved_by.firstname} {leave.approved_by.lastname or ''}".strip() if leave.approved_by else 'N/A',
        })

    return data

def extract_loan_report_data(request, start_date, end_date, filters=None):
    """Extract loan data for report"""
    role = get_user_role(request)
    current_employee = get_current_employee(request)

    # Base queryset
    if role in ['admin', 'hr', 'finance']:
        loans = Loan.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
    else:
        # Employees can only see their own loans
        if current_employee:
            loans = Loan.objects.filter(
                employee=current_employee,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
        else:
            loans = Loan.objects.none()

    # Apply filters
    if filters:
        if filters.get('status'):
            loans = loans.filter(status=filters['status'])
        if filters.get('department'):
            loans = loans.filter(employee__department_id=filters['department'])

    data = []
    for loan in loans:
        repayments = loan.repayments.all()
        total_paid = repayments.aggregate(total=Sum('amount'))['total'] or 0
        remaining = float(loan.total_amount) - float(total_paid)

        data.append({
            'loan_id': loan.id,
            'employee_code': loan.employee.code,
            'employee_name': f"{loan.employee.firstname} {loan.employee.lastname or ''}".strip(),
            'application_date': loan.created_at.strftime('%Y-%m-%d') if loan.created_at else 'N/A',
            'loan_amount': float(loan.loan_amount),
            'total_amount': float(loan.total_amount),
            'interest_rate': float(loan.interest_rate),
            'purpose': loan.purpose or 'N/A',
            'status': loan.get_status_display(),
            'total_paid': float(total_paid),
            'remaining': remaining,
            'installments': loan.number_of_installments,
            'monthly_payment': float(loan.monthly_payment) if loan.monthly_payment else 0,
        })

    return data

@login_required
def reports_dashboard(request):
    """Main reports dashboard view with search and filter"""
    user_role = get_user_role(request)

    # Base queryset - employees can only see their own reports
    if user_role == 'employee':
        report_qs = Report.objects.filter(generated_by=request.user)
    else:
        report_qs = Report.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        report_qs = report_qs.filter(
            Q(report_name__icontains=search_query) |
            Q(report_type__icontains=search_query)
        )

    # Filter by report type
    report_type_filter = request.GET.get('report_type', '')
    if report_type_filter:
        report_qs = report_qs.filter(report_type=report_type_filter)

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        report_qs = report_qs.filter(status=status_filter)

    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            report_qs = report_qs.filter(generated_on__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            report_qs = report_qs.filter(generated_on__date__lte=date_to_obj)
        except ValueError:
            pass

    # Calculate statistics
    total_reports = report_qs.count()
    employee_reports = report_qs.filter(report_type='employee').count()
    payroll_reports = report_qs.filter(report_type='payroll').count()
    attendance_reports = report_qs.filter(report_type='attendance').count()
    leave_reports = report_qs.filter(report_type='leave').count()
    loan_reports = report_qs.filter(report_type='loan').count()
    department_reports = report_qs.filter(report_type='department').count()

    # Get available report types based on user role
    available_report_types = []
    for report_type, display_name in Report.REPORT_TYPES:
        if can_access_report(request, report_type):
            available_report_types.append((report_type, display_name))

    stats = {
        'total_reports': total_reports,
        'employee_reports': employee_reports,
        'payroll_reports': payroll_reports,
        'attendance_reports': attendance_reports,
        'leave_reports': leave_reports,
        'loan_reports': loan_reports,
        'department_reports': department_reports,
    }

    # Get templates that user can access
    templates = ReportTemplate.objects.filter(
        is_active=True,
        report_type__in=[rt[0] for rt in available_report_types]
    )

    # Paginate recent reports
    paginator = Paginator(report_qs.order_by('-generated_on'), 20)
    page = request.GET.get('page', 1)
    try:
        recent_reports = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        recent_reports = paginator.page(1)

    # Get departments for filters
    departments = Department.objects.filter(status='active') if user_role in ['admin', 'hr', 'manager'] else []

    # Get employees for filters (for attendance reports)
    employees = []
    if user_role in ['admin', 'hr', 'manager']:
        from EMSwebsite.models import Employees
        employees = Employees.objects.filter(status=1).exclude(
            Q(code__icontains='test') |
            Q(code__icontains='dummy') |
            Q(code__icontains='sample')
        ).order_by('firstname', 'lastname')

    context = {
        'stats': stats,
        'templates': templates,
        'recent_reports': recent_reports,
        'user_role': user_role,
        'is_admin': user_role in ['admin', 'hr'],
        'available_report_types': available_report_types,
        'report_types': Report.REPORT_TYPES,
        'status_choices': Report.STATUS_CHOICES,
        'departments': departments,
        'employees': employees,
        'search_query': search_query,
        'report_type_filter': report_type_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'pages/reports.html', context)

@login_required
@require_http_methods(["POST"])
def generate_report(request):
    """Generate a new report with real data"""
    try:
        report_type = request.POST.get('report_type')

        # Check access control
        if not can_access_report(request, report_type):
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to generate this report type.'
            })

        date_range = request.POST.get('date_range')
        format_type = request.POST.get('format')
        include_charts = request.POST.get('include_charts') == 'on'
        include_summary = request.POST.get('include_summary') == 'on'
        include_raw_data = request.POST.get('include_raw_data') == 'on'

        # Get filters
        filters = {}
        if request.POST.get('department'):
            filters['department'] = request.POST.get('department')
        if request.POST.get('status'):
            filters['status'] = request.POST.get('status')
        if request.POST.get('employee'):
            filters['employee'] = request.POST.get('employee')
        # Attendance-specific sub-filter (late, weekend, late sitting)
        if request.POST.get('attendance_detail'):
            filters['attendance_detail'] = request.POST.get('attendance_detail')

        # Calculate date range
        end_date = timezone.now().date()
        if date_range == 'last_week':
            start_date = end_date - timedelta(days=7)
        elif date_range == 'last_month':
            start_date = end_date - timedelta(days=30)
        elif date_range == 'last_quarter':
            start_date = end_date - timedelta(days=90)
        elif date_range == 'last_year':
            start_date = end_date - timedelta(days=365)
        elif date_range == 'custom':
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else end_date - timedelta(days=30)
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else timezone.now().date()
        else:
            start_date = end_date - timedelta(days=30)

        # For reports that don't need date range, set to None
        if report_type in ['employee', 'department']:
            start_date = None
            end_date = None

        # Check for duplicate report creation (same user, same type, within last 5 seconds)
        recent_duplicate = Report.objects.filter(
            generated_by=request.user,
            report_type=report_type,
            generated_on__gte=timezone.now() - timedelta(seconds=5)
        ).first()

        if recent_duplicate:
            return JsonResponse({
                'success': False,
                'message': 'A similar report was just generated. Please wait a moment before generating another.'
            })

        # Create report name
        employee_name = None
        if filters.get('employee'):
            try:
                from EMSwebsite.models import Employees
                employee = Employees.objects.get(pk=filters['employee'])
                employee_name = f"{employee.firstname} {employee.lastname or ''}".strip()
            except Employees.DoesNotExist:
                pass

        if employee_name:
            if start_date and end_date:
                report_name = f"{report_type.title()} Report - {employee_name} - {start_date} to {end_date}"
            else:
                report_name = f"{report_type.title()} Report - {employee_name} - {timezone.now().strftime('%Y-%m-%d')}"
        elif start_date and end_date:
            report_name = f"{report_type.title()} Report - {start_date} to {end_date}"
        else:
            report_name = f"{report_type.title()} Report - {timezone.now().strftime('%Y-%m-%d')}"

        # Create report instance
        report = Report.objects.create(
            report_type=report_type,
            report_name=report_name,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date,
            format=format_type,
            include_charts=include_charts,
            include_summary=include_summary,
            include_raw_data=include_raw_data,
            generated_by=request.user,
            status='processing'
        )

        try:
            # Extract real data based on report type
            if report_type == 'employee':
                data = extract_employee_report_data(request, start_date, end_date, filters)
            elif report_type == 'payroll':
                data = extract_payroll_report_data(request, start_date, end_date, filters)
            elif report_type == 'attendance':
                data = extract_attendance_report_data(request, start_date, end_date, filters)
            elif report_type == 'department':
                data = extract_department_report_data(request, start_date, end_date, filters)
            elif report_type == 'leave':
                data = extract_leave_report_data(request, start_date, end_date, filters)
            elif report_type == 'loan':
                data = extract_loan_report_data(request, start_date, end_date, filters)
            else:
                data = []

            # Store data in report
            report.report_data = {
                'data': data,
                'total_records': len(data),
                'filters': filters,
            }
            report.save()

            # Generate report based on format
            if format_type == 'pdf':
                filename = f"report_{report.id}.pdf"
                file_content = generate_pdf_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))
            elif format_type == 'excel':
                filename = f"report_{report.id}.xlsx"
                file_content = generate_excel_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))
            elif format_type == 'csv':
                filename = f"report_{report.id}.csv"
                file_content = generate_csv_report(report, data)
                report.file_path.save(filename, ContentFile(file_content))

            # Mark as completed
            report.mark_completed()

            return JsonResponse({
                'success': True,
                'message': 'Report generated successfully',
                'report_id': str(report.id)
            })

        except Exception as e:
            report.mark_failed(str(e))
            return JsonResponse({
                'success': False,
                'message': f'Error generating report: {str(e)}'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

def generate_pdf_report(report, data=None):
    """Generate PDF report with real data"""
    import importlib

    try:
        # Dynamic import avoids static analysis errors when reportlab is not installed
        canvas_mod = importlib.import_module('reportlab.pdfgen.canvas')
        pagesizes = importlib.import_module('reportlab.lib.pagesizes')
        Canvas = getattr(canvas_mod, 'Canvas')
        letter = getattr(pagesizes, 'letter', (612.0, 792.0))

        buffer = BytesIO()
        p = Canvas(buffer, pagesize=letter)
        y_position = 750

        # Add header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, y_position, report.report_name)
        y_position -= 30

        p.setFont("Helvetica", 12)
        p.drawString(100, y_position, f"Report Type: {report.get_report_type_display()}")
        y_position -= 20

        if report.start_date and report.end_date:
            p.drawString(100, y_position, f"Date Range: {report.start_date} to {report.end_date}")
            y_position -= 20

        p.drawString(100, y_position, f"Generated On: {report.generated_on.strftime('%Y-%m-%d %H:%M')}")
        y_position -= 20

        generated_by_str = (report.generated_by.get_full_name() or report.generated_by.username) if report.generated_by else 'N/A'
        p.drawString(100, y_position, f"Generated By: {generated_by_str}")
        y_position -= 30

        # Add data
        if data and len(data) > 0:
            p.setFont("Helvetica-Bold", 12)
            p.drawString(100, y_position, f"Total Records: {len(data)}")
            y_position -= 30

            # Get column headers from first data item
            if isinstance(data[0], dict):
                headers = list(data[0].keys())
                p.setFont("Helvetica-Bold", 10)
                x = 50
                for header in headers[:6]:  # Limit columns for PDF
                    p.drawString(x, y_position, header.replace('_', ' ').title())
                    x += 100
                y_position -= 20

                # Add data rows
                p.setFont("Helvetica", 9)
                for row in data[:50]:  # Limit rows for PDF
                    if y_position < 50:
                        p.showPage()
                        y_position = 750
                    x = 50
                    for header in headers[:6]:
                        value = str(row.get(header, ''))[:15]  # Truncate long values
                        p.drawString(x, y_position, value)
                        x += 100
                    y_position -= 15
        else:
            p.drawString(100, y_position, "No data available for this report.")

        p.showPage()
        p.save()

        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    except Exception:
        # Fallback: return a plain text bytes payload
        report_data = data if data else []
        fallback_text = (
            f"{report.report_name}\n\n"
            f"Report Type: {report.get_report_type_display()}\n"
            f"Date Range: {report.start_date} to {report.end_date}\n"
            f"Generated On: {report.generated_on.strftime('%Y-%m-%d %H:%M')}\n"
            f"Generated By: {(report.generated_by.get_full_name() or report.generated_by.username) if report.generated_by else 'N/A'}\n"
            f"Total Records: {len(report_data)}\n\n"
        )

        if report_data and len(report_data) > 0:
            if isinstance(report_data[0], dict):
                headers = list(report_data[0].keys())
                fallback_text += "\t".join(headers) + "\n"
                for row in report_data:
                    fallback_text += "\t".join([str(row.get(h, '')) for h in headers]) + "\n"

        fallback_text += "\nNOTE: reportlab is not installed. Install 'reportlab' for proper PDF generation."
        return fallback_text.encode('utf-8')

def generate_excel_report(report, data=None):
    """Generate Excel report with real data"""
    buffer = BytesIO()

    if not data or len(data) == 0:
        # Create empty DataFrame with message
        df = pd.DataFrame({'Message': ['No data available for this report.']})
    else:
        # Convert data to DataFrame
        if isinstance(data[0], dict):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame(data)

    # Use openpyxl as engine for newer pandas versions
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Report Data', index=False)

        # Add summary sheet if include_summary is True
        if report.include_summary and len(data) > 0:
            summary_data = {
                'Metric': ['Total Records', 'Report Type', 'Date Range', 'Generated On'],
                'Value': [
                    len(data),
                    report.get_report_type_display(),
                    f"{report.start_date} to {report.end_date}" if report.start_date and report.end_date else 'N/A',
                    report.generated_on.strftime('%Y-%m-%d %H:%M')
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

    excel_data = buffer.getvalue()
    buffer.close()
    return excel_data

def generate_csv_report(report, data=None):
    """Generate CSV report with real data"""
    buffer = BytesIO()
    writer = csv.writer(buffer)

    if not data or len(data) == 0:
        writer.writerow(['Message'])
        writer.writerow(['No data available for this report.'])
    else:
        # Write headers
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            writer.writerow(headers)

            # Write data rows
            for row in data:
                writer.writerow([row.get(header, '') for header in headers])
        else:
            # If data is not dict format, write as-is
            for row in data:
                writer.writerow(row if isinstance(row, list) else [row])

    csv_data = buffer.getvalue()
    buffer.close()
    return csv_data

@login_required
def view_report(request, report_id):
    """View report details"""
    report = get_object_or_404(Report, id=report_id)

    # Check access - employees can only view their own reports
    user_role = get_user_role(request)
    if user_role == 'employee' and report.generated_by != request.user:
        messages.error(request, 'You do not have permission to view this report.')
        return redirect('reports')

    # Generate summary data from report_data if available
    summary = {}
    if report.report_data:
        data = report.report_data.get('data', [])
        total_records = len(data)
        summary['Total Records'] = total_records

        # Calculate statistics based on report type
        if report.report_type == 'payroll' and data:
            total_salary = sum(float(item.get('net_salary', 0)) for item in data if isinstance(item, dict))
            avg_salary = total_salary / total_records if total_records > 0 else 0
            summary['Total Payroll'] = f"${total_salary:,.2f}"
            summary['Average Salary'] = f"${avg_salary:,.2f}"
        elif report.report_type == 'attendance' and data:
            present_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Present')
            summary['Present Days'] = present_count
            summary['Total Records'] = total_records
        elif report.report_type == 'employee' and data:
            active_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Active')
            summary['Active Employees'] = active_count
            summary['Total Employees'] = total_records
        elif report.report_type == 'department' and data:
            total_depts = len(data)
            total_employees = sum(int(item.get('employee_count', 0)) for item in data if isinstance(item, dict))
            summary['Total Departments'] = total_depts
            summary['Total Employees'] = total_employees
        elif report.report_type == 'leave' and data:
            approved_count = sum(1 for item in data if isinstance(item, dict) and item.get('status') == 'Approved')
            summary['Approved Leaves'] = approved_count
            summary['Total Requests'] = total_records
        elif report.report_type == 'loan' and data:
            total_loans = len(data)
            total_amount = sum(float(item.get('amount', 0)) for item in data if isinstance(item, dict))
            summary['Total Loans'] = total_loans
            summary['Total Amount'] = f"${total_amount:,.2f}"
    else:
        summary['Total Records'] = 0
        summary['Status'] = 'No data available'

    # Format report data with nice column headers
    report_data = report.report_data.get('data', []) if report.report_data else []
    formatted_data = []
    column_headers = []

    if report_data and len(report_data) > 0 and isinstance(report_data[0], dict):
        # Get headers and format them
        column_headers = [key.replace('_', ' ').title() for key in report_data[0].keys()]

        # Create formatted data with original keys but also store formatted headers
        formatted_data = report_data
    else:
        formatted_data = report_data

    context = {
        'report': report,
        'summary': summary,
        'report_data': formatted_data,
        'column_headers': column_headers
    }

    return render(request, 'pages/view_report.html', context)

@login_required
def download_report(request, report_id):
    """Download report file"""
    report = get_object_or_404(Report, id=report_id)

    if not report.file_path or not report.file_path.name:
        return JsonResponse({'success': False, 'message': 'Report file not found'})

    try:
        response = HttpResponse(report.file_path.read(), content_type='application/octet-stream')
        filename = f"{report.report_name}.{report.format}"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error downloading file: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def delete_report(request, report_id):
    """Delete a report"""
    try:
        # Use try-except instead of get_object_or_404 to return JSON instead of HTML 404
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Report not found.'
            }, status=404)

        # Access control - employees can only delete their own reports
        user_role = get_user_role(request)
        if user_role == 'employee' and report.generated_by != request.user:
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to delete this report.'
            }, status=403)

        # Delete file if exists
        if report.file_path:
            try:
                if default_storage.exists(report.file_path.name):
                    default_storage.delete(report.file_path.name)
            except Exception as file_error:
                # Log but don't fail if file deletion fails
                print(f"Warning: Could not delete report file: {file_error}")

        report.delete()

        return JsonResponse({'success': True, 'message': 'Report deleted successfully'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting report: {str(e)}'
        }, status=500)

@login_required
def generate_from_template(request, template_id):
    """Generate report from template"""
    template = get_object_or_404(ReportTemplate, id=template_id)

    # Increment template usage
    template.increment_usage()

    # Create a new report based on template
    report = Report.objects.create(
        report_type=template.report_type,
        report_name=f"{template.name} - {timezone.now().strftime('%Y-%m-%d')}",
        date_range=template.default_date_range,
        format=template.default_format,
        generated_by=request.user,
        status='processing'
    )

    # Calculate dates based on default date range
    end_date = timezone.now().date()
    if template.default_date_range == 'last_week':
        start_date = end_date - timedelta(days=7)
    elif template.default_date_range == 'last_month':
        start_date = end_date - timedelta(days=30)
    elif template.default_date_range == 'last_quarter':
        start_date = end_date - timedelta(days=90)
    elif template.default_date_range == 'last_year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)

    report.start_date = start_date
    report.end_date = end_date
    report.save()

    # Redirect to view the new report
    return redirect('view_report', report_id=report.id)

# API endpoints for AJAX calls
@login_required
def get_report_status(request, report_id):
    """Get report generation status"""
    report = get_object_or_404(Report, id=report_id)
    return JsonResponse({
        'status': report.status,
        'progress': 100 if report.status == 'completed' else 50,
        'message': 'Report completed' if report.status == 'completed' else 'Processing...'
    })

@login_required
def get_recent_reports(request):
    """Get recent reports for AJAX updates"""
    recent_reports = Report.objects.all().order_by('-generated_on')[:10]

    reports_data = []
    for report in recent_reports:
        reports_data.append({
            'id': str(report.id),
            'report_name': report.report_name,
            'report_type': report.get_report_type_display(),
            'generated_on': report.generated_on.strftime('%M %d, %Y %H:%M'),
            'file_size': report.get_file_size_display(),
            'status': report.status,
            'status_display': report.get_status_display()
        })

    return JsonResponse({'reports': reports_data})