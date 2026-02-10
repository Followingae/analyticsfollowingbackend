"""
HRM (Human Resource Management) Models
For internal company management - separate from analytics platform
"""
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

# Import Base directly from unified_models to avoid circular dependency
from app.database.unified_models import Base


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class LeaveType(str, enum.Enum):
    ANNUAL = "annual"
    SICK = "sick"
    UNPAID = "unpaid"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    EMERGENCY = "emergency"


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class TimesheetStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PAID = "paid"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    PAID = "paid"
    FAILED = "failed"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HOLIDAY = "holiday"
    LEAVE = "leave"
    HALF_DAY = "half_day"


class HRMEmployee(Base):
    __tablename__ = "hrm_employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(50))
    department = Column(String(100))
    position = Column(String(100))
    hire_date = Column(Date, nullable=False)
    base_salary = Column(Float, nullable=False)

    # Enhanced personal info
    profile_picture_url = Column(String(500))  # S3/CDN URL for profile photo
    date_of_birth = Column(Date)
    nationality = Column(String(100))
    visa_status = Column(String(100))  # For expat employees
    visa_expiry = Column(Date)
    passport_number = Column(String(50))
    passport_expiry = Column(Date)
    national_id = Column(String(50))
    marital_status = Column(String(50))
    home_address = Column(Text)

    # Current compensation details
    current_total_package = Column(Float)  # Total including all allowances
    last_increment_date = Column(Date)
    last_increment_percentage = Column(Float)
    next_review_date = Column(Date)

    allowances = Column(JSON, default={})  # {"housing": 5000, "transport": 2000}
    bank_account_info = Column(JSON, default={})  # {"bank_name": "", "account_number": "", "iban": ""}
    emergency_contact = Column(JSON, default={})  # {"name": "", "phone": "", "relationship": ""}
    status = Column(SQLEnum(EmployeeStatus, values_callable=lambda obj: [e.value for e in obj]), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attendance_raw = relationship("HRMAttendanceRaw", back_populates="employee", cascade="all, delete-orphan")
    attendance_processed = relationship("HRMAttendanceProcessed", back_populates="employee", cascade="all, delete-orphan")
    timesheets = relationship("HRMTimesheet", back_populates="employee", cascade="all, delete-orphan")
    payroll_records = relationship("HRMPayroll", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("HRMLeave", back_populates="employee", cascade="all, delete-orphan")
    leave_balances = relationship("HRMLeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    documents = relationship("HRMEmployeeDocument", back_populates="employee", cascade="all, delete-orphan")
    salary_history = relationship("HRMSalaryHistory", back_populates="employee", cascade="all, delete-orphan")


class HRMAttendanceRaw(Base):
    """Raw attendance data from fingerprint machine"""
    __tablename__ = "hrm_attendance_raw"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code = Column(String(50), nullable=False, index=True)
    fingerprint_datetime = Column(DateTime, nullable=False)
    device_id = Column(String(50))
    upload_batch_id = Column(String(100), index=True)  # To track which upload batch this came from
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"))
    employee = relationship("HRMEmployee", back_populates="attendance_raw")


class HRMAttendanceProcessed(Base):
    """Processed attendance data (daily summary)"""
    __tablename__ = "hrm_attendance_processed"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    work_date = Column(Date, nullable=False, index=True)
    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)
    total_hours = Column(Float, default=0)
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    status = Column(SQLEnum(AttendanceStatus), default="present")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="attendance_processed")


class HRMTimesheet(Base):
    """Monthly timesheet summary"""
    __tablename__ = "hrm_timesheets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    total_days = Column(Integer, default=0)
    working_days = Column(Integer, default=0)
    present_days = Column(Integer, default=0)
    absent_days = Column(Integer, default=0)
    leave_days = Column(Integer, default=0)
    holidays = Column(Integer, default=0)
    total_hours = Column(Float, default=0)
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    status = Column(SQLEnum(TimesheetStatus), default="draft")
    approved_by = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="timesheets")


class HRMPayroll(Base):
    """Monthly payroll records"""
    __tablename__ = "hrm_payroll"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    basic_salary = Column(Float, nullable=False)
    allowances = Column(Float, default=0)
    overtime_pay = Column(Float, default=0)
    gross_salary = Column(Float, nullable=False)
    deductions = Column(JSON, default={})  # {"tax": 0, "insurance": 0, "other": 0}
    net_salary = Column(Float, nullable=False)
    payment_status = Column(SQLEnum(PaymentStatus), default="pending")
    payment_date = Column(Date)
    payment_method = Column(String(50))  # "bank_transfer", "cash", "cheque"
    payment_reference = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="payroll_records")


class HRMLeave(Base):
    """Leave requests"""
    __tablename__ = "hrm_leaves"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    leave_type = Column(SQLEnum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_count = Column(Float, nullable=False)  # Can be 0.5 for half day
    reason = Column(Text)
    status = Column(SQLEnum(LeaveStatus), default="pending")
    approver_id = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="leave_requests")


class HRMLeaveBalance(Base):
    """Annual leave balances"""
    __tablename__ = "hrm_leave_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    annual_leave_total = Column(Float, default=21)  # Total annual leave days
    annual_leave_used = Column(Float, default=0)
    annual_leave_balance = Column(Float, default=21)
    sick_leave_total = Column(Float, default=10)
    sick_leave_used = Column(Float, default=0)
    sick_leave_balance = Column(Float, default=10)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="leave_balances")


class HRMHoliday(Base):
    """Company holidays"""
    __tablename__ = "hrm_holidays"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    date = Column(Date, nullable=False, unique=True)
    year = Column(Integer, nullable=False)
    is_optional = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class HRMEmployeeDocument(Base):
    """Employee documents storage"""
    __tablename__ = "hrm_employee_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(100), nullable=False)  # "passport", "visa", "degree", "contract", "nda", etc
    document_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)  # S3/CDN URL
    file_size = Column(Integer)  # in bytes
    mime_type = Column(String(100))
    expiry_date = Column(Date)  # For documents like passport, visa
    is_verified = Column(Boolean, default=False)
    verified_by = Column(UUID(as_uuid=True))
    verified_at = Column(DateTime)
    notes = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="documents")


class HRMSalaryHistory(Base):
    """Track salary changes and increments"""
    __tablename__ = "hrm_salary_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hrm_employees.id", ondelete="CASCADE"), nullable=False)
    previous_salary = Column(Float, nullable=False)
    new_salary = Column(Float, nullable=False)
    increment_amount = Column(Float)
    increment_percentage = Column(Float)
    effective_date = Column(Date, nullable=False)
    reason = Column(String(255))  # "annual_increment", "promotion", "adjustment", etc
    approved_by = Column(UUID(as_uuid=True))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    employee = relationship("HRMEmployee", back_populates="salary_history")