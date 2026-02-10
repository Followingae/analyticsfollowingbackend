"""
HRM API Routes
Complete Human Resource Management endpoints for superadmin
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.services.hrm_service import HRMService
from app.models.hrm import EmployeeStatus, LeaveType, LeaveStatus, TimesheetStatus, PaymentStatus
import logging
logger = logging.getLogger(__name__)
from app.middleware.auth_middleware import require_admin
from app.database.unified_models import User


router = APIRouter()


# ==================== Request/Response Models ====================

class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: date
    base_salary: float
    allowances: Optional[Dict[str, float]] = Field(default_factory=dict)
    bank_account_info: Optional[Dict[str, str]] = Field(default_factory=dict)
    emergency_contact: Optional[Dict[str, str]] = Field(default_factory=dict)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    base_salary: Optional[float] = None
    allowances: Optional[Dict[str, float]] = None
    bank_account_info: Optional[Dict[str, str]] = None
    emergency_contact: Optional[Dict[str, str]] = None
    status: Optional[EmployeeStatus] = None


class EmployeeResponse(BaseModel):
    id: UUID
    employee_code: str
    full_name: str
    email: str
    phone: Optional[str]
    department: Optional[str]
    position: Optional[str]
    hire_date: date
    base_salary: float
    allowances: Dict[str, Any]
    status: EmployeeStatus
    created_at: datetime


class LeaveRequest(BaseModel):
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveApproval(BaseModel):
    approver_id: UUID
    rejection_reason: Optional[str] = None


class PayrollProcess(BaseModel):
    payment_method: str = Field(..., description="bank_transfer, cash, or cheque")
    payment_reference: str


class AttendanceUploadResponse(BaseModel):
    success: bool
    total_records: int
    success_count: int
    error_count: int
    errors: List[str]
    batch_id: str


class TimesheetResponse(BaseModel):
    id: UUID
    employee_id: UUID
    month: int
    year: int
    total_days: int
    working_days: int
    present_days: int
    absent_days: int
    leave_days: int
    holidays: int
    total_hours: float
    regular_hours: float
    overtime_hours: float
    status: TimesheetStatus


class PayrollResponse(BaseModel):
    id: UUID
    employee_id: UUID
    month: int
    year: int
    basic_salary: float
    allowances: float
    overtime_pay: float
    gross_salary: float
    deductions: Dict[str, float]
    net_salary: float
    payment_status: PaymentStatus
    payment_date: Optional[date]


# ==================== Employee Management Endpoints ====================

@router.get("/employees/check-code/{employee_code}")
async def check_employee_code(
    employee_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Check if employee code already exists"""
    service = HRMService(db)
    exists = await service.check_employee_code_exists(employee_code)
    return {"exists": exists, "employee_code": employee_code}


@router.get("/employees/check-email/{email}")
async def check_employee_email(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Check if employee email already exists"""
    service = HRMService(db)
    exists = await service.check_email_exists(email)
    return {"exists": exists, "email": email}


@router.post("/employees", response_model=EmployeeResponse)
async def create_employee(
    employee_data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Create a new employee (Superadmin only)"""
    try:
        service = HRMService(db)
        employee = await service.create_employee(employee_data.dict())
        return employee
    except ValueError as e:
        # User-friendly validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating employee: {e}")
        raise HTTPException(status_code=500, detail="Failed to create employee")


@router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    status: Optional[EmployeeStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """List all employees with optional status filter"""
    service = HRMService(db)
    employees = await service.list_employees(status)
    return employees


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get employee details by ID"""
    service = HRMService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    update_data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Update employee information"""
    service = HRMService(db)
    # Filter out None values
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    employee = await service.update_employee(employee_id, update_dict)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.delete("/employees/{employee_id}")
async def terminate_employee(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Terminate an employee (soft delete)"""
    service = HRMService(db)
    success = await service.terminate_employee(employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee terminated successfully"}


# ==================== Attendance Management Endpoints ====================

@router.post("/attendance/upload-csv", response_model=AttendanceUploadResponse)
async def upload_attendance_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Upload attendance data from fingerprint machine CSV"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        contents = await file.read()
        csv_content = contents.decode('utf-8')

        # Generate batch ID
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        service = HRMService(db)
        result = await service.upload_attendance_csv(csv_content, batch_id)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Upload failed'))

        return AttendanceUploadResponse(
            **result,
            batch_id=batch_id
        )
    except Exception as e:
        logger.error(f"Error uploading attendance CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attendance/employee/{employee_id}/monthly")
async def get_employee_attendance(
    employee_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2030),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get employee attendance for a specific month"""
    service = HRMService(db)
    attendance = await service.get_employee_attendance(employee_id, month, year)
    return [{
        "date": a.work_date,
        "check_in": a.check_in_time,
        "check_out": a.check_out_time,
        "total_hours": a.total_hours,
        "regular_hours": a.regular_hours,
        "overtime_hours": a.overtime_hours,
        "status": a.status
    } for a in attendance]


@router.get("/attendance/monthly-report")
async def get_monthly_attendance_report(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2030),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get attendance report for all employees for a month"""
    service = HRMService(db)
    employees = await service.list_employees('active')

    report = []
    for employee in employees:
        attendance = await service.get_employee_attendance(employee.id, month, year)

        present_days = sum(1 for a in attendance if a.status == 'present')
        absent_days = sum(1 for a in attendance if a.status == 'absent')
        total_hours = sum(a.total_hours for a in attendance)
        overtime_hours = sum(a.overtime_hours for a in attendance)

        report.append({
            "employee_id": employee.id,
            "employee_name": employee.full_name,
            "employee_code": employee.employee_code,
            "present_days": present_days,
            "absent_days": absent_days,
            "total_hours": round(total_hours, 2),
            "overtime_hours": round(overtime_hours, 2)
        })

    return report


# ==================== Timesheet Management Endpoints ====================

@router.post("/timesheets/generate/{employee_id}", response_model=TimesheetResponse)
async def generate_timesheet(
    employee_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2030),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Generate or update timesheet from attendance data"""
    service = HRMService(db)
    timesheet = await service.generate_timesheet(employee_id, month, year)
    return timesheet


@router.get("/timesheets/current-month", response_model=List[TimesheetResponse])
async def get_current_month_timesheets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get all timesheets for current month"""
    current_month = datetime.now().month
    current_year = datetime.now().year

    service = HRMService(db)
    employees = await service.list_employees('active')

    timesheets = []
    for employee in employees:
        try:
            timesheet = await service.generate_timesheet(employee.id, current_month, current_year)
            timesheets.append(timesheet)
        except Exception as e:
            logger.warning(f"Could not generate timesheet for {employee.full_name}: {e}")

    return timesheets


@router.get("/timesheets/by-month/{year}/{month}", response_model=List[TimesheetResponse])
async def get_timesheets_by_month(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get all timesheets for a specific month"""
    service = HRMService(db)
    employees = await service.list_employees('active')

    timesheets = []
    for employee in employees:
        try:
            timesheet = await service.generate_timesheet(employee.id, month, year)
            timesheets.append(timesheet)
        except Exception as e:
            logger.warning(f"Could not generate timesheet for {employee.full_name}: {e}")

    return timesheets


@router.post("/timesheets/approve/{timesheet_id}")
async def approve_timesheet(
    timesheet_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Approve a timesheet"""
    service = HRMService(db)
    # Using superadmin's ID as approver
    success = await service.approve_timesheet(timesheet_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return {"message": "Timesheet approved successfully"}


# ==================== Payroll Management Endpoints ====================

@router.post("/payroll/calculate/{employee_id}", response_model=PayrollResponse)
async def calculate_payroll(
    employee_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2030),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Calculate payroll for an employee"""
    try:
        service = HRMService(db)
        payroll = await service.calculate_payroll(employee_id, month, year)
        return payroll
    except Exception as e:
        logger.error(f"Error calculating payroll: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payroll/calculate/{year}/{month}")
async def calculate_all_payroll(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Calculate payroll for all active employees"""
    service = HRMService(db)
    employees = await service.list_employees('active')

    results = {"success": [], "errors": []}

    for employee in employees:
        try:
            payroll = await service.calculate_payroll(employee.id, month, year)
            results["success"].append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "net_salary": payroll.net_salary
            })
        except Exception as e:
            results["errors"].append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "error": str(e)
            })

    return results


@router.get("/payroll/pending")
async def get_pending_payroll(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get all pending payroll records"""
    from sqlalchemy import select, and_
    from app.models.hrm import HRMPayroll

    result = await db.execute(
        select(HRMPayroll)
        .where(HRMPayroll.payment_status == 'pending')
        .order_by(HRMPayroll.year.desc(), HRMPayroll.month.desc())
    )
    payrolls = result.scalars().all()

    return [{
        "id": p.id,
        "employee_id": p.employee_id,
        "month": p.month,
        "year": p.year,
        "net_salary": p.net_salary,
        "payment_status": p.payment_status
    } for p in payrolls]


@router.post("/payroll/process-payment/{payroll_id}")
async def process_payroll_payment(
    payroll_id: UUID,
    payment_data: PayrollProcess,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Process payment for payroll"""
    service = HRMService(db)
    success = await service.process_payroll_payment(
        payroll_id,
        payment_data.payment_method,
        payment_data.payment_reference
    )
    if not success:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    return {"message": "Payment processed successfully"}


@router.get("/payroll/payslips/{employee_id}")
async def get_employee_payslips(
    employee_id: UUID,
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get payslips for an employee"""
    from sqlalchemy import select, and_
    from app.models.hrm import HRMPayroll

    query = select(HRMPayroll).where(HRMPayroll.employee_id == employee_id)
    if year:
        query = query.where(HRMPayroll.year == year)
    query = query.order_by(HRMPayroll.year.desc(), HRMPayroll.month.desc())

    result = await db.execute(query)
    payrolls = result.scalars().all()

    return payrolls


@router.get("/payroll/summary/{year}/{month}")
async def get_payroll_summary(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get payroll summary for a month"""
    from sqlalchemy import select, and_, func
    from app.models.hrm import HRMPayroll

    result = await db.execute(
        select(
            func.count(HRMPayroll.id).label('employee_count'),
            func.sum(HRMPayroll.basic_salary).label('total_basic'),
            func.sum(HRMPayroll.allowances).label('total_allowances'),
            func.sum(HRMPayroll.overtime_pay).label('total_overtime'),
            func.sum(HRMPayroll.gross_salary).label('total_gross'),
            func.sum(HRMPayroll.net_salary).label('total_net')
        ).where(
            and_(
                HRMPayroll.month == month,
                HRMPayroll.year == year
            )
        )
    )
    summary = result.one()

    return {
        "month": month,
        "year": year,
        "employee_count": summary.employee_count or 0,
        "total_basic_salary": float(summary.total_basic or 0),
        "total_allowances": float(summary.total_allowances or 0),
        "total_overtime": float(summary.total_overtime or 0),
        "total_gross_salary": float(summary.total_gross or 0),
        "total_net_salary": float(summary.total_net or 0)
    }


# ==================== Leave Management Endpoints ====================

@router.post("/leaves/request")
async def request_leave(
    leave_data: LeaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Submit a leave request"""
    try:
        service = HRMService(db)
        leave = await service.request_leave(leave_data.dict())
        return {
            "id": leave.id,
            "employee_id": leave.employee_id,
            "leave_type": leave.leave_type,
            "start_date": leave.start_date,
            "end_date": leave.end_date,
            "days_count": leave.days_count,
            "status": leave.status
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leaves/pending")
async def get_pending_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get all pending leave requests"""
    from sqlalchemy import select
    from app.models.hrm import HRMLeave, HRMEmployee

    result = await db.execute(
        select(HRMLeave, HRMEmployee)
        .join(HRMEmployee, HRMLeave.employee_id == HRMEmployee.id)
        .where(HRMLeave.status == 'pending')
        .order_by(HRMLeave.created_at.desc())
    )
    leaves = result.all()

    return [{
        "id": leave.HRMLeave.id,
        "employee_id": leave.HRMLeave.employee_id,
        "employee_name": leave.HRMEmployee.full_name,
        "leave_type": leave.HRMLeave.leave_type,
        "start_date": leave.HRMLeave.start_date,
        "end_date": leave.HRMLeave.end_date,
        "days_count": leave.HRMLeave.days_count,
        "reason": leave.HRMLeave.reason,
        "status": leave.HRMLeave.status,
        "created_at": leave.HRMLeave.created_at
    } for leave in leaves]


@router.post("/leaves/approve/{leave_id}")
async def approve_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Approve a leave request"""
    service = HRMService(db)
    success = await service.approve_leave(leave_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return {"message": "Leave approved successfully"}


@router.post("/leaves/reject/{leave_id}")
async def reject_leave(
    leave_id: UUID,
    reason: str = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Reject a leave request"""
    service = HRMService(db)
    success = await service.reject_leave(leave_id, current_user.id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return {"message": "Leave rejected"}


@router.get("/leaves/balance/{employee_id}")
async def get_leave_balance(
    employee_id: UUID,
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get leave balance for an employee"""
    from sqlalchemy import select, and_
    from app.models.hrm import HRMLeaveBalance

    if not year:
        year = datetime.now().year

    result = await db.execute(
        select(HRMLeaveBalance).where(
            and_(
                HRMLeaveBalance.employee_id == employee_id,
                HRMLeaveBalance.year == year
            )
        )
    )
    balance = result.scalar_one_or_none()

    if not balance:
        return {
            "employee_id": employee_id,
            "year": year,
            "annual_leave_balance": 21,
            "annual_leave_used": 0,
            "sick_leave_balance": 10,
            "sick_leave_used": 0
        }

    return {
        "employee_id": balance.employee_id,
        "year": balance.year,
        "annual_leave_balance": balance.annual_leave_balance,
        "annual_leave_used": balance.annual_leave_used,
        "sick_leave_balance": balance.sick_leave_balance,
        "sick_leave_used": balance.sick_leave_used
    }


@router.get("/leaves/report")
async def get_leave_report(
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get leave utilization report"""
    from sqlalchemy import select, and_, func
    from app.models.hrm import HRMLeave, HRMEmployee

    if not year:
        year = datetime.now().year

    # Get leave statistics by employee
    result = await db.execute(
        select(
            HRMEmployee.full_name,
            HRMEmployee.id,
            func.count(HRMLeave.id).label('total_requests'),
            func.sum(HRMLeave.days_count).label('total_days')
        )
        .outerjoin(HRMLeave, and_(
            HRMLeave.employee_id == HRMEmployee.id,
            func.extract('year', HRMLeave.start_date) == year,
            HRMLeave.status == "approved"
        ))
        .where(HRMEmployee.status == 'active')
        .group_by(HRMEmployee.id, HRMEmployee.full_name)
    )

    report = []
    for row in result:
        report.append({
            "employee_name": row.full_name,
            "employee_id": row.id,
            "total_leave_requests": row.total_requests or 0,
            "total_leave_days": float(row.total_days or 0)
        })

    return report


# ==================== Dashboard Endpoints ====================

@router.get("/dashboard/overview")
async def get_hrm_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get HRM dashboard overview"""
    service = HRMService(db)
    stats = await service.get_hrm_dashboard_stats()
    return stats


@router.get("/dashboard/attendance-summary")
async def get_attendance_summary(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get attendance summary statistics"""
    if not month:
        month = datetime.now().month
    if not year:
        year = datetime.now().year

    from sqlalchemy import select, and_, func
    from app.models.hrm import HRMAttendanceProcessed

    # Get attendance statistics
    result = await db.execute(
        select(
            func.count(func.distinct(HRMAttendanceProcessed.employee_id)).label('unique_employees'),
            func.count(HRMAttendanceProcessed.id).label('total_records'),
            func.avg(HRMAttendanceProcessed.total_hours).label('avg_hours'),
            func.sum(HRMAttendanceProcessed.overtime_hours).label('total_overtime')
        ).where(
            and_(
                func.extract('month', HRMAttendanceProcessed.work_date) == month,
                func.extract('year', HRMAttendanceProcessed.work_date) == year
            )
        )
    )
    stats = result.one()

    return {
        "month": month,
        "year": year,
        "unique_employees": stats.unique_employees or 0,
        "total_attendance_records": stats.total_records or 0,
        "average_hours_per_day": round(stats.avg_hours or 0, 2),
        "total_overtime_hours": round(stats.total_overtime or 0, 2)
    }


@router.get("/dashboard/payroll-summary")
async def get_payroll_dashboard_summary(
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get annual payroll summary"""
    if not year:
        year = datetime.now().year

    from sqlalchemy import select, and_, func
    from app.models.hrm import HRMPayroll

    # Get monthly payroll totals
    result = await db.execute(
        select(
            HRMPayroll.month,
            func.count(HRMPayroll.id).label('employee_count'),
            func.sum(HRMPayroll.net_salary).label('total_net')
        )
        .where(HRMPayroll.year == year)
        .group_by(HRMPayroll.month)
        .order_by(HRMPayroll.month)
    )

    monthly_data = []
    total_annual = 0

    for row in result:
        monthly_data.append({
            "month": row.month,
            "employee_count": row.employee_count,
            "total_net_salary": float(row.total_net)
        })
        total_annual += float(row.total_net)

    return {
        "year": year,
        "monthly_data": monthly_data,
        "total_annual_payroll": total_annual
    }


@router.get("/dashboard/employee-statistics")
async def get_employee_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get employee statistics by department and status"""
    from sqlalchemy import select, func
    from app.models.hrm import HRMEmployee

    # By status
    status_result = await db.execute(
        select(
            HRMEmployee.status,
            func.count(HRMEmployee.id).label('count')
        )
        .group_by(HRMEmployee.status)
    )

    # By department
    dept_result = await db.execute(
        select(
            HRMEmployee.department,
            func.count(HRMEmployee.id).label('count')
        )
        .where(HRMEmployee.status == 'active')
        .group_by(HRMEmployee.department)
    )

    return {
        "by_status": {row.status: row.count for row in status_result},
        "by_department": {row.department or "Unassigned": row.count for row in dept_result}
    }


# ==================== Document Management ====================

@router.post("/employees/{employee_id}/upload-document")
async def upload_employee_document(
    employee_id: UUID,
    document_type: str = Body(...),
    document_name: str = Body(...),
    file_url: str = Body(...),  # In production, this would be from S3 upload
    expiry_date: Optional[date] = Body(None),
    notes: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Upload/store employee document reference"""
    from app.models.hrm import HRMEmployeeDocument

    document = HRMEmployeeDocument(
        employee_id=employee_id,
        document_type=document_type,
        document_name=document_name,
        file_url=file_url,
        expiry_date=expiry_date,
        notes=notes
    )

    db.add(document)
    await db.commit()

    return {"message": "Document uploaded successfully", "document_id": str(document.id)}


@router.get("/employees/{employee_id}/documents")
async def get_employee_documents(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get all documents for an employee"""
    from sqlalchemy import select
    from app.models.hrm import HRMEmployeeDocument

    result = await db.execute(
        select(HRMEmployeeDocument)
        .where(HRMEmployeeDocument.employee_id == employee_id)
        .order_by(HRMEmployeeDocument.uploaded_at.desc())
    )

    documents = []
    for doc in result.scalars():
        documents.append({
            "id": str(doc.id),
            "document_type": doc.document_type,
            "document_name": doc.document_name,
            "file_url": doc.file_url,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
            "is_verified": doc.is_verified,
            "uploaded_at": doc.uploaded_at.isoformat()
        })

    return documents


@router.post("/employees/{employee_id}/upload-profile-picture")
async def upload_profile_picture(
    employee_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Upload employee profile picture to Cloudflare R2"""
    import os
    from datetime import datetime
    from sqlalchemy import select
    from app.models.hrm import HRMEmployee
    from app.infrastructure.r2_storage_client import R2StorageClient

    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )

    # Validate file size (max 5MB)
    MAX_SIZE = 5 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 5MB"
        )

    # Get employee
    result = await db.execute(
        select(HRMEmployee).where(HRMEmployee.id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        # Initialize R2 client (same as influencer images)
        r2_client = R2StorageClient(
            account_id=os.getenv("CF_ACCOUNT_ID"),
            access_key=os.getenv("R2_ACCESS_KEY_ID"),
            secret_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            bucket_name="thumbnails-prod"  # Same bucket as influencer images
        )

        # Generate R2 key for employee profile picture
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        r2_key = f"hrm/employees/{employee_id}/profile.{file_extension}"

        # Upload to R2
        upload_success = await r2_client.upload_object(
            key=r2_key,
            content=contents,
            content_type=file.content_type,
            metadata={
                'employee_id': str(employee_id),
                'employee_code': employee.employee_code,
                'uploaded_by': current_user.email,
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )

        if upload_success:
            # Generate CDN URL
            cdn_url = f"https://cdn.following.ae/{r2_key}"

            # Update employee record
            employee.profile_picture_url = cdn_url
            await db.commit()

            return {
                "message": "Profile picture uploaded successfully",
                "cdn_url": cdn_url,
                "file_size": len(contents),
                "content_type": file.content_type
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to upload to CDN")

    except Exception as e:
        logger.error(f"Error uploading profile picture for employee {employee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Salary Management ====================

@router.post("/employees/{employee_id}/salary-increment")
async def create_salary_increment(
    employee_id: UUID,
    new_salary: float = Body(...),
    increment_percentage: Optional[float] = Body(None),
    reason: str = Body(...),
    effective_date: date = Body(...),
    notes: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Record a salary increment"""
    from sqlalchemy import select
    from app.models.hrm import HRMEmployee, HRMSalaryHistory

    # Get current employee
    result = await db.execute(
        select(HRMEmployee).where(HRMEmployee.id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    previous_salary = employee.current_total_package or employee.base_salary
    increment_amount = new_salary - previous_salary

    if not increment_percentage:
        increment_percentage = (increment_amount / previous_salary) * 100 if previous_salary > 0 else 0

    # Create salary history record
    salary_history = HRMSalaryHistory(
        employee_id=employee_id,
        previous_salary=previous_salary,
        new_salary=new_salary,
        increment_amount=increment_amount,
        increment_percentage=increment_percentage,
        effective_date=effective_date,
        reason=reason,
        approved_by=current_user.id,
        notes=notes
    )

    # Update employee record
    employee.current_total_package = new_salary
    employee.last_increment_date = effective_date
    employee.last_increment_percentage = increment_percentage

    db.add(salary_history)
    await db.commit()

    return {
        "message": "Salary increment recorded successfully",
        "previous_salary": previous_salary,
        "new_salary": new_salary,
        "increment_percentage": round(increment_percentage, 2)
    }


@router.get("/employees/{employee_id}/salary-history")
async def get_salary_history(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get salary history for an employee"""
    from sqlalchemy import select
    from app.models.hrm import HRMSalaryHistory

    result = await db.execute(
        select(HRMSalaryHistory)
        .where(HRMSalaryHistory.employee_id == employee_id)
        .order_by(HRMSalaryHistory.effective_date.desc())
    )

    history = []
    for record in result.scalars():
        history.append({
            "id": str(record.id),
            "previous_salary": record.previous_salary,
            "new_salary": record.new_salary,
            "increment_amount": record.increment_amount,
            "increment_percentage": record.increment_percentage,
            "effective_date": record.effective_date.isoformat(),
            "reason": record.reason,
            "notes": record.notes,
            "created_at": record.created_at.isoformat()
        })

    return history


@router.get("/documents/expiring-soon")
async def get_expiring_documents(
    days: int = Query(30, description="Days until expiry"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """Get documents expiring soon (passports, visas, etc)"""
    from sqlalchemy import select, and_
    from app.models.hrm import HRMEmployeeDocument, HRMEmployee
    from datetime import timedelta

    expiry_date = datetime.now().date() + timedelta(days=days)

    result = await db.execute(
        select(HRMEmployeeDocument, HRMEmployee)
        .join(HRMEmployee)
        .where(
            and_(
                HRMEmployeeDocument.expiry_date != None,
                HRMEmployeeDocument.expiry_date <= expiry_date
            )
        )
        .order_by(HRMEmployeeDocument.expiry_date)
    )

    expiring = []
    for doc, emp in result:
        expiring.append({
            "employee_name": emp.full_name,
            "employee_id": str(emp.id),
            "document_type": doc.document_type,
            "document_name": doc.document_name,
            "expiry_date": doc.expiry_date.isoformat(),
            "days_until_expiry": (doc.expiry_date - datetime.now().date()).days
        })

    return expiring