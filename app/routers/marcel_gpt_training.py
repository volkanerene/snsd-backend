"""
Marcel GPT Training - Incident Reports and GPT Training Generation
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission
from app.services.sharepoint_service import SharePointService
from app.services.training_generator_service import TrainingGeneratorService
from app.services.heygen_service import get_heygen_service

router = APIRouter()


class SyncSharePointRequest(BaseModel):
    force: bool = False


class GenerateTrainingRequest(BaseModel):
    title: str
    prompt: str
    avatar_id: str
    voice_id: str
    incident_report_ids: Optional[List[str]] = None
    config: Optional[dict] = None


# =========================================================================
# SharePoint Sync Endpoints
# =========================================================================

@router.post("/sync-sharepoint")
async def sync_sharepoint_reports(
    payload: SyncSharePointRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Trigger SharePoint sync to fetch incident reports
    Runs in background
    """
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Create sync log entry
    sync_log = supabase.table("marcel_gpt_sharepoint_sync_log").insert({
        "tenant_id": tenant_id,
        "sync_type": "manual",
        "status": "started"
    }).execute()

    sync_id = sync_log.data[0]["id"] if sync_log.data else None

    # Run sync in background
    background_tasks.add_task(
        run_sharepoint_sync,
        tenant_id,
        sync_id
    )

    return {
        "success": True,
        "sync_id": sync_id,
        "message": "SharePoint sync started in background"
    }


@router.get("/sync-status")
async def get_sync_status(
    user=Depends(get_current_user),
    limit: int = 10
):
    """Get recent SharePoint sync logs"""
    print(f"[Training] sync-status called by user: {user.get('id')}")
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = supabase.table("marcel_gpt_sharepoint_sync_log") \
        .select("*") \
        .eq("tenant_id", tenant_id) \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()

    return {
        "syncs": ensure_response(res),
        "count": len(res.data) if res.data else 0
    }


# =========================================================================
# Incident Reports Endpoints
# =========================================================================

@router.get("/incident-reports")
async def list_incident_reports(
    user=Depends(get_current_user),
    status: Optional[str] = None,
    incident_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List incident reports from SharePoint"""
    print(f"[Training] incident-reports called by user: {user.get('id')}, tenant: {user.get('tenant_id')}")
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("marcel_gpt_incident_reports") \
        .select("*") \
        .eq("tenant_id", tenant_id)

    if status:
        query = query.eq("processing_status", status)

    if incident_type:
        query = query.eq("incident_type", incident_type)

    query = query.order("uploaded_date", desc=True) \
        .range(offset, offset + limit - 1)

    res = query.execute()
    return {
        "reports": ensure_response(res),
        "count": len(res.data) if res.data else 0
    }


@router.get("/incident-reports/{report_id}")
async def get_incident_report(
    report_id: str,
    user=Depends(get_current_user)
):
    """Get a specific incident report"""
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = supabase.table("marcel_gpt_incident_reports") \
        .select("*") \
        .eq("id", report_id) \
        .eq("tenant_id", tenant_id) \
        .single() \
        .execute()

    if not res.data:
        raise HTTPException(404, "Report not found")

    return res.data


@router.post("/incident-reports/{report_id}/process")
async def process_incident_report(
    report_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Process an incident report (extract text, generate summary)
    Runs in background
    """
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Get report
    report_res = supabase.table("marcel_gpt_incident_reports") \
        .select("*") \
        .eq("id", report_id) \
        .eq("tenant_id", tenant_id) \
        .single() \
        .execute()

    if not report_res.data:
        raise HTTPException(404, "Report not found")

    # Mark as processing
    supabase.table("marcel_gpt_incident_reports") \
        .update({"processing_status": "processing"}) \
        .eq("id", report_id) \
        .execute()

    # Process in background
    background_tasks.add_task(
        process_report_background,
        tenant_id,
        report_id,
        report_res.data
    )

    return {
        "success": True,
        "message": "Report processing started"
    }


# =========================================================================
# Training Generation Endpoints
# =========================================================================

@router.post("/generate-training")
async def generate_training_script(
    payload: GenerateTrainingRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Generate training script from incident reports using GPT
    Then create HeyGen video
    """
    require_permission(user, "marcel_gpt.generate_training")

    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Create training session record
    session = supabase.table("marcel_gpt_training_sessions").insert({
        "tenant_id": tenant_id,
        "title": payload.title,
        "prompt": payload.prompt,
        "incident_report_ids": payload.incident_report_ids or [],
        "avatar_id": payload.avatar_id,
        "voice_id": payload.voice_id,
        "config": payload.config or {},
        "heygen_status": "pending",
        "created_by": user_id
    }).execute()

    session_id = session.data[0]["id"] if session.data else None

    # Generate training in background
    background_tasks.add_task(
        generate_training_background,
        tenant_id,
        session_id,
        payload
    )

    return {
        "success": True,
        "session_id": session_id,
        "message": "Training generation started"
    }


@router.get("/training-sessions")
async def list_training_sessions(
    user=Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """List training sessions"""
    print(f"[Training] training-sessions called by user: {user.get('id')}, tenant: {user.get('tenant_id')}")
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = supabase.table("marcel_gpt_training_sessions") \
        .select("""
            *,
            creator:created_by (
                id, full_name, email
            )
        """) \
        .eq("tenant_id", tenant_id) \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()

    return {
        "sessions": ensure_response(res),
        "count": len(res.data) if res.data else 0
    }


@router.get("/training-sessions/{session_id}")
async def get_training_session(
    session_id: str,
    user=Depends(get_current_user)
):
    """Get a specific training session"""
    require_permission(user, "marcel_gpt.view_training")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = supabase.table("marcel_gpt_training_sessions") \
        .select("*") \
        .eq("id", session_id) \
        .eq("tenant_id", tenant_id) \
        .single() \
        .execute()

    if not res.data:
        raise HTTPException(404, "Training session not found")

    return res.data


# =========================================================================
# Background Tasks
# =========================================================================

async def run_sharepoint_sync(tenant_id: str, sync_id: str):
    """Background task to sync SharePoint files"""
    try:
        sharepoint = SharePointService(tenant_id)
        results = await sharepoint.sync_incident_reports()

        # Update sync log
        supabase.table("marcel_gpt_sharepoint_sync_log") \
            .update({
                "status": "completed",
                "files_found": results['total_found'],
                "files_processed": results['new_files'] + results['updated_files'],
                "files_failed": results['failed'],
                "completed_at": datetime.now().isoformat(),
                "metadata": results
            }) \
            .eq("id", sync_id) \
            .execute()

    except Exception as e:
        # Update sync log with error
        supabase.table("marcel_gpt_sharepoint_sync_log") \
            .update({
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now().isoformat()
            }) \
            .eq("id", sync_id) \
            .execute()


async def process_report_background(tenant_id: str, report_id: str, report_data: dict):
    """Background task to process incident report"""
    try:
        generator = TrainingGeneratorService(tenant_id)

        # If we have text content, use it; otherwise try to download and extract
        text_content = report_data.get('text_content')

        if not text_content:
            # TODO: Download PDF and extract text
            # For now, skip if no text content
            raise Exception("No text content available")

        # Generate summary and extract metadata
        analysis = await generator.summarize_incident_report(text_content)

        # Update report with analysis
        supabase.table("marcel_gpt_incident_reports") \
            .update({
                "summary": analysis['summary'],
                "incident_type": analysis['incident_type'],
                "severity": analysis['severity'],
                "keywords": analysis['keywords'],
                "processing_status": "completed",
                "last_processed_at": datetime.now().isoformat()
            }) \
            .eq("id", report_id) \
            .execute()

    except Exception as e:
        # Update with error
        supabase.table("marcel_gpt_incident_reports") \
            .update({
                "processing_status": "failed",
                "error_message": str(e),
                "last_processed_at": datetime.now().isoformat()
            }) \
            .eq("id", report_id) \
            .execute()


async def generate_training_background(tenant_id: str, session_id: str, payload: GenerateTrainingRequest):
    """Background task to generate training script and video"""
    try:
        generator = TrainingGeneratorService(tenant_id)

        # Get incident reports
        incident_reports = []
        if payload.incident_report_ids:
            res = supabase.table("marcel_gpt_incident_reports") \
                .select("*") \
                .in_("id", payload.incident_report_ids) \
                .execute()
            incident_reports = res.data or []
        else:
            # Use recent reports
            incident_reports = await generator.retrieve_relevant_reports(payload.prompt)

        # Generate training script
        script_result = await generator.generate_training_script(
            prompt=payload.prompt,
            incident_reports=incident_reports
        )

        # Update session with generated text
        supabase.table("marcel_gpt_training_sessions") \
            .update({
                "generated_text": script_result['script'],
                "heygen_status": "processing"
            }) \
            .eq("id", session_id) \
            .execute()

        # Create HeyGen video
        heygen = get_heygen_service(tenant_id)
        if heygen:
            video_result = await heygen.create_video_from_text(
                text=script_result['script'],
                avatar_id=payload.avatar_id,
                voice_id=payload.voice_id
            )

            # Update session with video info
            supabase.table("marcel_gpt_training_sessions") \
                .update({
                    "heygen_video_id": video_result.get('video_id'),
                    "video_url": video_result.get('video_url'),
                    "heygen_status": "completed",
                    "updated_at": datetime.now().isoformat()
                }) \
                .eq("id", session_id) \
                .execute()

    except Exception as e:
        # Update with error
        supabase.table("marcel_gpt_training_sessions") \
            .update({
                "heygen_status": "failed",
                "updated_at": datetime.now().isoformat()
            }) \
            .eq("id", session_id) \
            .execute()
