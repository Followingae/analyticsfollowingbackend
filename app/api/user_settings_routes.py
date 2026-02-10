"""
User Settings Routes - For users to manage their own profile and documents
"""
from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import base64
import json
import logging

from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.models.auth import UserInDB

router = APIRouter(tags=["User Settings"])
logger = logging.getLogger(__name__)

# Maximum file sizes
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB

# Allowed MIME types
ALLOWED_LOGO_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/svg+xml",
    "image/webp"
]

ALLOWED_DOCUMENT_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "text/plain"
]


@router.post("/upload-logo")
async def upload_user_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Upload company logo for current user

    - **file**: Logo image file (max 5MB, PNG/JPEG/GIF/SVG/WebP)

    Users can upload their own company logo which will be displayed in their profile.
    """
    try:
        # Validate file size
        contents = await file.read()
        if len(contents) > MAX_LOGO_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Logo file too large. Maximum size is {MAX_LOGO_SIZE // (1024*1024)}MB"
            )

        # Validate file type
        if file.content_type not in ALLOWED_LOGO_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_LOGO_TYPES)}"
            )

        # Generate a unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"logo_{current_user.id}_{uuid4().hex[:8]}.{file_extension}"

        # Convert to base64 data URL for storage
        base64_content = base64.b64encode(contents).decode('utf-8')
        data_url = f"data:{file.content_type};base64,{base64_content}"

        # Update user's company_logo_url
        await db.execute(
            text("""
                UPDATE users
                SET company_logo_url = :logo_url,
                    updated_at = NOW()
                WHERE id = :user_id
            """),
            {"user_id": current_user.id, "logo_url": data_url}
        )

        # Also store in user_documents table for tracking
        document_id = uuid4()
        await db.execute(
            text("""
                INSERT INTO user_documents (
                    id, user_id, document_type, file_name, file_url,
                    file_size, mime_type, uploaded_by, is_public, created_at
                )
                VALUES (
                    :id, :user_id, 'logo', :file_name, :file_url,
                    :file_size, :mime_type, :uploaded_by, true, NOW()
                )
            """),
            {
                "id": document_id,
                "user_id": current_user.id,
                "file_name": unique_filename,
                "file_url": data_url,
                "file_size": len(contents),
                "mime_type": file.content_type,
                "uploaded_by": current_user.id
            }
        )

        await db.commit()

        logger.info(f"Logo uploaded by user {current_user.email}")

        return {
            "message": "Logo uploaded successfully",
            "document_id": str(document_id),
            "file_name": unique_filename,
            "file_size": len(contents),
            "mime_type": file.content_type,
            "logo_url": data_url,
            "uploaded_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading logo for user {current_user.id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo"
        )


@router.post("/upload-document")
async def upload_user_document(
    document_type: str = Form(..., description="Type: contract, invoice, tax_document, verification, other"),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Upload a document to user's account

    - **document_type**: Type of document (contract, invoice, tax_document, verification, other)
    - **description**: Optional description of the document
    - **file**: Document file (max 10MB, PDF/Word/Excel/Image)

    Users can upload documents requested by their account manager or for verification purposes.
    """
    try:
        # Validate document type
        valid_types = ['contract', 'invoice', 'tax_document', 'verification', 'agreement', 'report', 'other']
        if document_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}"
            )

        # Validate file size
        contents = await file.read()
        if len(contents) > MAX_DOCUMENT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Document too large. Maximum size is {MAX_DOCUMENT_SIZE // (1024*1024)}MB"
            )

        # Validate file type
        if file.content_type not in ALLOWED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Invalid file type. Allowed types: PDF, Word, Excel, Images"
            )

        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        unique_filename = f"{document_type}_{current_user.id}_{uuid4().hex[:8]}.{file_extension}"

        # Convert to base64 data URL
        base64_content = base64.b64encode(contents).decode('utf-8')
        data_url = f"data:{file.content_type};base64,{base64_content}"

        # Store in user_documents table
        document_id = uuid4()
        await db.execute(
            text("""
                INSERT INTO user_documents (
                    id, user_id, document_type, file_name, file_url,
                    file_size, mime_type, description, uploaded_by,
                    is_public, metadata, created_at
                )
                VALUES (
                    :id, :user_id, :document_type, :file_name, :file_url,
                    :file_size, :mime_type, :description, :uploaded_by,
                    false, :metadata, NOW()
                )
            """),
            {
                "id": document_id,
                "user_id": current_user.id,
                "document_type": document_type,
                "file_name": unique_filename,
                "file_url": data_url,
                "file_size": len(contents),
                "mime_type": file.content_type,
                "description": description,
                "uploaded_by": current_user.id,
                "metadata": json.dumps({
                    "original_filename": file.filename,
                    "uploaded_by_email": current_user.email,
                    "upload_timestamp": datetime.utcnow().isoformat()
                })
            }
        )

        await db.commit()

        logger.info(f"Document ({document_type}) uploaded by user {current_user.email}")

        return {
            "message": "Document uploaded successfully",
            "document_id": str(document_id),
            "document_type": document_type,
            "file_name": unique_filename,
            "file_size": len(contents),
            "mime_type": file.content_type,
            "description": description,
            "document_url": data_url,
            "uploaded_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document for user {current_user.id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/my-documents")
async def list_my_documents(
    document_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    List all documents for current user

    - **document_type**: Optional filter by document type

    Returns list of user's uploaded documents with metadata
    """
    try:
        # Build query
        query_params = {"user_id": current_user.id}
        where_clause = "user_id = :user_id"

        if document_type:
            where_clause += " AND document_type = :document_type"
            query_params["document_type"] = document_type

        # Fetch documents
        result = await db.execute(
            text(f"""
                SELECT
                    id, document_type, file_name, file_size,
                    mime_type, description, is_public,
                    created_at, file_url
                FROM user_documents
                WHERE {where_clause}
                ORDER BY created_at DESC
            """),
            query_params
        )

        documents = []
        for row in result:
            documents.append({
                "id": str(row.id),
                "document_type": row.document_type,
                "file_name": row.file_name,
                "file_size": row.file_size,
                "mime_type": row.mime_type,
                "description": row.description,
                "is_public": row.is_public,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "document_url": row.file_url  # Direct data URL for user's own documents
            })

        # Get user's logo URL
        logo_result = await db.execute(
            text("SELECT company_logo_url FROM users WHERE id = :user_id"),
            {"user_id": current_user.id}
        )
        logo_row = logo_result.first()

        return {
            "user_id": str(current_user.id),
            "company_logo_url": logo_row.company_logo_url if logo_row else None,
            "documents": documents,
            "total_documents": len(documents)
        }

    except Exception as e:
        logger.error(f"Error listing documents for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.delete("/my-documents/{document_id}")
async def delete_my_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Delete a document uploaded by current user

    - **document_id**: UUID of the document to delete

    Users can only delete their own documents.
    """
    try:
        # Check if document exists and belongs to user
        check_result = await db.execute(
            text("""
                SELECT id, document_type, user_id
                FROM user_documents
                WHERE id = :document_id AND user_id = :user_id
            """),
            {"document_id": document_id, "user_id": current_user.id}
        )
        document = check_result.first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have permission to delete it"
            )

        # If it's a logo, also clear the user's company_logo_url
        if document.document_type == 'logo':
            await db.execute(
                text("UPDATE users SET company_logo_url = NULL WHERE id = :user_id"),
                {"user_id": current_user.id}
            )

        # Delete the document
        await db.execute(
            text("DELETE FROM user_documents WHERE id = :document_id"),
            {"document_id": document_id}
        )

        await db.commit()

        logger.info(f"Document {document_id} deleted by user {current_user.email}")

        return {
            "message": "Document deleted successfully",
            "document_id": str(document_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.get("/profile")
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get current user's complete profile including company details

    Returns all user profile information including company fields and document counts
    """
    try:
        # Get user details with credits
        user_result = await db.execute(
            text("""
                SELECT
                    u.id, u.email, u.full_name, u.company, u.job_title,
                    u.phone_number, u.industry, u.company_size, u.use_case,
                    u.marketing_budget, u.role, u.status, u.subscription_tier,
                    u.billing_type, u.company_logo_url, u.created_at,
                    cw.current_balance
                FROM users u
                LEFT JOIN credit_wallets cw ON cw.user_id::text = u.supabase_user_id
                WHERE u.id = :user_id
            """),
            {"user_id": current_user.id}
        )

        user = user_result.first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Count documents
        doc_count_result = await db.execute(
            text("SELECT COUNT(*) FROM user_documents WHERE user_id = :user_id"),
            {"user_id": current_user.id}
        )
        doc_count = doc_count_result.scalar() or 0

        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "company": user.company,
            "job_title": user.job_title,
            "phone_number": user.phone_number,
            "industry": user.industry,
            "company_size": user.company_size,
            "use_case": user.use_case,
            "marketing_budget": user.marketing_budget,
            "role": user.role,
            "status": user.status,
            "subscription_tier": user.subscription_tier,
            "billing_type": user.billing_type,
            "company_logo_url": user.company_logo_url,
            "current_balance": user.current_balance or 0,
            "document_count": doc_count,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "upload_endpoints": {
                "logo": "/api/v1/settings/upload-logo",
                "documents": "/api/v1/settings/upload-document",
                "list_documents": "/api/v1/settings/my-documents"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )