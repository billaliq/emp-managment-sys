import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from zk import ZK
    from zk.user import User as ZKUser
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False


class ZKDeviceManager:

    UID_MAX = 65535

    def __init__(self, device):
        self.device = device
        self.zk = None
        self.conn = None

    # ================= CONNECT ================= #

    def connect(self):

        if not ZK_AVAILABLE:
            return False, "pyzk not installed", None

        try:
            self.zk = ZK(
                self.device.ip_address,
                port=self.device.port,
                timeout=self.device.timeout,
                password=self.device.password or 0
            )

            self.conn = self.zk.connect()

            self.device.status = "online"
            self.device.last_connected = timezone.now()
            self.device.save(update_fields=["status", "last_connected"])

            return True, "Connected", self.conn

        except Exception as e:
            self.device.status = "error"
            self.device.last_error = str(e)
            self.device.save(update_fields=["status", "last_error"])
            return False, str(e), None


    def _ensure(self):
        if not self.conn:
            ok, msg, _ = self.connect()
            if not ok:
                raise Exception(msg)

    def disconnect(self):
        try:
            if self.conn:
                self.conn.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from device: {e}")
        finally:
            self.conn = None
            self.zk = None

    # ================= UID (NUMERIC ONLY) ================= #

    def _uid(self, code):
        """
        OLD ZK WAY: employee.code MUST be numeric and used directly as UID
        """

        code = str(code).strip()

        if not code.isdigit():
            raise ValueError("ZK system requires numeric employee codes only")

        uid = int(code)

        if uid <= 0 or uid > self.UID_MAX:
            raise ValueError(f"UID must be between 1 and {self.UID_MAX}")

        return uid

    # ================= PUSH USER ================= #

    def push_user(self, employee):

        try:
            self._ensure()

            # STRICT NUMERIC
            uid = self._uid(employee.code)
            user_id = str(uid)

            name = employee.firstname.strip() if employee.firstname else user_id
            name = name[:24]

            # =========================================================
            # SMART REUSE EXISTING UID IF USER EXISTS
            # =========================================================

            existing_users = self.conn.get_users()

            existing_user = next(
                (u for u in existing_users if str(u.user_id) == user_id),
                None
            )

            if existing_user:
                uid = existing_user.uid

            else:
                conflict_user = next(
                    (u for u in existing_users if u.uid == uid),
                    None
                )

                if conflict_user:
                    logger.warning(
                        f"UID conflict {uid} used by {conflict_user.user_id}, deleting stale user"
                    )
                    self.conn.delete_user(uid=conflict_user.uid)

            # =========================================================

            try:
                user = ZKUser(
                    uid=int(uid),
                    name=str(name),
                    privilege=0,
                    password="",
                    group_id=0,
                    user_id=user_id,
                    card=0
                )
            except Exception as e:
                return False, f"ZKUser create error: {e}"

            try:
                self.conn.set_user(
                    uid=user.uid,
                    name=user.name,
                    privilege=user.privilege,
                    password=user.password,
                    group_id=user.group_id,
                    user_id=user.user_id,
                    card=user.card
                )

            except TypeError:
                self.conn.set_user(
                    user.uid,
                    user.name,
                    user.privilege,
                    user.password,
                    user.group_id,
                    user.user_id,
                    user.card
                )

            return True, "User pushed to device"

        except Exception as e:
            logger.error(e, exc_info=True)
            return False, str(e)

    # ================= FINGERPRINT ================= #

    def get_device_uid(self, code):

        self._ensure()
        code_str = str(code)

        for user in self.conn.get_users():
            if str(user.user_id) == code_str:
                return user.uid

        return self._uid(code)

    def start_fingerprint_enrollment(self, employee, index=0):

        try:
            self._ensure()

            ok, msg = self.push_user(employee)
            if not ok:
                return False, msg

            uid = self.get_device_uid(employee.code)

            if hasattr(self.conn, "enroll_user"):

                try:
                    self.conn.enroll_user(uid=int(uid), temp_id=int(index))
                except TypeError:
                    self.conn.enroll_user(int(uid), int(index))

                return True, "Fingerprint enrollment started"

            return False, "Auto enrollment not supported"

        except Exception as e:
            return False, str(e)

    def cancel_enrollment(self):

        try:
            self._ensure()

            if hasattr(self.conn, "cancel_capture"):
                self.conn.cancel_capture()
                return True, "Enrollment cancelled"

            return False, "Cancel not supported"

        except Exception as e:
            return False, str(e)

    def verify_fingerprint_enrollment(self, employee, index=0):

        try:
            self._ensure()

            uid = self.get_device_uid(employee.code)

            try:
                template = self.conn.get_user_template(
                    uid=int(uid),
                    temp_id=int(index)
                )

                if template:
                    return True, "Fingerprint enrolled"

            except Exception:
                pass

            return False, "Fingerprint not found"

        except Exception as e:
            return False, str(e)

    # ================= FACE ================= #

    def start_face_enrollment(self, employee, index=0):

        try:
            self._ensure()

            ok, msg = self.push_user(employee)
            if not ok:
                return False, msg

            return True, (
                f"User {employee.code} ready. "
                "Go to device → User → Face Enrollment"
            )

        except Exception as e:
            return False, str(e)

    # ================= VERIFY ================= #

    def verify_user_exists(self, employee):

        try:
            self._ensure()
            code = str(employee.code)

            for user in self.conn.get_users():
                if str(user.user_id) == code:
                    return True, "User exists"

            return False, "User not found"

        except Exception as e:
            return False, str(e)

    # ================= DATA ================= #

    def get_users(self):
        self._ensure()
        return self.conn.get_users()

    def get_attendance(self):
        self._ensure()
        return self.conn.get_attendance()

    def get_realtime_logs(self, callback=None):

        self._ensure()

        for event in self.conn.live_capture():
            if callback:
                callback(self.device, event)
            yield event


# ================= EVENT PROCESSING ================= #

def process_device_event(device, event_data):

    try:
        from .models import Employees, AttendanceLog

        user_id = str(getattr(event_data, 'user_id', '')).strip()
        timestamp = getattr(event_data, 'timestamp', timezone.now())
        uid = getattr(event_data, 'uid', None)

        if timezone.is_naive(timestamp):
            timestamp = timezone.make_aware(timestamp)

        employee = None

        if user_id.isdigit():
            employee = Employees.objects.filter(code=user_id).first()

        event_type_map = {
            0: 'check_in',
            1: 'check_out',
            2: 'check_out',
            3: 'check_in',
            4: 'check_in',
            5: 'check_out'
        }

        zk_status = getattr(event_data, 'punch', 0)
        event_type = event_type_map.get(zk_status, 'unknown')

        log = AttendanceLog.objects.create(
            device=device,
            employee=employee,
            user_id=user_id,
            user_name=employee.firstname if employee else f"Unknown ({user_id})",
            event_type=event_type,
            timestamp=timestamp,
            verification_mode=getattr(event_data, 'verify_mode', 0),
            raw_data={'uid': uid, 'punch': zk_status}
        )

        return log

    except Exception as e:
        logger.error(f"Error processing device event: {e}")
        return None
