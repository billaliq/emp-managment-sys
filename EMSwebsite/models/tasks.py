from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class AssignmentTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Normal'),
        (3, 'Medium'),
        (4, 'High'),
        (5, 'Critical'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    required_skills = models.JSONField(
        default=list,
        help_text="List of required skills e.g. ['Python', 'SQL']"
    )
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    assigned_to = models.ForeignKey(
        'Employees',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    deadline = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'created_at']
        verbose_name = "Assignment Task"
        verbose_name_plural = "Assignment Tasks"

    def __str__(self):
        return self.title

    def get_priority_label(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, 'Normal')
