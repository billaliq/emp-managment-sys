"""
BFS for Employee-Task Assignment.
Explores all assignment combinations level by level.
Returns the FIRST valid complete assignment found (not necessarily optimal).
"""

from collections import deque
from .ai_models import AssignmentState


def bfs_assign(employees, tasks):
    """
    employees : dict {emp_id: AIEmployee}
    tasks     : dict {task_id: AITask}
    Returns   : (dict {task_id: emp_id} or None, nodes_explored)
    """
    task_ids = list(tasks.keys())
    emp_ids = list(employees.keys())
    total_tasks = len(task_ids)

    initial_state = AssignmentState(
        assignments={},
        workloads={eid: 0 for eid in emp_ids}
    )

    queue = deque()
    queue.append((initial_state, 0))

    nodes_explored = 0
    visited = set()

    while queue:
        state, task_index = queue.popleft()
        nodes_explored += 1

        if task_index == total_tasks:
            return state.assignments, nodes_explored

        task_id = task_ids[task_index]
        task = tasks[task_id]

        for emp_id in emp_ids:
            emp = employees[emp_id]

            if state.workloads.get(emp_id, 0) >= emp.max_workload:
                continue

            if emp.skill_match_score(task) == 0.0:
                continue

            new_state = state.assign(task_id, emp_id)
            state_key = tuple(sorted(new_state.assignments.items()))
            if state_key in visited:
                continue
            visited.add(state_key)

            queue.append((new_state, task_index + 1))

    return None, nodes_explored
