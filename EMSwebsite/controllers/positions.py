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


@login_required
def positions(request):
    pos_qs = Position.objects.all().order_by("-date_added")
    total_positions = pos_qs.count()
    active_positions = pos_qs.filter(status="active").count()
    total_employees = only_me_employee_qs(request).count()  # scoped employee count

    return render(request, "pages/positions.html", {
        "positions": pos_qs,
        "total_positions": total_positions,
        "active_positions": active_positions,
        "total_employees": total_employees,
    })

@login_required
def add_position(request):
    if request.method == "POST":
        try:
            Position.objects.create(
                name=request.POST.get("name"),
                description=request.POST.get("description"),
                status=request.POST.get("status", "active")
            )
            messages.success(request, "Position created successfully!")
        except Exception as e:
            messages.error(request, f"Error creating position: {e}")
    return redirect("positions")

@login_required
def update_position(request, pk):
    position = get_object_or_404(Position, pk=pk)
    if request.method == "POST":
        try:
            position.name = request.POST.get("name")
            position.description = request.POST.get("description")
            position.status = request.POST.get("status", "active")
            position.save()
            messages.success(request, f"Position '{position.name}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating position: {e}")
    return redirect("positions")

@login_required
def delete_position(request, pk):
    position = get_object_or_404(Position, pk=pk)
    name = position.name
    position.delete()
    messages.success(request, f"Position '{name}' deleted successfully!")
    return redirect("positions")

