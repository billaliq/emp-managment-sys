"""
WebSocket consumers for real-time device events
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class DeviceEventConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time device events"""

    async def connect(self):
        """Handle WebSocket connection"""
        # Check authentication
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        # Join device events group
        self.group_name = 'device_events'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected: {self.scope['user']}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {close_code}")

    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'message': 'alive'
                }))
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")

    async def device_event(self, event):
        """Send device event to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'device_event',
            'data': event['data']
        }))

    async def attendance_log(self, event):
        """Send attendance log to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'attendance_log',
            'data': event['data']
        }))

    async def enrollment_update(self, event):
        """Send enrollment update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'enrollment_update',
            'data': event['data']
        }))


class AttendanceLiveConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for live attendance monitoring"""

    async def connect(self):
        """Handle WebSocket connection"""
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.group_name = 'attendance_live'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"Attendance Live WebSocket connected: {self.scope['user']}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages from WebSocket client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'message': 'alive'
                }))
        except json.JSONDecodeError:
            pass

    async def attendance_event(self, event):
        """Send attendance event to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'attendance_event',
            'data': event['data']
        }))


# Helper function to broadcast events
async def broadcast_device_event(event_type, data):
    """Broadcast device event to all connected clients"""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    if channel_layer:
        await channel_layer.group_send(
            'device_events',
            {
                'type': event_type,
                'data': data
            }
        )


async def broadcast_attendance_event(data):
    """Broadcast attendance event to live monitoring clients"""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    if channel_layer:
        await channel_layer.group_send(
            'attendance_live',
            {
                'type': 'attendance_event',
                'data': data
            }
        )

