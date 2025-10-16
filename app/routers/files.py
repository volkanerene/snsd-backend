"""
File Management Router
Handles all S3 file operations including upload, download, delete, and folder management.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import io

from app.utils.s3_client import get_s3_client, S3Client
from app.utils.auth import require_auth

router = APIRouter(prefix="/files", tags=["files"])


# Request/Response Models
class FileUploadResponse(BaseModel):
    success: bool
    bucket: str
    key: str
    url: str
    region: str


class FileMetadata(BaseModel):
    key: str
    size: int
    content_type: Optional[str] = None
    last_modified: str
    etag: str
    metadata: dict = {}


class FileListItem(BaseModel):
    key: str
    size: Optional[int] = None
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    type: Optional[str] = "file"


class DeleteResponse(BaseModel):
    success: bool
    deleted: List[dict]
    errors: List[dict]


class PresignedUrlResponse(BaseModel):
    url: str
    expires_in: int


class FolderCreateResponse(BaseModel):
    success: bool
    folder_path: str


# Routes
@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    folder: Optional[str] = Query(None, description="Folder path to upload to"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """
    Upload a file to S3

    - **file**: File to upload
    - **folder**: Optional folder path (e.g., "documents", "images/profile")
    - Automatically organizes files by tenant_id
    """
    try:
        # Construct object key with tenant organization
        base_path = f"tenants/{tenant_id}"
        if folder:
            folder = folder.strip("/")
            object_key = f"{base_path}/{folder}/{file.filename}"
        else:
            object_key = f"{base_path}/{file.filename}"

        # Upload file
        result = s3.upload_file(
            file_obj=file.file,
            object_key=object_key,
            content_type=file.content_type,
            metadata={
                "tenant_id": tenant_id,
                "original_filename": file.filename
            }
        )

        return FileUploadResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-multiple")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    folder: Optional[str] = Query(None, description="Folder path to upload to"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Upload multiple files at once"""
    try:
        results = []
        base_path = f"tenants/{tenant_id}"

        for file in files:
            if folder:
                folder_clean = folder.strip("/")
                object_key = f"{base_path}/{folder_clean}/{file.filename}"
            else:
                object_key = f"{base_path}/{file.filename}"

            result = s3.upload_file(
                file_obj=file.file,
                object_key=object_key,
                content_type=file.content_type,
                metadata={
                    "tenant_id": tenant_id,
                    "original_filename": file.filename
                }
            )
            results.append(result)

        return {"success": True, "uploaded": len(results), "files": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{file_path:path}")
async def download_file(
    file_path: str,
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """
    Download a file from S3

    - **file_path**: Path to the file within your tenant folder
    """
    try:
        # Construct full object key
        object_key = f"tenants/{tenant_id}/{file_path}"

        # Check if file exists
        if not s3.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")

        # Get file content
        file_content = s3.get_file_content(object_key)

        # Get metadata for content type
        metadata = s3.get_file_metadata(object_key)

        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=metadata.get("content_type", "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="{file_path.split("/")[-1]}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{file_path:path}")
async def delete_file(
    file_path: str,
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Delete a file from S3"""
    try:
        object_key = f"tenants/{tenant_id}/{file_path}"

        if not s3.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")

        s3.delete_file(object_key)

        return {"success": True, "message": "File deleted successfully", "key": object_key}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-multiple", response_model=DeleteResponse)
async def delete_multiple_files(
    file_paths: List[str],
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Delete multiple files at once"""
    try:
        object_keys = [f"tenants/{tenant_id}/{path}" for path in file_paths]
        result = s3.delete_files(object_keys)

        return DeleteResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[FileListItem])
async def list_files(
    folder: Optional[str] = Query(None, description="Folder path to list"),
    max_keys: int = Query(1000, le=1000, description="Maximum number of files to return"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """List files in a folder"""
    try:
        base_path = f"tenants/{tenant_id}"
        if folder:
            folder = folder.strip("/")
            prefix = f"{base_path}/{folder}/"
        else:
            prefix = f"{base_path}/"

        files = s3.list_files(prefix=prefix, max_keys=max_keys, delimiter="/")

        # Remove tenant prefix from keys for cleaner response
        for file in files:
            if file["key"].startswith(base_path + "/"):
                file["key"] = file["key"][len(base_path) + 1:]

        return files

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata/{file_path:path}", response_model=FileMetadata)
async def get_file_metadata(
    file_path: str,
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Get file metadata"""
    try:
        object_key = f"tenants/{tenant_id}/{file_path}"

        if not s3.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")

        metadata = s3.get_file_metadata(object_key)

        return FileMetadata(**metadata)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folder/create", response_model=FolderCreateResponse)
async def create_folder(
    folder_path: str = Query(..., description="Folder path to create"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Create a new folder"""
    try:
        full_path = f"tenants/{tenant_id}/{folder_path.strip('/')}"
        s3.create_folder(full_path)

        return FolderCreateResponse(success=True, folder_path=folder_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/folder/delete")
async def delete_folder(
    folder_path: str = Query(..., description="Folder path to delete"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Delete a folder and all its contents"""
    try:
        full_path = f"tenants/{tenant_id}/{folder_path.strip('/')}"
        result = s3.delete_folder(full_path)

        return {
            "success": True,
            "message": "Folder deleted successfully",
            "details": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy")
async def copy_file(
    source_path: str = Query(..., description="Source file path"),
    destination_path: str = Query(..., description="Destination file path"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Copy a file to a new location"""
    try:
        source_key = f"tenants/{tenant_id}/{source_path}"
        dest_key = f"tenants/{tenant_id}/{destination_path}"

        if not s3.file_exists(source_key):
            raise HTTPException(status_code=404, detail="Source file not found")

        s3.copy_file(source_key, dest_key)

        return {
            "success": True,
            "message": "File copied successfully",
            "source": source_path,
            "destination": destination_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/move")
async def move_file(
    source_path: str = Query(..., description="Source file path"),
    destination_path: str = Query(..., description="Destination file path"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Move a file to a new location"""
    try:
        source_key = f"tenants/{tenant_id}/{source_path}"
        dest_key = f"tenants/{tenant_id}/{destination_path}"

        if not s3.file_exists(source_key):
            raise HTTPException(status_code=404, detail="Source file not found")

        s3.move_file(source_key, dest_key)

        return {
            "success": True,
            "message": "File moved successfully",
            "source": source_path,
            "destination": destination_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presigned-url/{file_path:path}", response_model=PresignedUrlResponse)
async def get_presigned_url(
    file_path: str,
    expiration: int = Query(3600, le=604800, description="URL expiration in seconds (max 7 days)"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Generate a presigned URL for temporary file access"""
    try:
        object_key = f"tenants/{tenant_id}/{file_path}"

        if not s3.file_exists(object_key):
            raise HTTPException(status_code=404, detail="File not found")

        url = s3.generate_presigned_url(
            object_key=object_key,
            expiration=expiration,
            http_method="GET"
        )

        return PresignedUrlResponse(url=url, expires_in=expiration)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/presigned-upload")
async def get_presigned_upload_url(
    file_path: str = Query(..., description="Destination file path"),
    expiration: int = Query(3600, le=3600, description="URL expiration in seconds (max 1 hour)"),
    max_file_size: int = Query(10485760, le=104857600, description="Max file size in bytes (max 100MB)"),
    tenant_id: str = Depends(require_auth),
    s3: S3Client = Depends(get_s3_client)
):
    """Generate presigned POST data for direct browser upload"""
    try:
        object_key = f"tenants/{tenant_id}/{file_path}"

        presigned_data = s3.generate_presigned_post(
            object_key=object_key,
            expiration=expiration,
            max_file_size=max_file_size
        )

        return {
            "success": True,
            "url": presigned_data["url"],
            "fields": presigned_data["fields"],
            "expires_in": expiration
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
