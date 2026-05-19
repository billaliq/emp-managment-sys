from django.contrib import admin
from .models import (
    Department, Position, Employees,
    DepartmentEmployee, Attendance, AttendanceSettings, LeaveRequest, HolidayDate,
    Team, TeamMember, Project, Payroll, PayrollRecord, SalaryIncrement, SystemSettings,
    Loan, LoanRepayment, IncrementSettings, Notification
)


# Inline for department employees
class DepartmentEmployeeInline(admin.TabularInline):
    model = DepartmentEmployee
    extra = 1


# Inline for team members
class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1
    raw_id_fields = ('employee',)


# Inline for team projects
class ProjectInline(admin.TabularInline):
    model = Project
    extra = 1
    readonly_fields = ('created_at', 'updated_at')




from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'employee__firstname')
    raw_id_fields = ('employee',)


# Department Admin
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'employee_count_display', 'head', 'use_custom_timings', 'office_timings_display', 'created_at', 'updated_at')
    list_filter = ('status', 'use_custom_timings')
    search_fields = ('name', 'description')
    inlines = [DepartmentEmployeeInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status', 'head')
        }),
        ('Office Timings', {
            'fields': ('use_custom_timings', 'office_start_time', 'office_end_time', 'grace_period_minutes'),
            'description': 'Set custom office timings for this department. If disabled, uses global attendance settings. Changes apply going forward only and do not affect past attendance records.'
        }),
    )

    def employee_count_display(self, obj):
        # Count employees related to this department
        return obj.employees_set.count()
    employee_count_display.short_description = 'Employees'

    def office_timings_display(self, obj):
        """Display office timings in list view"""
        if obj.use_custom_timings and obj.office_start_time and obj.office_end_time:
            grace = obj.grace_period_minutes or obj.get_grace_period_minutes()
            return f"{obj.office_start_time.strftime('%H:%M')} - {obj.office_end_time.strftime('%H:%M')} (Grace: {grace}m)"
        return "Global Settings"
    office_timings_display.short_description = 'Office Timings'


# Position Admin
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'date_added')
    list_filter = ('status',)
    search_fields = ('name',)


# Employees Admin
@admin.register(Employees)
class EmployeesAdmin(admin.ModelAdmin):
    list_display = (
        'firstname', 'lastname', 'team', 'department', 'position',
        'status', 'date_hired', 'salary', 'employment_type', 'max_task_workload'
    )
    list_filter = ('status', 'team', 'department', 'position', 'employment_type', 'work_mode')
    search_fields = ('firstname', 'lastname', 'code', 'email', 'official_email', 'national_id')
    ordering = ('firstname',)
    date_hierarchy = 'date_hired'
    fieldsets = (
        ('Personal Information', {
            'fields': ('firstname', 'lastname', 'father_name', 'dob', 'gender', 'marital_status', 'blood_group', 'photo')
        }),
        ('Contact', {
            'fields': ('email', 'official_email', 'contact_1', 'contact_2', 'emergency_contact', 'emergency_contact_person')
        }),
        ('Job Details', {
            'fields': ('code', 'department', 'position', 'team', 'job_title', 'reporting_to', 'work_mode', 'employment_type', 'date_hired', 'date_permanent', 'status')
        }),
        ('AI Task Assignment', {
            'fields': ('skills', 'max_task_workload'),
            'description': 'Skills used by the BFS/A* task assignment algorithm.'
        }),
        ('Salary', {
            'fields': ('salary', 'bank_name', 'branch_name', 'account_title', 'account_number'),
            'classes': ('collapse',)
        }),
    )


# Team Admin
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'leader', 'department', 'status', 'members_count', 'projects_count', 'created_at')
    list_filter = ('status', 'department', 'created_at')
    search_fields = ('name', 'leader__firstname', 'leader__lastname', 'department__name')
    readonly_fields = ('created_at', 'updated_at', 'members_count', 'projects_count')
    inlines = [TeamMemberInline, ProjectInline]

    def members_count(self, obj):
        return obj.members.count()
    members_count.short_description = 'Members'

    def projects_count(self, obj):
        return obj.projects.count()
    projects_count.short_description = 'Projects'


# Team Member Admin
@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('employee', 'team', 'role', 'joined_at', 'is_active')
    list_filter = ('is_active', 'team', 'joined_at')
    search_fields = ('employee__firstname', 'employee__lastname', 'team__name', 'role')
    readonly_fields = ('joined_at',)
    list_editable = ('is_active', 'role')
    raw_id_fields = ('employee', 'team')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee', 'team')


# Project Admin
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'status', 'start_date', 'end_date', 'progress', 'created_at')
    list_filter = ('status', 'team', 'start_date', 'end_date')
    search_fields = ('name', 'team__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('status', 'progress')
    date_hierarchy = 'start_date'
    raw_id_fields = ('team',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team')


# Attendance Admin - CORRECTED VERSION
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'employee_display', 'team_display', 'date',
        'check_in_time', 'check_out_time', 'status',
        'late_display', 'leave_display', 'overtime_display',
        'weekend_display', 'holiday_display', 'duration_display'
    )
    list_filter = ('status', 'date', 'employee__department', 'employee__team')
    search_fields = ('employee__firstname', 'employee__lastname', 'employee__code')
    date_hierarchy = 'date'
    readonly_fields = (
        'created_at', 'updated_at',
    )
    list_editable = ('status',)
    raw_id_fields = ('employee',)
    ordering = ('-date', '-check_in_time')

    fieldsets = (
        ('Basic Information', {
            'fields': ('employee', 'date', 'status', 'leave_type')
        }),
        ('Time Tracking', {
            'fields': (
                'check_in_time', 'check_out_time', 'timetable'
            )
        }),
        ('Duration Calculations', {
            'fields': (
                'actual_work', 'required_work', 'break_time',
                'late_in', 'early_out', 'late_sitting'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('overtime_hours', 'reason', 'notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee')

    def employee_display(self, obj):
        """Display employee with ID/Code"""
        code = obj.employee.code if obj.employee.code else obj.employee.id
        return f"{code} - {obj.employee.firstname} {obj.employee.lastname or ''}"
    employee_display.short_description = 'Employee (ID / Name)'
    employee_display.admin_order_field = 'employee__firstname'

    def team_display(self, obj):
        """Display team name"""
        if obj.employee.team:
            try:
                team_label = obj.employee.get_team_display()
                if team_label and team_label != '-- Select Team --':
                    return team_label
            except:
                pass
        return 'No Team'
    team_display.short_description = 'Team'
    team_display.admin_order_field = 'employee__team'

    def late_display(self, obj):
        """Display late time"""
        if obj.late_in:
            return obj.late_in_display
        return '--'
    late_display.short_description = 'Late'
    late_display.admin_order_field = 'late_in'

    def leave_display(self, obj):
        """Display leave type"""
        if obj.status == 'leave' and obj.leave_type:
            return obj.get_leave_type_display()
        elif obj.status == 'leave':
            return 'On Leave'
        return '--'
    leave_display.short_description = 'Leave'

    def overtime_display(self, obj):
        """Display overtime hours"""
        if obj.overtime_hours and obj.overtime_hours > 0:
            return obj.overtime_display
        return '--'
    overtime_display.short_description = 'Overtime'
    overtime_display.admin_order_field = 'overtime_hours'

    def weekend_display(self, obj):
        """Display weekend indicator"""
        if obj.is_weekend_date and (obj.check_in_time or obj.check_out_time):
            return 'Weekend'
        return '--'
    weekend_display.short_description = 'Weekend'

    def holiday_display(self, obj):
        """Display holiday name if the date is a holiday"""
        try:
            from .models import HolidayDate
            holiday = HolidayDate.objects.filter(date=obj.date).first()
            if holiday:
                return holiday.name
        except Exception:
            pass
        return '--'
    holiday_display.short_description = 'Holiday'

    def duration_display(self, obj):
        """Display work duration"""
        return obj.duration
    duration_display.short_description = 'Duration'
    duration_display.admin_order_field = 'actual_work'

    # Admin actions for attendance
    def mark_as_present(self, request, queryset):
        queryset.update(status='present')
    mark_as_present.short_description = "Mark selected as Present"

    def mark_as_absent(self, request, queryset):
        queryset.update(status='absent')
    mark_as_absent.short_description = "Mark selected as Absent"

    def mark_as_late(self, request, queryset):
        queryset.update(status='late')
    mark_as_late.short_description = "Mark selected as Late"

    actions = [mark_as_present, mark_as_absent, mark_as_late]


# Attendance Settings Admin
@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'work_start_time', 'work_end_time',
        'grace_period_minutes', 'minimum_work_hours',
        'overtime_threshold_hours', 'weekend_work_allowed',
        'auto_checkout_enabled'
    )


# Holiday Date Admin
@admin.register(HolidayDate)
class HolidayDateAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'created_by', 'created_at')
    list_filter = ('date',)
    search_fields = ('name', 'description')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)


# Leave Request Admin
@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'leave_type', 'start_date', 'end_date',
        'duration_days', 'status', 'applied_on', 'approved_by'
    )
    list_filter = ('status', 'leave_type')
    search_fields = ('employee__firstname', 'employee__lastname', 'reason')
    date_hierarchy = 'applied_on'


# Optional: Add some admin actions for bulk operations
def activate_teams(modeladmin, request, queryset):
    queryset.update(status='active')
activate_teams.short_description = "Activate selected teams"

def deactivate_teams(modeladmin, request, queryset):
    queryset.update(status='inactive')
deactivate_teams.short_description = "Deactivate selected teams"

def mark_projects_completed(modeladmin, request, queryset):
    queryset.update(status='completed', progress=100)
mark_projects_completed.short_description = "Mark selected projects as completed"

def activate_team_members(modeladmin, request, queryset):
    queryset.update(is_active=True)
activate_team_members.short_description = "Activate selected team members"

def deactivate_team_members(modeladmin, request, queryset):
    queryset.update(is_active=False)
deactivate_team_members.short_description = "Deactivate selected team members"

# Add actions to the admin classes
TeamAdmin.actions = [activate_teams, deactivate_teams]
ProjectAdmin.actions = [mark_projects_completed]
TeamMemberAdmin.actions = [activate_team_members, deactivate_team_members]


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('pay_period', 'pay_date', 'processed_by', 'created_at')
    date_hierarchy = 'pay_date'
    ordering = ('-pay_date',)


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = (
        'employee',
        'base_salary',
        'allowances',
        'deductions',
        'net_salary',
        'pay_date',
        'status',
    )
    list_filter = ('status', 'pay_date')
    search_fields = (
        'employee__firstname',
        'employee__lastname',
        'employee__code',
        'employee__email',
    )
    date_hierarchy = 'pay_date'
    ordering = ('-pay_date',)
    list_editable = ('status',)
    list_per_page = 25
    readonly_fields = ('net_salary',)

    fieldsets = (
        ("Employee Info", {
            'fields': ('employee', 'pay_date', 'status')
        }),
        ("Salary Breakdown", {
            'fields': ('base_salary', 'allowances', 'deductions', 'net_salary')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee')


@admin.register(SalaryIncrement)
class SalaryIncrementAdmin(admin.ModelAdmin):
    list_display = ('employee', 'old_salary', 'new_salary', 'increase_percent', 'increase_amount', 'effective_date', 'is_automatic', 'applied_by', 'applied_at')
    date_hierarchy = 'effective_date'
    ordering = ('-effective_date',)
    search_fields = ('employee__firstname', 'employee__lastname', 'employee__code')
    list_filter = ('is_automatic', 'effective_date', 'notification_sent')
    readonly_fields = ('applied_at', 'is_automatic', 'notification_sent')


@admin.register(IncrementSettings)
class IncrementSettingsAdmin(admin.ModelAdmin):
    list_display = ('increment_percentage', 'increment_amount', 'use_percentage', 'cycle_months', 'is_active', 'updated_by', 'updated_at')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', 'updated_by')

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('language', 'date_format', 'time_format', 'dark_mode', 'theme', 'updated_at')
    readonly_fields = ('updated_at',)


class LoanRepaymentInline(admin.TabularInline):
    model = LoanRepayment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount', 'payment_date', 'payment_method', 'notes', 'created_by', 'created_at']


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['employee', 'loan_amount', 'interest_rate', 'total_amount', 'status', 'start_date', 'created_at']
    list_filter = ['status', 'start_date', 'created_at']
    search_fields = ['employee__firstname', 'employee__lastname', 'purpose']
    readonly_fields = ['created_at', 'updated_at', 'total_amount', 'monthly_payment', 'end_date']
    inlines = [LoanRepaymentInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('employee', 'loan_amount', 'interest_rate', 'number_of_installments', 'purpose')
        }),
        ('Dates & Status', {
            'fields': ('start_date', 'end_date', 'status', 'approved_by', 'approval_date')
        }),
        ('Calculated Fields', {
            'fields': ('total_amount', 'monthly_payment'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'amount', 'payment_date', 'payment_method', 'created_at']
    list_filter = ['payment_date', 'payment_method', 'created_at']
    search_fields = ['loan__employee__firstname', 'loan__employee__lastname', 'notes']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Repayment Information', {
            'fields': ('loan', 'amount', 'payment_date', 'payment_method', 'notes')
        }),
        ('Record Information', {
            'fields': ('created_by', 'created_at')
        }),
    )

from django.contrib import admin
from .models import Report, ReportTemplate, ReportSchedule

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['report_name', 'report_type', 'status', 'generated_by', 'generated_on']
    list_filter = ['report_type', 'status', 'generated_on']
    search_fields = ['report_name', 'generated_by__username']
    readonly_fields = ['generated_on', 'completed_on']

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'is_active', 'usage_count']
    list_filter = ['report_type', 'is_active']
    search_fields = ['name', 'description']

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'template', 'frequency', 'is_active', 'next_run']
    list_filter = ['frequency', 'is_active']
    search_fields = ['name', 'email_recipients']


# ZKTeco Device Admin
from .models import ZKDevice, AttendanceLog, EnrollmentLog

@admin.register(ZKDevice)
class ZKDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'port', 'status', 'is_active', 'last_connected']
    list_filter = ['status', 'is_active', 'realtime_enabled']
    search_fields = ['name', 'ip_address', 'serial_number']
    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'ip_address', 'port', 'timeout', 'password')
        }),
        ('Device Details', {
            'fields': ('serial_number', 'device_name', 'firmware_version', 'device_model'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'last_connected', 'last_error')
        }),
        ('Settings', {
            'fields': ('is_active', 'auto_sync', 'realtime_enabled')
        }),
    )
    readonly_fields = ['last_connected', 'last_error']

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'device', 'event_type', 'timestamp', 'is_processed']
    list_filter = ['event_type', 'is_processed', 'device', 'timestamp']
    search_fields = ['user_id', 'user_name', 'employee__code', 'employee__firstname']
    readonly_fields = ['device', 'employee', 'user_id', 'user_name', 'event_type', 'timestamp', 'verification_mode', 'raw_data', 'is_processed', 'processed_at', 'attendance_record']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

@admin.register(EnrollmentLog)
class EnrollmentLogAdmin(admin.ModelAdmin):
    list_display = ['employee', 'device', 'enrollment_type', 'template_index', 'status', 'started_at']
    list_filter = ['enrollment_type', 'status', 'device', 'started_at']
    search_fields = ['employee__code', 'employee__firstname', 'device__name']
    readonly_fields = ['started_at', 'completed_at']
    date_hierarchy = 'started_at'
    ordering = ['-started_at']


# AI Task Assignment Admin
from .models import AssignmentTask

@admin.register(AssignmentTask)
class AssignmentTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'assigned_to', 'deadline', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'deadline']
    search_fields = ['title', 'description', 'assigned_to__firstname', 'assigned_to__lastname']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status', 'priority']
    ordering = ['-priority', 'created_at']
    date_hierarchy = 'created_at'
    raw_id_fields = ['assigned_to', 'created_by']

    fieldsets = (
        ('Task Details', {
            'fields': ('title', 'description', 'required_skills', 'priority', 'deadline')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'status')
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )