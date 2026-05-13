from django.db import models
from django.utils import timezone
from django.conf import settings


class Policy(models.Model):
    """Company policy management"""
    CATEGORY_CHOICES = [
        ('hr', 'HR Policy'),
        ('leave', 'Leave Policy'),
        ('loan', 'Loan Policy'),
        ('code_of_conduct', 'Code of Conduct'),
        ('benefits', 'Benefits'),
        ('attendance', 'Attendance Policy'),
        ('safety', 'Safety Policy'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    effective_date = models.DateField()
    description = models.TextField(blank=True, null=True, help_text="Short description of the policy")
    document = models.FileField(upload_to='policies/', blank=True, null=True, help_text="Policy document (PDF, DOCX, etc.)")
    summary = models.TextField(help_text="AI-extracted or manually entered policy summary")
    key_points = models.JSONField(default=list, blank=True, help_text="List of key points from the policy")
    version = models.CharField(max_length=50, default='1.0', help_text="Policy version number")
    version_notes = models.TextField(blank=True, null=True, help_text="Notes about this version or update")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_policies')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_policies')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-effective_date', '-created_at']
        verbose_name = "Policy"
        verbose_name_plural = "Policies"

    def __str__(self):
        return f"{self.title} (v{self.version})"

    def get_category_display_name(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)


class Complaint(models.Model):
    """Employee complaints and queries"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    employee = models.ForeignKey('Employees', on_delete=models.CASCADE, related_name='complaints')
    title = models.CharField(max_length=200)
    description = models.TextField()
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    related_department = models.CharField(max_length=100, blank=True, null=True, help_text="Department name if not in system")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    response = models.TextField(blank=True, null=True, help_text="HR/Admin response to the complaint")
    responded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='responded_complaints')
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Complaint"
        verbose_name_plural = "Complaints"

    def __str__(self):
        return f"{self.employee} - {self.title} ({self.get_status_display()})"


class AIChatMessage(models.Model):
    """Store AI assistant chat history"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_chat_messages')
    message = models.TextField()
    response = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=[('user', 'User Message'), ('assistant', 'Assistant Response'), ('system', 'System Message')],
        default='user'
    )
    context = models.JSONField(default=dict, blank=True, help_text="Additional context for the conversation")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']
        verbose_name = "AI Chat Message"
        verbose_name_plural = "AI Chat Messages"

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
