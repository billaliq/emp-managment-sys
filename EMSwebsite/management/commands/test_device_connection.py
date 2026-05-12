"""
Management command to test ZK device connection
Helps diagnose connection issues and verify credentials

Usage:
    python manage.py test_device_connection --ip 36.50.12.191 --port 1752
    python manage.py test_device_connection --ip 36.50.12.191 --port 1752 --password 12345
    python manage.py test_device_connection --device-id 1
"""
from django.core.management.base import BaseCommand
from EMSwebsite.models import ZKDevice
from EMSwebsite.device_utils import ZKDeviceManager

# Try to import ZK library
try:
    from zk import ZK
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False
    ZK = None


class Command(BaseCommand):
    help = 'Test connection to ZK device and verify credentials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--device-id',
            type=int,
            help='Test connection for device by ID (from admin panel)',
        )
        parser.add_argument(
            '--ip',
            type=str,
            help='Device IP address (for direct test)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=4370,
            help='Device port (default: 4370)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='',
            help='Device admin password (if required)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=5,
            help='Connection timeout in seconds (default: 5)',
        )

    def handle(self, *args, **options):
        if not ZK_AVAILABLE:
            self.stdout.write(
                self.style.ERROR('ZK library not installed. Install with: pip install pyzk')
            )
            return

        device_id = options.get('device_id')
        ip = options.get('ip')
        port = options.get('port', 4370)
        password = options.get('password', '')
        timeout = options.get('timeout', 5)

        if device_id:
            # Test device from database
            try:
                device = ZKDevice.objects.get(id=device_id)
                self.stdout.write(self.style.SUCCESS(f'\nTesting device: {device.name}'))
                self.stdout.write(f'IP: {device.ip_address}:{device.port}')
                if device.password:
                    self.stdout.write(f'Password: {"*" * len(device.password)} (configured)')
                else:
                    self.stdout.write('Password: Not set')

                manager = ZKDeviceManager(device)
                success, message, conn = manager.connect()

                if success:
                    self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Connection successful!'))
                    self.stdout.write(f'Device Name: {device.device_name or "N/A"}')
                    self.stdout.write(f'Serial Number: {device.serial_number or "N/A"}')

                    # Test getting users
                    try:
                        users = manager.get_users()
                        self.stdout.write(f'Users on device: {len(users)}')
                        if users:
                            self.stdout.write('Sample users:')
                            for user in users[:5]:
                                self.stdout.write(f'  - ID: {user.user_id}, Name: {user.name}')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Could not fetch users: {str(e)}'))

                    manager.disconnect()
                else:
                    self.stdout.write(self.style.ERROR(f'\n[ERROR] Connection failed: {message}'))
                    self.stdout.write(self.style.WARNING('\nTroubleshooting tips:'))
                    self.stdout.write('1. Check if device IP and port are correct')
                    self.stdout.write('2. Verify device is on the same network')
                    self.stdout.write('3. Check firewall settings')
                    self.stdout.write('4. Try with password if device requires it')
                    self.stdout.write('5. Check device admin panel for connection settings')

            except ZKDevice.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Device with ID {device_id} not found'))
                return
        elif ip:
            # Direct connection test
            self.stdout.write(self.style.SUCCESS(f'\nTesting direct connection to {ip}:{port}'))

            if password:
                self.stdout.write(f'Using password: {"*" * len(password)}')
            else:
                self.stdout.write('No password (trying without credentials)')

            try:
                # Try without password first
                zk = ZK(ip, port=port, timeout=timeout, password=0)
                conn = zk.connect()

                if conn:
                    self.stdout.write(self.style.SUCCESS('[SUCCESS] Connection successful without password!'))

                    try:
                        device_name = conn.get_device_name()
                        self.stdout.write(f'Device Name: {device_name}')
                    except:
                        pass

                    try:
                        serial = conn.get_serialnumber()
                        self.stdout.write(f'Serial Number: {serial}')
                    except:
                        pass

                    try:
                        users = conn.get_users()
                        self.stdout.write(f'Users on device: {len(users)}')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Could not fetch users: {str(e)}'))
                        if password:
                            self.stdout.write(self.style.WARNING('Try with password if device requires admin access'))

                    conn.enable_device()
                    conn.disconnect()
                else:
                    self.stdout.write(self.style.ERROR('[ERROR] Connection failed'))
                    if not password:
                        self.stdout.write(self.style.WARNING('Try with --password option if device requires credentials'))

            except Exception as e:
                error_msg = str(e)
                self.stdout.write(self.style.ERROR(f'[ERROR] Connection error: {error_msg}'))

                if 'timeout' in error_msg.lower():
                    self.stdout.write(self.style.WARNING('\nPossible issues:'))
                    self.stdout.write('- Device is not reachable on network')
                    self.stdout.write('- Firewall blocking connection')
                    self.stdout.write('- Wrong IP address or port')
                elif 'password' in error_msg.lower() or 'authentication' in error_msg.lower():
                    self.stdout.write(self.style.WARNING('\nDevice may require password. Try:'))
                    self.stdout.write(f'python manage.py test_device_connection --ip {ip} --port {port} --password YOUR_PASSWORD')
                else:
                    self.stdout.write(self.style.WARNING('\nTroubleshooting:'))
                    self.stdout.write('1. Verify IP address and port')
                    self.stdout.write('2. Check network connectivity')
                    self.stdout.write('3. Try with password if device requires it')
        else:
            self.stdout.write(self.style.ERROR('Please provide either --device-id or --ip'))
            self.stdout.write('\nExamples:')
            self.stdout.write('  python manage.py test_device_connection --device-id 1')
            self.stdout.write('  python manage.py test_device_connection --ip 36.50.12.191 --port 1752')
            self.stdout.write('  python manage.py test_device_connection --ip 36.50.12.191 --port 1752 --password 12345')

