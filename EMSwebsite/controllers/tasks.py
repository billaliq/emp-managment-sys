import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from EMSwebsite.models import AssignmentTask, Employees
from EMSwebsite.services.task_assignment_service import run_ai_assignment, apply_astar_assignments
from .helpers import hr_or_admin_required

logger = logging.getLogger(__name__)


@login_required
@hr_or_admin_required
def task_list(request):
    tasks = AssignmentTask.objects.select_related('assigned_to', 'created_by').order_by('-priority', 'created_at')
    employees = Employees.objects.filter(status=1).order_by('firstname')

    stats = {
        'total': tasks.count(),
        'pending': tasks.filter(status='pending').count(),
        'assigned': tasks.filter(status='assigned').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'completed': tasks.filter(status='completed').count(),
    }

    return render(request, 'pages/tasks.html', {
        'tasks': tasks,
        'employees': employees,
        'stats': stats,
        'priority_choices': AssignmentTask.PRIORITY_CHOICES,
        'status_choices': AssignmentTask.STATUS_CHOICES,
    })


@login_required
@hr_or_admin_required
@require_POST
def task_create(request):
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    priority = int(request.POST.get('priority', 2))
    deadline = request.POST.get('deadline') or None
    skills_raw = request.POST.get('required_skills', '').strip()

    if not title:
        messages.error(request, 'Task title is required.')
        return redirect('task_list')

    required_skills = [s.strip() for s in skills_raw.split(',') if s.strip()]

    AssignmentTask.objects.create(
        title=title,
        description=description,
        priority=priority,
        deadline=deadline,
        required_skills=required_skills,
        created_by=request.user,
        status='pending',
    )
    messages.success(request, f'Task "{title}" created successfully.')
    return redirect('task_list')


@login_required
@hr_or_admin_required
@require_POST
def task_delete(request, task_id):
    task = get_object_or_404(AssignmentTask, pk=task_id)
    task.delete()
    messages.success(request, f'Task "{task.title}" deleted.')
    return redirect('task_list')


@login_required
@hr_or_admin_required
@require_POST
def task_update_status(request, task_id):
    task = get_object_or_404(AssignmentTask, pk=task_id)
    new_status = request.POST.get('status')
    if new_status in dict(AssignmentTask.STATUS_CHOICES):
        task.status = new_status
        task.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Task status updated to "{new_status}".')
    return redirect('task_list')


@login_required
@hr_or_admin_required
def run_assignment(request):
    """
    GET  → show the pre-run confirmation page (task + employee summary).
    POST → run BFS + A*, persist A* result, redirect to results page.
    """
    pending_tasks = AssignmentTask.objects.filter(status='pending')
    active_employees = Employees.objects.filter(status=1)

    if request.method == 'POST':
        result = run_ai_assignment(active_employees, pending_tasks)

        if result['errors'] and not result['astar_assignments']:
            for err in result['errors']:
                messages.error(request, err)
            return redirect('task_list')

        # Persist the A* result
        updated = apply_astar_assignments(
            result['astar_assignments'],
            active_employees,
            pending_tasks,
        )

        request.session['assignment_result'] = _serialise_result(
            result, updated, active_employees, pending_tasks
        )
        return redirect('assignment_result')

    return render(request, 'pages/run_assignment.html', {
        'pending_tasks': pending_tasks,
        'active_employees': active_employees,
    })


@login_required
@hr_or_admin_required
def assignment_result(request):
    result = request.session.pop('assignment_result', None)
    if not result:
        messages.warning(request, 'No assignment result found. Run the AI assignment first.')
        return redirect('task_list')

    return render(request, 'pages/assignment_result.html', {'result': result})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _serialise_result(result, updated, employee_qs, task_qs):
    """Convert the service result into a JSON-serialisable dict for the session."""
    emp_map = {str(e.pk): f"{e.firstname} {e.lastname or ''}".strip() for e in employee_qs}
    task_map = {str(t.pk): t.title for t in task_qs}

    def enrich(assignments):
        if not assignments:
            return []
        rows = []
        ai_emps = result['ai_employees']
        ai_tasks = result['ai_tasks']
        for tid, eid in assignments.items():
            emp_obj = ai_emps.get(eid)
            task_obj = ai_tasks.get(tid)
            score = emp_obj.skill_match_score(task_obj) * 100 if emp_obj and task_obj else 0
            rows.append({
                'task_id': tid,
                'task_title': task_map.get(tid, tid),
                'emp_id': eid,
                'emp_name': emp_map.get(eid, eid),
                'skill_match': round(score, 1),
            })
        return rows

    bfs_rows = enrich(result['bfs_assignments'])
    astar_rows = enrich(result['astar_assignments'])

    return {
        'bfs_rows': bfs_rows,
        'astar_rows': astar_rows,
        'comparison': result['comparison'],
        'errors': result['errors'],
        'applied_count': len(updated),
    }
