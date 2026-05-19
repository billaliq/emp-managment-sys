"""
Bridge between Django ORM models (Employees, AssignmentTask) and the AI
algorithm's lightweight in-memory objects (AIEmployee, AITask).

Usage:
    from EMSwebsite.services.task_assignment_service import run_ai_assignment

    result = run_ai_assignment(employee_qs, task_qs)
    # result keys: bfs_assignments, astar_assignments, comparison, errors
"""

import time

from EMSwebsite.ai.ai_models import AIEmployee, AITask
from EMSwebsite.ai.bfs import bfs_assign
from EMSwebsite.ai.astar import astar_assign


def _build_ai_employees(employee_qs):
    """Convert Django Employees queryset → {emp_id: AIEmployee}."""
    ai_emps = {}
    for emp in employee_qs:
        skills = emp.skills if isinstance(emp.skills, list) else []
        ai_emps[str(emp.pk)] = AIEmployee(
            emp_id=str(emp.pk),
            name=f"{emp.firstname} {emp.lastname or ''}".strip(),
            skills=skills,
            max_workload=emp.max_task_workload,
        )
    return ai_emps


def _build_ai_tasks(task_qs):
    """Convert Django AssignmentTask queryset → {task_id: AITask}."""
    ai_tasks = {}
    for task in task_qs:
        skills = task.required_skills if isinstance(task.required_skills, list) else []
        ai_tasks[str(task.pk)] = AITask(
            task_id=str(task.pk),
            title=task.title,
            required_skills=skills,
            priority=task.priority,
        )
    return ai_tasks


def _avg_skill_match(assignments, ai_employees, ai_tasks):
    if not assignments:
        return 0.0
    scores = [
        ai_employees[eid].skill_match_score(ai_tasks[tid]) * 100
        for tid, eid in assignments.items()
        if tid in ai_tasks and eid in ai_employees
    ]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def run_ai_assignment(employee_qs, task_qs):
    """
    Run BFS then A* over the given querysets.

    Returns a dict:
        {
          'bfs_assignments':   {task_id_str: emp_id_str} | None,
          'astar_assignments': {task_id_str: emp_id_str} | None,
          'comparison': {
              'bfs_nodes', 'astar_nodes',
              'bfs_time_ms', 'astar_time_ms',
              'bfs_avg_match', 'astar_avg_match',
              'winner',            # 'astar' | 'bfs' | 'tie'
          },
          'errors': []  # list of human-readable problem strings
        }
    """
    errors = []
    ai_employees = _build_ai_employees(employee_qs)
    ai_tasks = _build_ai_tasks(task_qs)

    if not ai_employees:
        errors.append("No active employees with skills found.")
    if not ai_tasks:
        errors.append("No pending tasks to assign.")

    bfs_result = astar_result = None
    bfs_nodes = astar_nodes = 0
    bfs_time = astar_time = 0.0
    astar_cost = 0.0

    if ai_employees and ai_tasks:
        t0 = time.perf_counter()
        bfs_result, bfs_nodes = bfs_assign(dict(ai_employees), dict(ai_tasks))
        bfs_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        astar_result, astar_nodes, astar_cost = astar_assign(dict(ai_employees), dict(ai_tasks))
        astar_time = time.perf_counter() - t0

        if not bfs_result and not astar_result:
            errors.append(
                "Neither BFS nor A* found a valid assignment. "
                "Check that employees have the required skills and workload capacity."
            )

    bfs_match = _avg_skill_match(bfs_result, ai_employees, ai_tasks)
    astar_match = _avg_skill_match(astar_result, ai_employees, ai_tasks)

    if astar_match > bfs_match:
        winner = 'astar'
    elif bfs_match > astar_match:
        winner = 'bfs'
    else:
        winner = 'tie'

    return {
        'bfs_assignments': bfs_result,
        'astar_assignments': astar_result,
        'ai_employees': ai_employees,
        'ai_tasks': ai_tasks,
        'comparison': {
            'bfs_nodes': bfs_nodes,
            'astar_nodes': astar_nodes,
            'bfs_time_ms': round(bfs_time * 1000, 2),
            'astar_time_ms': round(astar_time * 1000, 2),
            'bfs_avg_match': bfs_match,
            'astar_avg_match': astar_match,
            'astar_cost': astar_cost,
            'winner': winner,
        },
        'errors': errors,
    }


def apply_astar_assignments(astar_assignments, employee_qs, task_qs):
    """
    Persist the A* result back to Django: set AssignmentTask.assigned_to
    and update each task's status to 'assigned'.
    Returns list of (task, employee) tuples that were updated.
    """
    from EMSwebsite.models import AssignmentTask, Employees

    updated = []
    for task_id_str, emp_id_str in (astar_assignments or {}).items():
        try:
            task = task_qs.get(pk=int(task_id_str))
            emp = employee_qs.get(pk=int(emp_id_str))
            task.assigned_to = emp
            task.status = 'assigned'
            task.save(update_fields=['assigned_to', 'status', 'updated_at'])
            updated.append((task, emp))
        except Exception:
            continue
    return updated
