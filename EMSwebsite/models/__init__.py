# EMSwebsite/models/__init__.py
# Re-export all models for backward compatibility

from .employee import (
    Department, Position, Employees, Employee,
    EmployeeAdditionalDocument, DepartmentEmployee, UserProfile,
    generate_secure_password, _sanitize_username, _unique_username_from_firstname,
)

from .attendance import (
    Attendance, AttendanceSettings, HolidayDate, LeaveRequest,
)

from .payroll import (
    Payroll, PayrollRecord, SalarySlipRequest, SalaryIncrement,
    SalaryDisbursement, SalaryDisbursementRecord, IncrementSettings,
)

from .team import (
    Team, TeamMember, Project,
)

from .loan import (
    LoanPool, LoanPoolTransaction, Loan, LoanRepayment,
)

from .report import (
    Report, ReportTemplate, ReportSchedule,
)

from .settings import (
    SystemSettings,
)

from .notification import (
    Notification,
)

from .device import (
    ZKDevice, AttendanceLog, EnrollmentLog,
)

from .ai import (
    Policy, Complaint, AIChatMessage,
)
