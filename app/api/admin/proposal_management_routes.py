"""
Admin Proposal Management API Routes
Comprehensive proposal creation and management for super admins and admins
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date
from pydantic import BaseModel, Field

from app.middleware.role_based_auth import (
    get_current_user_with_permissions,
    requires_permission,
    auth_service,
    audit_action
)
from app.database.connection import get_db
from app.database.unified_models import (
    AdminBrandProposals, ProposalTemplates, ProposalAnalytics, Users
)

router = APIRouter(prefix="/admin/proposals", tags=["Admin - Proposal Management"])

# Pydantic Models
class ProposalCreateRequest(BaseModel):
    brand_user_id: UUID
    proposal_title: str = Field(..., min_length=1, max_length=200)
    proposal_description: str = Field(..., min_length=1, max_length=2000)
    service_type: str = Field(..., min_length=1, max_length=100)
    proposed_budget_usd: float = Field(..., gt=0)
    proposed_start_date: Optional[datetime] = None
    proposed_end_date: Optional[datetime] = None
    brand_response_due_date: Optional[datetime] = None
    priority_level: str = Field(default="medium", regex="^(low|medium|high|urgent)$")
    deliverables: Optional[List[str]] = None
    terms_conditions: Optional[str] = None
    template_id: Optional[UUID] = None

class ProposalUpdateRequest(BaseModel):
    proposal_title: Optional[str] = Field(None, min_length=1, max_length=200)
    proposal_description: Optional[str] = Field(None, min_length=1, max_length=2000)
    service_type: Optional[str] = None
    proposed_budget_usd: Optional[float] = Field(None, gt=0)
    status: Optional[str] = Field(None, regex="^(draft|sent|viewed|under_review|accepted|rejected|revised)$")
    proposed_start_date: Optional[datetime] = None
    proposed_end_date: Optional[datetime] = None
    brand_response_due_date: Optional[datetime] = None
    priority_level: Optional[str] = Field(None, regex="^(low|medium|high|urgent)$")
    admin_notes: Optional[str] = None

class TemplateCreateRequest(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=200)
    service_type: str = Field(..., min_length=1, max_length=100)
    template_content: Dict[str, Any] = Field(..., description="Template content structure")
    default_pricing: Optional[Dict[str, Any]] = None
    default_deliverables: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_default: bool = False

class ProposalResponse(BaseModel):
    id: str
    brand_user_id: str
    brand_user_email: str
    proposal_title: str
    service_type: str
    proposed_budget_usd: float
    status: str
    priority_level: str
    created_at: datetime
    brand_response_due_date: Optional[datetime]
    last_viewed_at: Optional[datetime]

class ProposalDetailResponse(ProposalResponse):
    proposal_description: str
    proposed_start_date: Optional[datetime]
    proposed_end_date: Optional[datetime]
    deliverables: Optional[List[str]]
    terms_conditions: Optional[str]
    admin_notes: Optional[str]
    template_id: Optional[str]
    created_by: Optional[str]

class TemplateResponse(BaseModel):
    id: str
    template_name: str
    service_type: str
    usage_count: int
    success_rate: Optional[float]
    is_active: bool
    is_default: bool
    created_at: datetime

class ProposalAnalyticsResponse(BaseModel):
    total_proposals: int
    proposals_by_status: Dict[str, int]
    average_response_time_days: float
    acceptance_rate: float
    revenue_generated: float
    top_performing_templates: List[Dict[str, Any]]
    monthly_proposal_trends: List[Dict[str, Any]]

@router.get("/analytics", response_model=ProposalAnalyticsResponse)
@requires_permission("can_view_proposal_analytics")
@audit_action("view_proposal_analytics")
async def get_proposal_analytics(
    period_days: int = Query(90, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive proposal analytics"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Total proposals count
    total_query = select(func.count(AdminBrandProposals.id)).where(
        AdminBrandProposals.created_at >= cutoff_date
    )
    total_result = await db.execute(total_query)
    total_proposals = total_result.scalar()
    
    # Proposals by status
    status_query = select(
        AdminBrandProposals.status,
        func.count(AdminBrandProposals.id).label('count')
    ).where(
        AdminBrandProposals.created_at >= cutoff_date
    ).group_by(AdminBrandProposals.status)
    
    status_result = await db.execute(status_query)
    proposals_by_status = {row.status: row.count for row in status_result.all()}
    
    # Average response time (for proposals that got responses)
    response_time_query = select(
        func.avg(
            func.extract('epoch', AdminBrandProposals.updated_at - AdminBrandProposals.created_at) / 86400
        ).label('avg_days')
    ).where(
        and_(
            AdminBrandProposals.created_at >= cutoff_date,
            AdminBrandProposals.status.in_(['accepted', 'rejected', 'under_review'])
        )
    )
    
    response_time_result = await db.execute(response_time_query)
    avg_response_time = float(response_time_result.scalar() or 0)
    
    # Acceptance rate
    accepted_count = proposals_by_status.get('accepted', 0)
    responded_count = sum(proposals_by_status.get(status, 0) for status in ['accepted', 'rejected'])
    acceptance_rate = (accepted_count / responded_count * 100) if responded_count > 0 else 0
    
    # Revenue generated from accepted proposals
    revenue_query = select(
        func.sum(AdminBrandProposals.proposed_budget_usd)
    ).where(
        and_(
            AdminBrandProposals.created_at >= cutoff_date,
            AdminBrandProposals.status == 'accepted'
        )
    )
    
    revenue_result = await db.execute(revenue_query)
    revenue_generated = float(revenue_result.scalar() or 0)
    
    # Top performing templates
    template_performance_query = select(
        ProposalTemplates.id,
        ProposalTemplates.template_name,
        ProposalTemplates.service_type,
        ProposalTemplates.usage_count,
        ProposalTemplates.success_rate
    ).where(
        ProposalTemplates.is_active == True
    ).order_by(desc(ProposalTemplates.success_rate)).limit(5)
    
    template_result = await db.execute(template_performance_query)
    top_templates = [
        {
            "id": str(row.id),
            "name": row.template_name,
            "service_type": row.service_type,
            "usage_count": row.usage_count,
            "success_rate": float(row.success_rate or 0)
        }
        for row in template_result.all()
    ]
    
    # Monthly proposal trends (last 12 months)
    monthly_trends_query = select(
        func.date_trunc('month', AdminBrandProposals.created_at).label('month'),
        func.count(AdminBrandProposals.id).label('proposal_count'),
        func.sum(
            func.case([(AdminBrandProposals.status == 'accepted', 1)], else_=0)
        ).label('accepted_count')
    ).where(
        AdminBrandProposals.created_at >= datetime.utcnow() - timedelta(days=365)
    ).group_by('month').order_by('month')
    
    trends_result = await db.execute(monthly_trends_query)
    monthly_trends = [
        {
            "month": row.month.strftime('%Y-%m'),
            "proposal_count": row.proposal_count,
            "accepted_count": row.accepted_count,
            "acceptance_rate": (row.accepted_count / row.proposal_count * 100) if row.proposal_count > 0 else 0
        }
        for row in trends_result.all()
    ]
    
    return ProposalAnalyticsResponse(
        total_proposals=total_proposals,
        proposals_by_status=proposals_by_status,
        average_response_time_days=avg_response_time,
        acceptance_rate=acceptance_rate,
        revenue_generated=revenue_generated,
        top_performing_templates=top_templates,
        monthly_proposal_trends=monthly_trends
    )

@router.get("/", response_model=List[ProposalResponse])
@requires_permission("can_view_all_proposals")
@audit_action("view_all_proposals")
async def get_all_proposals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    priority_level: Optional[str] = Query(None),
    brand_user_email: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get all proposals with filtering and pagination"""
    
    # Build query with join to Users
    query = select(AdminBrandProposals, Users.email).join(
        Users, AdminBrandProposals.brand_user_id == Users.id
    )
    
    # Apply filters
    conditions = []
    
    if status:
        conditions.append(AdminBrandProposals.status == status)
    
    if service_type:
        conditions.append(AdminBrandProposals.service_type.icontains(service_type))
    
    if priority_level:
        conditions.append(AdminBrandProposals.priority_level == priority_level)
    
    if brand_user_email:
        conditions.append(Users.email.icontains(brand_user_email))
    
    if date_from:
        conditions.append(AdminBrandProposals.created_at >= datetime.combine(date_from, datetime.min.time()))
    
    if date_to:
        conditions.append(AdminBrandProposals.created_at <= datetime.combine(date_to, datetime.max.time()))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(desc(AdminBrandProposals.created_at)).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    proposals_data = result.all()
    
    # Format response
    proposals = []
    for proposal, user_email in proposals_data:
        proposals.append(ProposalResponse(
            id=str(proposal.id),
            brand_user_id=str(proposal.brand_user_id),
            brand_user_email=user_email,
            proposal_title=proposal.proposal_title,
            service_type=proposal.service_type,
            proposed_budget_usd=float(proposal.proposed_budget_usd),
            status=proposal.status,
            priority_level=proposal.priority_level,
            created_at=proposal.created_at,
            brand_response_due_date=proposal.brand_response_due_date,
            last_viewed_at=proposal.last_viewed_at
        ))
    
    return proposals

@router.post("/", response_model=ProposalDetailResponse)
@requires_permission("can_create_proposals")
@audit_action("create_proposal")
async def create_proposal(
    proposal_data: ProposalCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Create a new proposal for a brand user"""
    
    # Verify brand user exists
    user_query = select(Users).where(Users.id == proposal_data.brand_user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand user not found"
        )
    
    try:
        # Create new proposal
        new_proposal = AdminBrandProposals(
            brand_user_id=proposal_data.brand_user_id,
            proposal_title=proposal_data.proposal_title,
            proposal_description=proposal_data.proposal_description,
            service_type=proposal_data.service_type,
            proposed_budget_usd=proposal_data.proposed_budget_usd,
            proposed_start_date=proposal_data.proposed_start_date,
            proposed_end_date=proposal_data.proposed_end_date,
            brand_response_due_date=proposal_data.brand_response_due_date,
            priority_level=proposal_data.priority_level,
            deliverables=proposal_data.deliverables,
            terms_conditions=proposal_data.terms_conditions,
            template_id=proposal_data.template_id,
            created_by=UUID(current_user["id"]),
            status="draft"
        )
        
        db.add(new_proposal)
        await db.flush()
        
        # Update template usage count if template was used
        if proposal_data.template_id:
            template_query = select(ProposalTemplates).where(ProposalTemplates.id == proposal_data.template_id)
            template_result = await db.execute(template_query)
            template = template_result.scalar()
            if template:
                template.usage_count += 1
        
        await db.commit()
        
        # Log proposal creation analytics
        analytics_entry = ProposalAnalytics(
            proposal_id=new_proposal.id,
            event_type="created",
            event_data={
                "created_by": current_user["email"],
                "service_type": proposal_data.service_type,
                "budget_usd": float(proposal_data.proposed_budget_usd)
            }
        )
        
        db.add(analytics_entry)
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="proposal_create",
            target_user_id=proposal_data.brand_user_id,
            new_values={
                "proposal_id": str(new_proposal.id),
                "title": proposal_data.proposal_title,
                "budget_usd": float(proposal_data.proposed_budget_usd)
            },
            reason="Proposal created via admin panel",
            db=db
        )
        
        await db.commit()
        
        # Return created proposal details
        return await get_proposal_details(new_proposal.id, current_user, db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create proposal: {str(e)}"
        )

@router.get("/{proposal_id}", response_model=ProposalDetailResponse)
@requires_permission("can_view_all_proposals")
@audit_action("view_proposal_details")
async def get_proposal_details(
    proposal_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific proposal"""
    
    # Get proposal with user details
    query = select(AdminBrandProposals, Users.email).join(
        Users, AdminBrandProposals.brand_user_id == Users.id
    ).where(AdminBrandProposals.id == proposal_id)
    
    result = await db.execute(query)
    proposal_data = result.first()
    
    if not proposal_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    proposal, user_email = proposal_data
    
    # Get creator info
    created_by_name = None
    if proposal.created_by:
        creator_query = select(Users.email).where(Users.id == proposal.created_by)
        creator_result = await db.execute(creator_query)
        created_by_name = creator_result.scalar()
    
    return ProposalDetailResponse(
        id=str(proposal.id),
        brand_user_id=str(proposal.brand_user_id),
        brand_user_email=user_email,
        proposal_title=proposal.proposal_title,
        proposal_description=proposal.proposal_description,
        service_type=proposal.service_type,
        proposed_budget_usd=float(proposal.proposed_budget_usd),
        status=proposal.status,
        priority_level=proposal.priority_level,
        created_at=proposal.created_at,
        proposed_start_date=proposal.proposed_start_date,
        proposed_end_date=proposal.proposed_end_date,
        brand_response_due_date=proposal.brand_response_due_date,
        deliverables=proposal.deliverables,
        terms_conditions=proposal.terms_conditions,
        admin_notes=proposal.admin_notes,
        template_id=str(proposal.template_id) if proposal.template_id else None,
        created_by=created_by_name,
        last_viewed_at=proposal.last_viewed_at
    )

@router.put("/{proposal_id}", response_model=ProposalDetailResponse)
@requires_permission("can_create_proposals")
@audit_action("update_proposal")
async def update_proposal(
    proposal_id: UUID,
    proposal_updates: ProposalUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Update proposal details"""
    
    # Get existing proposal
    query = select(AdminBrandProposals).where(AdminBrandProposals.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar()
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found"
        )
    
    # Store old values for audit
    old_values = {
        "status": proposal.status,
        "budget_usd": float(proposal.proposed_budget_usd),
        "priority_level": proposal.priority_level
    }
    
    try:
        # Update proposal fields
        update_data = proposal_updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(proposal, field):
                setattr(proposal, field, value)
        
        proposal.updated_at = datetime.utcnow()
        
        await db.commit()
        
        # Log analytics event if status changed
        if 'status' in update_data:
            analytics_entry = ProposalAnalytics(
                proposal_id=proposal_id,
                event_type="status_changed",
                event_data={
                    "old_status": old_values["status"],
                    "new_status": update_data["status"],
                    "changed_by": current_user["email"]
                }
            )
            db.add(analytics_entry)
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="proposal_update",
            target_user_id=proposal.brand_user_id,
            old_values=old_values,
            new_values=update_data,
            reason="Proposal updated via admin panel",
            db=db
        )
        
        await db.commit()
        
        # Return updated proposal details
        return await get_proposal_details(proposal_id, current_user, db)
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update proposal: {str(e)}"
        )

@router.get("/templates/", response_model=List[TemplateResponse])
@requires_permission("can_manage_templates")
@audit_action("view_proposal_templates")
async def get_proposal_templates(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    service_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Get all proposal templates"""
    
    # Build query
    query = select(ProposalTemplates)
    
    # Apply filters
    conditions = []
    
    if service_type:
        conditions.append(ProposalTemplates.service_type.icontains(service_type))
    
    if is_active is not None:
        conditions.append(ProposalTemplates.is_active == is_active)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(desc(ProposalTemplates.usage_count)).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    templates = result.scalars().all()
    
    # Format response
    template_list = []
    for template in templates:
        template_list.append(TemplateResponse(
            id=str(template.id),
            template_name=template.template_name,
            service_type=template.service_type,
            usage_count=template.usage_count,
            success_rate=float(template.success_rate) if template.success_rate else None,
            is_active=template.is_active,
            is_default=template.is_default,
            created_at=template.created_at
        ))
    
    return template_list

@router.post("/templates/", response_model=TemplateResponse)
@requires_permission("can_manage_templates")
@audit_action("create_proposal_template")
async def create_proposal_template(
    template_data: TemplateCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_with_permissions),
    db: AsyncSession = Depends(get_db)
):
    """Create a new proposal template"""
    
    try:
        # Create new template
        new_template = ProposalTemplates(
            template_name=template_data.template_name,
            service_type=template_data.service_type,
            template_content=template_data.template_content,
            default_pricing=template_data.default_pricing or {},
            default_deliverables=template_data.default_deliverables or [],
            tags=template_data.tags or [],
            is_default=template_data.is_default,
            created_by=UUID(current_user["id"]),
            is_active=True,
            usage_count=0
        )
        
        db.add(new_template)
        await db.commit()
        
        # Log admin action
        await auth_service.log_admin_action(
            admin_user_id=UUID(current_user["id"]),
            action_type="template_create",
            new_values={
                "template_id": str(new_template.id),
                "template_name": template_data.template_name,
                "service_type": template_data.service_type
            },
            reason="Template created via admin panel",
            db=db
        )
        
        return TemplateResponse(
            id=str(new_template.id),
            template_name=new_template.template_name,
            service_type=new_template.service_type,
            usage_count=new_template.usage_count,
            success_rate=None,
            is_active=new_template.is_active,
            is_default=new_template.is_default,
            created_at=new_template.created_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)}"
        )