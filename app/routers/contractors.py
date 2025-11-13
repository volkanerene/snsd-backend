from copy import deepcopy
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_admin, require_tenant
from app.utils.auth import get_current_user

router = APIRouter()

class LegalInfo(BaseModel):
    legal_company_name: str = Field(..., min_length=2)
    dba_name: str | None = None
    legal_entity_type: str = Field(..., min_length=2)
    country_of_incorporation: str = Field(..., min_length=2)
    company_registration_number: str = Field(..., min_length=2)
    tax_number: str = Field(..., min_length=2)
    duns_number: str | None = None
    year_established: str | None = None
    number_of_employees: str | None = None
    annual_revenue: str | None = None
    parent_company: str | None = None
    ownership_and_directors: str | None = None
    website_url: str | None = None


class AddressContacts(BaseModel):
    registered_address: str = Field(..., min_length=5)
    operational_address: str | None = None
    mailing_address: str | None = None
    primary_contact_name: str = Field(..., min_length=2)
    primary_contact_job_title: str = Field(..., min_length=2)
    primary_contact_email: str = Field(..., min_length=5)
    primary_contact_phone: str = Field(..., min_length=5)
    ap_email: str = Field(..., min_length=5)
    po_email: str | None = None
    edi_contact: str | None = None
    support_contact: str | None = None


class ProductsServices(BaseModel):
    description: str = Field(..., min_length=5)
    unspsc_code: str = Field(..., min_length=2)
    regions_served: str | None = None
    delivery_locations: str | None = None
    capacity_lead_times: str | None = None


class BankPayment(BaseModel):
    bank_name: str = Field(..., min_length=2)
    bank_branch_address: str | None = None
    account_holder_name: str = Field(..., min_length=2)
    iban: str = Field(..., min_length=8)
    swift_bic: str = Field(..., min_length=6)
    routing_bank_key: str | None = None
    payment_currency: str = Field(..., min_length=2)
    payment_terms: str | None = None


class TaxCompliance(BaseModel):
    business_certificate: str = Field(..., min_length=2)
    w9_w8_form: str | None = None
    anti_bribery_statement: bool = Field(...)
    code_of_conduct_acceptance: bool = Field(...)
    sanctions_disclosure: str | None = None
    insurance_certificates: str | None = None
    quality_certification: str | None = None
    environmental_certification: str | None = None
    health_safety_certification: str | None = None
    data_privacy_compliance: bool = Field(...)
    information_security: str | None = None


class InvoicingIntegration(BaseModel):
    invoicing_method: str | None = None
    electronic_invoicing_id: str | None = None
    tax_schema: str | None = None
    po_flip_acceptance: bool = Field(False)
    remittance_email: str | None = None
    terms_acceptance: bool = Field(...)


class CsrSustainability(BaseModel):
    diversity_status: str | None = None
    sustainability_metrics: str | None = None
    conflict_minerals: str | None = None


class ReferencesSection(BaseModel):
    reference_customers: str | None = None
    past_projects: str | None = None


class ContractorAribaProfile(BaseModel):
    legal_info: LegalInfo
    address_contacts: AddressContacts
    products_services: ProductsServices
    bank_payment: BankPayment
    tax_compliance: TaxCompliance
    invoicing_integration: InvoicingIntegration
    csr: CsrSustainability
    references: ReferencesSection


def _default_profile_dict() -> Dict[str, Any]:
    """
    Returns a default Ariba profile payload with empty strings / False flags.
    Used to bootstrap contractors who have not filled the profile yet.
    """
    return {
        "legal_info": {
            "legal_company_name": "",
            "dba_name": "",
            "legal_entity_type": "",
            "country_of_incorporation": "",
            "company_registration_number": "",
            "tax_number": "",
            "duns_number": "",
            "year_established": "",
            "number_of_employees": "",
            "annual_revenue": "",
            "parent_company": "",
            "ownership_and_directors": "",
            "website_url": ""
        },
        "address_contacts": {
            "registered_address": "",
            "operational_address": "",
            "mailing_address": "",
            "primary_contact_name": "",
            "primary_contact_job_title": "",
            "primary_contact_email": "",
            "primary_contact_phone": "",
            "ap_email": "",
            "po_email": "",
            "edi_contact": "",
            "support_contact": ""
        },
        "products_services": {
            "description": "",
            "unspsc_code": "",
            "regions_served": "",
            "delivery_locations": "",
            "capacity_lead_times": ""
        },
        "bank_payment": {
            "bank_name": "",
            "bank_branch_address": "",
            "account_holder_name": "",
            "iban": "",
            "swift_bic": "",
            "routing_bank_key": "",
            "payment_currency": "",
            "payment_terms": ""
        },
        "tax_compliance": {
            "business_certificate": "",
            "w9_w8_form": "",
            "anti_bribery_statement": False,
            "code_of_conduct_acceptance": False,
            "sanctions_disclosure": "",
            "insurance_certificates": "",
            "quality_certification": "",
            "environmental_certification": "",
            "health_safety_certification": "",
            "data_privacy_compliance": False,
            "information_security": ""
        },
        "invoicing_integration": {
            "invoicing_method": "",
            "electronic_invoicing_id": "",
            "tax_schema": "",
            "po_flip_acceptance": False,
            "remittance_email": "",
            "terms_acceptance": False
        },
        "csr": {
            "diversity_status": "",
            "sustainability_metrics": "",
            "conflict_minerals": ""
        },
        "references": {
            "reference_customers": "",
            "past_projects": ""
        }
    }


REQUIRED_FIELDS: List[Tuple[str, str]] = [
    ("legal_info", "legal_company_name"),
    ("legal_info", "legal_entity_type"),
    ("legal_info", "country_of_incorporation"),
    ("legal_info", "company_registration_number"),
    ("legal_info", "tax_number"),
    ("address_contacts", "registered_address"),
    ("address_contacts", "primary_contact_name"),
    ("address_contacts", "primary_contact_job_title"),
    ("address_contacts", "primary_contact_email"),
    ("address_contacts", "primary_contact_phone"),
    ("address_contacts", "ap_email"),
    ("products_services", "description"),
    ("products_services", "unspsc_code"),
    ("bank_payment", "bank_name"),
    ("bank_payment", "account_holder_name"),
    ("bank_payment", "iban"),
    ("bank_payment", "swift_bic"),
    ("bank_payment", "payment_currency"),
    ("tax_compliance", "business_certificate"),
    ("tax_compliance", "anti_bribery_statement"),
    ("tax_compliance", "code_of_conduct_acceptance"),
    ("tax_compliance", "data_privacy_compliance"),
    ("invoicing_integration", "terms_acceptance"),
]


def _merge_profile(stored: Dict[str, Any] | None) -> Dict[str, Any]:
    base = deepcopy(_default_profile_dict())
    if not stored:
        return base

    for section, fields in base.items():
        stored_section = stored.get(section) if isinstance(stored, dict) else None
        if isinstance(fields, dict) and isinstance(stored_section, dict):
            for key, value in fields.items():
                if key in stored_section:
                    base[section][key] = stored_section[key]
        else:
            base[section] = stored.get(section, fields)
    return base


def _evaluate_completion(profile: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[str] = []
    total = len(REQUIRED_FIELDS)
    completed = 0

    for section, field in REQUIRED_FIELDS:
        section_data = profile.get(section, {})
        value = section_data.get(field)
        if isinstance(value, bool):
            if value:
                completed += 1
            else:
                missing.append(f"{section}.{field}")
        else:
            if value and str(value).strip():
                completed += 1
            else:
                missing.append(f"{section}.{field}")

    completion_rate = (completed / total * 100) if total else 100
    return {
        "completed": len(missing) == 0,
        "completion_rate": round(completion_rate, 2),
        "missing_fields": missing
    }


def _ensure_profile_edit_access(user: dict, contractor_id: str):
    role_id = user.get("role_id")
    if role_id is not None and role_id <= 2:
        return
    user_contractor_id = user.get("contractor_id")
    if not user_contractor_id or str(user_contractor_id) != str(contractor_id):
        raise HTTPException(403, "You do not have permission to edit this contractor profile")


@router.get("/")
async def list_contractors(
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = (
        supabase.table("contractors")
        .select("*")
        .eq("tenant_id", tenant_id)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    res = query.execute()
    return ensure_response(res)


@router.post("/")
async def create_contractor(
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)

    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    payload["created_by"] = user["id"]

    # Combine country_code and contact_phone if both exist
    country_code = payload.pop("country_code", None)
    contact_phone = payload.get("contact_phone", "")
    if country_code and contact_phone:
        payload["contact_phone"] = f"{country_code} {contact_phone}"

    # Normalize contact_email to lowercase and ensure uniqueness per tenant
    contact_email = payload.get("contact_email")
    if contact_email:
        normalized_email = contact_email.strip().lower()
        payload["contact_email"] = normalized_email

        existing_res = (
            supabase.table("contractors")
            .select("id")
            .eq("tenant_id", tenant_id)
            .ilike("contact_email", normalized_email)
            .limit(1)
            .execute()
        )
        if ensure_response(existing_res):
            raise HTTPException(
                400,
                "A contractor with this email already exists for this tenant."
            )

    res = supabase.table("contractors").insert(payload).execute()
    return ensure_response(res)


@router.get("/{contractor_id}")
async def get_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    res = (
        supabase.table("contractors")
        .select("*")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.put("/{contractor_id}")
async def update_contractor(
    contractor_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    require_admin(user)
    if not payload:
        raise HTTPException(400, "No fields to update")

    # Combine country_code and contact_phone if both exist
    country_code = payload.pop("country_code", None)
    contact_phone = payload.get("contact_phone", "")
    if country_code and contact_phone:
        payload["contact_phone"] = f"{country_code} {contact_phone}"

    # Normalize and validate contact_email uniqueness when provided
    contact_email = payload.get("contact_email")
    if contact_email:
        normalized_email = contact_email.strip().lower()
        payload["contact_email"] = normalized_email

        existing_res = (
            supabase.table("contractors")
            .select("id")
            .eq("tenant_id", tenant_id)
            .ilike("contact_email", normalized_email)
            .neq("id", contractor_id)
            .limit(1)
            .execute()
        )
        if ensure_response(existing_res):
            raise HTTPException(
                400,
                "Another contractor with this email already exists for this tenant."
            )

    res = (
        supabase.table("contractors")
        .update(payload)
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Not found")
    if isinstance(data, list):
        return data[0]
    return data


@router.delete("/{contractor_id}")
async def delete_contractor(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """Delete a contractor and all associated data (cascade delete)"""
    require_admin(user)

    # 1) Verify contractor exists and belongs to tenant
    contractor_res = (
        supabase.table("contractors")
        .select("id, contact_email")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor = ensure_response(contractor_res)
    if not contractor:
        raise HTTPException(404, "Contractor not found")

    try:
        # 1.5) Find and delete auth users associated with this contractor's profiles
        # Auth users are stored in profiles.id field (they reference auth.users.id)
        try:
            profiles_res = (
                supabase.table("profiles")
                .select("id, email")
                .eq("contractor_id", contractor_id)
                .execute()
            )
            profiles_data = ensure_response(profiles_res) or []
            if not isinstance(profiles_data, list):
                profiles_data = [profiles_data] if profiles_data else []

            # Extract auth user IDs (profiles.id = auth.users.id)
            auth_user_ids = [p.get("id") for p in profiles_data if p.get("id")]
            print(f"[delete_contractor] Found {len(auth_user_ids)} auth users to delete")

            # Delete each auth user
            for auth_user_id in auth_user_ids:
                try:
                    supabase.auth.admin.delete_user(auth_user_id)
                    print(f"[delete_contractor] Successfully deleted auth user: {auth_user_id}")
                except Exception as e:
                    print(f"[delete_contractor] Warning: Failed to delete auth user {auth_user_id}: {e}")
                    # Continue with other deletions even if auth user delete fails
        except Exception as e:
            print(f"[delete_contractor] Warning: Error processing auth users: {e}")
            # Continue with profile/submission deletions

        # 2) Delete all FRM32 submissions for this contractor
        try:
            supabase.table("frm32_submissions").delete().eq(
                "contractor_id", contractor_id
            ).eq("tenant_id", tenant_id).execute()
            print(f"[delete_contractor] Deleted FRM32 submissions for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting FRM32 submissions: {e}")
            raise

        # 3) Delete evren_gpt_session_contractors records
        try:
            session_res = supabase.table("evren_gpt_session_contractors").delete().eq(
                "contractor_id", contractor_id
            ).execute()
            print(f"[delete_contractor] Deleted session_contractors for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting session_contractors: {e}")
            raise

        # 4) Delete profile records for this contractor
        try:
            supabase.table("profiles").delete().eq(
                "contractor_id", contractor_id
            ).execute()
            print(f"[delete_contractor] Deleted profiles for contractor {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting profiles: {e}")
            raise

        # 5) Delete the contractor itself
        try:
            delete_res = (
                supabase.table("contractors")
                .delete()
                .eq("id", contractor_id)
                .eq("tenant_id", tenant_id)
                .execute()
            )
            ensure_response(delete_res)
            print(f"[delete_contractor] Deleted contractor record: {contractor_id}")
        except Exception as e:
            print(f"[delete_contractor] Error deleting contractor record: {e}")
            raise

        return {"success": True, "message": "Contractor deleted successfully"}

    except Exception as e:
        print(f"[delete_contractor] Cascade delete failed: {str(e)}")
        raise HTTPException(500, f"Failed to delete contractor: {str(e)}")


@router.get("/{contractor_id}/ariba-profile")
async def get_ariba_profile(
    contractor_id: str,
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """
    Retrieve SAP Ariba-style extended supplier profile stored in contractor metadata.
    """
    _ensure_profile_edit_access(user, contractor_id)

    contractor_res = (
        supabase.table("contractors")
        .select("metadata")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor_data = ensure_response(contractor_res)
    if not contractor_data:
        raise HTTPException(404, "Contractor not found")
    contractor = contractor_data[0]
    metadata = contractor.get("metadata") or {}
    profile = _merge_profile(metadata.get("ariba_profile"))
    completion = _evaluate_completion(profile)
    return {"profile": profile, "meta": completion}


@router.put("/{contractor_id}/ariba-profile")
async def upsert_ariba_profile(
    contractor_id: str,
    payload: ContractorAribaProfile = Body(...),
    user=Depends(get_current_user),
    tenant_id: str = Depends(require_tenant),
):
    """
    Create or update the SAP Ariba-style supplier profile for a contractor.
    Accessible by admins or the contractor themselves.
    """
    _ensure_profile_edit_access(user, contractor_id)

    contractor_res = (
        supabase.table("contractors")
        .select("metadata")
        .eq("id", contractor_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    contractor_data = ensure_response(contractor_res)
    if not contractor_data:
        raise HTTPException(404, "Contractor not found")

    contractor = contractor_data[0]
    metadata = contractor.get("metadata") or {}
    profile_dict = payload.model_dump()
    metadata["ariba_profile"] = profile_dict

    supabase.table("contractors") \
        .update({"metadata": metadata}) \
        .eq("id", contractor_id) \
        .eq("tenant_id", tenant_id) \
        .execute()

    completion = _evaluate_completion(profile_dict)
    return {"profile": profile_dict, "meta": completion}
