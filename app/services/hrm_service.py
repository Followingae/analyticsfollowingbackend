"""
HRM Service Layer
Handles all business logic for Human Resource Management
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from uuid import UUID
import pandas as pd
import io
from sqlalchemy import select, and_, or_, func, extract, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hrm import (
    HRMEmployee, HRMAttendanceRaw, HRMAttendanceProcessed,
    HRMTimesheet, HRMPayroll, HRMLeave, HRMLeaveBalance, HRMHoliday,
    EmployeeStatus, LeaveStatus, TimesheetStatus, PaymentStatus, AttendanceStatus
)
import logging
logger = logging.getLogger(__name__)


class HRMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Employee Management ====================

    async def create_employee(self, employee_data: Dict[str, Any]) -> HRMEmployee:
        """Create a new employee"""
        # Validate employee_code is provided
        if not employee_data.get('employee_code') or not employee_data['employee_code'].strip():
            raise ValueError("Employee code is required and cannot be empty")

        # Check if employee code already exists
        existing = await self.get_employee_by_code(employee_data['employee_code'])
        if existing:
            raise ValueError(f"Employee code '{employee_data['employee_code']}' already exists")

        # Check if email already exists
        existing_email = await self.get_employee_by_email(employee_data.get('email'))
        if existing_email:
            raise ValueError(f"Email '{employee_data['email']}' is already registered")

        employee = HRMEmployee(**employee_data)
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)

        # Create initial leave balance for current year
        current_year = datetime.now().year
        leave_balance = HRMLeaveBalance(
            employee_id=employee.id,
            year=current_year
        )
        self.db.add(leave_balance)
        await self.db.commit()

        return employee

    async def get_employee(self, employee_id: UUID) -> Optional[HRMEmployee]:
        """Get employee by ID"""
        result = await self.db.execute(
            select(HRMEmployee).where(HRMEmployee.id == employee_id)
        )
        return result.scalar_one_or_none()

    async def get_employee_by_code(self, employee_code: str) -> Optional[HRMEmployee]:
        """Get employee by employee code"""
        result = await self.db.execute(
            select(HRMEmployee).where(HRMEmployee.employee_code == employee_code)
        )
        return result.scalar_one_or_none()

    async def get_employee_by_email(self, email: str) -> Optional[HRMEmployee]:
        """Get employee by email"""
        if not email:
            return None
        result = await self.db.execute(
            select(HRMEmployee).where(HRMEmployee.email == email)
        )
        return result.scalar_one_or_none()

    async def check_employee_code_exists(self, employee_code: str) -> bool:
        """Check if employee code exists"""
        existing = await self.get_employee_by_code(employee_code)
        return existing is not None

    async def check_email_exists(self, email: str) -> bool:
        """Check if email exists"""
        existing = await self.get_employee_by_email(email)
        return existing is not None

    async def list_employees(self, status: Optional[EmployeeStatus] = None) -> List[Dict[str, Any]]:
        """List all employees with optional status filter"""
        # Use raw SQL query directly for PGBouncer compatibility
        try:
            if status:
                if isinstance(status, str):
                    status = EmployeeStatus(status)
                raw_query = text("""
                    SELECT * FROM hrm_employees
                    WHERE status = :status
                    ORDER BY full_name
                """)
                raw_result = await self.db.execute(raw_query, {"status": status.value if hasattr(status, 'value') else status})
            else:
                raw_query = text("SELECT * FROM hrm_employees ORDER BY full_name")
                raw_result = await self.db.execute(raw_query)

            employees = []
            for row in raw_result:
                # Convert row to dictionary
                emp_dict = dict(row._mapping)
                # Convert UUID to string
                if 'id' in emp_dict and emp_dict['id']:
                    emp_dict['id'] = str(emp_dict['id'])
                # Ensure JSON fields are not None
                for json_field in ['allowances', 'bank_account_info', 'emergency_contact']:
                    if json_field in emp_dict and emp_dict[json_field] is None:
                        emp_dict[json_field] = {}
                employees.append(emp_dict)

            return employees

        except Exception as e:
            logger.error(f"Error in list_employees: {e}")
            return []

    async def update_employee(self, employee_id: UUID, update_data: Dict[str, Any]) -> Optional[HRMEmployee]:
        """Update employee information"""
        employee = await self.get_employee(employee_id)
        if not employee:
            return None

        for key, value in update_data.items():
            if hasattr(employee, key):
                setattr(employee, key, value)

        employee.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def terminate_employee(self, employee_id: UUID) -> bool:
        """Terminate an employee"""
        employee = await self.get_employee(employee_id)
        if not employee:
            return False

        employee.status = EmployeeStatus.TERMINATED
        employee.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    # ==================== Attendance Management ====================

    async def upload_attendance_csv(self, csv_content: str, batch_id: str) -> Dict[str, Any]:
        """Process and upload attendance data from CSV"""
        try:
            # Parse CSV
            df = pd.read_csv(io.StringIO(csv_content))

            # Validate required columns
            required_columns = ['employee_code', 'datetime', 'device_id']
            if not all(col in df.columns for col in required_columns):
                return {"success": False, "error": "Missing required columns"}

            # Process each row
            success_count = 0
            error_count = 0
            errors = []

            for _, row in df.iterrows():
                try:
                    # Get employee
                    employee = await self.get_employee_by_code(row['employee_code'])
                    if not employee:
                        errors.append(f"Employee {row['employee_code']} not found")
                        error_count += 1
                        continue

                    # Create raw attendance record
                    attendance = HRMAttendanceRaw(
                        employee_id=employee.id,
                        employee_code=row['employee_code'],
                        fingerprint_datetime=pd.to_datetime(row['datetime']),
                        device_id=row['device_id'],
                        upload_batch_id=batch_id
                    )
                    self.db.add(attendance)
                    success_count += 1

                except Exception as e:
                    errors.append(f"Error processing row: {str(e)}")
                    error_count += 1

            await self.db.commit()

            # Process the uploaded data into daily attendance
            await self.process_attendance_data(batch_id)

            return {
                "success": True,
                "total_records": len(df),
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors[:10]  # Limit errors shown
            }

        except Exception as e:
            logger.error(f"Error uploading attendance CSV: {e}")
            return {"success": False, "error": str(e)}

    async def process_attendance_data(self, batch_id: str) -> None:
        """Process raw attendance data into daily summaries"""
        # Get all raw records for this batch
        result = await self.db.execute(
            select(HRMAttendanceRaw)
            .where(HRMAttendanceRaw.upload_batch_id == batch_id)
            .order_by(HRMAttendanceRaw.fingerprint_datetime)
        )
        raw_records = result.scalars().all()

        # Group by employee and date
        from collections import defaultdict
        daily_records = defaultdict(list)

        for record in raw_records:
            date_key = (record.employee_id, record.fingerprint_datetime.date())
            daily_records[date_key].append(record.fingerprint_datetime)

        # Process each day's attendance
        for (employee_id, work_date), timestamps in daily_records.items():
            # Check if already processed
            existing = await self.db.execute(
                select(HRMAttendanceProcessed).where(
                    and_(
                        HRMAttendanceProcessed.employee_id == employee_id,
                        HRMAttendanceProcessed.work_date == work_date
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # Skip if already processed

            # Calculate attendance
            check_in = min(timestamps)
            check_out = max(timestamps)

            # Calculate hours
            if check_in != check_out:
                total_hours = (check_out - check_in).total_seconds() / 3600
                # Subtract lunch break (1 hour) if worked more than 6 hours
                if total_hours > 6:
                    total_hours -= 1

                regular_hours = min(total_hours, 8)
                overtime_hours = max(0, total_hours - 8)
            else:
                # Only one punch, might be missing checkout
                total_hours = 0
                regular_hours = 0
                overtime_hours = 0

            # Create processed record
            processed = HRMAttendanceProcessed(
                employee_id=employee_id,
                work_date=work_date,
                check_in_time=check_in,
                check_out_time=check_out if check_in != check_out else None,
                total_hours=total_hours,
                regular_hours=regular_hours,
                overtime_hours=overtime_hours,
                status=AttendanceStatus.PRESENT if total_hours > 0 else AttendanceStatus.ABSENT
            )
            self.db.add(processed)

        await self.db.commit()

    async def get_employee_attendance(self, employee_id: UUID, month: int, year: int) -> List[HRMAttendanceProcessed]:
        """Get processed attendance for an employee for a specific month"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        result = await self.db.execute(
            select(HRMAttendanceProcessed)
            .where(
                and_(
                    HRMAttendanceProcessed.employee_id == employee_id,
                    HRMAttendanceProcessed.work_date >= start_date,
                    HRMAttendanceProcessed.work_date <= end_date
                )
            )
            .order_by(HRMAttendanceProcessed.work_date)
        )
        return result.scalars().all()

    # ==================== Timesheet Management ====================

    async def generate_timesheet(self, employee_id: UUID, month: int, year: int) -> HRMTimesheet:
        """Generate or update timesheet from attendance data"""
        # Check if timesheet exists
        result = await self.db.execute(
            select(HRMTimesheet).where(
                and_(
                    HRMTimesheet.employee_id == employee_id,
                    HRMTimesheet.month == month,
                    HRMTimesheet.year == year
                )
            )
        )
        timesheet = result.scalar_one_or_none()

        # Get attendance data
        attendance_records = await self.get_employee_attendance(employee_id, month, year)

        # Calculate totals
        total_days = len(attendance_records)
        present_days = sum(1 for a in attendance_records if a.status == "present")
        absent_days = sum(1 for a in attendance_records if a.status == "absent")
        leave_days = sum(1 for a in attendance_records if a.status == "leave")
        holidays = sum(1 for a in attendance_records if a.status == "holiday")

        total_hours = sum(a.total_hours for a in attendance_records)
        regular_hours = sum(a.regular_hours for a in attendance_records)
        overtime_hours = sum(a.overtime_hours for a in attendance_records)

        # Get working days in month
        from calendar import monthrange
        _, days_in_month = monthrange(year, month)

        # Count weekends
        weekends = 0
        for day in range(1, days_in_month + 1):
            if date(year, month, day).weekday() in [5, 6]:  # Saturday, Sunday
                weekends += 1

        working_days = days_in_month - weekends - holidays

        if timesheet:
            # Update existing
            timesheet.total_days = total_days
            timesheet.working_days = working_days
            timesheet.present_days = present_days
            timesheet.absent_days = absent_days
            timesheet.leave_days = leave_days
            timesheet.holidays = holidays
            timesheet.total_hours = total_hours
            timesheet.regular_hours = regular_hours
            timesheet.overtime_hours = overtime_hours
            timesheet.updated_at = datetime.utcnow()
        else:
            # Create new
            timesheet = HRMTimesheet(
                employee_id=employee_id,
                month=month,
                year=year,
                total_days=total_days,
                working_days=working_days,
                present_days=present_days,
                absent_days=absent_days,
                leave_days=leave_days,
                holidays=holidays,
                total_hours=total_hours,
                regular_hours=regular_hours,
                overtime_hours=overtime_hours
            )
            self.db.add(timesheet)

        await self.db.commit()
        await self.db.refresh(timesheet)
        return timesheet

    async def approve_timesheet(self, timesheet_id: UUID, approver_id: UUID) -> bool:
        """Approve a timesheet"""
        result = await self.db.execute(
            select(HRMTimesheet).where(HRMTimesheet.id == timesheet_id)
        )
        timesheet = result.scalar_one_or_none()

        if not timesheet:
            return False

        timesheet.status = TimesheetStatus.APPROVED
        timesheet.approved_by = approver_id
        timesheet.approved_at = datetime.utcnow()
        await self.db.commit()
        return True

    # ==================== Payroll Management ====================

    async def calculate_payroll(self, employee_id: UUID, month: int, year: int) -> HRMPayroll:
        """Calculate payroll for an employee"""
        # Get employee
        employee = await self.get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found")

        # Get timesheet
        result = await self.db.execute(
            select(HRMTimesheet).where(
                and_(
                    HRMTimesheet.employee_id == employee_id,
                    HRMTimesheet.month == month,
                    HRMTimesheet.year == year
                )
            )
        )
        timesheet = result.scalar_one_or_none()

        if not timesheet:
            raise ValueError("Timesheet not found. Please generate timesheet first.")

        # Check if payroll exists
        result = await self.db.execute(
            select(HRMPayroll).where(
                and_(
                    HRMPayroll.employee_id == employee_id,
                    HRMPayroll.month == month,
                    HRMPayroll.year == year
                )
            )
        )
        payroll = result.scalar_one_or_none()

        # Calculate salary components
        basic_salary = employee.base_salary

        # Calculate allowances
        allowances_total = sum(employee.allowances.values()) if employee.allowances else 0

        # Calculate overtime pay (1.5x hourly rate)
        hourly_rate = basic_salary / (22 * 8)  # Assuming 22 working days, 8 hours per day
        overtime_pay = timesheet.overtime_hours * hourly_rate * 1.5

        # Calculate gross salary
        gross_salary = basic_salary + allowances_total + overtime_pay

        # Calculate deductions
        tax = gross_salary * 0.1 if gross_salary > 10000 else 0  # Simple tax calculation
        insurance = gross_salary * 0.05  # 5% for insurance

        # Deduct for absent days
        daily_rate = basic_salary / 22
        absence_deduction = timesheet.absent_days * daily_rate

        total_deductions = tax + insurance + absence_deduction

        # Calculate net salary
        net_salary = gross_salary - total_deductions

        deductions = {
            "tax": round(tax, 2),
            "insurance": round(insurance, 2),
            "absence": round(absence_deduction, 2),
            "total": round(total_deductions, 2)
        }

        if payroll:
            # Update existing
            payroll.basic_salary = basic_salary
            payroll.allowances = allowances_total
            payroll.overtime_pay = round(overtime_pay, 2)
            payroll.gross_salary = round(gross_salary, 2)
            payroll.deductions = deductions
            payroll.net_salary = round(net_salary, 2)
            payroll.updated_at = datetime.utcnow()
        else:
            # Create new
            payroll = HRMPayroll(
                employee_id=employee_id,
                month=month,
                year=year,
                basic_salary=basic_salary,
                allowances=allowances_total,
                overtime_pay=round(overtime_pay, 2),
                gross_salary=round(gross_salary, 2),
                deductions=deductions,
                net_salary=round(net_salary, 2)
            )
            self.db.add(payroll)

        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def process_payroll_payment(self, payroll_id: UUID, payment_method: str, payment_reference: str) -> bool:
        """Mark payroll as paid"""
        result = await self.db.execute(
            select(HRMPayroll).where(HRMPayroll.id == payroll_id)
        )
        payroll = result.scalar_one_or_none()

        if not payroll:
            return False

        payroll.payment_status = PaymentStatus.PAID
        payroll.payment_date = date.today()
        payroll.payment_method = payment_method
        payroll.payment_reference = payment_reference
        await self.db.commit()

        # Update timesheet status
        await self.db.execute(
            select(HRMTimesheet).where(
                and_(
                    HRMTimesheet.employee_id == payroll.employee_id,
                    HRMTimesheet.month == payroll.month,
                    HRMTimesheet.year == payroll.year
                )
            )
        )
        timesheet = result.scalar_one_or_none()
        if timesheet:
            timesheet.status = TimesheetStatus.PAID
            await self.db.commit()

        return True

    # ==================== Leave Management ====================

    async def request_leave(self, leave_data: Dict[str, Any]) -> HRMLeave:
        """Create a leave request"""
        # Calculate days count
        start_date = leave_data['start_date']
        end_date = leave_data['end_date']
        days_count = (end_date - start_date).days + 1

        # Check leave balance
        employee_id = leave_data['employee_id']
        year = start_date.year

        result = await self.db.execute(
            select(HRMLeaveBalance).where(
                and_(
                    HRMLeaveBalance.employee_id == employee_id,
                    HRMLeaveBalance.year == year
                )
            )
        )
        balance = result.scalar_one_or_none()

        if not balance:
            # Create balance for this year
            balance = HRMLeaveBalance(
                employee_id=employee_id,
                year=year
            )
            self.db.add(balance)
            await self.db.commit()
            await self.db.refresh(balance)

        # Check if sufficient balance
        leave_type = leave_data['leave_type']
        if leave_type == 'annual' and balance.annual_leave_balance < days_count:
            raise ValueError("Insufficient annual leave balance")
        elif leave_type == 'sick' and balance.sick_leave_balance < days_count:
            raise ValueError("Insufficient sick leave balance")

        leave = HRMLeave(
            **leave_data,
            days_count=days_count
        )
        self.db.add(leave)
        await self.db.commit()
        await self.db.refresh(leave)
        return leave

    async def approve_leave(self, leave_id: UUID, approver_id: UUID) -> bool:
        """Approve a leave request"""
        result = await self.db.execute(
            select(HRMLeave).where(HRMLeave.id == leave_id)
        )
        leave = result.scalar_one_or_none()

        if not leave:
            return False

        leave.status = LeaveStatus.APPROVED
        leave.approver_id = approver_id
        leave.approved_at = datetime.utcnow()

        # Update leave balance
        result = await self.db.execute(
            select(HRMLeaveBalance).where(
                and_(
                    HRMLeaveBalance.employee_id == leave.employee_id,
                    HRMLeaveBalance.year == leave.start_date.year
                )
            )
        )
        balance = result.scalar_one_or_none()

        if balance:
            if leave.leave_type == 'annual':
                balance.annual_leave_used += leave.days_count
                balance.annual_leave_balance -= leave.days_count
            elif leave.leave_type == 'sick':
                balance.sick_leave_used += leave.days_count
                balance.sick_leave_balance -= leave.days_count

        await self.db.commit()
        return True

    async def reject_leave(self, leave_id: UUID, approver_id: UUID, reason: str) -> bool:
        """Reject a leave request"""
        result = await self.db.execute(
            select(HRMLeave).where(HRMLeave.id == leave_id)
        )
        leave = result.scalar_one_or_none()

        if not leave:
            return False

        leave.status = LeaveStatus.REJECTED
        leave.approver_id = approver_id
        leave.rejection_reason = reason
        await self.db.commit()
        return True

    # ==================== Dashboard & Reporting ====================

    async def get_hrm_dashboard_stats(self) -> Dict[str, Any]:
        """Get HRM dashboard statistics"""
        # Employee stats
        query = text("""
            SELECT COUNT(*) as count
            FROM hrm_employees
            WHERE status = 'active'::employeestatus
        """)
        result = await self.db.execute(query)
        total_employees = result.scalar()

        # Current month attendance
        current_month = datetime.now().month
        current_year = datetime.now().year

        # Use text queries to avoid prepared statement issues with PGBouncer
        attendance_query = text("""
            SELECT
                COUNT(id) as total,
                AVG(total_hours) as avg_hours
            FROM hrm_attendance_processed
            WHERE EXTRACT(month FROM work_date) = :month
              AND EXTRACT(year FROM work_date) = :year
        """)
        attendance_stats = await self.db.execute(
            attendance_query,
            {"month": current_month, "year": current_year}
        )

        # Pending leaves - use text query
        pending_leaves_query = text("""
            SELECT COUNT(id) as count
            FROM hrm_leaves
            WHERE status = 'pending'::leavestatus
        """)
        pending_leaves = await self.db.execute(pending_leaves_query)

        # Current month payroll - use text query
        payroll_query = text("""
            SELECT
                COUNT(id) as count,
                SUM(net_salary) as total
            FROM hrm_payroll
            WHERE month = :month AND year = :year
        """)
        payroll_stats = await self.db.execute(
            payroll_query,
            {"month": current_month, "year": current_year}
        )

        attendance_data = attendance_stats.one()
        payroll_data = payroll_stats.one()
        pending_count = pending_leaves.scalar()

        return {
            "total_employees": total_employees or 0,
            "attendance": {
                "total_records": attendance_data.total or 0,
                "avg_hours_per_day": round(attendance_data.avg_hours or 0, 2)
            },
            "pending_leaves": pending_count or 0,
            "current_month_payroll": {
                "processed_count": payroll_data.count or 0,
                "total_amount": float(payroll_data.total or 0)
            },
            "month": current_month,
            "year": current_year
        }