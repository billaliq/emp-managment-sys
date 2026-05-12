"""
Background service to monitor ZK devices 24/7
Listens for real-time events and broadcasts via WebSocket

Usage:
    python manage.py device_monitor
    python manage.py device_monitor --device-id 1
    python manage.py device_monitor --all-devices
"""
import logging
import time
import asyncio
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from EMSwebsite.models import ZKDevice, AttendanceLog
from EMSwebsite.device_utils import ZKDeviceManager, process_device_event
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor ZK devices 24/7 for real-time events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--device-id',
            type=int,
            help='Monitor specific device by ID',
        )
        parser.add_argument(
            '--all-devices',
            action='store_true',
            help='Monitor all active devices',
        )
        parser.add_argument(
            '--reconnect-delay',
            type=int,
            default=5,
            help='Delay in seconds before reconnecting after error (default: 5)',
        )

    def handle(self, *args, **options):
        device_id = options.get('device_id')
        all_devices = options.get('all_devices', False)
        reconnect_delay = options.get('reconnect_delay', 5)

        if device_id:
            devices = ZKDevice.objects.filter(id=device_id, is_active=True)
        elif all_devices:
            devices = ZKDevice.objects.filter(is_active=True, realtime_enabled=True)
        else:
            # Default: monitor all active devices with realtime enabled
            devices = ZKDevice.objects.filter(is_active=True, realtime_enabled=True)

        if not devices.exists():
            self.stdout.write(
                self.style.WARNING('No active devices found to monitor.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Starting device monitor for {devices.count()} device(s)...')
        )

        # Monitor each device
        for device in devices:
            self.stdout.write(f'Monitoring device: {device.name} ({device.ip_address})')
            self.monitor_device(device, reconnect_delay)

    def monitor_device(self, device, reconnect_delay):
        """Monitor a single device continuously"""
        manager = None
        reconnect_count = 0
        max_reconnect_attempts = 10

        while True:
            try:
                # Connect to device
                manager = ZKDeviceManager(device)
                success, message, conn = manager.connect()

                if not success:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to connect to {device.name}: {message}')
                    )
                    device.status = 'error'
                    device.last_error = message
                    device.save(update_fields=['status', 'last_error'])

                    reconnect_count += 1
                    if reconnect_count >= max_reconnect_attempts:
                        self.stdout.write(
                            self.style.ERROR(f'Max reconnection attempts reached for {device.name}. Stopping.')
                        )
                        break

                    time.sleep(reconnect_delay)
                    continue

                # Reset reconnect count on successful connection
                reconnect_count = 0
                self.stdout.write(
                    self.style.SUCCESS(f'Connected to {device.name}. Listening for events...')
                )

                # Listen for real-time events
                try:
                    for event in manager.get_realtime_logs(callback=self.handle_event):
                        # Event is processed in callback
                        pass
                except Exception as e:
                    logger.error(f"Error in realtime monitoring for {device.name}: {str(e)}")
                    self.stdout.write(
                        self.style.WARNING(f'Realtime monitoring error for {device.name}: {str(e)}')
                    )
                    # Fallback to polling if realtime fails
                    self.poll_device(manager, device)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\nStopping device monitor...'))
                if manager:
                    manager.disconnect()
                break
            except Exception as e:
                logger.error(f"Unexpected error monitoring {device.name}: {str(e)}")
                self.stdout.write(
                    self.style.ERROR(f'Error monitoring {device.name}: {str(e)}')
                )
                if manager:
                    try:
                        manager.disconnect()
                    except:
                        pass

                time.sleep(reconnect_delay)
                reconnect_count += 1
                if reconnect_count >= max_reconnect_attempts:
                    self.stdout.write(
                        self.style.ERROR(f'Max reconnection attempts reached for {device.name}. Stopping.')
                    )
                    break

    def poll_device(self, manager, device):
        """Fallback: Poll device for new attendance records"""
        last_sync = timezone.now()

        while True:
            try:
                # Get new attendance records
                attendance_records = manager.get_attendance()

                for record in attendance_records:
                    # Check if this record is new
                    timestamp = getattr(record, 'timestamp', None)
                    if timestamp and timezone.is_naive(timestamp):
                        import pytz
                        tz = pytz.timezone('Asia/Karachi')
                        timestamp = timezone.make_aware(timestamp, tz)

                    if timestamp and timestamp > last_sync:
                        self.handle_event(device, record)

                last_sync = timezone.now()
                time.sleep(1)  # Poll every second

            except Exception as e:
                logger.error(f"Error polling device {device.name}: {str(e)}")
                time.sleep(5)  # Wait longer on error

    def handle_event(self, device, event_data):
        """Handle device event - save to DB and broadcast via WebSocket"""
        try:
            # Process event and save to database
            log = process_device_event(device, event_data)

            if log:
                # Broadcast via WebSocket
                self.broadcast_event(log)

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Event: {log.user_name} - {log.get_event_type_display()} @ {log.timestamp}'
                    )
                )
        except Exception as e:
            logger.error(f"Error handling event: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def broadcast_event(self, log):
        """Broadcast event to WebSocket clients"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            # Prepare event data
            event_data = {
                'id': log.id,
                'device_id': log.device.id,
                'device_name': log.device.name,
                'user_id': log.user_id,
                'user_name': log.user_name,
                'employee_code': log.employee.code if log.employee else None,
                'employee_name': f"{log.employee.firstname} {log.employee.lastname or ''}".strip() if log.employee else None,
                'event_type': log.event_type,
                'timestamp': log.timestamp.isoformat(),
                'verification_mode': log.verification_mode,
                'is_processed': log.is_processed,
            }

            # Broadcast to device events group
            async_to_sync(channel_layer.group_send)(
                'device_events',
                {
                    'type': 'attendance_log',
                    'data': event_data
                }
            )

            # Broadcast to attendance live group
            async_to_sync(channel_layer.group_send)(
                'attendance_live',
                {
                    'type': 'attendance_event',
                    'data': event_data
                }
            )

        except Exception as e:
            logger.error(f"Error broadcasting event: {str(e)}")

