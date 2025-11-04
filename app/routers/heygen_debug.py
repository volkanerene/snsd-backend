"""
HeyGen API Debug/Test Router
Test all HeyGen endpoints and see raw data
"""
from fastapi import APIRouter, Depends
from app.utils.auth import get_current_user
from app.services.heygen_service import HeyGenService
from app.db.supabase_client import supabase

router = APIRouter(prefix="/heygen-debug", tags=["HeyGen Debug"])


@router.get("/test-all")
async def test_all_heygen_endpoints(user=Depends(get_current_user)):
    """
    Test ALL HeyGen API endpoints and return raw data
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant_id"}

    # Get HeyGen API key for tenant
    tenant_res = supabase.table("tenants").select("heygen_api_key").eq("id", tenant_id).single().execute()
    api_key = tenant_res.data.get("heygen_api_key") if tenant_res.data else None

    if not api_key:
        return {"error": "No HeyGen API key configured for tenant"}

    heygen = HeyGenService(api_key)
    results = {}

    # 1. Test /v2/avatars
    try:
        avatars = await heygen.list_avatars(force_refresh=True)
        results["avatars"] = {
            "success": True,
            "count": len(avatars),
            "sample": avatars[:3] if avatars else [],
            "all_ids": [a.get("avatar_id") for a in avatars]
        }
    except Exception as e:
        results["avatars"] = {"success": False, "error": str(e)}

    # 2. Test /v2/avatar_group.list
    try:
        groups = await heygen.list_avatar_groups()
        results["avatar_groups"] = {
            "success": True,
            "count": len(groups),
            "groups": groups
        }
    except Exception as e:
        results["avatar_groups"] = {"success": False, "error": str(e)}

    # 3. Test /v2/avatar_group/{id}/avatars for each group with looks
    results["group_looks"] = []
    if results.get("avatar_groups", {}).get("success"):
        for group in results["avatar_groups"]["groups"]:
            group_id = group.get("group_id") or group.get("avatar_group_id") or group.get("id")
            if not group_id:
                continue
            if (group.get("num_looks") or group.get("look_count") or group.get("num_avatars") or 0) > 0:
                try:
                    looks = await heygen.list_avatars_in_group(str(group_id))
                    results["group_looks"].append({
                        "group_id": group_id,
                        "group_name": group["name"],
                        "success": True,
                        "count": len(looks),
                        "looks": looks
                    })
                except Exception as e:
                    results["group_looks"].append({
                        "group_id": group_id,
                        "group_name": group["name"],
                        "success": False,
                        "error": str(e)
                    })

    # 4. Test /v2/voices
    try:
        voices = await heygen.list_voices(force_refresh=True)
        results["voices"] = {
            "success": True,
            "count": len(voices),
            "sample": voices[:3] if voices else []
        }
    except Exception as e:
        results["voices"] = {"success": False, "error": str(e)}

    return results


@router.get("/search-look/{look_id}")
async def search_look_id(look_id: str, user=Depends(get_current_user)):
    """
    Search for a specific look ID across all endpoints
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant_id"}

    tenant_res = supabase.table("tenants").select("heygen_api_key").eq("id", tenant_id).single().execute()
    api_key = tenant_res.data.get("heygen_api_key") if tenant_res.data else None

    if not api_key:
        return {"error": "No HeyGen API key configured for tenant"}

    heygen = HeyGenService(api_key)
    found_in = []

    # Search in avatars
    try:
        avatars = await heygen.list_avatars(force_refresh=True)
        matching = [a for a in avatars if a.get("avatar_id") == look_id]
        if matching:
            found_in.append({
                "location": "avatars",
                "data": matching[0]
            })
    except Exception as e:
        pass

    # Search in avatar groups
    try:
        groups = await heygen.list_avatar_groups()
        for group in groups:
            group_id = group.get("group_id") or group.get("avatar_group_id") or group.get("id")
            if not group_id:
                continue
            if (group.get("num_looks") or group.get("look_count") or group.get("num_avatars") or 0) > 0:
                try:
                    looks = await heygen.list_avatars_in_group(str(group_id))
                    matching = [l for l in looks if l.get("avatar_id") == look_id]
                    if matching:
                        found_in.append({
                            "location": f"avatar_group:{group['name']}",
                            "group_id": group_id,
                            "data": matching[0]
                        })
                except:
                    pass
    except Exception as e:
        pass

    return {
        "look_id": look_id,
        "found": len(found_in) > 0,
        "locations": found_in
    }


@router.get("/avatars")
async def get_all_avatars(user=Depends(get_current_user)):
    """Get all avatars from /v2/avatars"""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant_id"}

    tenant_res = supabase.table("tenants").select("heygen_api_key").eq("id", tenant_id).single().execute()
    api_key = tenant_res.data.get("heygen_api_key") if tenant_res.data else None

    if not api_key:
        return {"error": "No HeyGen API key"}

    heygen = HeyGenService(api_key)
    avatars = await heygen.list_avatars(force_refresh=True)

    return {
        "count": len(avatars),
        "avatars": avatars
    }


@router.get("/avatar-groups")
async def get_all_avatar_groups(user=Depends(get_current_user)):
    """Get all avatar groups from /v2/avatar_group.list"""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant_id"}

    tenant_res = supabase.table("tenants").select("heygen_api_key").eq("id", tenant_id).single().execute()
    api_key = tenant_res.data.get("heygen_api_key") if tenant_res.data else None

    if not api_key:
        return {"error": "No HeyGen API key"}

    heygen = HeyGenService(api_key)
    groups = await heygen.list_avatar_groups()

    return {
        "count": len(groups),
        "groups": groups
    }


@router.get("/voices")
async def get_all_voices(user=Depends(get_current_user)):
    """Get all voices from /v2/voices"""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        return {"error": "No tenant_id"}

    tenant_res = supabase.table("tenants").select("heygen_api_key").eq("id", tenant_id).single().execute()
    api_key = tenant_res.data.get("heygen_api_key") if tenant_res.data else None

    if not api_key:
        return {"error": "No HeyGen API key"}

    heygen = HeyGenService(api_key)
    voices = await heygen.list_voices(force_refresh=True)

    return {
        "count": len(voices),
        "voices": voices
    }
