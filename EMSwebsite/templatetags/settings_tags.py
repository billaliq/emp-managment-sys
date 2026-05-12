"""
Custom template tags for formatting dates and times according to system settings.
"""
from django import template
from django.utils import timezone
from datetime import datetime, date, time
from EISwebsite.models import SystemSettings

register = template.Library()


def get_system_settings():
    """Get the system settings singleton"""
    try:
        return SystemSettings.objects.first() or SystemSettings.get_solo()
    except Exception:
        return None


@register.filter(name='format_date')
def format_date(value):
    """
    Format a date according to system settings.
    Usage: {{ record.date|format_date }}
    """
    if not value:
        return '--'

    settings = get_system_settings()
    date_format = settings.date_format if settings else 'yyyy-mm-dd'

    # Convert to date if it's a datetime
    if isinstance(value, datetime):
        value = value.date()

    if not isinstance(value, date):
        return str(value)

    # Format based on setting
    if date_format == 'mm/dd/yyyy':
        return value.strftime('%m/%d/%Y')
    elif date_format == 'dd/mm/yyyy':
        return value.strftime('%d/%m/%Y')
    else:  # yyyy-mm-dd (default)
        return value.strftime('%Y-%m-%d')


@register.filter(name='format_time')
def format_time(value):
    """
    Format a time according to system settings.
    Usage: {{ record.check_in_time|format_time }}
    """
    if not value:
        return '--'

    settings = get_system_settings()
    time_format = settings.time_format if settings else '24h'

    # Convert to time if it's a datetime
    if isinstance(value, datetime):
        value = value.time()

    if not isinstance(value, time):
        return str(value)

    # Format based on setting
    if time_format == '12h':
        return value.strftime('%I:%M %p')
    else:  # 24h (default)
        return value.strftime('%H:%M')


@register.filter(name='format_datetime')
def format_datetime(value):
    """
    Format a datetime according to system settings.
    Usage: {{ record.created_at|format_datetime }}
    """
    if not value:
        return '--'

    settings = get_system_settings()
    date_format = settings.date_format if settings else 'yyyy-mm-dd'
    time_format = settings.time_format if settings else '24h'

    if not isinstance(value, datetime):
        # Try to handle date-only
        if isinstance(value, date):
            return format_date(value)
        return str(value)

    # Format date part
    if date_format == 'mm/dd/yyyy':
        date_str = value.strftime('%m/%d/%Y')
    elif date_format == 'dd/mm/yyyy':
        date_str = value.strftime('%d/%m/%Y')
    else:  # yyyy-mm-dd
        date_str = value.strftime('%Y-%m-%d')

    # Format time part
    if time_format == '12h':
        time_str = value.strftime('%I:%M %p')
    else:  # 24h
        time_str = value.strftime('%H:%M')

    return f"{date_str} {time_str}"


@register.simple_tag
def get_date_format():
    """Get the current date format setting"""
    settings = get_system_settings()
    return settings.date_format if settings else 'yyyy-mm-dd'


@register.simple_tag
def get_time_format():
    """Get the current time format setting"""
    settings = get_system_settings()
    return settings.time_format if settings else '24h'


@register.simple_tag
def get_timezone():
    """Get the current timezone setting"""
    settings = get_system_settings()
    return settings.TIMEZONE if settings else 'utc+0'


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''
