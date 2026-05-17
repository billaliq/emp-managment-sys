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


def team(request):
    base_qs = Team.objects.select_related('leader', 'department')
    if request.user.is_superuser:
        teams = base_qs.all()
    else:
        me = get_current_employee(request)
        teams = base_qs.filter(Q(leader=me) | Q(members__employee=me, members__is_active=True)).distinct()

    total_teams = teams.count()
    total_members = TeamMember.objects.filter(is_active=True, team__in=teams).count()
    active_projects = Project.objects.filter(status='active', team__in=teams).count()

    # simple demo stats
    team_availability = 85; teams_change = 2; members_change = 5; projects_change = 3; availability_change = 2

    # Get TEAM_CHOICES for dropdown
    from EMSwebsite.models import Employees
    team_choices = Employees.TEAM_CHOICES

    return render(request, 'pages/team.html', {
        'teams': teams,
        'stats': {
            'total_teams': total_teams,
            'total_members': total_members,
            'active_projects': active_projects,
            'team_availability': team_availability,
            'teams_change': teams_change,
            'members_change': members_change,
            'projects_change': projects_change,
            'availability_change': availability_change,
        },
        'employees': only_me_employee_qs(request).filter(status=1),
        'departments': Department.objects.all(),
        'team_choices': team_choices,  # TEAM_CHOICES for dropdown
    })

@login_required
@require_http_methods(["POST"])
def add_team(request):
    try:
        data = request.POST
        team_name = data.get('team_name')
        team_lead = data.get('team_lead')  # Can be TEAM_CHOICES value or employee ID
        department_id = data.get('department')
        team_members = data.getlist('team_members')

        if not team_name or not team_lead or not department_id:
            return JsonResponse({'success': False, 'message': 'Team name, leader, and department are required'})

        # Handle team_lead - can be TEAM_CHOICES value (string) or employee ID (integer)
        team_lead_id = None
        try:
            # Try to convert to integer - if it works, it's an employee ID
            team_lead_id = int(team_lead)
            # Verify the employee exists
            employee = Employees.objects.filter(id=team_lead_id).first()
            if not employee:
                return JsonResponse({'success': False, 'message': f'Employee with ID {team_lead_id} not found'})
        except (ValueError, TypeError):
            # It's a string (TEAM_CHOICES value like "Sir Faisal")
            team_lead_name = str(team_lead).strip()

            # Find employee by matching the team_lead name
            # First, try to find by employee's team field matching TEAM_CHOICES
            employee = Employees.objects.filter(
                team=team_lead_name,
                status=1
            ).first()

            # If not found, try to find by name matching
            if not employee:
                # Try matching firstname or full name
                employee = Employees.objects.filter(
                    Q(firstname__icontains=team_lead_name.replace('Sir', '').strip()) |
                    Q(firstname__icontains=team_lead_name) |
                    Q(lastname__icontains=team_lead_name.replace('Sir', '').strip())
                ).filter(status=1).first()

            if not employee:
                return JsonResponse({
                    'success': False,
                    'message': f'No employee found matching team lead: {team_lead_name}'
                })

            team_lead_id = employee.id

        # Non-superusers can only create teams they lead themselves
        if not request.user.is_superuser:
            me = get_current_employee(request)
            if me.id != team_lead_id:
                return JsonResponse({'success': False, 'message': 'Not allowed'}, status=403)

        # Check if team with this name already exists
        if Team.objects.filter(name=team_name).exists():
            return JsonResponse({
                'success': False,
                'message': f'A team with the name "{team_name}" already exists. Please choose a different name.'
            })

        team = Team.objects.create(name=team_name, leader_id=team_lead_id, department_id=department_id)

        # Sync team lead to ensure the employee's team field is set
        if employee.team != team_lead:
            employee.team = team_lead if isinstance(team_lead, str) else employee.team
            employee.save()

        for member_id in team_members:
            TeamMember.objects.create(team=team, employee_id=member_id)

        return JsonResponse({'success': True, 'message': 'Team created successfully', 'team_id': team.id})
    except IntegrityError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Integrity error creating team: {str(e)}', exc_info=True)
        # Check if it's a unique constraint on name
        if 'name' in str(e).lower() or 'UNIQUE constraint' in str(e):
            return JsonResponse({
                'success': False,
                'message': f'A team with the name "{team_name}" already exists. Please choose a different name.'
            })
        return JsonResponse({
            'success': False,
            'message': f'Error creating team: A team with this name or configuration already exists.'
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error creating team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error creating team: {str(e)}'})

@login_required
def team_details(request, team_id):
    try:
        base_qs = Team.objects.select_related('leader', 'department').prefetch_related('members__employee', 'projects')
        if request.user.is_superuser:
            team = get_object_or_404(base_qs, id=team_id)
        else:
            me = get_current_employee(request)
            team = get_object_or_404(base_qs.filter(Q(leader=me) | Q(members__employee=me, members__is_active=True)).distinct(), id=team_id)

        # Get the team lead's TEAM_CHOICES value for the dropdown
        team_lead_name = None
        if team.leader:
            # First, check if the leader's team field matches a TEAM_CHOICES value
            if team.leader.team and team.leader.team in [choice[0] for choice in Employees.TEAM_CHOICES]:
                team_lead_name = team.leader.team
            else:
                # Try to match by name - check if leader's name contains any TEAM_CHOICES name
                leader_name = f"{team.leader.firstname} {team.leader.lastname or ''}".strip().lower()
                for choice_value, choice_display in Employees.TEAM_CHOICES:
                    # Remove "Sir" and spaces for matching
                    choice_name = choice_value.replace('Sir', '').strip().lower()
                    if choice_name in leader_name or leader_name in choice_name:
                        team_lead_name = choice_value
                        break
                    # Also check if firstname matches
                    if team.leader.firstname and choice_name in team.leader.firstname.lower():
                        team_lead_name = choice_value
                        break

        team_data = {
            'id': team.id,
            'name': team.name,
            'status': team.status,
            'leader': {
                'id': team.leader.id if team.leader else None,
                'name': f"{team.leader.firstname} {team.leader.lastname or ''}" if team.leader else 'No Leader',
                'initials': f"{team.leader.firstname[0]}{team.leader.lastname[0] if team.leader and team.leader.lastname else ''}".upper() if team.leader else 'NL',
                'team_lead_name': team_lead_name,  # TEAM_CHOICES value for dropdown
            },
            'department_id': team.department.id if team.department else None,
            'members_count': team.members_count,
            'projects_count': team.projects_count,
            'capacity': team.capacity,
            'members': [],
            'projects': []
        }

        for member in team.members.filter(is_active=True):
            e = member.employee
            team_data['members'].append({
                'id': e.id,
                'name': f"{e.firstname} {e.lastname or ''}",
                'initials': f"{e.firstname[0]}{e.lastname[0] if e.lastname else ''}".upper(),
                'role': member.role or e.job_title or 'Team Member'
            })

        for project in team.projects.all():
            team_data['projects'].append({
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'progress': project.progress,
                'due_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else 'N/A'
            })

        return JsonResponse({'success': True, 'team': team_data})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error retrieving team details: {str(e)}'})

@login_required
def team_members_attendance(request, team_id):
    """
    Get attendance data for all members of a specific team for today
    """
    try:
        today = timezone.now().date()

        # Get team
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Get all active team members
        team_members = TeamMember.objects.filter(team=team, is_active=True).select_related('employee')

        # Get employee IDs
        employee_ids = [tm.employee_id for tm in team_members]

        # Get today's attendance for all team members
        attendance_records = Attendance.objects.filter(
            employee_id__in=employee_ids,
            date=today
        ).select_related('employee')

        # Create attendance map
        attendance_map = {}
        for att in attendance_records:
            attendance_map[att.employee_id] = {
                'status': att.status,
                'status_display': att.get_status_display(),
                'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else None,
                'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else None,
                'is_present': att.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'weekend']
            }

        # Build response with all team members and their attendance
        members_data = []
        for tm in team_members:
            emp = tm.employee
            att_data = attendance_map.get(emp.id, {
                'status': 'absent',
                'status_display': 'Absent',
                'check_in': None,
                'check_out': None,
                'is_present': False
            })

            members_data.append({
                'id': emp.id,
                'name': f"{emp.firstname} {emp.lastname or ''}",
                'attendance': att_data
            })

        return JsonResponse({
            'success': True,
            'team_id': team_id,
            'date': today.strftime('%Y-%m-%d'),
            'members': members_data
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error getting team members attendance: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error getting attendance: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def update_team(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        team_name = data.get('team_name')
        team_lead = data.get('team_lead')
        department = data.get('department')
        status = data.get('status')

        if not team_id:
            return JsonResponse({'success': False, 'message': 'Team ID is required'})

        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Update team name
        if team_name:
            team.name = team_name

        # Update team lead - handle both ID and TEAM_CHOICES value
        if team_lead:
            # Check if team_lead is a TEAM_CHOICES value (string) or an employee ID (integer)
            try:
                # Try to convert to integer - if it works, it's an ID
                team_lead_id = int(team_lead)
                # Verify the employee exists
                employee = Employees.objects.filter(id=team_lead_id).first()
                if not employee:
                    return JsonResponse({'success': False, 'message': f'Employee with ID {team_lead_id} not found'})
                team.leader_id = team_lead_id
            except (ValueError, TypeError):
                # It's a string (TEAM_CHOICES value like "Sir Faisal")
                # Find employee by matching the team_lead name
                team_lead_name = str(team_lead).strip()

                # First, try to find by employee's team field matching TEAM_CHOICES
                employee = Employees.objects.filter(
                    team=team_lead_name,
                    status=1
                ).first()

                # If not found, try to find by name matching
                if not employee:
                    # Try matching firstname or full name
                    employee = Employees.objects.filter(
                        Q(firstname__icontains=team_lead_name.replace('Sir', '').strip()) |
                        Q(firstname__icontains=team_lead_name) |
                        Q(lastname__icontains=team_lead_name.replace('Sir', '').strip())
                    ).filter(status=1).first()

                if not employee:
                    return JsonResponse({
                        'success': False,
                        'message': f'No employee found matching team lead: {team_lead_name}'
                    })

                team.leader_id = employee.id

                # Sync the employee's team field to the TEAM_CHOICES value
                if employee.team != team_lead_name:
                    employee.team = team_lead_name
                    employee.save()

        # Update department
        if department:
            try:
                department_id = int(department)
                team.department_id = department_id
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'Invalid department ID'})

        # Update status
        if status in dict(Team.STATUS_CHOICES).keys():
            team.status = status

        team.save()
        return JsonResponse({'success': True, 'message': 'Team updated successfully'})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error updating team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error updating team: {str(e)}'})

@login_required
@require_http_methods(["POST"])
def add_team_members(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        member_ids = data.get('member_ids', [])

        # Validate inputs
        if not team_id:
            return JsonResponse({'success': False, 'message': 'Team ID is required'})

        if not member_ids or len(member_ids) == 0:
            return JsonResponse({'success': False, 'message': 'At least one member must be selected'})

        # Convert to integers
        try:
            team_id = int(team_id)
            member_ids = [int(mid) for mid in member_ids if mid]
        except (ValueError, TypeError) as e:
            return JsonResponse({'success': False, 'message': f'Invalid ID format: {str(e)}'})

        # Get team with permission check
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Add members
        added_count = 0
        skipped_count = 0
        errors = []

        for member_id in member_ids:
            try:
                # Check if employee exists
                employee = Employees.objects.filter(id=member_id).first()
                if not employee:
                    errors.append(f'Employee with ID {member_id} not found')
                    continue

                # Use get_or_create to handle existing members
                team_member, created = TeamMember.objects.get_or_create(
                    team=team,
                    employee_id=member_id,
                    defaults={'is_active': True}
                )

                # If member already exists but is inactive, reactivate them
                if not created:
                    if team_member.is_active:
                        skipped_count += 1
                        continue  # Already an active member
                    else:
                        team_member.is_active = True
                        team_member.save()
                        added_count += 1
                else:
                    added_count += 1
            except IntegrityError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Integrity error adding member {member_id}: {str(e)}')
                errors.append(f'Member {member_id} could not be added due to constraint violation')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error adding member {member_id}: {str(e)}')
                errors.append(f'Error adding member {member_id}: {str(e)}')

        # Build response message
        if errors:
            message = f'{added_count} member(s) added. {len(errors)} error(s) occurred.'
            if skipped_count > 0:
                message += f' {skipped_count} member(s) already in team.'
        else:
            if skipped_count > 0:
                message = f'{added_count} member(s) added. {skipped_count} member(s) already in team.'
            else:
                message = f'{added_count} member(s) added to team successfully'

        response_data = {
            'success': True if added_count > 0 or skipped_count > 0 else False,
            'message': message,
            'added_count': added_count,
            'skipped_count': skipped_count
        }

        if errors:
            response_data['errors'] = errors

        return JsonResponse(response_data)
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'}, status=404)
    except json.JSONDecodeError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'JSON decode error in add_team_members: {str(e)}')
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error adding members to team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error adding members to team: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_team(request, team_id):
    try:
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)
        name = team.name
        team.delete()
        return JsonResponse({'success': True, 'message': f'Team "{name}" deleted successfully'})
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'}, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error deleting team: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error deleting team: {str(e)}'}, status=500)

@login_required
@require_http_methods(["POST"])
def remove_team_member(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id'); member_id = data.get('member_id')

        base_qs = TeamMember.objects.all() if request.user.is_superuser else TeamMember.objects.filter(
            Q(team__leader=get_current_employee(request)) | Q(team__members__employee=get_current_employee(request), team__members__is_active=True)
        ).distinct()
        team_member = get_object_or_404(base_qs, team_id=team_id, employee_id=member_id)
        team_member.delete()
        return JsonResponse({'success': True, 'message': 'Member removed from team successfully'})
    except TeamMember.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team member not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error removing member from team: {str(e)}'})

@login_required
def available_employees(request):
    try:
        # Get team_id from query parameter (optional - to allow re-adding to current team)
        team_id = request.GET.get('team_id')

        # Get all employees who are active team members in OTHER teams
        if team_id:
            # Exclude members from other teams, but allow re-adding to current team
            team_members = TeamMember.objects.filter(
                is_active=True
            ).exclude(team_id=team_id).values_list('employee_id', flat=True)
        else:
            # Exclude all team members if no team_id provided
            team_members = TeamMember.objects.filter(is_active=True).values_list('employee_id', flat=True)

        base_emps = only_me_employee_qs(request).filter(status=1)
        available_employees = base_emps.exclude(id__in=team_members)

        employees_data = [{'id': e.id, 'name': f"{e.firstname} {e.lastname or ''}", 'role': e.job_title or 'Employee'} for e in available_employees]
        return JsonResponse({'success': True, 'employees': employees_data})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error retrieving available employees: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error retrieving available employees: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def add_project(request):
    try:
        data = json.loads(request.body)
        team_id = data.get('team_id')
        name = data.get('name')
        description = data.get('description', '')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        status = data.get('status', 'active')
        progress = data.get('progress', 0)

        if not team_id or not name:
            return JsonResponse({'success': False, 'message': 'Team and project name are required'})

        try:
            team = Team.objects.get(id=int(team_id))
        except (Team.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid team'}, status=400)

        # Parse dates if provided
        from datetime import datetime
        start = None
        end = None
        try:
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        try:
            progress_val = int(progress)
        except (ValueError, TypeError):
            progress_val = 0

        progress_val = max(0, min(100, progress_val))

        project = Project.objects.create(
            team=team,
            name=name,
            description=description,
            start_date=start or timezone.now().date(),
            end_date=end or timezone.now().date(),
            status=status if status in dict(Project.STATUS_CHOICES).keys() else 'active',
            progress=progress_val,
        )

        return JsonResponse({'success': True, 'message': 'Project created successfully', 'project_id': project.id})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error creating project: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error creating project: {str(e)}'}, status=500)

@login_required
def team_members_attendance(request, team_id):
    """
    Get attendance data for all members of a specific team for today
    """
    try:
        from django.utils import timezone
        today = timezone.now().date()

        # Get team
        base_qs = Team.objects.all() if request.user.is_superuser else Team.objects.filter(
            Q(leader=get_current_employee(request)) | Q(members__employee=get_current_employee(request), members__is_active=True)
        ).distinct()
        team = get_object_or_404(base_qs, id=team_id)

        # Get all active team members
        team_members = TeamMember.objects.filter(team=team, is_active=True).select_related('employee')

        # Get employee IDs
        employee_ids = [tm.employee_id for tm in team_members]

        # Get today's attendance for all team members
        attendance_records = Attendance.objects.filter(
            employee_id__in=employee_ids,
            date=today
        ).select_related('employee')

        # Create attendance map
        attendance_map = {}
        for att in attendance_records:
            attendance_map[att.employee_id] = {
                'status': att.status,
                'status_display': att.get_status_display(),
                'check_in': att.check_in_time.strftime('%H:%M') if att.check_in_time else None,
                'check_out': att.check_out_time.strftime('%H:%M') if att.check_out_time else None,
                'is_present': att.status in ['present', 'late', 'early-in', 'early-out', 'overtime', 'weekend']
            }

        # Build response with all team members and their attendance
        members_data = []
        for tm in team_members:
            emp = tm.employee
            att_data = attendance_map.get(emp.id, {
                'status': 'absent',
                'status_display': 'Absent',
                'check_in': None,
                'check_out': None,
                'is_present': False
            })

            members_data.append({
                'id': emp.id,
                'name': f"{emp.firstname} {emp.lastname or ''}",
                'attendance': att_data
            })

        return JsonResponse({
            'success': True,
            'team_id': team_id,
            'date': today.strftime('%Y-%m-%d'),
            'members': members_data
        })
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Team not found'})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error getting team members attendance: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': f'Error getting attendance: {str(e)}'})

@login_required
def employee_details(request, employee_id):
    try:
        employee = get_object_or_404(only_me_employee_qs(request), id=employee_id)
        employee_data = {
            'id': employee.id,
            'name': f"{employee.firstname} {employee.lastname or ''}",
            'email': employee.email or 'N/A',
            'phone': getattr(employee, 'phone', None) or 'N/A',
            'department': employee.department.name if employee.department else 'N/A',
            'position': employee.job_title or 'N/A',
            'join_date': employee.hire_date.strftime('%Y-%m-%d') if getattr(employee, 'hire_date', None) else 'N/A',
            # demo metrics
            'attendance_rate': 95, 'leaves_taken': 5, 'performance_rating': 4.2,
            'attendance_records': [
                {'date': '2025-10-01', 'status': 'Present', 'check_in': '09:00', 'check_out': '17:00'},
                {'date': '2025-10-02', 'status': 'Present', 'check_in': '08:45', 'check_out': '17:15'},
            ]
        }
        return JsonResponse({'success': True, 'member': employee_data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error getting employee details: {str(e)}'})
