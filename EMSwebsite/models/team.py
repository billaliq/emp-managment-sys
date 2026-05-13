from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Team(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    leader = models.ForeignKey('Employees', on_delete=models.SET_NULL, null=True, related_name='led_teams')
    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='teams')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def members_count(self):
        return self.members.count()

    @property
    def projects_count(self):
        return self.projects.count()

    @property
    def capacity(self):
        if self.members_count == 0:
            return 0
        return self.members_count

    class Meta:
        ordering = ['name']


class TeamMember(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField(max_length=100, blank=True, null=True)
    joined_at = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('team', 'employee')
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.employee} in {self.team}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    start_date = models.DateField()
    end_date = models.DateField()
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
