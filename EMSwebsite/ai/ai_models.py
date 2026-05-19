"""
In-memory data models used by BFS and A* algorithms.
These are lightweight dataclasses — NOT Django ORM models.
The service layer (task_assignment_service.py) converts between
Django Employees/AssignmentTask and these objects.
"""


class AIEmployee:
    def __init__(self, emp_id, name, skills, max_workload=3):
        self.emp_id = emp_id
        self.name = name
        self.skills = set(skills)
        self.max_workload = max_workload
        self.current_workload = 0

    def is_available(self):
        return self.current_workload < self.max_workload

    def skill_match_score(self, task):
        """Returns fraction of task required skills this employee covers (0.0–1.0)."""
        if not task.required_skills:
            return 1.0
        matched = self.skills & task.required_skills
        return len(matched) / len(task.required_skills)

    def __repr__(self):
        return (f"AIEmployee(id={self.emp_id}, name={self.name}, "
                f"skills={self.skills}, workload={self.current_workload}/{self.max_workload})")


class AITask:
    def __init__(self, task_id, title, required_skills, priority=1):
        self.task_id = task_id
        self.title = title
        self.required_skills = set(required_skills)
        self.priority = priority
        self.assigned_to = None

    def is_assigned(self):
        return self.assigned_to is not None

    def __repr__(self):
        return (f"AITask(id={self.task_id}, title={self.title}, "
                f"skills={self.required_skills}, priority={self.priority})")


class AssignmentState:
    """Search-space state: which tasks are assigned to which employees."""
    def __init__(self, assignments=None, workloads=None):
        self.assignments = assignments or {}   # {task_id: emp_id}
        self.workloads = workloads or {}       # {emp_id: current_load}

    def copy(self):
        return AssignmentState(
            assignments=dict(self.assignments),
            workloads=dict(self.workloads),
        )

    def assign(self, task_id, emp_id):
        new_state = self.copy()
        new_state.assignments[task_id] = emp_id
        new_state.workloads[emp_id] = new_state.workloads.get(emp_id, 0) + 1
        return new_state

    def is_goal(self, all_task_ids):
        return all(tid in self.assignments for tid in all_task_ids)

    def __repr__(self):
        return f"State(assignments={self.assignments})"
