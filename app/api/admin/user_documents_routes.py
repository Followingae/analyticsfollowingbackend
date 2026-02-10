"""
User Documents and Logo Upload Routes
Handles company logos and document uploads for users
"""
from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import logging
import base64
import json

from app.middleware.auth_middleware import get_current_active_user, require_admin
from app.database.connection import get_db

router = APIRouter(tags=["User Documents"])
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


@router.post("/users/{user_id}/upload-logo")
async def upload_company_logo(
    user_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """
    Upload company logo for a user

    - **user_id**: UUID of the user
    - **file**: Logo image file (max 5MB, PNG/JPEG/GIF/SVG/WebP)

    Returns the URL of the uploaded logo
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
        unique_filename = f"logo_{user_id}_{uuid4().hex[:8]}.{file_extension}"

        # Upload to Cloudflare R2 (same as influencer images)
        from app.infrastructure.r2_storage_client import R2StorageClient
        import os

        r2_client = R2StorageClient(
            account_id=os.getenv("CF_ACCOUNT_ID"),
            access_key=os.getenv("R2_ACCESS_KEY_ID"),
            secret_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            bucket_name="thumbnails-prod"
        )

        # Generate R2 key for logo
        r2_key = f"logos/users/{user_id}/{unique_filename}"

        # Upload to R2
        upload_success = await r2_client.upload_object(
            key=r2_key,
            content=contents,
            content_type=file.content_type,
            metadata={
                'user_id': str(user_id),
                'uploaded_by': current_user.email,
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )

        if not upload_success:
            raise HTTPException(status_code=500, detail="Failed to upload to CDN")

        # Generate CDN URL
        cdn_url = f"https://cdn.following.ae/{r2_key}"

        # Check if user exists
        user_check = await db.execute(
            text("SELECT id, email FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = user_check.first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user's company_logo_url
        await db.execute(
            text("""
                UPDATE users
                SET company_logo_url = :logo_url,
                    updated_at = NOW()
                WHERE id = :user_id
            """),
            {"user_id": user_id, "logo_url": cdn_url}
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
                "user_id": user_id,
                "file_name": unique_filename,
                "file_url": cdn_url,
                "file_size": len(contents),
                "mime_type": file.content_type,
                "uploaded_by": current_user.id
            }
        )

        await db.commit()

        logger.info(f"Logo uploaded for user {user_id} by admin {current_user.email}")

        return {
            "message": "Logo uploaded successfully",
            "document_id": str(document_id),
            "file_name": unique_filename,
            "file_size": len(contents),
            "mime_type": file.content_type,
            "logo_url": cdn_url,
            "uploaded_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading logo for user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload logo"
        )


@router.post("/users/{user_id}/upload-document")
async def upload_user_document(
    user_id: UUID,
    document_type: str = Form(..., description="Type: contract, invoice, tax_document, other"),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """
    Upload a document for a user (contracts, invoices, tax documents, etc.)

    - **user_id**: UUID of the user
    - **document_type**: Type of document (contract, invoice, tax_document, other)
    - **description**: Optional description of the document
    - **file**: Document file (max 10MB, PDF/Word/Excel/Image)

    Returns document details and URL
    """
    try:
        # Validate document type
        valid_types = ['contract', 'invoice', 'tax_document', 'other', 'agreement', 'report']
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

        # Check if user exists
        user_check = await db.execute(
            text("SELECT id, email FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = user_check.first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        unique_filename = f"{document_type}_{user_id}_{uuid4().hex[:8]}.{file_extension}"

        # Upload to Cloudflare R2 (same as influencer images)
        from app.infrastructure.r2_storage_client import R2StorageClient
        import os

        r2_client = R2StorageClient(
            account_id=os.getenv("CF_ACCOUNT_ID"),
            access_key=os.getenv("R2_ACCESS_KEY_ID"),
            secret_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            bucket_name="thumbnails-prod"
        )

        # Generate R2 key for document
        r2_key = f"documents/users/{user_id}/{document_type}/{unique_filename}"

        # Upload to R2
        upload_success = await r2_client.upload_object(
            key=r2_key,
            content=contents,
            content_type=file.content_type,
            metadata={
                'user_id': str(user_id),
                'document_type': document_type,
                'uploaded_by': current_user.email,
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )

        if not upload_success:
            raise HTTPException(status_code=500, detail="Failed to upload to CDN")

        # Generate CDN URL
        cdn_url = f"https://cdn.following.ae/{r2_key}"

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
                "user_id": user_id,
                "document_type": document_type,
                "file_name": unique_filename,
                "file_url": cdn_url,
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

        logger.info(f"Document ({document_type}) uploaded for user {user_id} by admin {current_user.email}")

        return {
            "message": "Document uploaded successfully",
            "document_id": str(document_id),
            "document_type": document_type,
            "file_name": unique_filename,
            "file_size": len(contents),
            "mime_type": file.content_type,
            "description": description,
            "document_url": cdn_url,
            "uploaded_at": datetime.utcnow().isoformat(),
            "uploaded_by": current_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document for user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/users/{user_id}/documents")
async def list_user_documents(
    user_id: UUID,
    document_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """
    List all documents for a user

    - **user_id**: UUID of the user
    - **document_type**: Optional filter by document type

    Returns list of documents with metadata
    """
    try:
        # Build query
        query_params = {"user_id": user_id}
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
                    created_at, uploaded_by
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
                "download_url": f"/api/v1/admin/documents/{row.id}/download"
            })

        # Get user's logo URL
        logo_result = await db.execute(
            text("SELECT company_logo_url FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        logo_row = logo_result.first()

        return {
            "user_id": str(user_id),
            "company_logo_url": logo_row.company_logo_url if logo_row else None,
            "documents": documents,
            "total_documents": len(documents)
        }

    except Exception as e:
        logger.error(f"Error listing documents for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """
    Download/retrieve a specific document

    - **document_id**: UUID of the document

    Returns the document URL/content
    """
    try:
        result = await db.execute(
            text("""
                SELECT file_url, file_name, mime_type, user_id
                FROM user_documents
                WHERE id = :document_id
            """),
            {"document_id": document_id}
        )

        document = result.first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "document_id": str(document_id),
            "file_name": document.file_name,
            "mime_type": document.mime_type,
            "file_url": document.file_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin())
):
    """
    Delete a document

    - **document_id**: UUID of the document to delete
    """
    try:
        # Check if document exists
        check_result = await db.execute(
            text("SELECT id, document_type, user_id FROM user_documents WHERE id = :document_id"),
            {"document_id": document_id}
        )
        document = check_result.first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # If it's a logo, also clear the user's company_logo_url
        if document.document_type == 'logo':
            await db.execute(
                text("UPDATE users SET company_logo_url = NULL WHERE id = :user_id"),
                {"user_id": document.user_id}
            )

        # Delete the document
        await db.execute(
            text("DELETE FROM user_documents WHERE id = :document_id"),
            {"document_id": document_id}
        )

        await db.commit()

        logger.info(f"Document {document_id} deleted by admin {current_user.email}")

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