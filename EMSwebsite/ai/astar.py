"""
A* Search for Optimal Employee-Task Assignment.

f(n) = g(n) + h(n)
  g(n) = sum of (1 - skill_match_score) per assignment so far
  h(n) = number of tasks still unassigned  (admissible, consistent)

A* finds the OPTIMAL (best skill-matched) assignment.
"""

import heapq
from .ai_models import AssignmentState


class AStarNode:
    def __init__(self, state, task_index, g_cost, parent=None):
        self.state = state
        self.task_index = task_index
        self.g_cost = g_cost
        self.h_cost = 0
        self.f_cost = 0
        self.parent = parent

    def __lt__(self, other):
        return self.f_cost < other.f_cost


def _heuristic(task_index, total_tasks):
    return total_tasks - task_index


def astar_assign(employees, tasks):
    """
    employees : dict {emp_id: AIEmployee}
    tasks     : dict {task_id: AITask}
    Returns   : (dict {task_id: emp_id} or None, nodes_explored, total_cost)
    """
    task_ids = list(tasks.keys())
    emp_ids = list(employees.keys())
    total_tasks = len(task_ids)

    initial_state = AssignmentState(
        assignments={},
        workloads={eid: 0 for eid in emp_ids}
    )

    start = AStarNode(state=initial_state, task_index=0, g_cost=0.0)
    start.h_cost = _heuristic(0, total_tasks)
    start.f_cost = start.g_cost + start.h_cost

    open_heap = []
    heapq.heappush(open_heap, start)

    visited = set()
    nodes_explored = 0

    while open_heap:
        node = heapq.heappop(open_heap)
        nodes_explored += 1

        if node.task_index == total_tasks:
            return node.state.assignments, nodes_explored, round(node.g_cost, 4)

        task_id = task_ids[node.task_index]
        task = tasks[task_id]

        state_key = (node.task_index, tuple(sorted(node.state.assignments.items())))
        if state_key in visited:
            continue
        visited.add(state_key)

        for emp_id in emp_ids:
            emp = employees[emp_id]

            if node.state.workloads.get(emp_id, 0) >= emp.max_workload:
                continue

            skill_score = emp.skill_match_score(task)
            if skill_score == 0.0:
                continue

            new_g = node.g_cost + (1.0 - skill_score)
            new_state = node.state.assign(task_id, emp_id)
            new_index = node.task_index + 1

            child = AStarNode(state=new_state, task_index=new_index, g_cost=new_g, parent=node)
            child.h_cost = _heuristic(new_index, total_tasks)
            child.f_cost = new_g + child.h_cost
            heapq.heappush(open_heap, child)

    return None, nodes_explored, 0
