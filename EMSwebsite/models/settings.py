from django.db import models
from django.utils import timezone


class SystemSettings(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"), ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("ar", "Arabic"), ("ur", "Urdu")
    ]
    DATE_FORMAT_CHOICES = [("mm/dd/yyyy", "MM/DD/YYYY"), ("dd/mm/yyyy", "DD/MM/YYYY"), ("yyyy-mm-dd", "YYYY-MM-DD")]
    TIME_FORMAT_CHOICES = [("12h", "12-hour"), ("24h", "24-hour")]
    THEME_CHOICES = [
        ("default", "Default"),
        ("indigo", "Indigo"),
        ("emerald", "Emerald"),
        ("crimson", "Crimson"),
    ]
    FONT_SIZE_CHOICES = [("small", "Small"), ("medium", "Medium"), ("large", "Large")]
    SIDEBAR_WIDTH_CHOICES = [("compact", "Compact"), ("normal", "Normal"), ("wide", "Wide")]

    TIMEZONE = models.CharField(max_length=20, default="utc+0")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
    date_format = models.CharField(max_length=12, choices=DATE_FORMAT_CHOICES, default="yyyy-mm-dd")
    time_format = models.CharField(max_length=3, choices=TIME_FORMAT_CHOICES, default="24h")

    dark_mode = models.BooleanField(default=False)
    theme = models.CharField(max_length=32, choices=THEME_CHOICES, default="default")
    font_size = models.CharField(max_length=8, choices=FONT_SIZE_CHOICES, default="medium")
    sidebar_width = models.CharField(max_length=8, choices=SIDEBAR_WIDTH_CHOICES, default="normal")

    notification_settings = models.JSONField(default=dict, blank=True, help_text="Email, push, and in-app notification preferences")
    security_settings = models.JSONField(default=dict, blank=True, help_text="Security preferences including 2FA, session management")
    privacy_settings = models.JSONField(default=dict, blank=True, help_text="Privacy preferences and data sharing settings")
    backup_settings = models.JSONField(default=dict, blank=True, help_text="Backup and restore configuration")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "System Settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def get_notification_setting(self, key, default=False):
        return self.notification_settings.get(key, default)

    def set_notification_setting(self, key, value):
        if not self.notification_settings:
            self.notification_settings = {}
        self.notification_settings[key] = value
        self.save()

    def get_security_setting(self, key, default=False):
        return self.security_settings.get(key, default)

    def set_security_setting(self, key, value):
        if not self.security_settings:
            self.security_settings = {}
        self.security_settings[key] = value
        self.save()

    def get_privacy_setting(self, key, default=False):
        return self.privacy_settings.get(key, default)

    def set_privacy_setting(self, key, value):
        if not self.privacy_settings:
            self.privacy_settings = {}
        self.privacy_settings[key] = value
        self.save()
