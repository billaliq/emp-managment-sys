"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/device/events/$', consumers.DeviceEventConsumer.as_asgi()),
    re_path(r'ws/attendance/live/$', consumers.AttendanceLiveConsumer.as_asgi()),
]

