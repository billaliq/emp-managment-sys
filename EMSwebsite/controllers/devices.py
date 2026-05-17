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

import pytz
import atexit

# Optional dependency for background scheduling
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    IntervalTrigger = None

# Optional dependency for biometric device integration
try:
    from zk import ZK
    from zk.user import User as ZKUser
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False
    ZK = None

from EMSwebsite.models import Employees, Attendance, ZKDevice, AttendanceLog, EnrollmentLog
from EMSwebsite.device_utils import ZKDeviceManager


def device_management(request):
    """Device management page - add, edit, delete devices"""
    from EMSwebsite.models import ZKDevice

    devices = ZKDevice.objects.all().order_by('-created_at')

    context = {
        'devices': devices,
    }
    return render(request, 'pages/device/management.html', context)


@login_required
@hr_or_admin_required
def device_enrollment(request):
    """Device enrollment page - select employee and enroll"""
    from EMSwebsite.models import ZKDevice, Employees, EnrollmentLog

    devices = ZKDevice.objects.filter(is_active=True)
    employees = Employees.objects.filter(status=1).order_by('firstname')

    # Get recent enrollments
    recent_enrollments = EnrollmentLog.objects.select_related('device', 'employee', 'initiated_by').order_by('-started_at')[:20]

    context = {
        'devices': devices,
        'employees': employees,
        'recent_enrollments': recent_enrollments,
    }
    return render(request, 'pages/device/enrollment.html', context)


@login_required
@hr_or_admin_required
def attendance_live(request):
    """Live attendance monitoring page"""
    from EMSwebsite.models import ZKDevice, AttendanceLog

    devices = ZKDevice.objects.filter(is_active=True)
    today_logs = AttendanceLog.objects.filter(
        timestamp__date=timezone.now().date()
    ).select_related('device', 'employee').order_by('-timestamp')[:100]

    context = {
        'devices': devices,
        'today_logs': today_logs,
    }
    return render(request, 'pages/attendance/live.html', context)


# ===========================
#   CORE FETCH & SYNC LOGIC
# ===========================

def fetch_and_save_employees(request):
    """
    Fetch employees from ALL active ZKDevices and save to DB.
    """
    if not ZK_AVAILABLE:
        return JsonResponse({"status": "error", "message": "pyzk library not installed"}, status=500)

    devices = ZKDevice.objects.filter(is_active=True)
    if not devices.exists():
        return JsonResponse({"status": "error", "message": "No active devices found in database"}, status=404)

    total_created = 0
    all_created_users = []
    errors = []

    for device_obj in devices:
        try:
            manager = ZKDeviceManager(device_obj)
            ok, msg, conn = manager.connect()

            if not ok:
                errors.append(f"{device_obj.name}: Connection failed - {msg}")
                continue

            try:
                users = manager.get_users()
            except Exception as e:
                errors.append(f"{device_obj.name}: Failed to get users - {e}")
                manager.disconnect()
                continue

            created_count = 0

            for user in users:
                logger.info(f"Processing device user: {user.user_id} - {user.name}")

                # Skip incomplete entries
                if not user.user_id:
                    logger.warning(f"Skipping user with empty user_id: {user.name}")
                    continue

                user_id_str = str(user.user_id).strip()
                if not user_id_str:
                    logger.warning(f"Skipping user with empty stripped user_id: {user.name}")
                    continue

                # Basic username + company email from device name
                name_str = user.name.strip() if user.name else f"Emp_{user_id_str}"
                username = name_str.split()[0].lower()
                official_email = f"{username}{user_id_str}@aliqtechnology.com" # Ensure uniqueness

                # Avoid duplicates: we use `code` as the unique fingerprint id
                if Employees.objects.filter(code=user_id_str).exists():
                    logger.info(f"User {user_id_str} already exists. Skipping.")
                    continue

                try:
                    # Create minimal employee with ONLY data we have from device
                    emp = Employees.objects.create(
                        code=user_id_str,                # Employee ID from device
                        firstname=name_str,              # Full name from device
                        lastname="",                     # Not available → keep empty
                        official_email=official_email,   # Generated company email
                        date_hired=date.today(),         # Default
                        status=1,                        # Active
                        # Set defaults for FKs if they exist, otherwise leave null
                        department_id=1 if Department.objects.filter(id=1).exists() else None,
                        position_id=1 if Position.objects.filter(id=1).exists() else None,
                    )

                    # The post_save signal on Employees will auto-create the auth User

                    all_created_users.append({
                        "device": device_obj.name,
                        "id": emp.id,
                        "name": emp.firstname,
                        "code": emp.code
                    })
                    created_count += 1
                    logger.info(f"Created employee: {emp.firstname} ({emp.code})")

                except Exception as create_err:
                     err_msg = f"Failed to create employee {name_str} ({user_id_str}): {create_err}"
                     logger.error(err_msg)
                     errors.append(err_msg)

            total_created += created_count
            manager.disconnect()

        except Exception as e:
            errors.append(f"{device_obj.name}: Unexpected error - {str(e)}")
            logger.error(f"Error fetching employees from {device_obj.name}: {e}")

    message = f"Imported {total_created} new employees."
    if errors:
        message += f" Errors: {'; '.join(errors)}"

    return JsonResponse({
        "status": "success" if total_created > 0 else ("warning" if errors else "success"),
        "message": message,
        "employees": all_created_users,
        "errors": errors
    })


def fetch_and_save_attendance(request=None):
    """
    Fetch attendance from ALL active ZKDevices and save to DB.
    Can be used as:
    - a Django view: /import-attendance/  → returns JsonResponse
    - a background job (scheduler)       → request will be None
    """
    logger.info("*********** Fetching Attendance ***********")

    if not ZK_AVAILABLE:
        if request:
            return JsonResponse({"status": "error", "message": "pyzk library not installed"}, status=500)
        return

    devices = ZKDevice.objects.filter(is_active=True)
    if not devices.exists():
        msg = "No active devices found."
        logger.warning(msg)
        if request:
             return JsonResponse({"status": "warning", "message": msg})
        return

    total_processed = 0
    total_new = 0
    errors = []

    for device_obj in devices:
        try:
            logger.info(f"Connecting to {device_obj.name}...")
            manager = ZKDeviceManager(device_obj)
            ok, msg, conn = manager.connect()

            if not ok:
                err = f"{device_obj.name}: {msg}"
                logger.error(err)
                errors.append(err)
                continue

            try:
                attendance_data = manager.get_attendance()
            except Exception as e:
                err = f"{device_obj.name}: Failed to get attendance - {e}"
                logger.error(err)
                errors.append(err)
                manager.disconnect()
                continue

            device_processed = 0
            device_new = 0

            # Group by (employee, date) to process simplified logic
            attendance_by_employee = {}

            for record in attendance_data:
                # Map device user_id -> Employees.code
                user_id_str = str(record.user_id).strip()

                # Check if employee exists
                # OPTIMIZATION: In production, load all employees code->id map once before loop
                try:
                    emp = Employees.objects.get(code=user_id_str)
                except Employees.DoesNotExist:
                    # Fallback: If user_id is numeric, try to find a match ignoring leading zeros (e.g. "1" matches "001")
                    found_fallback = False
                    if user_id_str.isdigit():
                        # 1. Try regex match for DB "001" when Device is "1"
                        emp = Employees.objects.filter(code__iregex=r'^[0]*' + user_id_str + '$').first()
                        if emp:
                            found_fallback = True
                            logger.info(f"Matched device user {user_id_str} to employee {emp.code}")

                        # 2. Try stripping device zeros for DB "1" when Device is "001"
                        if not found_fallback:
                            try:
                                clean_id = str(int(user_id_str))
                                emp = Employees.objects.get(code=clean_id)
                                found_fallback = True
                                logger.info(f"Matched device user {user_id_str} to employee {emp.code} (stripped zeros)")
                            except Employees.DoesNotExist:
                                pass

                    if not found_fallback:
                        logger.warning(f"Skipping attendance for unknown user_id: {user_id_str} on device {device_obj.name}")
                        continue

                timestamp = record.timestamp

                # Ensure timezone-aware datetime
                if timezone.is_naive(timestamp):
                    tz = pytz.timezone('Asia/Karachi') # Should be configurable from settings
                    timestamp = timezone.make_aware(timestamp, tz)

                # Save raw log first (Audit trail / Backup)
                # Using update_or_create to avoid duplicates if re-fetched
                # We assume (device, employee, timestamp) is unique enough
                try:
                    log, created = AttendanceLog.objects.get_or_create(
                        device=device_obj,
                        employee=emp,
                        timestamp=timestamp,
                        defaults={
                            'user_id': user_id_str,
                            'event_type': 'check_in' if getattr(record, 'punch', 0) in [0, 4, 3] else 'check_out', # APPROXIMATION
                            'verification_mode': getattr(record, 'verify_mode', 0),
                            'raw_data': {'uid': getattr(record, 'uid', None), 'punch': getattr(record, 'punch', 0)}
                        }
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to save AttendanceLog: {log_err}")

                # Prepare for aggregation
                date_obj = timestamp.date()
                time_obj = timestamp.time()
                key = (emp.id, date_obj)
                attendance_by_employee.setdefault(key, []).append(time_obj)

                device_processed += 1

            # Process aggregated data for Attendance table
            for (emp_id, date_obj), punch_times in attendance_by_employee.items():
                if not punch_times:
                    continue

                punch_times.sort()

                # Deduplicate punches within 2 mins
                filtered_punches = []
                prev_punch = None
                for punch in punch_times:
                    if prev_punch is None:
                        filtered_punches.append(punch)
                        prev_punch = punch
                    else:
                        delta_minutes = (
                            datetime.combine(date_obj, punch) -
                            datetime.combine(date_obj, prev_punch)
                        ).total_seconds() / 60
                        if delta_minutes >= 2:
                            filtered_punches.append(punch)
                            prev_punch = punch

                # Get or Create Attendance Record
                try:
                    att, created = Attendance.objects.get_or_create(
                        employee_id=emp_id,
                        date=date_obj,
                    )
                except Exception as e:
                    logger.error(f"Error getting attendance record: {e}")
                    continue

                # If finalized, maybe skip? For now, we update.
                updated = False

                # Thresholds (Should ideally come from Employee -> Department -> Settings)
                # We use the method on the model or simple defaults
                thresholds = att.get_office_timings()
                check_in_threshold = thresholds['office_start'] # e.g. 9:00
                check_out_threshold = thresholds['office_end']  # e.g. 18:00

                # Logic: Flexible Min/Max update to support incremental sync
                if filtered_punches:
                    for punch in filtered_punches:
                        # 1. Update Check-In (Earliest punch is always Check-In)
                        if not att.check_in_time or punch < att.check_in_time:
                            att.check_in_time = punch
                            updated = True

                    # 2. Update Check-Out (Latest punch > Check-In is Check-Out)
                    for punch in filtered_punches:
                        if att.check_in_time and punch > att.check_in_time:
                             if not att.check_out_time or punch > att.check_out_time:
                                att.check_out_time = punch
                                updated = True

                if updated or created:
                    att.calculate_durations() # updates late_in, early_out based on new times
                    status = att.auto_determine_status()
                    if status:
                         att.status = status
                    att.save()
                    device_new += 1

            manager.disconnect()
            total_processed += device_processed
            total_new += device_new
            logger.info(f"{device_obj.name}: Processed {device_processed} logs, Updated {device_new} records.")

        except Exception as e:
            err = f"{device_obj.name}: Global error - {e}"
            logger.error(err)
            errors.append(err)

    result_msg = f"Processed {total_processed} records across {len(devices)} devices. Updated {total_new} entries."
    logger.info(result_msg)

    if request:
        return JsonResponse({
            "status": "success" if not errors else "warning",
            "message": result_msg,
            "errors": errors
        })


def start_sync_on_django_start():
    """
    Start a background scheduler that syncs attendance
    from the device every 2 minutes.
    Call this from AppConfig.ready().
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("APScheduler not available. Background attendance sync disabled.")
        return

    try:
        tz = pytz.timezone('Asia/Karachi')
        scheduler = BackgroundScheduler(timezone=tz)

        trigger = IntervalTrigger(seconds=120, timezone=tz)

        scheduler.add_job(
            func=fetch_and_save_attendance,
            trigger=trigger,
            id='attendance_sync_job',
            name='Fetch and save attendance data every 2 minutes',
            replace_existing=True,
        )

        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
    except Exception as e:
        logger.error(f"Failed to start attendance sync scheduler: {e}")


def check_device_status(request):
    """
    Check status of a specific device.
    Requires device_id parameter.
    If no device_id provided, returns error to prevent timeout on default IP.
    """
    device_id = request.GET.get('device_id')

    if not device_id:
        return JsonResponse({
            "status": "error",
            "message": "Device ID required"
        }, status=400)

    if not ZK_AVAILABLE:
        return JsonResponse({"status": "error", "message": "ZK library not installed"}, status=500)

    try:
        from EMSwebsite.models import ZKDevice
        device = ZKDevice.objects.get(id=device_id)

        zk = ZK(device.ip_address, port=device.port, timeout=5)
        conn = zk.connect()
        # Just check connection, don't disable/enable which disrupts service!
        conn.disconnect()

        return JsonResponse({"status": "success", "message": f"Device {device.name} is online."})
    except Exception as e:
        logger.error(f"Error in device connection: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ===========================
#   DEVICE API VIEWS
# ===========================

# API Views for Device Operations


@login_required
@hr_or_admin_required
@require_POST
def api_device_push_user(request):
    """API: Push user to device"""
    from EMSwebsite.models import ZKDevice, Employees
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')

        # Use explicit getters to avoid HTML 404 pages
        try:
            device = ZKDevice.objects.get(id=device_id, is_active=True)
        except ZKDevice.DoesNotExist:
             return JsonResponse({'success': False, 'message': 'Device not found or inactive'}, status=404)

        try:
            employee = Employees.objects.get(id=employee_id)
        except Employees.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found'}, status=404)

        manager = ZKDeviceManager(device)
        success, message = manager.push_user(employee)

        manager.disconnect()

        if success:
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        # Catch any other error (including unexpected ones) and return JSON
        return JsonResponse({'success': False, 'message': f"Internal Error: {str(e)}"}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_enroll_fingerprint(request):
    """API: Start fingerprint enrollment"""
    from EMSwebsite.models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        # Check if enrollment already exists (handle unique constraint)
        enrollment, created = EnrollmentLog.objects.get_or_create(
            device=device,
            employee=employee,
            enrollment_type='fingerprint',
            template_index=template_index,
            defaults={
                'status': 'in_progress',
                'initiated_by': request.user,
                'started_at': timezone.now(),
            }
        )

        # If enrollment already exists, update it to restart
        if not created:
            # If it's already in progress, allow restarting
            enrollment.status = 'in_progress'
            enrollment.error_message = None
            enrollment.completed_at = None
            enrollment.started_at = timezone.now()
            enrollment.initiated_by = request.user
            enrollment.save()

        manager = ZKDeviceManager(device)
        success, message = manager.start_fingerprint_enrollment(employee, template_index)

        if success:
            enrollment.status = 'in_progress'
            enrollment.save()

            # Verify user is registered on device before disconnecting
            user_exists, verify_msg = manager.verify_user_exists(employee)
            if user_exists:
                logger.info(f"User {employee.code} confirmed registered on device {device.name}")
            else:
                logger.warning(f"User {employee.code} may not be registered: {verify_msg}")

            manager.disconnect()

            # Broadcast via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'device_events',
                    {
                        'type': 'enrollment_update',
                        'data': {
                            'id': enrollment.id,
                            'employee': employee.code,
                            'type': 'fingerprint',
                            'status': 'in_progress',
                            'message': message
                        }
                    }
                )

            return JsonResponse({'success': True, 'message': message, 'enrollment_id': enrollment.id})
        else:
            enrollment.status = 'failed'
            enrollment.error_message = message
            enrollment.save()
            manager.disconnect()
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_enroll_face(request):
    """API: Start face enrollment"""
    from EMSwebsite.models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        # Check if enrollment already exists (handle unique constraint)
        enrollment, created = EnrollmentLog.objects.get_or_create(
            device=device,
            employee=employee,
            enrollment_type='face',
            template_index=template_index,
            defaults={
                'status': 'in_progress',
                'initiated_by': request.user,
                'started_at': timezone.now(),
            }
        )

        # If enrollment already exists, update it to restart
        if not created:
            # If it's already in progress, allow restarting
            enrollment.status = 'in_progress'
            enrollment.error_message = None
            enrollment.completed_at = None
            enrollment.started_at = timezone.now()
            enrollment.initiated_by = request.user
            enrollment.save()

        manager = ZKDeviceManager(device)
        success, message = manager.start_face_enrollment(employee, template_index)

        if success:
            enrollment.status = 'in_progress'
            enrollment.save()
            manager.disconnect()

            # Broadcast via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'device_events',
                    {
                        'type': 'enrollment_update',
                        'data': {
                            'id': enrollment.id,
                            'employee': employee.code,
                            'type': 'face',
                            'status': 'in_progress',
                            'message': message
                        }
                    }
                )

            return JsonResponse({'success': True, 'message': message, 'enrollment_id': enrollment.id})
        else:
            enrollment.status = 'failed'
            enrollment.error_message = message
            enrollment.save()
            manager.disconnect()
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
def api_device_verify_enrollment(request):
    """API: Verify fingerprint enrollment completion"""
    from EMSwebsite.models import ZKDevice, Employees, EnrollmentLog
    from .device_utils import ZKDeviceManager
    import json
    import traceback

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        employee_id = data.get('employee_id')
        template_index = int(data.get('template_index', 0))

        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)
        employee = get_object_or_404(Employees, id=employee_id)

        manager = ZKDeviceManager(device)
        success, message = manager.verify_fingerprint_enrollment(employee, template_index)
        manager.disconnect()

        if success:
            # Update enrollment log if exists
            try:
                enrollment = EnrollmentLog.objects.get(
                    device=device,
                    employee=employee,
                    enrollment_type='fingerprint',
                    template_index=template_index,
                    status='in_progress'
                )
                enrollment.status = 'completed'
                enrollment.completed_at = timezone.now()
                enrollment.save()

                # Broadcast completion via WebSocket
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        'device_events',
                        {
                            'type': 'enrollment_update',
                            'data': {
                                'id': enrollment.id,
                                'employee': employee.code,
                                'type': 'fingerprint',
                                'status': 'completed',
                                'message': message
                            }
                        }
                    )
            except EnrollmentLog.DoesNotExist:
                pass

            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        logger.error(f"Error verifying enrollment: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
def api_device_test_connection(request):
    """API: Test device connection"""
    from .device_utils import ZKDeviceManager
    from EMSwebsite.models import ZKDevice

    ip = (request.GET.get('ip') or '').strip()
    port = int(request.GET.get('port') or 4370)
    password = (request.GET.get('password') or '').strip() or None

    if not ip:
        return JsonResponse({'success': False, 'message': 'IP address required'}, status=400)

    # Create temporary device object for testing
    class TempDevice:
        def __init__(self, ip, port, timeout, password):
            self.ip_address = ip
            self.port = port
            self.timeout = timeout
            self.password = password
            self.status = 'offline'
            self.last_error = None
            self.device_name = None
            self.serial_number = None

        def save(self, update_fields=None):
            pass

    temp_device = TempDevice(ip, port, 5, password)
    manager = ZKDeviceManager(temp_device)
    success, message, conn = manager.connect()

    if success:
        manager.disconnect()
        return JsonResponse({
            'success': True,
            'message': f'Connection successful to {ip}:{port}',
            'device_name': temp_device.device_name,
            'serial_number': temp_device.serial_number
        })
    else:
        return JsonResponse({
            'success': False,
            'message': message
        })


@login_required
@hr_or_admin_required

def api_device_status(request, device_id):
    """API: Get device status (JSON safe)"""

    from EMSwebsite.models import ZKDevice
    from .device_utils import ZKDeviceManager

    # 🔐 Manual auth check (JSON response instead of redirect)
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required"
        }, status=401)

    try:
        device = get_object_or_404(ZKDevice, id=device_id)

        manager = ZKDeviceManager(device)
        success, message, conn = manager.connect()

        data = {
            "success": True,
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "port": device.port,
            "status": device.status,
            "is_online": success,
            "last_connected": device.last_connected.isoformat() if device.last_connected else None,
            "last_error": device.last_error,
            "message": message,
        }

        if conn:
            manager.disconnect()

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)



@login_required
@hr_or_admin_required
def api_device_logs(request, device_id):
    """API: Get device logs"""
    from EMSwebsite.models import ZKDevice, AttendanceLog

    device = get_object_or_404(ZKDevice, id=device_id)

    # Get recent logs
    limit = int(request.GET.get('limit', 50))
    logs = AttendanceLog.objects.filter(device=device).select_related('employee').order_by('-timestamp')[:limit]

    logs_data = []
    for log in logs:
        logs_data.append({
            'id': log.id,
            'user_id': log.user_id,
            'user_name': log.user_name,
            'employee_code': log.employee.code if log.employee else None,
            'employee_name': f"{log.employee.firstname} {log.employee.lastname or ''}".strip() if log.employee else None,
            'event_type': log.event_type,
            'timestamp': log.timestamp.isoformat(),
            'verification_mode': log.verification_mode,
            'is_processed': log.is_processed,
        })

    return JsonResponse({'logs': logs_data})


@login_required
@hr_or_admin_required
@require_POST
def api_device_create(request):
    """API: Create new device"""
    from EMSwebsite.models import ZKDevice
    import json

    try:
        data = json.loads(request.body)
        # Safely handle None values - convert to string first to avoid NoneType errors
        name = str(data.get('name') or '').strip()
        ip_address = str(data.get('ip_address') or '').strip()
        port = int(data.get('port') or 4370)
        timeout = int(data.get('timeout') or 5)
        password_value = data.get('password')
        password = str(password_value).strip() if password_value else None
        if password == '':
            password = None

        if not name or not ip_address:
            return JsonResponse({'success': False, 'message': 'Name and IP address are required'}, status=400)

        # Check if device with same name exists
        if ZKDevice.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'message': f'Device with name "{name}" already exists'}, status=400)

        device = ZKDevice.objects.create(
            name=name,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            password=password,
            is_active=True,
            realtime_enabled=True
        )

        return JsonResponse({
            'success': True,
            'message': f'Device "{name}" created successfully',
            'device': {
                'id': device.id,
                'name': device.name,
                'ip_address': device.ip_address,
                'port': device.port
            }
        })

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating device: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_delete(request, device_id):
    """API: Delete device"""
    from EMSwebsite.models import ZKDevice

    try:
        device = get_object_or_404(ZKDevice, id=device_id)
        device_name = device.name
        device.delete()
        return JsonResponse({'success': True, 'message': f'Device "{device_name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@hr_or_admin_required
@require_POST
def api_device_cancel_enrollment(request):
    """API: Cancel current enrollment process"""
    from EMSwebsite.models import ZKDevice
    from .device_utils import ZKDeviceManager
    import json

    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')

        # Use explicit check to allow 'get_object_or_404' to work or handle manually if imports issue
        # Assuming get_object_or_404 is valid as per file analysis
        device = get_object_or_404(ZKDevice, id=device_id, is_active=True)

        manager = ZKDeviceManager(device)
        success, message = manager.cancel_enrollment()
        manager.disconnect()

        if success:
             # Find any in-progress enrollments for this device and mark as cancelled
            from EMSwebsite.models import EnrollmentLog
            EnrollmentLog.objects.filter(
                device=device,
                status='in_progress'
            ).update(
                status='failed',
                error_message='Cancelled by user',
                completed_at=timezone.now()
            )

            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'message': message}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
